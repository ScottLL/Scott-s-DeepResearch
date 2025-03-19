import json
import re
import os
import requests
from urllib.parse import urlparse, urljoin
import logging
import hashlib
import base64
import time
import asyncio

async def filter_images_by_relevance(images, topic, relevance_threshold=60):
    """
    Filter images based on their relevance to a topic.
    Process images until we find 5 with scores above the relevance threshold.
    
    Args:
        images: List of image dictionaries with URLs
        topic: The topic to check relevance against
        relevance_threshold: Minimum relevance score to include the image (default 60)
        
    Returns:
        List of relevant images with relevance data added
    """
    try:
        print(f"\n[DEBUG] Starting filter_images_by_relevance")
        print(f"[DEBUG] Number of images to filter: {len(images)}")
        print(f"[DEBUG] Topic: '{topic}'")
        print(f"[DEBUG] Relevance threshold: {relevance_threshold}")
        
        from tools import ToolRegistry
        
        # Get the image relevance tool
        image_tool = ToolRegistry.get_tool("image_relevance")
        print(f"[DEBUG] Successfully retrieved image_relevance tool")
        
        # Track processed URLs to avoid duplicates
        processed_urls = set()
        
        # Process a single image
        async def process_image(img, index):
            # Extract URL based on whether img is a dict or string
            img_url = img.get('url') if isinstance(img, dict) else img
            
            if not img_url or img_url in processed_urls:
                return None
                
            processed_urls.add(img_url)
            print(f"[DEBUG] Processing image {index+1}: {img_url}")
            
            try:
                # Download the image
                response = requests.get(img_url, timeout=10)
                if response.status_code == 200:
                    print(f"[DEBUG] Successfully downloaded image ({len(response.content)} bytes)")
                    
                    # Convert image to base64
                    image_content = base64.b64encode(response.content).decode('utf-8')
                    print(f"[DEBUG] Converted to base64 (length: {len(image_content)})")
                    
                    # Now run relevance check with the actual image content
                    print(f"[DEBUG] Analyzing image relevance...")
                    relevance = await image_tool.run(
                        img_url, 
                        topic, 
                        download_image=False,
                        image_content=image_content
                    )
                    
                    score = relevance.get('relevance_score', 0)
                    is_relevant = relevance.get('is_relevant', False)
                    print(f"[DEBUG] Relevance result - Score: {score}, Is relevant: {is_relevant}")
                    
                    # Create result with relevance data
                    if isinstance(img, dict):
                        result_img = img.copy()  # Create a copy to avoid modifying original
                        result_img['relevance_score'] = score
                        result_img['relevance_analysis'] = relevance.get('analysis', '')
                        result_img['is_relevant'] = is_relevant
                    else:
                        # Create a new dict for string URLs
                        result_img = {
                            'url': img,
                            'relevance_score': score,
                            'relevance_analysis': relevance.get('analysis', ''),
                            'is_relevant': is_relevant
                        }
                    
                    return result_img
                else:
                    print(f"[DEBUG] Failed to download image {img_url}: HTTP {response.status_code}")
            except Exception as e:
                print(f"[DEBUG] Error processing image {img_url}: {e}")
            
            return None
        
        # Target number of relevant images to find
        target_count = 5
        
        # Store relevant results (images with scores above threshold)
        relevant_results = []
        
        # Store all valid results in case we don't find enough relevant ones
        all_results = []
        
        # Process images one by one until we find enough relevant ones
        for i, img in enumerate(images):
            # Check if we already have enough relevant images
            if len(relevant_results) >= target_count:
                print(f"[DEBUG] Found {target_count} relevant images with scores above {relevance_threshold}, stopping early")
                break
                
            # Process this image
            result = await process_image(img, i)
            
            # If valid result, add to our collections
            if result is not None:
                all_results.append(result)
                
                # Check if it meets the relevance threshold
                if result.get('relevance_score', 0) >= relevance_threshold:
                    relevant_results.append(result)
                    print(f"[DEBUG] Found relevant image ({len(relevant_results)}/{target_count}): Score {result.get('relevance_score', 0)}")
                    
                    # EARLY EXIT CHECK: if we have enough relevant images, break immediately
                    if len(relevant_results) >= target_count:
                        print(f"[DEBUG] Found {len(relevant_results)} relevant images (target: {target_count}), stopping early")
                        break
        
        # If we have enough relevant images, return just those
        if len(relevant_results) >= target_count:
            print(f"[DEBUG] Returning {len(relevant_results)} images with scores above {relevance_threshold}")
            # Sort by relevance score (highest first)
            relevant_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            return relevant_results[:target_count]
        
        # Otherwise, return the best images we found, regardless of threshold
        print(f"[DEBUG] Only found {len(relevant_results)} images above threshold {relevance_threshold}")
        print(f"[DEBUG] Returning top {min(target_count, len(all_results))} images out of {len(all_results)} processed")
        
        # Sort all results by relevance score (highest first)
        all_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return all_results[:target_count]
    
    except Exception as e:
        print(f"[DEBUG] Error in filter_images_by_relevance: {e}")
        print(f"Error filtering images by relevance: {e}")
        return images[:5]  # Return up to 5 original images if there's an error

