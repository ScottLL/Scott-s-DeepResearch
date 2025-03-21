import sys
import os
import logging
import queue
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlwaysAllStdin:
    """Utility class that always returns 'all' for stdin operations."""
    def readline(self, *args, **kwargs):
        return "all\n"
    
    def read(self, *args, **kwargs):
        return "all"
        
    def flush(self):
        pass

class QueueWriter:
    """Utility class that captures stdout and puts it into a queue."""
    def __init__(self, stdout_queue, filter_image_messages=True):
        self.stdout_queue = stdout_queue
        self.filter_image_messages = filter_image_messages
        
    def write(self, text):
        if text:
            # Log what we're capturing for debugging
            logger.info(f"Captured stdout: {text[:100].strip()}")
            
            # Filter certain messages if needed
            if self.filter_image_messages and any([
                "[IMAGE]" in text,
                "image relevance" in text.lower(),
                "relevance_score" in text.upper(),
                "additional information from clarifying questions" in text.lower(),
                "[DEBUG]" in text,
                "HTTP Request:" in text,
                "processing image" in text.lower(),
                "downloaded image" in text.lower(),
                "base64" in text.lower(),
                "imagerelevance" in text.lower(),
                "converted to" in text.lower(),
                "threshold" in text.lower(),
                "executing llm" in text.lower()
            ]):
                # Don't forward these messages to avoid duplicate processing
                logger.info("Filtered image processing message (preventing duplicate processing)")
                return len(text)
            
            # Check if this is the final report message
            if "Report saved to" in text or "Results saved to" in text:
                # This is an important message, but avoid double-processing
                if self.stdout_queue.empty() or "Report saved to" not in ''.join([
                    item for item in list(self.stdout_queue.queue) if isinstance(item, str)
                ]):
                    # Use synchronous put() for stdout queue
                    self.stdout_queue.put(text.strip())
                return len(text)
            
            # Always send at least non-empty lines that aren't image processing related
            if text.strip():
                # Use synchronous put() for stdout queue
                self.stdout_queue.put(text.strip())
        return len(text)
    
    def flush(self):
        pass

async def process_queue_messages(task, stdout_queue, message_queue, ws):
    """Process messages from stdout queue and forward to WebSocket."""
    # Create a task to monitor the stdout_queue and transfer to message_queue
    async def transfer_queue():
        while True:
            # Check if task is done
            if task.done():
                # Give a chance for final messages to be processed
                await asyncio.sleep(0.5)
                if stdout_queue.empty():
                    break
            
            # Check for new messages
            try:
                # Non-blocking check
                message = stdout_queue.get_nowait()
                # Transfer to async queue
                await message_queue.put(message)
            except queue.Empty:
                # No messages, wait a bit
                await asyncio.sleep(0.1)
                continue
        
        # Signal end of processing
        await message_queue.put(None)

    # Start the transfer task
    transfer_task = asyncio.create_task(transfer_queue())
    
    # Process messages from the async queue
    try:
        while True:
            try:
                message = await asyncio.wait_for(message_queue.get(), timeout=1.0)
                if message is None:  # End of messages
                    logger.info("Received end-of-messages signal")
                    break
                
                logger.info(f"Sending message: {message}")
                if isinstance(message, dict):
                    await ws.send_json(message)
                else:
                    await ws.send_json({
                        'type': 'message',
                        'message': str(message)
                    })
            except asyncio.TimeoutError:
                # Check if the task is still running
                if task.done():
                    if task.exception():
                        logger.error(f"Task failed: {task.exception()}")
                        await ws.send_json({
                            'type': 'error',
                            'error': f"Task failed: {str(task.exception())}"
                        })
                    # Check if transfer task is also done
                    if transfer_task.done():
                        break
    except Exception as e:
        logger.error(f"Error in message processing loop: {e}")
        await ws.send_json({
            'type': 'error',
            'error': f"Error processing messages: {str(e)}"
        })
    finally:
        # Cancel tasks if still running
        if not transfer_task.done():
            transfer_task.cancel()
    
    return transfer_task

async def progress_updater(task, ws, increment=2, max_progress=95, interval=1.0):
    """Send periodic progress updates to the WebSocket client."""
    progress = 0
    try:
        while not task.done() and progress < 100:
            # Increment progress
            progress = min(max_progress, progress + increment)
            # Send progress update
            await ws.send_json({
                'type': 'progress',
                'progress': progress
            })
            # Also send a heartbeat message
            await ws.send_json({
                'type': 'message',
                'message': f"Progress... {progress}%"
            })
            # Wait a bit before the next update
            await asyncio.sleep(interval)
    except Exception as e:
        logger.error(f"Error in progress updater: {e}") 