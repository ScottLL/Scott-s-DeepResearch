"""
Module for performing web searches using various search engines.
"""
import re
import logging
import json
import time
import random
from urllib.parse import quote_plus

# Flag to check Google search availability
try:
    from googlesearch import search as google_search
    google_search_available = True
except ImportError:
    google_search_available = False
    logging.warning("Google search module not available. Install with: pip install google")

def search_with_google(query: str, num_results: int = 5) -> list:
    """
    Enhanced Google search with custom parameter detection for your specific library version.
    Only uses the parameters that are confirmed to work with your installed version.
    
    Args:
        query: Search query string
        num_results: Maximum number of results to return
        
    Returns:
        List of URLs from Google search results
    """
    results = []
    
    if not google_search_available:
        logging.warning("Google search not available. Install with: pip install google")
        return results
    
    # Try multiple approaches based on the error message
    try:
        logging.info("Using Google search with 'term' parameter")
        # Based on your error message, your library uses 'term' parameter
        for url in google_search(term=query, num_results=num_results*2):
            if url not in results:
                results.append(url)
                if len(results) >= num_results:
                    break
                    
        logging.info(f"Google search for '{query}' returned {len(results)} results")
        return results[:num_results]
    except Exception as e1:
        logging.warning(f"First Google search approach failed: {e1}")
        
        # Try second approach - just query
        try:
            logging.info("Trying basic Google search approach")
            for url in google_search(query):
                if url not in results:
                    results.append(url)
                    if len(results) >= num_results:
                        break
                        
            logging.info(f"Basic Google search for '{query}' returned {len(results)} results")
            return results[:num_results]
        except Exception as e2:
            logging.warning(f"Second Google search approach failed: {e2}")
    
    # If we get here, both approaches failed
    logging.error("All Google search approaches failed")
    return []

def direct_baidu_search(query: str, num_results: int = 5) -> list:
    """
    Perform a search using Baidu search engine directly via HTML scraping.
    
    Args:
        query: The search query string
        num_results: Number of results to return
        
    Returns:
        List of dictionaries with search result information
    """
    results = []
    
    try:
        import requests
        from bs4 import BeautifulSoup
        
        # Encode the query for URL
        encoded_query = quote_plus(query)
        baidu_url = f"https://www.baidu.com/s?wd={encoded_query}"
        
        # Set up request headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.baidu.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Make the request
        response = requests.get(baidu_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            logging.info(f"Baidu search successful for '{query}'")
            soup = BeautifulSoup(response.text, 'html.parser')
            found_results = False
            
            # Try different selectors for Baidu search results
            selectors = [
                '.result.c-container',         # Common result container
                '.c-container',                # Alternative container
                '.result-op',                  # Special results
                '[srcid]',                     # Elements with srcid attribute
                '.c-result',                   # Another result class
                'div[id^="content_"]',         # Content divs
                '#content_left > div',         # Left content column divs
            ]
            
            # Try each selector
            for selector in selectors:
                items = soup.select(selector)
                
                if items:
                    found_results = True
                    logging.info(f"Found {len(items)} items with selector: {selector}")
                    
                    for item in items:
                        # Get the link (look for different possible link containers)
                        link = item.select_one('a.news-title-font_1xS-F') or \
                               item.select_one('a[href^="http"]') or \
                               item.select_one('a')
                        
                        if not link:
                            continue
                            
                        # Get the redirect URL and title
                        href = link.get('href', '')
                        title = link.get_text(strip=True)
                        
                        # Try to get the snippet
                        snippet_elem = item.select_one('.c-abstract') or item.select_one('.c-summary') or item.select_one('p')
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        
                        # Add to results if we have a URL
                        if href and href not in [r.get('url') for r in results]:
                            results.append({
                                "title": title,
                                "url": href,
                                "snippet": snippet,
                                "source": "Baidu"
                            })
                    
                    # If we found results with this selector, break the loop
                    if results:
                        break
            
            # If we couldn't find any results with the selectors
            if not found_results:
                logging.warning("Could not identify result elements in Baidu search page")
                # Add the direct search URL as a fallback
                results.append({
                    "title": "Baidu Search Results for " + query,
                    "url": baidu_url,
                    "snippet": "Direct link to Baidu search results.",
                    "source": "Baidu"
                })
        else:
            logging.warning(f"Baidu search request failed with status code: {response.status_code}")
            
    except ImportError:
        logging.warning("Required libraries (requests, BeautifulSoup) not available for Baidu search")
    except Exception as e:
        logging.error(f"Baidu search error: {e}")
        
    return results[:num_results] 