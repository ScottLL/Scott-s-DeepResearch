"""
Tool interfaces for search functionality.
"""
import re
import logging
from typing import List, Dict, Any
from urllib.parse import quote_plus

from tools.base_tool import BaseTool
from core.search import search_with_google, direct_baidu_search

class GoogleSearchTool(BaseTool):
    """Tool for performing Google searches."""
    
    def __init__(self):
        super().__init__(
            name="google_search",
            description="Searches the web using Google search engine"
        )
        # Flag to check Google search availability
        try:
            from googlesearch import search as google_search
            self.google_search = google_search
            self.google_search_available = True
        except ImportError:
            self.google_search_available = False
            self.logger.warning("Google search module not available. Install with: pip install google")
    
    async def run(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        """
        Perform a Google search for the given query.
        
        Args:
            query: The search query
            num_results: Maximum number of results to return
            
        Returns:
            Dict with results and metadata
        """
        results = []
        
        if not self.google_search_available:
            self.logger.warning("Google search not available. Install with: pip install google")
            return {
                "success": False,
                "results": [],
                "message": "Google search not available"
            }
        
        try:
            self.logger.info(f"Searching Google for: {query}")
            for url in self.google_search(query, stop=num_results*2):  # Fetch a bit more to account for duplicates
                if url not in results:
                    results.append(url)
                    if len(results) >= num_results:
                        break
                        
            self.logger.info(f"Google search for '{query}' returned {len(results)} results")
            return {
                "success": True,
                "results": [{"title": "", "url": url, "snippet": "", "source": "Google"} for url in results],
                "count": len(results)
            }
        except Exception as e:
            self.logger.error(f"Google search error: {e}")
            return {
                "success": False,
                "results": [],
                "message": f"Error: {str(e)}"
            }

class BaiduSearchTool(BaseTool):
    """Tool for performing Baidu searches."""
    
    def __init__(self):
        super().__init__(
            name="baidu_search",
            description="Searches the web using Baidu search engine"
        )
    
    async def run(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        """
        Perform a Baidu search for the given query.
        
        Args:
            query: The search query
            num_results: Maximum number of results to return
            
        Returns:
            Dict with results and metadata
        """
        results = []
        
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # Encode the query for URL
            encoded_query = quote_plus(query)
            baidu_url = f"https://www.baidu.com/s?wd={encoded_query}"
            
            # Set up headers to mimic a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            self.logger.info(f"Searching Baidu for: {query}")
            response = requests.get(baidu_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find search results - Baidu structures may change over time
                for result_div in soup.select('.result, .c-container'):
                    # Extract title and URL
                    title_element = result_div.select_one('.t, .c-title')
                    link_element = result_div.select_one('a')
                    snippet_element = result_div.select_one('.c-abstract')
                    
                    if link_element and 'href' in link_element.attrs:
                        url = link_element['href']
                        
                        # Baidu often uses redirects; try to extract the real URL
                        if url.startswith('http://www.baidu.com/link?'):
                            try:
                                # Follow the redirect to get the real URL
                                redirect_response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
                                if redirect_response.url != url:
                                    url = redirect_response.url
                            except:
                                # If following redirect fails, keep the original URL
                                pass
                        
                        title = title_element.get_text(strip=True) if title_element else ""
                        snippet = snippet_element.get_text(strip=True) if snippet_element else ""
                        
                        # Skip repetitive or ad results
                        if url not in [r.get('url') for r in results]:
                            results.append({
                                "title": title,
                                "url": url,
                                "snippet": snippet,
                                "source": "Baidu"
                            })
                            
                            if len(results) >= num_results:
                                break
                
                return {
                    "success": True,
                    "results": results,
                    "count": len(results)
                }
            else:
                self.logger.warning(f"Baidu search request failed with status code: {response.status_code}")
                return {
                    "success": False,
                    "results": [],
                    "message": f"HTTP Error: {response.status_code}"
                }
        except ImportError:
            self.logger.warning("Required libraries (requests, BeautifulSoup) not available for Baidu search")
            return {
                "success": False,
                "results": [],
                "message": "Required libraries not available"
            }
        except Exception as e:
            self.logger.error(f"Baidu search error: {e}")
            return {
                "success": False,
                "results": [],
                "message": f"Error: {str(e)}"
            } 