"""
Primary web crawler implementation.
"""
import asyncio
import logging
import re
from urllib.parse import urlparse

from .search import search_with_google, direct_baidu_search
from .extraction import crawl_page
from .page_explorer import explore_page_links

# Import Crawl4AI crawler and configurations
try:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
    has_crawl4ai = True
except ImportError:
    logging.error("crawl4ai package not available. Install with: pip install crawl4ai")
    has_crawl4ai = False

class WebCrawler:
    """
    The WebCrawler class integrates Crawl4AI for web crawling and scraping.
    It uses Google search directly, with Baidu as a backup, and provides robust fallbacks.
    """
    def __init__(self):
        if not has_crawl4ai:
            logging.warning("crawl4ai not available - crawler will have limited functionality")
            
        # Initialize a headless browser configuration for Crawl4AI
        self.browser_config = BrowserConfig() if has_crawl4ai else None
        
        # Default run configuration - DISABLED IFRAME PROCESSING and SHORT TIMEOUT
        self.default_run_config = CrawlerRunConfig(
            word_count_threshold=5,      # Minimum words per content block
            remove_overlay_elements=True,
            process_iframes=False,       # IMPORTANT: Disable iframe processing to avoid errors
            page_timeout=10000           # Short 10s timeout - skip slow pages instead of waiting
        ) if has_crawl4ai else None
        
        self.crawler = None  # AsyncWebCrawler will be created on first use
        
        # URL filtering patterns
        self.low_quality_patterns = [
            r'/(ads|advertising)/',
            r'/careers?/',
            r'/contact-?us/',
            r'/cookie-?policy/',
            r'/disclaimer/',
            r'/privacy-?policy/',
            r'/terms-?(of-?service|and-?conditions)/',
            r'/login/',
            r'/register/',
            r'/sign(up|in)/',
            r'/shopping-?cart/',
            r'/checkout/',
            r'/(tags?|categories?)/',
            r'/search/',
            r'/404/',
            r'/error/',
            r'/maintenance/',
            r'/comments?/',
            r'/captcha/',
            r'.*\.(jpg|jpeg|png|gif|svg|webp|mp4|mp3|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar)$'
        ]
        
        # Domains that typically have low-quality content
        self.low_quality_domains = [
            'pinterest.com',
            'instagram.com',
            'facebook.com',
            'twitter.com',
            'tiktok.com',
            'reddit.com',
            'quora.com',
            'youtube.com',
            'vimeo.com',
            'dailymotion.com',
            'flickr.com',
            'tumblr.com',
            'medium.com',
            'amazonaws.com',
            'cloudfront.net',
            'doubleclick.net',
            'googleadservices.com',
            'googlesyndication.com',
            'adroll.com',
            'sharethis.com',
            'addthis.com',
            'disqus.com'
        ]
        
        # Domains that are likely to have high-quality content
        self.high_quality_domains = [
            'wikipedia.org',
            'github.com',
            'arxiv.org',
            'scholar.google.com',
            'nih.gov',
            'nature.com',
            'science.org',
            'ieee.org',
            'acm.org',
            'researchgate.net',
            'springer.com',
            'sciencedirect.com',
            'jstor.org',
            'baidu.com',
            'automate.org'
        ]

    async def _ensure_crawler(self):
        """Ensure the AsyncWebCrawler is initialized (called before any crawl)."""
        if not has_crawl4ai:
            raise ImportError("crawl4ai not available - cannot create crawler")
            
        if self.crawler is None:
            # Configure with correct parameters (without using default_timeout which isn't supported)
            self.browser_config = BrowserConfig(
                headless=True
                # No default_timeout parameter - it's not supported by BrowserConfig
            )
            self.crawler = AsyncWebCrawler(config=self.browser_config)
            await self.crawler.__aenter__()  # Enter the async context for the crawler
    
    async def close(self):
        """Close the crawler when done."""
        if self.crawler:
            await self.crawler.__aexit__(None, None, None)
            self.crawler = None

    def score_url(self, url: str, query_terms: list) -> float:
        """
        Score a URL based on its quality and relevance to the query.
        Returns a score between 0.0 (lowest) and 1.0 (highest).
        """
        if not url:
            return 0.0
            
        try:
            # Parse the URL
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            
            # Initialize score
            score = 0.5  # Neutral starting point
            
            # Check for high-quality domains
            for high_domain in self.high_quality_domains:
                if high_domain in domain:
                    score += 0.3
                    break
                    
            # Check for low-quality domains
            for low_domain in self.low_quality_domains:
                if low_domain in domain:
                    score -= 0.2
                    break
                    
            # Check for low-quality URL patterns
            for pattern in self.low_quality_patterns:
                if re.search(pattern, path):
                    score -= 0.1
                    break
                    
            # Check for HTTPS (slight boost)
            if url.startswith('https://'):
                score += 0.05
                
            # Check for query term matches in domain and path
            domain_and_path = domain + path
            term_matches = sum(1 for term in query_terms if term.lower() in domain_and_path)
            score += min(0.3, term_matches * 0.1)  # Cap at 0.3 boost
            
            # Ensure score is within bounds
            return max(0.1, min(1.0, score))
        except Exception:
            # If anything goes wrong, return a neutral score
            return 0.5

    async def crawl_page(self, url: str) -> dict:
        """
        Crawl a single web page and extract its content.
        
        Args:
            url: URL to crawl
        
        Returns:
            Dict with page data (url, title, content, links)
        """
        # Check if the URL is a PDF
        if self._is_pdf_file(url):
            return await self._process_pdf_with_ocr(url)
        
        # Check if it's a problematic Baidu URL
        if self._is_problematic_baidu_url(url):
            return {
                "url": url,
                "title": "",
                "content": "",
                "links": [],
                "skipped": True,
                "skip_reason": "Problematic Baidu redirect URL that may cause timeouts"
            }
        
        # Check URL file type before attempting to crawl
        if self._is_unsupported_file_type(url):
            return {
                "url": url,
                "title": "",
                "content": "",
                "links": [],
                "skipped": True,
                "skip_reason": "Unsupported file type"
            }
        
        try:
            # Call the implementation from content_extraction module with a timeout
            return await asyncio.wait_for(
                crawl_page(url, self),
                timeout=10  # 10 second timeout at function level as additional protection
            )
        except asyncio.TimeoutError:
            logging.warning(f"Timeout while crawling {url} - skipping")
            return {
                "url": url,
                "title": "",
                "content": "",
                "links": [],
                "skipped": True,
                "skip_reason": "Timeout after 10 seconds"
            }
        except Exception as e:
            logging.error(f"Error crawling {url}: {str(e)}")
            return {
                "url": url,
                "title": "",
                "content": "",
                "links": [],
                "skipped": True,
                "skip_reason": f"Error: {str(e)}"
            }

    def _is_pdf_file(self, url: str) -> bool:
        """Check if the URL points to a PDF file."""
        lower_url = url.lower()
        return (lower_url.endswith('.pdf') or 
                '.pdf?' in lower_url or 
                '.pdf&' in lower_url or 
                '/pdf/' in lower_url)

    def _is_unsupported_file_type(self, url: str) -> bool:
        """
        Check if the URL points to an unsupported file type.
        
        Args:
            url: URL to check
            
        Returns:
            True if the URL points to an unsupported file type, False otherwise
        """
        # Don't count PDFs as unsupported since we handle them specially
        if self._is_pdf_file(url):
            return False
        
        # Check if it's a problematic Baidu redirect URL
        if self._is_problematic_baidu_url(url):
            return True
            
        # File extensions to avoid
        unsupported_extensions = [
            # Documents (exclude PDFs since we handle them separately)
            '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.odt', '.rtf', '.txt',
            # Images
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg', '.webp',
            # Audio/Video
            '.mp3', '.wav', '.mp4', '.avi', '.mov', '.flv', '.wmv', '.webm',
            # Archives
            '.zip', '.rar', '.tar', '.gz', '.7z',
            # Other
            '.xml', '.csv', '.json', '.exe', '.dmg', '.apk'
        ]
        
        # Extract the file extension from the URL
        lower_url = url.lower()
        
        # Check for file extensions
        for ext in unsupported_extensions:
            if lower_url.endswith(ext) or f"{ext}?" in lower_url or f"{ext}&" in lower_url:
                return True
            
        # Check for URL patterns that indicate binary downloads
        if "download" in lower_url and ("file" in lower_url or "document" in lower_url):
            return True
        
        # Check URL patterns that suggest non-HTML content
        if "/download/" in lower_url or "/dl/" in lower_url or "/files/" in lower_url:
            return True
        
        return False

    def _is_problematic_baidu_url(self, url: str) -> bool:
        """
        Check if the URL is a Baidu redirect URL that could cause timeouts.
        
        Args:
            url: URL to check
            
        Returns:
            True if the URL is a problematic Baidu redirect URL, False otherwise
        """
        # Check for baidu.com/link? patterns which are redirect URLs
        if 'baidu.com/link?' in url.lower():
            logging.warning(f"Skipping problematic Baidu redirect URL: {url}")
            return True
            
        # Also check for other Baidu redirect patterns
        baidu_redirect_patterns = [
            'www.baidu.com/link?',
            'www.baidu.com/baidu.php?url=',
            'c.tieba.baidu.com/c/s/jump?url='
        ]
        
        for pattern in baidu_redirect_patterns:
            if pattern in url:
                logging.warning(f"Skipping problematic Baidu redirect URL (pattern: {pattern}): {url}")
                return True
                
        return False

    async def preview_url(self, url: str, query_terms: list) -> float:
        """
        Preview a URL by making a quick request to check its contents
        and calculate a relevance score.
        
        Args:
            url: URL to preview
            query_terms: List of query terms to check relevance against
            
        Returns:
            Relevance score (0-100)
        """
        # Skip processing if URL points to unsupported file type
        if self._is_unsupported_file_type(url):
            return 0.0
            
        # Skip if it's a problematic Baidu URL
        if self._is_problematic_baidu_url(url):
            return 0.0
        
        # First apply basic URL scoring
        base_score = self.score_url(url, query_terms)
        
        if base_score < 0.3:
            logging.info(f"URL {url} has low base score ({base_score:.2f}), skipping preview")
            return base_score
            
        # Skip URLs that don't start with http:// or https://
        if not url.startswith(('http://', 'https://')):
            logging.warning(f"Invalid URL scheme: {url}")
            return max(0.1, base_score - 0.2)
        
        # Only do preview with crawl4ai if available 
        if has_crawl4ai:    
            try:
                # Use a lightweight request with a short timeout
                await self._ensure_crawler()
                # Set a configuration for lightweight crawling with short timeout
                preview_config = CrawlerRunConfig(
                    word_count_threshold=5,
                    process_iframes=False,  # Disable iframe processing
                    remove_overlay_elements=False,
                    page_timeout=10000  # 10s timeout for preview
                )
                
                # Use asyncio.wait_for to provide an additional timeout layer
                result = await asyncio.wait_for(
                    self.crawler.arun(url=url, config=preview_config),
                    timeout=10  # 10 second timeout
                )
                
                # Extract the title
                title = ""
                if hasattr(result, "title"):
                    title = result.title
                    
                # If no title, this page might not be worth crawling
                if not title:
                    return max(0.1, base_score - 0.2)
                    
                # Check if title contains query terms
                title_lower = title.lower()
                term_matches = sum(1 for term in query_terms if term.lower() in title_lower)
                
                # Adjust score based on title relevance
                relevance_boost = min(0.4, 0.1 * term_matches)
                final_score = base_score + relevance_boost
                
                logging.info(f"URL preview for {url} - Title: '{title}', Score: {final_score:.2f}")
                return final_score
                
            except asyncio.TimeoutError:
                logging.warning(f"Timeout while previewing {url} - skipping")
                return 0.0  # Skip URLs that timeout
            except Exception as e:
                logging.warning(f"Error previewing URL {url}: {e}")
                return base_score  # Return the base score if preview fails
        else:
            # No crawl4ai available, return the base score
            return base_score

    def search_web(self, query: str, num_results: int = 5) -> list:
        """
        Perform a web search for the given query and return a list of results.
        Uses Google search first, with direct fallbacks to Baidu and other engines.
        
        Args:
            query: The search query string
            num_results: Number of results to return
            
        Returns:
            List of dictionaries with 'title', 'url', 'snippet', and 'score'
        """
        logging.info(f"Searching web for query: \"{query}\" (breadth={num_results})")
        results = []
        
        # Extract query terms for URL scoring
        query_terms = [term.strip() for term in query.split() if len(term.strip()) > 2]
        
        # Skip DuckDuckGo entirely and go directly to Google
        try:
            logging.info("Attempting Google search...")
            google_results = search_with_google(query, num_results=num_results)
            
            if google_results:
                for url in google_results:
                    if url and url not in [r.get('url') for r in results]:
                        # Score the URL
                        score = self.score_url(url, query_terms)
                        results.append({
                            "title": "",  # Google search doesn't provide titles
                            "url": url,
                            "snippet": "",
                            "score": score,
                            "source": "Google"
                        })
                logging.info(f"Google search returned {len(google_results)} results")
            else:
                logging.warning("Google search returned no results")
        except Exception as e:
            logging.error(f"Google search error: {str(e)}")
        
        # Try Baidu search if we need more results
        if len(results) < num_results:
            logging.info("Attempting Baidu search...")
            try:
                baidu_results = direct_baidu_search(query, num_results=(num_results - len(results)))
                
                if baidu_results:
                    for r in baidu_results:
                        url = r.get("url", "")
                        if url and url not in [r.get('url') for r in results]:
                            # Skip problematic Baidu redirect URLs
                            if self._is_problematic_baidu_url(url):
                                logging.info(f"Skipping problematic Baidu URL: {url}")
                                continue
                                
                            score = self.score_url(url, query_terms)
                            # Baidu results have a redirect URL
                            results.append({
                                "title": r.get("title", ""),
                                "url": url,
                                "snippet": r.get("snippet", ""),
                                "score": score,
                                "source": "Baidu"
                            })
                    logging.info(f"Baidu search returned {len(baidu_results)} results")
                else:
                    logging.warning("Baidu search returned no results")
            except Exception as e:
                logging.error(f"Baidu search error: {str(e)}")
        
        # If we still need more results, use generic fallbacks suitable for any topic
        if len(results) < num_results:
            logging.info("Using fallback websites due to insufficient search results")
            
            # Generic fallback results that work for any topic (no topic specific conditions)
            fallback_results = [
                {"title": "Google Search Results", "url": f"https://www.google.com/search?q={query.replace(' ', '+')}",
                "snippet": "Direct Google search link for the query.", "score": 0.9, "source": "Fallback"},
                {"title": "Baidu Search Results", "url": f"https://www.baidu.com/s?wd={query.replace(' ', '+')}",
                "snippet": "Direct Baidu search link for the query.", "score": 0.85, "source": "Fallback"},
                {"title": "Wikipedia - " + query, "url": f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}", 
                "snippet": "Wikipedia article related to the query.", "score": 0.8, "source": "Fallback"},
                {"title": "Google Scholar Results", "url": f"https://scholar.google.com/scholar?q={query.replace(' ', '+')}",
                "snippet": "Academic papers related to the query.", "score": 0.75, "source": "Fallback"},
                {"title": "ArXiv Search Results", "url": f"https://arxiv.org/search/?query={query.replace(' ', '+')}&searchtype=all",
                "snippet": "Scientific papers from arXiv repository.", "score": 0.7, "source": "Fallback"},
                {"title": "ResearchGate - " + query, "url": f"https://www.researchgate.net/search/publication?q={query.replace(' ', '+')}",
                "snippet": "Scientific and academic publications.", "score": 0.72, "source": "Fallback"},
                {"title": "ScienceDirect - " + query, "url": f"https://www.sciencedirect.com/search?qs={query.replace(' ', '+')}",
                "snippet": "Scientific articles and research papers.", "score": 0.73, "source": "Fallback"}
            ]
            
            # Add new results to our list, avoiding duplicates
            for r in fallback_results:
                if len(results) >= num_results:
                    break
                    
                url = r.get("url", "")
                if url and url not in [existing.get('url') for existing in results]:
                    results.append(r)
                    
            logging.info(f"Added fallback websites for a total of {len(results)} results")
        
        # Sort results by score and return the top ones
        sorted_results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)
        return sorted_results[:num_results]

    async def explore_search_results(self, query: str, depth: int = 2, breadth: int = 5, visited_urls=None) -> list:
        """
        Intelligently explore search results using scored URLs and preview data.
        
        Args:
            query: The search query string
            depth: How many levels deep to follow links
            breadth: How many top search results to consider
            visited_urls: Set of already visited URLs to avoid duplicates
            
        Returns:
            List of dictionaries containing page data for all crawled pages
        """
        if visited_urls is None:
            visited_urls = set()
            
        all_pages = []
        query_terms = [term.strip() for term in query.split() if len(term.strip()) > 2]
        
        # Detect query language at the beginning
        from analysis import detect_language
        query_language = detect_language(query)
        logging.info(f"Detected query language: {query_language}")
        
        # Get initial search results (no limit on how many we'll use)
        search_results = self.search_web(query, num_results=breadth*2)  # Get more results than needed
        
        # For non-English queries, also search in English to get more diverse results
        if query_language != 'en':
            try:
                from analysis import translate_to_english
                # Use the async version directly and await its result
                translated_query = await translate_to_english(query, query_language)
                logging.info(f"Translated query for multi-language search: \"{translated_query}\"")
                
                # Add additional results from English search
                logging.info(f"Searching web for query: \"{translated_query}\" (breadth={max(1, breadth//2)})")
                english_results = self.search_web(translated_query, num_results=max(1, breadth//2))
                search_results.extend(english_results)
            except Exception as e:
                logging.error(f"Error adding English search results: {e}")
        
        # Mark original language results
        for result in search_results:
            if not result.get('original_language'):
                result['original_language'] = query_language
        
        # Preview and score URLs to find the promising ones
        scored_results = []
        for result in search_results:
            url = result.get('url')
            if not url or url in visited_urls:
                continue
                
            # Score the URL based on a quick preview
            relevance_score = await self.preview_url(url, query_terms)
            scored_results.append({
                "result": result,
                "score": relevance_score
            })
            
        # Keep all results with acceptable scores instead of just the top ones
        valid_results = [r for r in scored_results if r["score"] > 0.3]
        
        logging.info(f"Selected {len(valid_results)} URLs from {len(search_results)} search results")
        
        # Process each valid result
        for scored_result in valid_results:
            result = scored_result["result"]
            url = result.get('url')
            if not url or url in visited_urls:
                continue
                
            # Mark as visited
            visited_urls.add(url)
            
            # Crawl the page
            logging.info(f"Crawling search result: {url} (score: {scored_result['score']:.2f})")
            page_data = await self.crawl_page(url)
            page_data['depth'] = 0  # Root level (direct search result)
            page_data['query'] = query
            page_data['score'] = scored_result["score"]
            page_data['original_language'] = result.get('original_language', query_language)
            all_pages.append(page_data)
            
            # If depth > 0 and we got good content, explore links from this page
            if depth > 0 and page_data.get('content') and len(page_data['content']) > 500:
                nested_pages = await explore_page_links(
                    url, depth, breadth, visited_urls, query, query_language, self
                )
                all_pages.extend(nested_pages)
                
        return all_pages

    async def deep_crawl_site(self, start_url: str, max_pages: int = 10, max_depth: int = 3, semaphore=None):
        """
        Crawl a website starting from a given URL, up to a specified depth and number of pages.
        Now with parallel processing for improved performance.
        
        Args:
            start_url: The starting URL for the crawl
            max_pages: Maximum number of pages to crawl
            max_depth: Maximum depth of links to follow
            semaphore: Optional semaphore to control concurrency
            
        Returns:
            List of dictionaries containing page data for all crawled pages
        """
        all_pages = []
        visited_urls = set()
        
        logging.info(f"Starting deep crawl of {start_url} (max_pages={max_pages}, max_depth={max_depth})")
        
        # Create semaphore if not provided
        if semaphore is None:
            semaphore = asyncio.Semaphore(10)  # Allow 10 concurrent requests
        
        # Crawl the starting page first
        page_data = await self.crawl_page(start_url)
        page_data['depth'] = 0  # Root level
        all_pages.append(page_data)
        visited_urls.add(start_url)
        
        # Extract domain from start_url to stay on the same site
        parsed_url = urlparse(start_url)
        base_domain = parsed_url.netloc
        
        # Use parallel approach to explore the site
        async def process_url(url, depth):
            async with semaphore:  # Control concurrency
                if url in visited_urls or len(all_pages) >= max_pages:
                    return []
                
                visited_urls.add(url)
                result_pages = []
                
                try:
                    # Crawl the page
                    page_data = await self.crawl_page(url)
                    page_data['depth'] = depth
                    result_pages.append(page_data)
                    
                    # If depth limit not reached, extract and process links
                    if depth < max_depth and len(all_pages) + len(result_pages) < max_pages:
                        links = await self._extract_links(url)
                        
                        # Filter links to stay on the same domain
                        filtered_links = []
                        for link in links:
                            try:
                                parsed_link = urlparse(link)
                                # Only include links from the same domain and not yet visited
                                if parsed_link.netloc == base_domain and link not in visited_urls:
                                    filtered_links.append(link)
                            except Exception:
                                continue
                        
                        # Limit number of links to process to avoid overwhelming
                        filtered_links = filtered_links[:max(5, (max_pages - len(all_pages) - len(result_pages)))]
                        
                        # Process links in parallel
                        if filtered_links:
                            tasks = [process_url(link, depth + 1) for link in filtered_links]
                            nested_results = await asyncio.gather(*tasks)
                            for nested_result in nested_results:
                                result_pages.extend(nested_result)
                
                except Exception as e:
                    logging.error(f"Error processing {url}: {e}")
                
                return result_pages
        
        # Start parallel processing from the root links
        links = await self._extract_links(start_url)
        
        # Filter links to stay on the same domain
        filtered_links = []
        for link in links:
            try:
                parsed_link = urlparse(link)
                # Only include links from the same domain
                if parsed_link.netloc == base_domain and link not in visited_urls:
                    filtered_links.append(link)
            except Exception:
                continue
        
        # Limit the number of links to process
        filtered_links = filtered_links[:max(10, max_pages - 1)]
        
        # Process filtered links in parallel
        if filtered_links:
            tasks = [process_url(link, 1) for link in filtered_links]
            results = await asyncio.gather(*tasks)
            
            for result in results:
                all_pages.extend(result)
                if len(all_pages) >= max_pages:
                    break
        
        logging.info(f"Completed deep crawl of {start_url}. Crawled {len(all_pages)} pages.")
        return all_pages[:max_pages]  # Ensure we return at most max_pages

    # Helper method to extract links
    async def _extract_links(self, url):
        """Extract all links from a page."""
        try:
            await self._ensure_crawler()
            # Use config with iframe processing disabled
            from crawl4ai.async_configs import CrawlerRunConfig
            config = CrawlerRunConfig(
                word_count_threshold=5,
                process_iframes=False,  # Disable iframe processing
                remove_overlay_elements=False
            )
            
            result = await self.crawler.arun(url, config=config)
            
            # Extract links
            if hasattr(result, "links"):
                links = result.links
            elif isinstance(result, list) and all(hasattr(r, "links") for r in result):
                for r in result:
                    links.extend(r.links)
            
            # Filter links before returning
            filtered_links = []
            for link in links:
                # Skip if it's an unsupported file type
                if not self._is_unsupported_file_type(link):
                    filtered_links.append(link)
            
            return filtered_links
        except Exception as e:
            logging.error(f"Error extracting links from {url}: {e}")
            return [] 

    async def _process_pdf_with_ocr(self, url: str) -> dict:
        """
        Process a PDF file by downloading it, converting to images, and running OCR.
        
        Args:
            url: URL of the PDF file
            
        Returns:
            Dict with page data including OCR-extracted content
        """
        import tempfile
        import requests
        import os
        
        try:
            logging.info(f"Processing PDF with OCR: {url}")
            
            # Create a temporary file for the PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                # Download the PDF
                response = requests.get(url, stream=True, timeout=30)
                if response.status_code != 200:
                    return {
                        "url": url,
                        "title": os.path.basename(url),
                        "content": "",
                        "links": [],
                        "skipped": True,
                        "skip_reason": f"Failed to download PDF: HTTP {response.status_code}"
                    }
                    
                # Write PDF content to the temp file
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_pdf.write(chunk)
                
                temp_pdf_path = temp_pdf.name
            
            # Convert PDF to images using pdf2image
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(temp_pdf_path, dpi=300, first_page=1, last_page=5)  # Process up to 5 pages
            except ImportError:
                logging.error("pdf2image not installed. Install with: pip install pdf2image")
                logging.error("You may also need to install poppler: https://pdf2image.readthedocs.io/en/latest/installation.html")
                return {
                    "url": url,
                    "title": os.path.basename(url),
                    "content": "",
                    "links": [],
                    "skipped": True,
                    "skip_reason": "pdf2image not installed"
                }
            
            # Use easyOCR to extract text from the images
            try:
                import easyocr
                reader = easyocr.Reader(['en'])  # Initialize with English language
                
                all_text = []
                for i, img in enumerate(images):
                    # Save image to temporary file
                    img_path = f"{temp_pdf_path}_page{i+1}.jpg"
                    img.save(img_path)
                    
                    # Run OCR on the image
                    result = reader.readtext(img_path)
                    page_text = " ".join([text for _, text, _ in result])
                    all_text.append(f"--- Page {i+1} ---\n{page_text}")
                    
                    # Clean up the temporary image file
                    os.unlink(img_path)
                    
                # Combine text from all pages
                content = "\n\n".join(all_text)
                
                # Create a meaningful title from the PDF filename
                filename = os.path.basename(url)
                title = filename.replace('.pdf', '').replace('_', ' ').replace('-', ' ')
                
                # Clean up the temporary PDF file
                os.unlink(temp_pdf_path)
                
                return {
                    "url": url,
                    "title": title,
                    "content": content,
                    "links": [],
                    "is_pdf": True,
                    "pdf_pages_processed": len(images)
                }
                
            except ImportError:
                logging.error("easyocr not installed. Install with: pip install easyocr")
                
                # Clean up the temporary PDF file
                os.unlink(temp_pdf_path)
                
                return {
                    "url": url,
                    "title": os.path.basename(url),
                    "content": "",
                    "links": [],
                    "skipped": True,
                    "skip_reason": "easyocr not installed"
                }
                
        except Exception as e:
            logging.error(f"Error processing PDF {url}: {e}")
            return {
                "url": url,
                "title": os.path.basename(url),
                "content": "",
                "links": [],
                "skipped": True,
                "skip_reason": f"Error processing PDF: {str(e)}"
            } 