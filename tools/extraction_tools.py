"""
Tools for extracting content from web pages.
"""
import re
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urljoin

from .base_tool import BaseTool
from .tool_registry import ToolRegistry  # Import from the new file

class ContentExtractionTool(BaseTool):
    """Tool for extracting content from web pages."""
    
    def __init__(self):
        super().__init__(
            name="content_extraction",
            description="Extracts content from web pages"
        )
        # Check for crawl4ai availability
        self.has_crawl4ai = False
        try:
            from crawl4ai import AsyncWebCrawler
            from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
            self.has_crawl4ai = True
            self.browser_config = BrowserConfig()
            self.run_config = CrawlerRunConfig(
                word_count_threshold=5,
                remove_overlay_elements=True,
                process_iframes=False
            )
            self.crawler = None
        except ImportError:
            self.logger.warning("crawl4ai package not available. Install with: pip install crawl4ai")
    
    async def _ensure_crawler(self):
        """Ensure that the crawler is initialized."""
        if self.has_crawl4ai and self.crawler is None:
            from crawl4ai import AsyncWebCrawler
            self.crawler = AsyncWebCrawler(browser_config=self.browser_config)
            await self.crawler.start()
        return self.has_crawl4ai and self.crawler is not None
    
    async def close(self):
        """Close the crawler if it exists."""
        if self.has_crawl4ai and self.crawler is not None:
            await self.crawler.stop()
            self.crawler = None
    
    async def run(self, url: str, topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract content from a web page.
        
        Args:
            url: The URL to extract content from
            topic: Optional topic to filter relevant images
            
        Returns:
            Dict with extracted content
        """
        # Check for valid URL scheme
        if not url.startswith(('http://', 'https://')):
            self.logger.error(f"Invalid URL scheme: {url}")
            return {
                "success": False,
                "url": url, 
                "title": "", 
                "content": "", 
                "images": [],
                "error": "Invalid URL: must start with http:// or https://"
            }
        
        # Try with crawl4ai first if available
        crawler_available = await self._ensure_crawler()
        if crawler_available:
            try:
                self.logger.info(f"Extracting content from {url} with crawl4ai")
                
                # Use crawl4ai to fetch the page content
                crawl_result = await self.crawler.get_page_content(
                    url=url,
                    run_config=self.run_config
                )
                
                title = crawl_result.title
                content = crawl_result.text
                
                # Extract images
                images = []
                for img in crawl_result.images:
                    image_url = img.get('src')
                    if image_url:
                        # Handle relative URLs
                        if not image_url.startswith(('http://', 'https://')):
                            image_url = urljoin(url, image_url)
                        
                        images.append({
                            'url': image_url,
                            'alt': img.get('alt', '')
                        })
                
                result = {
                    "success": True,
                    "url": url,
                    "title": title or "",
                    "content": content or "",
                    "images": images,
                    "extracted_with": "crawl4ai"
                }
            except Exception as e:
                self.logger.error(f"Error with crawl4ai for {url}: {e}")
                # Fall through to the requests-based fallback
        
        # Fallback to simple requests-based scraper
        try:
            import requests
            from bs4 import BeautifulSoup
            
            self.logger.info(f"Fallback scraping for: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = ""
            if soup.title:
                title = soup.title.string
            
            # Extract h1 if available and title is empty
            if not title and soup.h1:
                title = soup.h1.get_text(strip=True)
            
            # Remove unwanted elements
            for element in soup.select('script, style, nav, footer, iframe, [class*="nav"], [class*="menu"], [class*="sidebar"]'):
                element.decompose()
            
            # Extract main content
            content = ""
            
            # Try to find the main content
            main_content = None
            for element in [
                soup.select_one('main, article, [role="main"], .main-content, #main-content'),
                soup.select_one('.content, #content, .body, #body'),
                soup.body
            ]:
                if element:
                    main_content = element
                    break
            
            if main_content:
                content = main_content.get_text(separator='\n', strip=True)
            else:
                # Fallback to extracting all paragraphs
                paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 20]
                content = '\n\n'.join(paragraphs)
            
            # Extract images
            images = []
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if src and not src.startswith('data:'):
                    # Handle relative URLs
                    if not src.startswith(('http://', 'https://')):
                        src = urljoin(url, src)
                    
                    images.append({
                        'url': src,
                        'alt': img.get('alt', '')
                    })
            
            result = {
                "success": True,
                "url": url,
                "title": title or "",
                "content": content or "",
                "images": images[:10],  # Limit to top 10 images
                "extracted_with": "requests-bs4"
            }
            
        except ImportError:
            self.logger.error("requests and BeautifulSoup are required for fallback scraping")
            return {
                "success": False,
                "url": url, 
                "title": "", 
                "content": "", 
                "images": [],
                "error": "Required libraries not available for scraping"
            }
        except Exception as e:
            self.logger.error(f"Error crawling {url}: {e}")
            return {
                "success": False,
                "url": url, 
                "title": "", 
                "content": "", 
                "images": [],
                "error": str(e)
            } 
        
        # Add image relevance filtering if topic is provided
        if topic and 'images' in result and result['images']:
            print(f"\n[DEBUG] Starting image relevance filtering for topic: '{topic}'")
            print(f"[DEBUG] Found {len(result['images'])} images to analyze")
            
            # Get the image relevance tool
            try:
                image_tool = ToolRegistry.get_tool("image_relevance")
                print(f"[DEBUG] Successfully retrieved image_relevance tool")
                
                import requests
                import base64
                
                # Process each image
                relevant_images = []
                for idx, img in enumerate(result['images']):
                    try:
                        print(f"\n[DEBUG] Processing image {idx+1}/{len(result['images'])}: {img['url']}")
                        start_time = time.time()
                        
                        # Download the image first
                        print(f"[DEBUG] Downloading image...")
                        response = requests.get(img['url'], timeout=10)
                        if response.status_code == 200:
                            print(f"[DEBUG] Successfully downloaded image ({len(response.content)} bytes)")
                            
                            # Convert image to base64
                            image_content = base64.b64encode(response.content).decode('utf-8')
                            print(f"[DEBUG] Converted to base64 (length: {len(image_content)})")
                            
                            # Check relevance with downloaded content
                            print(f"[DEBUG] Analyzing image relevance...")
                            relevance = await image_tool.run(
                                img['url'], 
                                topic, 
                                download_image=False,
                                image_content=image_content
                            )
                            
                            print(f"[DEBUG] Relevance analysis complete:")
                            print(f"[DEBUG]   - Is relevant: {relevance.get('is_relevant', False)}")
                            print(f"[DEBUG]   - Score: {relevance.get('relevance_score', 0)}")
                            
                            if relevance.get('is_relevant', False):
                                img['relevance_score'] = relevance.get('relevance_score', 0)
                                img['relevance_analysis'] = relevance.get('analysis', '')
                                relevant_images.append(img)
                                print(f"[DEBUG] ✅ Image added to relevant images list")
                            else:
                                print(f"[DEBUG] ❌ Image not relevant, skipping")
                            
                            elapsed = time.time() - start_time
                            print(f"[DEBUG] Image processing took {elapsed:.2f} seconds")
                        else:
                            print(f"[DEBUG] Failed to download image: HTTP {response.status_code}")
                    except Exception as e:
                        print(f"[DEBUG] Error analyzing image: {e}")
                
                print(f"\n[DEBUG] Image relevance filtering complete")
                print(f"[DEBUG] Original images: {len(result['images'])}")
                print(f"[DEBUG] Relevant images: {len(relevant_images)}")
                
                # Replace with filtered images
                result['all_images'] = result['images']  # Store all original images
                result['images'] = relevant_images      # Keep only relevant ones
                result['image_relevance_filtered'] = True
            except Exception as e:
                print(f"[DEBUG] Failed to filter images by relevance: {e}")
        else:
            print(f"\n[DEBUG] No topic provided or no images found, skipping relevance filtering")
            if not topic:
                print(f"[DEBUG] Topic is empty or None")
            else:
                print(f"[DEBUG] Images list is empty or missing (keys: {list(result.keys())})")
        
        return result