async def generate_markdown_content(query: str, url: str, pages: list, final_answer: dict, target_language=None) -> str:
    """
    Generate a Markdown formatted report given the research query or site URL, 
    the pages (with content/summary), and the final answer or summary.
    
    Args:
        query: The research query
        url: The site URL (for crawl mode)
        pages: List of crawled pages
        final_answer: The final answer or summary
        target_language: The language to use for the report
    """
    # Detect query language if not provided
    if query and not target_language:
        try:
            from analysis import detect_language
            target_language = detect_language(query)
        except:
            target_language = "en"
    
    # Create directory for images
    report_name = "research_results"
    if query:
        safe_query = "".join(c for c in query[:50] if c.isalnum() or c in " _-")
        report_name = f"results_{safe_query.strip().replace(' ','_')}" or report_name
    elif url:
        domain = extract_domain_from_url(url)
        report_name = f"crawl_{domain.replace(' ', '_')}"
    
    images_dir = f"{report_name}_images"
    
    report_lines = []
    # Title of report
    if query:
        report_lines.append(f"# Research Report")
        report_lines.append(f"**Query:** {query}\n")
    elif url:
        report_lines.append(f"# Website Crawl Report")
        report_lines.append(f"**Website:** {url}\n")
    else:
        report_lines.append(f"# Research Report\n")
    
    # For section titles, use appropriate language
    if target_language == "zh":
        report_lines.append("## 研究结果\n")
        sources_title = "## 来源"
    elif target_language == "es":
        report_lines.append("## Hallazgos\n")
        sources_title = "## Fuentes"
    elif target_language == "fr":
        report_lines.append("## Résultats\n")
        sources_title = "## Sources"
    elif target_language == "de":
        report_lines.append("## Ergebnisse\n")
        sources_title = "## Quellen"
    elif target_language == "ja":
        report_lines.append("## 調査結果\n")
        sources_title = "## 情報源"
    else:  # Default to English
        report_lines.append("## Findings\n")
        sources_title = "## Sources"
    
    # Prepare all sources and images
    all_images = []
    for i, page in enumerate(pages, 1):
        images = page.get('images', [])
        if images:
            # Add source metadata to images
            for img in images:
                img_url = img.get('url') if isinstance(img, dict) else img
                if img_url:
                    all_images.append({
                        "url": img_url, 
                        "source_num": i,
                        "source_title": clean_page_title(page.get('title', '')) or f"Source {i}",
                        "alt": img.get('alt', '') if isinstance(img, dict) else "",
                        "relevance_score": img.get('relevance_score', 0) if isinstance(img, dict) else 0,
                        "relevance_analysis": img.get('relevance_analysis', '') if isinstance(img, dict) else "",
                        "is_relevant": img.get('is_relevant', False) if isinstance(img, dict) else False
                    })
    
    # Use our filter_images_by_relevance function to efficiently find 5 relevant images
    # This function will stop once it finds 5 relevant images above the threshold
    print(f"[DEBUG] Filtering {len(all_images)} images for relevance to '{query}'")
    filtered_images = await filter_images_by_relevance(all_images, query, relevance_threshold=60)
    print(f"[DEBUG] Found {len(filtered_images)} relevant images after filtering")
    
    # Extract the answer_text from the final_answer dictionary
    answer_text = ""
    if isinstance(final_answer, dict):
        answer_text = final_answer.get("answer_text", "")
    elif isinstance(final_answer, str):
        answer_text = final_answer
    
    # Process the final answer and insert source references
    if answer_text:
        # Split the final answer into paragraphs
        paragraphs = answer_text.strip().split('\n\n')
        
        # Include relevance score in image caption if available
        # The filtered_images are already in order of relevance
        image_index = 0
        
        for i, para in enumerate(paragraphs):
            # First, add the paragraph text
            report_lines.append(para)
            
            # Add an image after this paragraph if appropriate
            if image_index < len(filtered_images) and (i == 0 or i % 3 == 0):  # Distribute images evenly
                img_data = filtered_images[image_index]
                image_index += 1  # Move to next image
                
                try:
                    local_filename = download_image(img_data["url"], images_dir)
                    if local_filename:
                        report_lines.append("")  # Empty line before image
                        # Fix: Sanitize alt text to remove markdown characters
                        alt_text = img_data["alt"] or img_data["source_title"]
                        alt_text = re.sub(r'[\[\]\(\)]', '', alt_text).strip()  # Remove brackets and parentheses
                        report_lines.append(f"![{alt_text}]({images_dir}/{local_filename})")
                        
                        # Add relevance info if available
                        if img_data.get('relevance_score', 0) > 0:
                            report_lines.append(f"*Image from [Source {img_data['source_num']}] - Relevance: {img_data['relevance_score']}/100*")
                        else:
                            report_lines.append(f"*Image from [Source {img_data['source_num']}]*")
                except Exception as e:
                    print(f"Error including image {img_data['url']}: {e}")
            
            report_lines.append("")  # Empty line between paragraphs
        
    else:
        report_lines.append("_No conclusive answer available._\n")
    
    # Sources section
    report_lines.append(sources_title)
    
    for i, page in enumerate(pages, 1):
        # Get the URL
        url = page.get('url', '')
        
        if url:
            # Just use the domain name as the display text
            domain = extract_domain_from_url(url)
            if domain:
                report_lines.append(f"{i}. [{domain}]({url})")
            else:
                # If domain extraction fails, just use the URL as is
                report_lines.append(f"{i}. [{url}]({url})")
        else:
            # Fallback if no URL
            report_lines.append(f"{i}. Source {i}")
        
        report_lines.append("")  # Add a blank line after each source
    
    report_lines.append("")  # end with newline
    return "\n".join(report_lines)

