"""
Base class for all tools in the system.
"""
import logging
from typing import Dict, Any, Optional, Callable

class BaseTool:
    """
    Base class for all tools in the system.
    Each tool implements a specific functionality with a standardized interface.
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"tool.{name}")
    
    async def run(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool's functionality.
        Each tool should override this method.
        
        Returns:
            Dict containing the tool's output and metadata
        """
        raise NotImplementedError("Tool must implement run method")
    
    def __str__(self):
        return f"{self.name}: {self.description}" 

class WebCrawlerTool(BaseTool):
    """
    Tool for crawling websites using the WebCrawler class from the crawling package.
    Provides standardized access to web crawling functionality.
    """
    def __init__(self):
        super().__init__(
            name="WebCrawlerTool",
            description="Crawls websites to extract content and explore links"
        )
        # Import WebCrawler lazily to avoid circular imports
        from core.crawler import WebCrawler
        self.crawler = WebCrawler()
        
    async def run(self, 
                  url_or_query: str, 
                  mode: str = "explore", 
                  depth: int = 2, 
                  breadth: int = 5,
                  max_pages: int = 10,
                  visited_urls: set = None) -> Dict[str, Any]:
        """
        Execute the web crawler functionality.
        
        Args:
            url_or_query: URL to crawl or query to search for
            mode: "explore" for search-and-crawl, "crawl" for site crawling, or "page" for single page
            depth: How deep to follow links
            breadth: How many top results or links to explore
            max_pages: Maximum pages to crawl (for site crawling)
            visited_urls: Set of already visited URLs to avoid duplicates
            
        Returns:
            Dict containing the crawling results and metadata
        """
        if visited_urls is None:
            visited_urls = set()
            
        try:
            if mode == "explore":
                # Explore search results for a query
                self.logger.info(f"Exploring search results for: {url_or_query}")
                pages = await self.crawler.explore_search_results(
                    url_or_query, 
                    depth=depth, 
                    breadth=breadth, 
                    visited_urls=visited_urls
                )
                return {
                    "success": True,
                    "pages": pages,
                    "query": url_or_query,
                    "visited_urls": list(visited_urls)
                }
                
            elif mode == "crawl":
                # Deep crawl a specific site
                self.logger.info(f"Deep crawling site: {url_or_query}")
                pages = await self.crawler.deep_crawl_site(
                    url_or_query,
                    max_pages=max_pages,
                    max_depth=depth
                )
                return {
                    "success": True, 
                    "pages": pages,
                    "url": url_or_query
                }
                
            elif mode == "page":
                # Crawl a single page
                self.logger.info(f"Crawling single page: {url_or_query}")
                page_data = await self.crawler.crawl_page(url_or_query)
                return {
                    "success": True,
                    "page": page_data,
                    "url": url_or_query
                }
                
            else:
                self.logger.error(f"Unknown mode: {mode}")
                return {
                    "success": False,
                    "error": f"Unknown mode: {mode}. Must be 'explore', 'crawl', or 'page'."
                }
                
        except Exception as e:
            self.logger.error(f"Error in WebCrawlerTool: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def close(self):
        """Close the underlying crawler when done."""
        if hasattr(self, 'crawler'):
            await self.crawler.close() 