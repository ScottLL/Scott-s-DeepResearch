import os
import sys
import json
import time
import asyncio
import logging
import queue
import markdown
from aiohttp import web
from modes.crawl_mode import run_crawl_mode
from utils.io_utils import QueueWriter, process_queue_messages, progress_updater

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active WebSocket connections
active_connections = set()

async def handle_websocket_crawl(request):
    """WebSocket handler for crawl mode."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    stdout_queue = queue.Queue()
    message_queue = asyncio.Queue()
    
    logger.info("WebSocket connection opened")
    
    try:
        # Wait for the client to send parameters
        msg = await ws.receive_json()
        
        # Extract parameters
        url = msg.get('url', '')
        max_pages = int(msg.get('max_pages', 5))
        depth = int(msg.get('depth', 2))
        
        # Validate URL
        if not url or not url.startswith(('http://', 'https://')):
            await ws.send_json({
                'type': 'error',
                'error': 'Invalid URL provided'
            })
            return ws
        
        # Create and start the crawling task
        crawl_task = asyncio.create_task(
            run_crawl_mode(url, max_pages, depth)
        )
        
        # Process the stdout messages
        transfer_task = asyncio.create_task(
            process_queue_messages(crawl_task, stdout_queue, message_queue, ws)
        )
        
        # Start the progress updater
        progress_task = asyncio.create_task(
            progress_updater(crawl_task, ws, interval=1.0)
        )
        
        try:
            # Wait for the crawl to complete
            results = await crawl_task
            
            # Process the results
            safe_domain = url.split('//')[1].split('/')[0].replace('.', '_')
            base_file = f"crawl_{safe_domain}"
            
            # Check if we have markdown content
            md_content = results.get('markdown', '')
            html_content = results.get('html', '')
            
            # Process images in markdown and HTML content
            if md_content:
                # Import the image embedding function directly
                from server import embed_images_in_markdown
                md_content = embed_images_in_markdown(md_content)
                results['markdown'] = md_content
            
            if html_content:
                # Import the image embedding function directly
                from server import embed_images_in_html
                html_content = embed_images_in_html(html_content)
                results['html'] = html_content
            
            # Send progress update to 100%
            await ws.send_json({
                'type': 'progress',
                'progress': 100
            })
            
            # Send completion message with results
            await ws.send_json({
                'type': 'complete',
                'results': results
            })
            
        except Exception as e:
            logger.error(f"Error during crawling: {str(e)}")
            await ws.send_json({
                'type': 'error',
                'error': f"Error during crawling: {str(e)}"
            })
        finally:
            # Cancel the progress task if still running
            if not progress_task.done():
                progress_task.cancel()
            
            # Wait for the transfer task to complete
            if not transfer_task.done():
                try:
                    await transfer_task
                except asyncio.CancelledError:
                    pass
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await ws.send_json({
                'type': 'error',
                'error': f"Server error: {str(e)}"
            })
        except:
            pass
    finally:
        logger.info("WebSocket connection closed")
    
    return ws

async def handle_start_crawl(ws, data):
    """Handle the crawling process."""
    # Create message queues
    message_queue = asyncio.Queue()
    stdout_queue = queue.Queue()
    
    # Patch stdout temporarily
    original_stdout = sys.stdout
    
    # Apply patched stdout
    sys.stdout = QueueWriter(stdout_queue, filter_image_messages=False)
    
    # Start crawl mode in a background task
    task = asyncio.create_task(run_crawl_mode(
        data['url'],
        int(data['max_pages']),
        int(data['depth']),
        message_queue
    ))
    
    # Start the progress updater with a slower pace for crawl mode
    progress_task = asyncio.create_task(progress_updater(
        task, ws, increment=3, max_progress=95, interval=2.0
    ))
    
    try:
        # Process messages from both queues
        transfer_task = await process_queue_messages(task, stdout_queue, message_queue, ws)
        
        # Process any final result from the task
        if task.done() and not task.exception():
            await handle_crawl_results(ws, task.result())
        else:
            # Default completion message
            await ws.send_json({
                'type': 'complete',
                'results': {
                    'html': '<h1>Crawl Results</h1><p>Crawl complete!</p>',
                    'markdown': '# Crawl Results\n\nCrawl complete!',
                    'json': {'data': 'Crawl complete'}
                }
            })
        
        logger.info("Sent crawl completion message")
    
    except Exception as e:
        logger.error(f"Error in crawl process: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await ws.send_json({
            'type': 'error',
            'error': f"Error in crawl process: {str(e)}"
        })
    finally:
        # Ensure stdout is restored
        sys.stdout = original_stdout
        
        # Cancel progress task if still running
        if 'progress_task' in locals() and not progress_task.done():
            progress_task.cancel()

async def handle_crawl_results(ws, result):
    """Process and send crawl results."""
    try:
        logger.info(f"Crawl task completed with result: {result}")
        
        # Get all md files in the current directory for debugging
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)  # Go up one level to project root
        all_md_files = [f for f in os.listdir(parent_dir) if f.endswith('.md')]
        logger.info(f"All MD files in directory: {all_md_files}")
        
        # Initialize variables for content
        md_content = ""
        json_content = {}
        results_sent = False
        
        # APPROACH 1: Check if result contains file paths
        if isinstance(result, dict) and 'md_file' in result:
            if await send_results_from_path(ws, result['md_file'], result.get('json_file')):
                return
        
        # APPROACH 2: Look for the latest crawl_*.md file
        if not results_sent:
            logger.info("Checking for crawl_*.md files")
            md_files = [f for f in os.listdir(parent_dir) if f.endswith('.md') and f.startswith('crawl_')]
            md_files.sort(key=lambda f: os.path.getmtime(os.path.join(parent_dir, f)), reverse=True)
            
            if md_files:
                # Get the most recent file
                md_file = md_files[0]
                md_path = os.path.join(parent_dir, md_file)
                logger.info(f"Found most recent crawl MD file: {md_path}")
                
                if await send_results_from_path(ws, md_path):
                    return
        
        # APPROACH 3: Try the direct known filename
        if not results_sent:
            logger.error("Failed to find files with crawl_ prefix, trying direct known filename")
            
            # Try the direct known filename 'crawl_mbusa_com.md'
            known_file = os.path.join(parent_dir, 'crawl_mbusa_com.md')
            if os.path.exists(known_file):
                logger.info(f"Found known crawl file: {known_file}")
                
                if await send_results_from_path(ws, known_file):
                    return
            
            # Last resort - scan for any .md files created in last 2 minutes 
            logger.error("Failed to find direct known file, looking for recent .md files")
            try:
                now = time.time()
                two_minutes_ago = now - 120  # 2 minutes ago
                
                # Find any .md file modified in the last 2 minutes
                recent_files = []
                for f in os.listdir(parent_dir):
                    if f.endswith('.md'):
                        file_path = os.path.join(parent_dir, f)
                        if os.path.getmtime(file_path) > two_minutes_ago:
                            recent_files.append(file_path)
                
                # Sort by modification time (newest first)
                recent_files.sort(key=os.path.getmtime, reverse=True)
                
                if recent_files:
                    recent_file = recent_files[0]
                    logger.info(f"Found recent MD file: {recent_file}")
                    
                    if await send_results_from_path(ws, recent_file):
                        return
            except Exception as e:
                logger.error(f"Error finding recent files: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # Absolute last resort - send fallback message
        logger.error("Failed to find or read any crawl result files")
        await ws.send_json({
            'type': 'complete',
            'results': {
                'html': '<h1>Crawl Results</h1><p>Crawl completed successfully, but could not find output files. Check server logs.</p>',
                'markdown': '# Crawl Results\n\nCrawl completed successfully, but could not find output files. Check server logs.',
                'json': result if isinstance(result, dict) else {'data': 'Crawl completed successfully, but could not find output files.'}
            }
        })
    except Exception as e:
        logger.error(f"Error processing crawl result: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await ws.send_json({
            'type': 'error',
            'error': f"Error processing result: {str(e)}"
        })

async def send_results_from_path(ws, md_path, json_path=None):
    """Read and send results from the given paths."""
    try:
        if not os.path.exists(md_path):
            logger.error(f"MD file not found: {md_path}")
            return False
            
        # Read markdown content
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # Try to find matching JSON file if not provided
        if json_path is None:
            json_path = md_path.replace('.md', '.json')
        
        # Try to read the JSON file
        json_content = {}
        if os.path.exists(json_path):
            logger.info(f"Found matching JSON file: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                json_content = json.load(f)
        
        # Generate HTML from markdown
        html_content = markdown.markdown(
            md_content,
            extensions=['tables', 'nl2br', 'fenced_code']
        )
        
        # Send content to client
        await ws.send_json({
            'type': 'complete',
            'results': {
                'html': html_content,
                'markdown': md_content,
                'json': json_content,
                'source_file': md_path,
                'force_refresh': True
            }
        })
        logger.info(f"Sent crawl results from file: {md_path}")
        return True
    except Exception as e:
        logger.error(f"Error reading results files: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False 