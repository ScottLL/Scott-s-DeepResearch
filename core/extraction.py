"""
Module for extracting content from web pages.
"""
import re
import logging
from urllib.parse import urlparse

async def crawl_page(url: str, crawler=None) -> dict:
    """
    Crawl a single page by URL and return its content.
    Returns a dict with 'url', 'title', 'content', 'images', and possibly 'error'.
    
    If crawl4ai is not available, attempts a simple request-based fallback.
    
    Args:
        url: The URL to crawl
        crawler: Optional WebCrawler instance (used to access crawler config)
    """
    # Check for valid URL scheme
    if not url.startswith(('http://', 'https://')):
        logging.error(f"Invalid URL scheme: {url}")
        return {"url": url, "title": "", "content": "", "images": [],
                "error": "Invalid URL: must start with http:// or https://"}
    
    # Try to determine if we have crawl4ai available
    has_crawl4ai = False
    if crawler is not None and hasattr(crawler, 'crawler'):
        has_crawl4ai = True
    
    # Try with crawl4ai first if available
    if has_crawl4ai:
        try:
            # Ensure the crawler is initialized
            if hasattr(crawler, '_ensure_crawler'):
                await crawler._ensure_crawler()
            
            # Set a reasonable page timeout
            try:
                # Instead of copy(), create a new CrawlerRunConfig with the same settings
                from crawl4ai.async_configs import CrawlerRunConfig
                # Use same settings as default config with modified timeout
                custom_config = CrawlerRunConfig(
                    word_count_threshold=crawler.default_run_config.word_count_threshold 
                        if hasattr(crawler.default_run_config, 'word_count_threshold') else 5,
                    remove_overlay_elements=crawler.default_run_config.remove_overlay_elements 
                        if hasattr(crawler.default_run_config, 'remove_overlay_elements') else True,
                    process_iframes=False,  # Always disable iframe processing
                    page_timeout=30000  # 30 seconds in milliseconds
                )
            except ImportError:
                # If we can't import CrawlerRunConfig, use the default config
                custom_config = crawler.default_run_config
                logging.warning("Could not create custom config, using default config")
            
            # Log attempt
            logging.info(f"Attempting to crawl {url} with crawl4ai")
            
            result = await crawler.crawler.arun(url=url, config=custom_config)
            
            # Extract content from the crawl4ai result
            content_text = ""
            title = ""
            images = []
            
            # Try to extract markdown content first
            if hasattr(result, "markdown"):
                try:
                    if isinstance(result.markdown, str):
                        content_text = result.markdown
                    else:
                        content_text = getattr(result.markdown, "text", "") or str(result.markdown)
                except Exception as e:
                    logging.warning(f"Error extracting markdown content: {e}")
            
            # If no markdown content, try HTML content
            if not content_text and hasattr(result, "cleaned_html"):
                try:
                    content_text = getattr(result, "cleaned_html", "")
                except Exception:
                    pass
            
            # Last resort, try raw HTML
            if not content_text and hasattr(result, "html"):
                try:
                    content_text = getattr(result, "html", "")
                except Exception:
                    pass
                    
            # Extract images from the page
            try:
                # Try to get images from the result object
                if hasattr(result, "images") and result.images:
                    images = result.images
                # If images aren't directly available, try to extract from HTML
                elif hasattr(result, "html") or hasattr(result, "cleaned_html"):
                    html_content = getattr(result, "cleaned_html", "") or getattr(result, "html", "")
                    # Extract image URLs using regex
                    img_urls = re.findall(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', html_content)
                    # Filter for common image formats and prepare image objects
                    for img_url in img_urls:
                        if re.search(r'\.(jpg|jpeg|png|gif|webp)(\?.*)?$', img_url.lower()):
                            # Create image object with URL and empty alt text
                            images.append({"url": img_url, "alt": "", "width": None, "height": None})
                
                # Take only the top 5 largest/most relevant images
                images = images[:5]
                logging.info(f"Extracted {len(images)} images from {url}")
            except Exception as e:
                logging.warning(f"Error extracting images: {e}")
                images = []
                
            # Try to get title
            try:
                title = result.title if hasattr(result, "title") else ""
            except Exception:
                title = ""
                
            # If we have content but no title, extract first line as title
            if content_text and not title:
                for line in content_text.splitlines():
                    if line.strip():
                        title = line.strip()
                        if len(title) > 150:
                            title = title[:150] + "..."
                        break
            
            # Check if we got useful content            
            if not content_text or len(content_text.strip()) < 100:
                logging.warning(f"Limited or no content found at {url}")
                
            # Log content size for debugging
            content_size = len(content_text) if content_text else 0
            logging.info(f"Extracted {content_size} characters from {url}")
                
            return {"url": url, "title": title, "content": content_text, "images": images}
            
        except Exception as e:
            logging.error(f"Error with crawl4ai for {url}: {str(e)}")
            logging.info(f"Falling back to requests-based crawler for {url}")
            # Fall through to the requests-based fallback
            has_crawl4ai = False  # Force fallback even if crawl4ai was available
    
    # Fallback to simple requests-based scraper
    try:
        import requests
        from bs4 import BeautifulSoup
        
        logging.info(f"Fallback scraping for: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Set a shorter timeout for the fallback request
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title_elem = soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Extract main content by removing boilerplate
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            
            # Get all paragraphs and headings
            content_elements = soup.select('p, h1, h2, h3, h4, h5, h6, article, section, main')
            content_text = "\n\n".join([elem.get_text(strip=True) for elem in content_elements if elem.get_text(strip=True)])
            
            # Extract images
            images = []
            img_tags = soup.find_all('img', src=True)
            for img in img_tags[:5]:  # Limit to 5 images
                src = img['src']
                
                # Handle relative URLs
                if src.startswith('/'):
                    parsed_url = urlparse(url)
                    src = f"{parsed_url.scheme}://{parsed_url.netloc}{src}"
                elif not src.startswith(('http://', 'https://')):
                    parsed_url = urlparse(url)
                    src = f"{parsed_url.scheme}://{parsed_url.netloc}/{src}"
                
                if re.search(r'\.(jpg|jpeg|png|gif|webp)(\?.*)?$', src.lower()):
                    images.append({
                        "url": src,
                        "alt": img.get('alt', ''),
                        "width": img.get('width'),
                        "height": img.get('height')
                    })
            
            logging.info(f"Fallback extracted {len(content_text)} characters and {len(images)} images from {url}")
            
            return {"url": url, "title": title, "content": content_text, "images": images}
        else:
            logging.error(f"Fallback request failed for {url}: HTTP {response.status_code}")
            return {"url": url, "title": "", "content": "", "images": [], 
                    "error": f"HTTP Error: {response.status_code}"}
            
    except ImportError:
        logging.error("requests and BeautifulSoup are required for fallback scraping")
        return {"url": url, "title": "", "content": "", "images": [], 
                "error": "Required libraries not available for scraping"}
    except Exception as e:
        logging.error(f"Error crawling {url}: {e}")
        return {"url": url, "title": "", "content": "", "images": [], "error": str(e)} 