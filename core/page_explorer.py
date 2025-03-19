"""
Module for exploring links and related content from web pages.
"""
import re
import asyncio
import logging
from urllib.parse import urlparse

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
    Intelligently explore links on a page, keeping all relevant ones.
    
    Args:
        start_url: Starting URL to explore
        max_depth: Maximum link depth to explore
        max_links_per_page: Maximum links to follow per page
        visited_urls: Set of already visited URLs
        original_query: The original search query
        query_language: The language of the original query
        crawler: WebCrawler instance to use for crawling
    """
    all_pages = []
    query_terms = [term.strip() for term in original_query.split() if len(term.strip()) > 2]
    
    # Verify we have a crawler instance
    if crawler is None:
        logging.error("No crawler instance provided to explore_page_links")
        return all_pages
    
    try:
        logging.info(f"Exploring links from {start_url} (max_depth={max_depth})")

        # Try to determine if we have crawl4ai available
        has_crawl4ai = False
        if hasattr(crawler, 'crawler'):
            has_crawl4ai = True
        
        # Extract and score links from the page first
        links = []
        
        if has_crawl4ai:
            try:
                await crawler._ensure_crawler()
                from crawl4ai.async_configs import CrawlerRunConfig
                
                # Get links from the page with iframes disabled
                config = CrawlerRunConfig(
                    word_count_threshold=5,
                    process_iframes=False,  # Disable iframe processing
                    remove_overlay_elements=False
                )
                
                links_result = await crawler.crawler.arun(start_url, config=config)
                
                # Extract links from the result
                if hasattr(links_result, "links"):
                    links = links_result.links
                elif isinstance(links_result, list) and all(hasattr(r, "links") for r in links_result):
                    for r in links_result:
                        links.extend(r.links)
            except Exception as e:
                logging.error(f"Error getting links with crawl4ai: {e}")
        
        # If no links found or crawl4ai not available, use requests fallback
        if not links:
            try:
                import requests
                from bs4 import BeautifulSoup
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(start_url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    links = []
                    for a_tag in soup.find_all('a', href=True):
                        href = a_tag['href']
                        
                        # Handle relative URLs
                        if href.startswith('/'):
                            parsed_url = urlparse(start_url)
                            href = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
                        elif not href.startswith(('http://', 'https://')):
                            # Skip anchors, javascript, etc.
                            if href.startswith('#') or href.startswith('javascript:'):
                                continue
                            # Convert other relative URLs
                            parsed_url = urlparse(start_url)
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
                
                logging.info(f"Found {len(links)} links using requests fallback")
            except ImportError:
                logging.error("Required libraries not available for fallback link extraction")
            except Exception as e:
                logging.error(f"Error extracting links with requests: {e}")
                
        # Score and filter links
        scored_links = []
        for link in links:
            if link in visited_urls:
                continue
                
            score = crawler.score_url(link, query_terms)
            if score >= 0.3:  # Only consider links with a decent score
                scored_links.append({"url": link, "score": score})
                
        # Keep all links with good scores
        max_to_process = min(len(scored_links), max_links_per_page * 3) if max_links_per_page else len(scored_links)
        valid_links = scored_links[:max_to_process]
        
        logging.info(f"Selected {len(valid_links)} promising links from {len(links)} total links")
        
        # Create tasks for each link
        tasks = []
        for link_data in valid_links:
            link = link_data["url"]
            if link in visited_urls:
                continue
                
            visited_urls.add(link)
            tasks.append(crawler.crawl_page(link))
            
        # Execute all tasks concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logging.error(f"Error crawling link: {result}")
                    continue
                    
                # Add metadata to the page data
                if i < len(valid_links):  # Safety check
                    result['depth'] = 1  # First level of links
                    result['query'] = original_query
                    result['score'] = valid_links[i]["score"]
                    result['original_language'] = query_language  # Pass the original query language
                    all_pages.append(result)
                
                # If we have more depth to explore and content is good, add second-level links
                if max_depth > 1 and result.get('content') and len(result['content']) > 500:
                    if i < len(valid_links):  # Safety check
                        sub_visited = visited_urls.copy()
                        sub_pages = await explore_page_links(
                            valid_links[i]["url"], 
                            max_depth - 1,
                            max(1, max_links_per_page),
                            sub_visited,
                            original_query,
                            query_language,  # Pass the original query language
                            crawler
                        )
                        for sp in sub_pages:
                            if sp['url'] not in visited_urls:
                                visited_urls.add(sp['url'])
                                sp['depth'] = 2  # Second level of links
                                sp['original_language'] = query_language  # Pass the original query language
                                all_pages.append(sp)
            
    except Exception as e:
        logging.error(f"Error exploring links from {start_url}: {e}")
        
    return all_pages