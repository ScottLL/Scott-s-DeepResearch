"""
Tools for exploring and analyzing links on web pages.
"""
import re
import asyncio
import logging
from typing import Dict, Any, List, Set, Optional
from urllib.parse import urlparse, urljoin

from tools.base_tool import BaseTool

class LinkExplorationTool(BaseTool):
    """Tool for exploring links on web pages."""
    
    def __init__(self):
        super().__init__(
            name="link_exploration",
            description="Explores links on web pages to find related content"
        )
        # Check for crawl4ai availability
        self.has_crawl4ai = False
        try:
            from crawl4ai import AsyncWebCrawler
            from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
            self.has_crawl4ai = True
        except ImportError:
            self.logger.warning("crawl4ai package not available. Some link exploration features will be limited.")
    
    def score_url(self, url: str, query_terms: List[str]) -> float:
        """
        Score a URL based on its relevance to the query terms.
        
        Args:
            url: The URL to score
            query_terms: List of query terms to compare against
            
        Returns:
            A relevance score between 0 and 1
        """
        # Skip data URLs, javascript, and anchors
        if not url or not isinstance(url, str):
            return 0
        
        if url.startswith(('data:', 'javascript:', 'mailto:', 'tel:')):
            return 0
            
        # Parse the URL
        try:
            parsed_url = urlparse(url)
            
            # Skip URLs without a domain
            if not parsed_url.netloc:
                return 0
                
            # Get the path and query components
            path = parsed_url.path.lower()
            query = parsed_url.query.lower()
            
            # Skip common asset file extensions
            if path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.svg', '.css', '.js', '.pdf')):
                return 0.1  # Very low score but not zero, as PDFs might be relevant
                
            # Check if the URL contains any of the query terms
            url_text = f"{parsed_url.netloc} {path} {query}".lower()
            
            # Score based on query terms in URL
            term_matches = sum(1 for term in query_terms if term.lower() in url_text)
            
            # Base score from query term matches
            if len(query_terms) > 0:
                score = min(0.7, 0.3 + (term_matches / len(query_terms)) * 0.5)
            else:
                score = 0.3  # Default score when no query terms
                
            # Boost score for URLs with obvious content indicators
            if any(indicator in path for indicator in ['/article/', '/blog/', '/news/', '/post/']):
                score += 0.2
                
            # Reduce score for URLs that likely point to listings or index pages
            if any(indicator in path for indicator in ['/category/', '/tag/', '/search/', '/page/']):
                score -= 0.1
                
            # Reduce score for URLs with many query parameters (likely search/filter pages)
            if len(parsed_url.query) > 30:
                score -= 0.1
                
            return max(0, min(1.0, score))  # Ensure score is between 0 and 1
            
        except Exception as e:
            self.logger.error(f"Error scoring URL {url}: {e}")
            return 0
    
    async def extract_links(self, url: str, crawler=None) -> List[str]:
        """
        Extract all links from a web page.
        
        Args:
            url: The URL to extract links from
            crawler: Optional WebCrawler instance to use
            
        Returns:
            List of links found on the page
        """
        links = []
        
        # Try to extract links using crawl4ai if available
        if self.has_crawl4ai and crawler and hasattr(crawler, 'crawler'):
            try:
                self.logger.info(f"Extracting links from {url} with crawl4ai")
                await crawler._ensure_crawler()
                from crawl4ai.async_configs import CrawlerRunConfig
                
                # Get links from the page with iframes disabled
                config = CrawlerRunConfig(
                    word_count_threshold=5,
                    process_iframes=False,  # Disable iframe processing
                    remove_overlay_elements=False
                )
                
                links_result = await crawler.crawler.arun(url, config=config)
                
                # Extract links from the result
                if hasattr(links_result, "links"):
                    links = links_result.links
                elif isinstance(links_result, list) and all(hasattr(r, "links") for r in links_result):
                    for r in links_result:
                        links.extend(r.links)
                        
                self.logger.info(f"Found {len(links)} links using crawl4ai")
            except Exception as e:
                self.logger.error(f"Error getting links with crawl4ai: {e}")
        
        # If no links found or crawl4ai not available, use requests fallback
        if not links:
            try:
                import requests
                from bs4 import BeautifulSoup
                
                self.logger.info(f"Extracting links from {url} with requests/BeautifulSoup")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for a_tag in soup.find_all('a', href=True):
                        href = a_tag['href']
                        
                        # Handle relative URLs
                        if href.startswith('/'):
                            parsed_url = urlparse(url)
                            href = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
                        elif not href.startswith(('http://', 'https://')):
                            # Skip anchors, javascript, etc.
                            if href.startswith('#') or href.startswith('javascript:'):
                                continue
                            # Convert other relative URLs
                            parsed_url = urlparse(url)
                            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                            if parsed_url.path:
                                # Get the directory part of the path
                                path_parts = parsed_url.path.split('/')
                                if '.' in path_parts[-1]:  # It's a file
                                    directory = '/'.join(path_parts[:-1])
                                else:  # It's a directory
                                    directory = parsed_url.path
                                base_url = f"{base_url}{directory}"
                                if not base_url.endswith('/'):
                                    base_url += '/'
                            href = f"{base_url}{href}"
                        
                        links.append(href)
                
                self.logger.info(f"Found {len(links)} links using requests/BeautifulSoup")
            except ImportError:
                self.logger.error("Required libraries not available for fallback link extraction")
            except Exception as e:
                self.logger.error(f"Error extracting links with requests: {e}")
        
        return links
    
    async def run(self, 
                start_url: str, 
                max_depth: int = 1, 
                max_links: int = 5, 
                visited_urls: Optional[Set[str]] = None,
                original_query: str = "",
                query_language: str = 'en',
                crawler = None) -> Dict[str, Any]:
        """
        Explore links on a web page.
        
        Args:
            start_url: The URL to start exploration from
            max_depth: Maximum depth to crawl
            max_links: Maximum number of links to explore per page
            visited_urls: Set of already visited URLs
            original_query: Original search query (for relevance filtering)
            query_language: Language of the query
            crawler: Optional WebCrawler instance
            
        Returns:
            Dict with exploration results
        """
        if visited_urls is None:
            visited_urls = set()
            
        if start_url in visited_urls:
            return {
                "success": True,
                "start_url": start_url,
                "pages": [],
                "visited_urls": list(visited_urls)
            }
            
        # Add the start URL to visited_urls
        visited_urls.add(start_url)
        
        all_pages = []
        query_terms = [term.strip() for term in original_query.split() if len(term.strip()) > 2]
        
        try:
            self.logger.info(f"Exploring links from {start_url} (max_depth={max_depth})")
            
            # Extract links from the page
            links = await self.extract_links(start_url, crawler)
            
            # Score and filter links
            scored_links = []
            for link in links:
                if link in visited_urls:
                    continue
                    
                score = self.score_url(link, query_terms)
                if score >= 0.3:  # Only consider links with a decent score
                    scored_links.append({"url": link, "score": score})
            
            # Sort by score (highest first)
            scored_links.sort(key=lambda x: x["score"], reverse=True)
            
            # Keep all links with good scores, up to the limit
            max_to_process = min(len(scored_links), max_links * 3) if max_links else len(scored_links)
            valid_links = scored_links[:max_to_process]
            
            self.logger.info(f"Selected {len(valid_links)} promising links from {len(links)} total links")
            
            # Create tasks for each link
            tasks = []
            for link_data in valid_links:
                link = link_data["url"]
                if link in visited_urls:
                    continue
                    
                visited_urls.add(link)
                if crawler:
                    tasks.append(crawler.crawl_page(link))
                
            # Execute all tasks concurrently
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.logger.error(f"Error crawling link: {result}")
                        continue
                        
                    # Add metadata to the page data
                    if i < len(valid_links):  # Safety check
                        result['depth'] = 1  # First level of links
                        result['query'] = original_query
                        result['score'] = valid_links[i]["score"]
                        result['original_language'] = query_language  # Pass the original query language
                        all_pages.append(result)
                    
                    # If we have more depth to explore and content is good, explore second-level links
                    if max_depth > 1 and result.get('content') and len(result.get('content', '')) > 500:
                        if i < len(valid_links):  # Safety check
                            sub_visited = visited_urls.copy()
                            sub_result = await self.run(
                                valid_links[i]["url"], 
                                max_depth - 1,
                                max(1, max_links),
                                sub_visited,
                                original_query,
                                query_language,
                                crawler
                            )
                            
                            if sub_result.get("success", False):
                                for page in sub_result.get("pages", []):
                                    if page['url'] not in visited_urls:
                                        visited_urls.add(page['url'])
                                        page['depth'] = 2  # Second level of links
                                        page['original_language'] = query_language
                                        all_pages.append(page)
                                        
                                # Update visited_urls with all URLs explored in the sub-exploration
                                visited_urls.update(sub_visited)
            
        except Exception as e:
            self.logger.error(f"Error exploring links from {start_url}: {e}")
            return {
                "success": False,
                "start_url": start_url,
                "pages": [],
                "error": str(e)
            }
            
        return {
            "success": True,
            "start_url": start_url,
            "pages": all_pages,
            "visited_urls": list(visited_urls)
        }

# Include the explore_page_links function for backward compatibility
async def explore_page_links(
    start_url: str, 
    max_depth: int, 
    max_links_per_page: int, 
    visited_urls: set, 
    original_query: str, 
    query_language: str = 'en',
    crawler = None
) -> list:
    """
    Backward compatibility wrapper for explore_page_links function.
    Now uses the LinkExplorationTool.
    """
    tool = LinkExplorationTool()
    result = await tool.run(
        start_url=start_url,
        max_depth=max_depth,
        max_links=max_links_per_page,
        visited_urls=visited_urls,
        original_query=original_query,
        query_language=query_language,
        crawler=crawler
    )
    
    return result.get("pages", []) 