def get_key_phrases(text, num_phrases=5):
    """Extract key phrases from text for matching purposes."""
    sentences = re.split(r'[.!?]', text)
    words = [word.strip().lower() for sentence in sentences for word in sentence.split() 
             if len(word.strip()) > 4]  # Only consider words with 5+ chars
    
    # Get most frequent meaningful words
    word_freq = {}
    for word in words:
        if word not in word_freq:
            word_freq[word] = 0
        word_freq[word] += 1
    
    # Get top words
    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:num_phrases*2]
    top_words = [word for word, _ in top_words]
    
    # Find phrases containing these words
    phrases = []
    for sentence in sentences:
        if len(sentence.strip()) < 10:  # Skip very short sentences
            continue
        for word in top_words:
            if word in sentence.lower():
                clean_phrase = sentence.strip()
                # Take a reasonable chunk of the sentence
                if len(clean_phrase) > 40:
                    pos = clean_phrase.lower().find(word)
                    start = max(0, pos - 20)
                    end = min(len(clean_phrase), pos + 20)
                    clean_phrase = clean_phrase[start:end]
                
                if clean_phrase and clean_phrase not in phrases:
                    phrases.append(clean_phrase)
                break
    
    return phrases[:num_phrases]

def clean_page_title(title):
    """Clean a page title to make it more readable."""
    if not title:
        return "Untitled"
    
    # Remove common prefixes and suffixes
    title = re.sub(r'^(\[ ?!\[\]\(.*?\) ?\]|\[\])\s*\(.*?\)', '', title)
    title = re.sub(r'\s*\|.*$', '', title)
    
    # Remove URLs
    title = re.sub(r'https?://\S+', '', title)
    
    # Clean up whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title or "Untitled"

