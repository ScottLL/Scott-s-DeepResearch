import asyncio
import sys

async def ensure_json_serializable(data):
    """
    Recursively ensures all elements in the data structure are JSON serializable
    by resolving any asyncio.Task objects.
    """
    if isinstance(data, asyncio.Task):
        try:
            return await data
        except Exception as e:
            print(f"Error awaiting task: {e}")
            return str(e)  # Return error as string to maintain structure
    elif isinstance(data, dict):
        return {k: await ensure_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [await ensure_json_serializable(item) for item in data]
    elif isinstance(data, set):
        return [await ensure_json_serializable(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(await ensure_json_serializable(item) for item in data)
    else:
        return data

async def run_crawl_mode(url: str, max_pages: int, crawl_depth: int, raw_only: bool = False):
    """Run a basic web crawl on a site and generate a summary.
    
    Args:
        url: The URL to crawl
        max_pages: Maximum number of pages to crawl
        crawl_depth: Maximum depth of links to follow
        raw_only: If True, skip analysis and only return raw content
    """
    crawler = None
    try:
        # Import the WebCrawler class here inside the function to avoid PyTorch conflicts
        from core.crawler import WebCrawler
        
        # Import other modules needed for processing
        import reporting
        from analysis import detect_language, async_answer_question
        
        # Initialize the crawler
        crawler = WebCrawler()
        print(f"Starting crawl on {url}")
        
        # Use semaphore to control concurrency
        semaphore = asyncio.Semaphore(10)  # Allow 10 concurrent requests
        pages = await crawler.deep_crawl_site(url, max_pages=max_pages, max_depth=crawl_depth, semaphore=semaphore)
        
        print(f"Crawled {len(pages)} pages. Processing content...")
        
        # Detect site language from the first page content
        site_language = "en"  # Default to English
        for page in pages:
            if page.get('content'):
                try:
                    site_language = detect_language(page['content'])
                    print(f"Site language detected: {site_language}")
                    break
                except Exception as e:
                    print(f"Error detecting language: {e}")
                    continue
        
        # Skip individual page summaries and use raw content directly
        print("Using raw content from crawled pages...")
        all_content = []
        
        # Collect content from all pages
        for page in pages:
            if page.get('content'):
                # Just collect the content without summarizing
                all_content.append(page.get('content', ''))
        
        # Skip overview generation if raw_only is True
        if not raw_only and all_content:
            print("\nGenerating site overview...")
            prompt = f"Provide a comprehensive overview of this website: {url}"
            try:
                # Use async version directly with raw content
                overview = await async_answer_question(
                    prompt, 
                    all_content,
                    model="gpt-4o-mini", 
                    target_language=site_language
                )
                
                if isinstance(overview, dict):
                    overview_text = overview.get('answer_text', '')
                else:
                    overview_text = str(overview)
                
                print("\nOverview generated.")
            except Exception as e:
                print(f"Error generating overview: {e}")
                overview_text = f"Error generating overview for {url}: {str(e)}"
        else:
            if raw_only:
                print("\nSkipping overview generation as raw_only=True.")
                overview_text = "No overview generated (raw content only mode)."
            else:
                overview_text = f"No content could be extracted from {url}."
                print("\nNo content could be extracted for analysis.")
        
        # Save results
        try:
            domain = reporting.extract_domain_from_url(url)
            base_name = f"crawl_{domain.replace('.', '_')}"
            json_path = base_name + ".json"
            md_path = base_name + ".md"
            
            # Before saving, ensure all data is JSON serializable
            data = {
                "url": url,
                "site_language": site_language,
                "pages": pages,  # Include full pages but without summaries
                "overview": overview_text,
                "raw_only": raw_only
            }
            
            # Ensure all elements are JSON serializable
            serializable_data = await ensure_json_serializable(data)
            reporting.save_json(serializable_data, json_path)
            
            # Generate markdown report
            if raw_only:
                # For raw_only mode, create a simplified markdown report with just the content
                md_content = reporting.generate_raw_content_markdown(
                    url=url,
                    pages=pages,
                    site_language=site_language
                )
            else:
                md_content = reporting.generate_markdown_content(
                    query="", 
                    url=url, 
                    pages=pages, 
                    final_answer={"answer_text": overview_text}, 
                    target_language=site_language
                )
                
            reporting.save_markdown(md_content, md_path)
            
            print(f"\nCrawl complete. Results saved to {md_path} and {json_path}")
            return md_content
        except Exception as e:
            print(f"Error saving results: {e}")
            return f"Error saving results: {e}"
    except Exception as e:
        print(f"Error in crawl mode: {e}")
        return f"Error in crawl mode: {e}"
    finally:
        # Ensure we properly close the crawler in all cases
        if crawler:
            try:
                await crawler.close()
                print("Crawler closed successfully")
            except Exception as e:
                print(f"Error closing crawler: {e}")

# Helper function for parallel summarization
async def generate_summary(page, url, site_language):
    try:
        summary = summarize_text(
            page['content'], 
            context=f"Page from {url}", 
            target_language=site_language
        )
        return (summary, page)
    except Exception as e:
        return e 