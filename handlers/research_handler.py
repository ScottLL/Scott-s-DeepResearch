import os
import sys
import json
import asyncio
import builtins
import logging
import queue
import inspect
import markdown
from aiohttp import web
from modes.research_mode import async_analyze_query, run_research_mode
from utils.io_utils import AlwaysAllStdin, QueueWriter, process_queue_messages, progress_updater

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active WebSocket connections
active_connections = set()

async def handle_websocket_research(request):
    """WebSocket handler for research mode."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    stdout_queue = queue.Queue()
    message_queue = asyncio.Queue()
    
    logger.info("WebSocket connection opened")
    
    query_analysis = None  # Store the query analysis for later use
    
    try:
        # Main message processing loop
        while True:
            # Wait for the client to send a message
            msg = await ws.receive_json()
            logger.info(f"Received message: {msg}")
            
            if msg.get('action') == 'analyze_query':
                # Get the query
                query = msg.get('query', '')
                if not query:
                    await ws.send_json({
                        'type': 'error',
                        'error': 'No query provided'
                    })
                    continue
                
                # Analyze the query
                analysis_task = asyncio.create_task(async_analyze_query(query))
                
                # Process the stdout messages
                process_task = asyncio.create_task(
                    process_queue_messages(analysis_task, stdout_queue, message_queue, ws)
                )
                
                # Start the progress updater
                progress_task = asyncio.create_task(
                    progress_updater(analysis_task, ws, interval=0.5, max_progress=95)
                )
                
                # Wait for both tasks to complete
                try:
                    query_analysis = await analysis_task
                    logger.info(f"Query analysis completed: {query_analysis}")
                    await ws.send_json({
                        'type': 'clarifying_questions',
                        'query_analysis': query_analysis,
                        'questions': query_analysis.get('clarifying_questions', [])
                    })
                    
                    logger.info("Waiting for start_research message...")
                    
                except Exception as e:
                    logger.error(f"Error during query analysis: {e}")
                    await ws.send_json({
                        'type': 'error',
                        'error': f"Error during query analysis: {str(e)}"
                    })
                finally:
                    # Cancel the progress task if still running
                    if not progress_task.done():
                        progress_task.cancel()
                    
                    # Wait for the process task to complete
                    if not process_task.done():
                        await process_task
            
            elif msg.get('action') == 'start_research':
                # Get the query
                query = msg.get('query', '')
                # Also get query_analysis and clarifying_responses
                msg_query_analysis = msg.get('query_analysis', None)
                clarifying_responses = msg.get('clarifying_responses', {})
                iterations = msg.get('iterations', 3)
                breadth = msg.get('breadth', 5)
                depth = msg.get('depth', 2)
                
                # Use the query_analysis we received earlier if not provided in this message
                if not msg_query_analysis and query_analysis:
                    msg_query_analysis = query_analysis
                
                if not query:
                    await ws.send_json({
                        'type': 'error',
                        'error': 'No query provided'
                    })
                    continue
                
                # Do the actual research (this will take a while)
                research_task = asyncio.create_task(
                    run_research_mode(
                        query=query,
                        iterations=iterations,
                        breadth=breadth, 
                        depth=depth,
                        query_analysis=msg_query_analysis,
                        clarifying_responses=clarifying_responses
                    )
                )
                
                # Process the stdout messages
                transfer_task = asyncio.create_task(
                    process_queue_messages(research_task, stdout_queue, message_queue, ws)
                )
                
                # Start the progress updater
                progress_task = asyncio.create_task(
                    progress_updater(research_task, ws, interval=2.0)
                )
                
                try:
                    # Redirect stdin and stdout to simulate interactive mode
                    saved_stdin = sys.stdin
                    sys.stdin = AlwaysAllStdin()
                    
                    # Run the research and wait for it to complete
                    results = await research_task
                    
                    # Log the results details for debugging
                    logger.info(f"Research completed. Results type: {type(results)}")
                    
                    # Check if results is None
                    if results is None:
                        logger.warning("Research task returned None")
                        results = {
                            'markdown': '# Research Results\n\nNo results were returned from the research task.',
                            'html': '<h1>Research Results</h1><p>No results were returned from the research task.</p>',
                            'source_file': 'unknown'
                        }
                    
                    # Make sure results is a dictionary
                    if not isinstance(results, dict):
                        logger.warning(f"Results is not a dictionary, converting to dictionary: {results}")
                        if isinstance(results, str):
                            # If it's a string, assume it's markdown
                            results = {'markdown': results, 'html': '', 'source_file': 'unknown'}
                        else:
                            # Otherwise create an empty dictionary
                            results = {'markdown': str(results), 'html': '', 'source_file': 'unknown'}
                    
                    # Initialize default values in case the results don't have these keys
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
                    
                    # Send the final results
                    await ws.send_json({
                        'type': 'progress',
                        'progress': 100
                    })
                    await ws.send_json({
                        'type': 'complete',
                        'results': results
                    })
                    
                    # Research is complete, break the loop
                    break
                    
                except Exception as e:
                    logger.error(f"Error during research: {str(e)}")
                    await ws.send_json({
                        'type': 'error',
                        'error': f"Error during research: {str(e)}"
                    })
                finally:
                    # Restore stdin
                    sys.stdin = saved_stdin
                    
                    # Cancel the progress task if still running
                    if not progress_task.done():
                        progress_task.cancel()
                    
                    # Wait for the transfer task to complete
                    if not transfer_task.done():
                        try:
                            await transfer_task
                        except asyncio.CancelledError:
                            pass
            else:
                await ws.send_json({
                    'type': 'error',
                    'error': f"Unknown action: {msg.get('action')}"
                })
    
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

async def handle_analyze_query(ws, data):
    """Handle the initial query analysis step."""
    query = data['query']
    
    # Send status update
    await ws.send_json({
        'type': 'status',
        'message': 'Analyzing your query...'
    })
    
    # Analyze the query to get clarifying questions
    try:
        query_analysis = await async_analyze_query(query)
        
        # Send the clarifying questions to the frontend
        await ws.send_json({
            'type': 'clarifying_questions',
            'query_analysis': query_analysis,
            'questions': query_analysis.get('clarifying_questions', [])
        })
        
    except Exception as e:
        logger.error(f"Error analyzing query: {e}")
        await ws.send_json({
            'type': 'error',
            'error': f"Error analyzing query: {str(e)}"
        })

async def handle_start_research(ws, data):
    """Handle the actual research with user responses."""
    import os  # Make sure os is available in this function
    query = data['query']
    query_analysis = data.get('query_analysis', {})
    clarifying_responses = data.get('clarifying_responses', {})
    
    # Create a message queue for this connection
    message_queue = asyncio.Queue()
    
    # Enhance the query with clarifying responses
    enhanced_query = query
    if clarifying_responses:
        # Add the responses to the query text itself
        enhanced_query += "\n\nAdditional information from clarifying questions:\n"
        for question, response in clarifying_responses.items():
            enhanced_query += f"- {question}: {response}\n"
    
    # Use a regular queue for capturing stdout
    stdout_queue = queue.Queue()
    
    # Patch stdout, stdin, and input() temporarily
    original_stdout = sys.stdout
    original_stdin = sys.stdin
    original_input = builtins.input
    original_env = os.environ.copy()
    
    # Pass additional parameters to control image processing
    env_vars = os.environ.copy()
    env_vars["IMAGE_TOP_K"] = "5"  # Stop after finding 5 relevant images
    env_vars["IMAGE_EARLY_STOP"] = "true"  # Enable early stopping
    
    # Apply patched environment and I/O
    sys.stdout = QueueWriter(stdout_queue)
    sys.stdin = AlwaysAllStdin()  # Redirect stdin
    builtins.input = lambda *args: "all"  # Override input() function
    os.environ.update(env_vars)
    
    # Start the research task
    task = asyncio.create_task(run_research_mode(
        enhanced_query,
        data['iterations'],
        data['breadth'],
        data['depth']
    ))
    
    # Start the progress updater
    progress_task = asyncio.create_task(progress_updater(task, ws))
    
    try:
        # Process messages from both queues
        transfer_task = await process_queue_messages(task, stdout_queue, message_queue, ws)
        
        # Process any final result from the task
        if task.done() and not task.exception():
            await handle_research_results(ws, task, stdout_queue)
        else:
            # Default completion message
            await ws.send_json({
                'type': 'complete',
                'results': {
                    'html': '<h1>Research Results</h1><p>Research complete!</p>',
                    'markdown': '# Research Results\n\nResearch complete!',
                    'json': {'data': 'Research complete'}
                }
            })
        
        logger.info("Sent completion message")
    
    except Exception as e:
        logger.error(f"Error in research process: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await ws.send_json({
            'type': 'error',
            'error': f"Error in research process: {str(e)}"
        })
    finally:
        # Ensure everything is restored
        sys.stdout = original_stdout
        sys.stdin = original_stdin
        builtins.input = original_input
        os.environ.clear()
        os.environ.update(original_env)
        
        # Cancel tasks if still running
        if 'progress_task' in locals() and not progress_task.done():
            progress_task.cancel()

async def handle_research_results(ws, task, stdout_queue):
    """Process and send research results."""
    try:
        result = task.result()
        logger.info(f"Research task completed with result: {result}")
        
        # More detailed debug logging
        logger.info(f"Result type: {type(result)}")
        
        # Initialize variables for content
        md_content = ""
        json_content = {}
        md_path = None
        json_path = None
        results_sent = False
        
        # If the result is a coroutine, await it
        if inspect.iscoroutine(result):
            try:
                logger.info("Awaiting coroutine result")
                result = await result
                logger.info(f"Awaited result: {result}")
                
                # If we got markdown content directly from the coroutine
                if isinstance(result, str) and ('# ' in result or '## ' in result):
                    logger.info("Coroutine returned markdown content directly")
                    md_content = result
                    
                    # Generate HTML
                    html_content = markdown.markdown(
                        md_content,
                        extensions=['tables', 'nl2br', 'fenced_code']
                    )
                    
                    # Send the results directly
                    await ws.send_json({
                        'type': 'complete',
                        'results': {
                            'html': html_content,
                            'markdown': md_content,
                            'json': {'data': 'Research complete'}
                        }
                    })
                    
                    logger.info("Sent markdown results directly from coroutine")
                    results_sent = True
            except Exception as e:
                logger.error(f"Error awaiting coroutine: {e}")
        
        # Check if result is a dictionary containing paths
        if isinstance(result, dict) and not results_sent:
            logger.info(f"Result keys: {list(result.keys())}")
            if 'md_path' in result:
                md_path = result['md_path']
                logger.info(f"MD path: {md_path}")
                logger.info(f"MD path exists: {os.path.exists(md_path)}")
            if 'json_path' in result:
                json_path = result['json_path']
                logger.info(f"JSON path: {json_path}")
                logger.info(f"JSON path exists: {os.path.exists(json_path)}")
            if 'markdown' in result:
                logger.info("Result already contains markdown content")
                md_content = result['markdown']
                results_sent = True
        
        # Debug: print all captured messages
        logger.info(f"Searching for filenames in {len(list(stdout_queue.queue))} captured stdout messages")
        
        # Find file paths if not directly available
        if not results_sent:
            md_path, json_path = find_result_files(stdout_queue)
            
            # If we found valid paths, read and send the content
            if md_path and os.path.exists(md_path):
                await send_file_results(ws, md_path, json_path)
            else:
                # Fallback to scanning for recent files
                await send_fallback_results(ws)
                
    except Exception as e:
        logger.error(f"Error processing result: {e}")
        await ws.send_json({
            'type': 'error',
            'error': f"Error processing result: {str(e)}"
        })

def find_result_files(stdout_queue):
    """Extract file paths from stdout messages."""
    # Convert queue items to a list for processing
    stdout_messages = list(stdout_queue.queue)
    md_path = None
    json_path = None
    
    # First check for direct report file info in stdout messages
    report_message = None
    for message in stdout_messages:
        if isinstance(message, str) and ("Report saved to" in message or "Results saved to" in message):
            report_message = message
            break
    
    if report_message:
        logger.info(f"Found direct report message: {report_message}")
        if "Report saved to" in report_message:
            parts = report_message.split("Report saved to", 1)[1].strip().split()
            if parts:
                md_path = parts[0]
                logger.info(f"Found MD path directly from report message: {md_path}")
        elif "Results saved to" in report_message:
            parts = report_message.split("Results saved to", 1)[1].strip().split()
            if parts:
                md_path = parts[0]
                logger.info(f"Found MD path directly from results message: {md_path}")
                
                # Try to extract JSON path from the same message
                if "and" in report_message and ".json" in report_message:
                    json_parts = report_message.split("and", 1)[1].strip().split()
                    if json_parts:
                        json_path = json_parts[0]
                        logger.info(f"Found JSON path directly from message: {json_path}")
    
    # If we didn't find the path from direct report message, search all messages
    if not md_path:
        # Search through all captured stdout messages
        for message in stdout_messages:
            if isinstance(message, str) and '.md' in message:
                logger.info(f"Checking message for file paths: {message[:100]}")
                
                # Try different patterns for finding the MD file
                # Pattern 1: "Report saved to <filename.md>"
                if "Report saved to" in message:
                    parts = message.split("Report saved to", 1)[1].strip().split()
                    if parts:
                        md_path = parts[0]
                        logger.info(f"Found MD path using pattern 1: {md_path}")
                
                # Pattern 2: "Results saved to <filename.md> and <filename.json>"
                elif "Results saved to" in message:
                    parts = message.split("Results saved to", 1)[1].strip().split()
                    if parts:
                        md_path = parts[0]
                        logger.info(f"Found MD path using pattern 2: {md_path}")
                        
                        # Try to extract JSON path from the same message
                        if "and" in message and ".json" in message:
                            json_parts = message.split("and", 1)[1].strip().split()
                            if json_parts:
                                json_path = json_parts[0]
                                logger.info(f"Found JSON path from the same message: {json_path}")
                
                # Pattern 3: Try to find any word ending with .md
                else:
                    import re
                    md_matches = re.findall(r'\S+\.md', message)
                    if md_matches:
                        md_path = md_matches[0]
                        logger.info(f"Found MD path using regex: {md_path}")
    
    # If we still don't have a JSON path but have an MD path, derive it
    if md_path and not json_path:
        potential_json_path = md_path.replace('.md', '.json')
        if os.path.exists(potential_json_path):
            json_path = potential_json_path
            logger.info(f"Derived JSON path from MD path: {json_path}")
    
    # Try to fix any path with spaces
    if md_path and " " in md_path:
        # Sometimes the path gets split due to spaces
        potential_path = md_path.split()[0]
        if os.path.exists(potential_path):
            md_path = potential_path
            logger.info(f"Fixed MD path by removing spaces: {md_path}")
    
    return md_path, json_path

async def send_file_results(ws, md_path, json_path):
    """Read content from files and send to client."""
    try:
        # Read markdown content
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # Try to read the JSON file too
        json_content = {}
        if json_path and os.path.exists(json_path):
            logger.info(f"Reading content from {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                json_content = json.load(f)
        
        # Generate HTML from markdown
        html_content = markdown.markdown(
            md_content,
            extensions=['tables', 'nl2br', 'fenced_code']
        )
        
        # Send results
        await ws.send_json({
            'type': 'complete',
            'results': {
                'html': html_content,
                'markdown': md_content,
                'json': json_content
            }
        })
        logger.info(f"Sent research results from {md_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error reading research results files: {e}")
        # Send default message as fallback
        await ws.send_json({
            'type': 'complete',
            'results': {
                'html': f'<h1>Research Results</h1><p>Results saved to {md_path} but could not be read: {str(e)}</p>',
                'markdown': f'# Research Results\n\nResults saved to {md_path} but could not be read: {str(e)}',
                'json': {'error': str(e)}
            }
        })
        return False

async def send_fallback_results(ws):
    """Scan for recent results files and send as fallback."""
    # Log more details about what went wrong
    logger.error(f"Could not find valid MD file.")
    logger.error(f"Current directory: {os.path.abspath('.')}")
    logger.error(f"Files in current directory: {os.listdir('.')}")
    
    # Last resort: Check for any results_*.md files
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)  # Go up one level to the project root
    results_files = [f for f in os.listdir(parent_dir) if f.endswith('.md') and f.startswith('results_')]
    
    if results_files:
        # Sort by modification time (newest first)
        results_files.sort(key=lambda f: os.path.getmtime(os.path.join(parent_dir, f)), reverse=True)
        latest_results_file = os.path.join(parent_dir, results_files[0])
        
        logger.info(f"Found latest results file as fallback: {latest_results_file}")
        
        try:
            # Read the markdown file
            with open(latest_results_file, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            # Try to read matching JSON file
            json_file = latest_results_file.replace('.md', '.json')
            json_content = {}
            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_content = json.load(f)
            
            # Generate HTML
            html_content = markdown.markdown(
                md_content,
                extensions=['tables', 'nl2br', 'fenced_code']
            )
            
            # Send results
            await ws.send_json({
                'type': 'complete',
                'results': {
                    'html': html_content,
                    'markdown': md_content,
                    'json': json_content
                }
            })
            logger.info(f"Sent fallback results from {latest_results_file}")
            return True
        except Exception as e:
            logger.error(f"Error reading fallback results file: {e}")
    
    # Couldn't find any results files to send
    await ws.send_json({
        'type': 'complete',
        'results': {
            'html': '<h1>Research Results</h1><p>Research complete, but could not find output files. Check server logs for more details.</p>',
            'markdown': '# Research Results\n\nResearch complete, but could not find output files. Check server logs for more details.',
            'json': {'data': 'Research complete, but could not find output files.'}
        }
    })
    return False 