def extract_domain_from_url(url):
    """
    Extract the domain from a URL, handling various cases and potential errors.
    """
    try:
        from urllib.parse import urlparse
        
        if not url:
            return "unknown_domain"
            
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Parse URL
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Remove www. if present
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # Handle empty domain
        if not domain:
            # Try to get something from the path
            if parsed_url.path:
                parts = parsed_url.path.strip('/').split('/')
                if parts and parts[0]:
                    return parts[0]
            return "unknown_domain"
            
        return domain
    except Exception as e:
        print(f"Error extracting domain from URL {url}: {e}")
        return "unknown_domain"

def extract_h1_title(content):
    """Try to extract an h1 title from HTML content."""
    if not content:
        return ""
    
    match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
    if match:
        # Clean up HTML entities and tags
        title = re.sub(r'<.*?>', '', match.group(1))
        return title.strip()
    return ""

def save_markdown(content, filepath):
    """Save markdown content to a file."""
    # Check if content is a coroutine (async function result)
    if hasattr(content, '__await__'):
        import asyncio
        
        # If the event loop is already running, we need to use a different approach
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Use a new thread to run the coroutine in a new event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    def run_coro():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result = new_loop.run_until_complete(asyncio.ensure_future(content))
                        new_loop.close()
                        return result
                    content = executor.submit(run_coro).result()
            else:
                # No loop is running, run the coroutine directly
                content = asyncio.run(content)
        except RuntimeError:
            # If we can't get an event loop, create a new one
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            content = new_loop.run_until_complete(asyncio.ensure_future(content))
            new_loop.close()
    
    # Check if the filepath has a directory component
    dir_name = os.path.dirname(filepath)
    if dir_name:  # Only create directories if there's a directory component
        os.makedirs(dir_name, exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Report saved to {filepath}")

def download_image(url, folder, max_size=10*1024*1024):
    """
    Download an image and save it to disk.
    Returns the local filename on success, None on failure.
    """
    try:
        os.makedirs(folder, exist_ok=True)
        
        # Generate a filename based on URL hash
        url_hash = hashlib.md5(url.encode()).hexdigest()
        
        # Get file extension from URL or default to .jpg
        parsed_url = urlparse(url)
        path = parsed_url.path
        ext = os.path.splitext(path)[1].lower()
        if not ext or ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            ext = '.jpg'  # Default to jpg
        
        filename = f"{url_hash}{ext}"
        filepath = os.path.join(folder, filename)
        
        # Check if file already exists
        if os.path.exists(filepath):
            return filename
        
        # Download the image
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10, stream=True)
        
        if response.status_code == 200:
            # Check file size before downloading completely
            content_length = int(response.headers.get('Content-Length', 0))
            if content_length > max_size:
                print(f"Image too large: {content_length/1024/1024:.2f}MB > {max_size/1024/1024:.2f}MB")
                return None
            
            # Write image to file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return filename
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
    
    return None

async def analyze_page_images(url, topic):
    """
    Analyze the relevance of images on a webpage to a specific topic.
    This is a standalone function for testing the image relevance functionality.
    
    Args:
        url: URL of the webpage to analyze
        topic: Topic to check image relevance against
    """
    # Get the content extraction tool
    from tools import ToolRegistry
    extractor = ToolRegistry.get_tool("content_extraction")
    
    # Extract content from the webpage
    content = await extractor.run(url, topic=topic)
    
    print(f"Analyzing images on {url} for relevance to '{topic}'")
    print(f"Found {len(content.get('images', []))} images")
    
    # Check image relevance directly
    if content.get('images'):
        for i, img in enumerate(content.get('images')[:3]):  # Check first 3 images
            print(f"\nImage {i+1}:")
            print(f"URL: {img['url']}")
            print(f"Relevance score: {img.get('relevance_score', 'N/A')}")
            analysis = img.get('relevance_analysis', 'N/A')
            print(f"Analysis: {analysis[:100]}..." if len(analysis) > 100 else f"Analysis: {analysis}")
    
    return content.get('images', [])

async def test_image_relevance(image_url, topic):
    """
    Test function to analyze a single image's relevance to a topic.
    
    Args:
        image_url: URL of the image to analyze
        topic: Topic to check relevance against
    """
    print(f"\n===== TESTING IMAGE RELEVANCE =====")
    print(f"Image URL: {image_url}")
    print(f"Topic: {topic}")
    
    try:
        from tools import ToolRegistry
        import requests
        import base64
        
        # Get the image relevance tool
        image_tool = ToolRegistry.get_tool("image_relevance")
        print(f"Successfully retrieved image_relevance tool")
        
        # Download the image
        print(f"Downloading image...")
        response = requests.get(image_url, timeout=10)
        if response.status_code == 200:
            print(f"Successfully downloaded image ({len(response.content)} bytes)")
            
            # Convert image to base64
            image_content = base64.b64encode(response.content).decode('utf-8')
            print(f"Converted to base64 (length: {len(image_content)})")
            
            # Analyze relevance
            print(f"Analyzing image relevance...")
            relevance = await image_tool.run(
                image_url, 
                topic, 
                download_image=False,
                image_content=image_content
            )
            
            print(f"\nRelevance Analysis Result:")
            print(f"  Is relevant: {relevance.get('is_relevant', False)}")
            print(f"  Score: {relevance.get('relevance_score', 0)}")
            print(f"  Analysis: {relevance.get('analysis', '')[:200]}...")
            
            return relevance
        else:
            print(f"Failed to download image: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"Error testing image relevance: {e}")
        return None

def save_json(data, filepath):
    """Save json data to a file."""
    # Check if the filepath has a directory component
    dir_name = os.path.dirname(filepath)
    if dir_name:  # Only create directories if there's a directory component
        os.makedirs(dir_name, exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"JSON data saved to {filepath}")

def sanitize_filename(filename):
    """Sanitize a string to be used as a filename."""
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Remove unsafe characters
    filename = re.sub(r'[^\w\-.]', '', filename)
    # Limit length
    if len(filename) > 50:
        filename = filename[:47] + '...'
    return filename

def generate_raw_content_markdown(url: str, pages: list, site_language: str = "en") -> str:
    """
    Generate a simple markdown report with just the raw content from pages.
    No summaries or analysis, just the content from each page.
    
    Args:
        url: The URL that was crawled
        pages: List of page dictionaries from the crawler
        site_language: The detected language of the site
        
    Returns:
        Markdown content as a string
    """
    from datetime import datetime
    
    # Start with a header
    lines = []
    lines.append(f"# Raw Content from {url}")
    lines.append(f"Crawled on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Language: {site_language}")
    lines.append(f"Number of pages: {len(pages)}")
    lines.append("\n---\n")
    
    # Add a table of contents
    lines.append("## Table of Contents")
    for i, page in enumerate(pages, 1):
        title = page.get('title', 'Untitled')
        page_url = page.get('url', '')
        if title and page_url:
            lines.append(f"{i}. [{title}](#{i})")
    
    lines.append("\n---\n")
    
    # Add each page's content
    for i, page in enumerate(pages, 1):
        title = page.get('title', 'Untitled')
        page_url = page.get('url', '')
        content = page.get('content', '')
        
        # Add a header for the page
        lines.append(f"## {i}. {title}")
        lines.append(f"URL: {page_url}")
        
        # Add metadata if available
        if 'depth' in page:
            lines.append(f"Depth: {page.get('depth', 0)}")
        
        # Add the raw content directly (without code block)
        lines.append("\n<hr>\n")
        lines.append("### Page Content:\n")
        
        # Truncate extremely long content
        if len(content) > 50000:
            content = content[:50000] + "... [content truncated due to length]"
            
        # Clean up content to display nicely as markdown
        # Replace multiple newlines with a paragraph break
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Add the content directly, without code block
        lines.append(content)
        
        # Add a separator
        lines.append("\n<hr>\n")
    
    # Add a footer
    lines.append("## End of Raw Content")
    lines.append("This report contains only the raw extracted content from each page.")
    
    return "\n".join(lines)

