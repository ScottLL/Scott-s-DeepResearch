import os
import asyncio
import logging
import shutil
import glob
import base64
import re
from PIL import Image
import io
from aiohttp import web
from aiohttp.web import FileResponse
from dotenv import load_dotenv

# Import the handler modules
from handlers.research_handler import handle_websocket_research
from handlers.crawl_handler import handle_websocket_crawl

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure the images directory exists
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), 'frontend')
IMAGES_DIR = os.path.join(FRONTEND_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

def copy_images_to_frontend():
    """Copy all images from results directories to the frontend/images folder."""
    try:
        # Find all image files in the project directory and subdirectories
        base_dir = os.path.dirname(__file__)
        logger.info(f"Looking for images in: {base_dir}")
        
        # 1. First specifically look for results_*_images directories - these are our priority
        results_image_dirs = []
        for root, dirs, files in os.walk(base_dir):
            for dir_name in dirs:
                if '_images' in dir_name:
                    full_path = os.path.join(root, dir_name)
                    results_image_dirs.append(full_path)
                    logger.info(f"Found potential images directory: {full_path}")
        
        # Copy images from these specific directories first
        for img_dir in results_image_dirs:
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']:
                img_files = glob.glob(os.path.join(img_dir, ext))
                logger.info(f"Found {len(img_files)} {ext} files in {img_dir}")
                
                for file_path in img_files:
                    file_name = os.path.basename(file_path)
                    dest_path = os.path.join(IMAGES_DIR, file_name)
                    
                    # Skip if already exists
                    if os.path.exists(dest_path):
                        continue
                        
                    # Copy the file
                    shutil.copy2(file_path, dest_path)
                    logger.info(f"Copied {file_name} to frontend/images")
        
        # 2. Also search for other images as a backup
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']:
            for file_path in glob.glob(os.path.join(base_dir, '**', ext), recursive=True):
                # Skip files already in the frontend/images directory
                if IMAGES_DIR in file_path:
                    continue
                    
                file_name = os.path.basename(file_path)
                dest_path = os.path.join(IMAGES_DIR, file_name)
                
                # Skip if the file already exists in the destination
                if os.path.exists(dest_path):
                    continue
                    
                # Copy the file
                shutil.copy2(file_path, dest_path)
                logger.info(f"Copied {file_name} to frontend/images")
        
        # Log the contents of the images directory for verification
        num_images = len(os.listdir(IMAGES_DIR))
        logger.info(f"Total images copied to frontend/images: {num_images}")
        logger.info(f"Images available: {os.listdir(IMAGES_DIR)[:10]}")
        
    except Exception as e:
        logger.error(f"Error copying images: {e}")
        logger.exception(e)

def embed_images_in_markdown(md_content):
    """Convert markdown with local image references to markdown with base64-embedded images."""
    # Regular expression to find image tags in markdown
    img_pattern = r'!\[(.*?)\]\((.*?)\)'
    
    def replace_image_path(match):
        alt_text = match.group(1)
        img_path = match.group(2)
        
        # If it's already a data URL or remote URL, keep it as is
        if img_path.startswith(('data:', 'http://', 'https://')):
            return f'![{alt_text}]({img_path})'
        
        # Otherwise try to load the local file
        try:
            # Handle paths from various formats
            img_path = img_path.replace('\\', '/')
            
            # Try different possible locations for the image
            possible_paths = [
                img_path,
                os.path.join(os.path.dirname(__file__), img_path),
                os.path.join(IMAGES_DIR, os.path.basename(img_path))
            ]
            
            # Also check if there are any *_images directories
            for root, dirs, _ in os.walk(os.path.dirname(__file__)):
                for dirname in dirs:
                    if '_images' in dirname:
                        img_name = os.path.basename(img_path)
                        possible_paths.append(os.path.join(root, dirname, img_name))
            
            # Try each possible path
            for path in possible_paths:
                if os.path.exists(path):
                    logger.info(f"Found image at: {path}")
                    with open(path, "rb") as img_file:
                        img_bytes = img_file.read()
                        
                    # Determine image format
                    img_format = os.path.splitext(path)[1].lstrip('.').lower()
                    if not img_format or img_format not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                        img_format = 'png'  # Default format if none detected or unsupported
                        
                    # For JPEG format, ensure correct MIME type
                    if img_format == 'jpg':
                        img_format = 'jpeg'
                        
                    # Convert to base64
                    img_base64 = base64.b64encode(img_bytes).decode()
                    data_url = f'data:image/{img_format};base64,{img_base64}'
                    
                    # Return markdown with embedded image
                    return f'![{alt_text}]({data_url})'
            
            # If we get here, no image was found
            logger.warning(f"Image not found: {img_path}")
            return f'![Image not found: {alt_text}]'
        except Exception as e:
            logger.error(f"Error embedding image {img_path}: {str(e)}")
            return f'![Error loading image: {alt_text}]'
    
    # Replace all image references with base64 encoded versions
    return re.sub(img_pattern, replace_image_path, md_content)

def embed_images_in_html(html_content):
    """Convert HTML with local image references to HTML with base64-embedded images."""
    # Simple regex to find <img> tags
    img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
    
    def replace_image_src(match):
        img_tag = match.group(0)
        img_src = match.group(1)
        
        # If it's already a data URL or remote URL, keep it as is
        if img_src.startswith(('data:', 'http://', 'https://')):
            return img_tag
        
        # Otherwise try to load the local file
        try:
            # Handle paths from various formats
            img_src = img_src.replace('\\', '/')
            
            # Try different possible locations for the image
            possible_paths = [
                img_src,
                os.path.join(os.path.dirname(__file__), img_src),
                os.path.join(IMAGES_DIR, os.path.basename(img_src))
            ]
            
            # Also check if there are any *_images directories
            for root, dirs, _ in os.walk(os.path.dirname(__file__)):
                for dirname in dirs:
                    if '_images' in dirname:
                        img_name = os.path.basename(img_src)
                        possible_paths.append(os.path.join(root, dirname, img_name))
            
            # Try each possible path
            for path in possible_paths:
                if os.path.exists(path):
                    logger.info(f"Found image at: {path}")
                    with open(path, "rb") as img_file:
                        img_bytes = img_file.read()
                        
                    # Determine image format
                    img_format = os.path.splitext(path)[1].lstrip('.').lower()
                    if not img_format or img_format not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                        img_format = 'png'  # Default format if none detected or unsupported
                        
                    # For JPEG format, ensure correct MIME type
                    if img_format == 'jpg':
                        img_format = 'jpeg'
                        
                    # Convert to base64
                    img_base64 = base64.b64encode(img_bytes).decode()
                    data_url = f'data:image/{img_format};base64,{img_base64}'
                    
                    # Replace the src in the img tag
                    return img_tag.replace(f'src="{img_src}"', f'src="{data_url}"').replace(f"src='{img_src}'", f"src='{data_url}'")
            
            # If we get here, no image was found
            logger.warning(f"Image not found: {img_src}")
            return img_tag  # Return original tag if image not found
        except Exception as e:
            logger.error(f"Error embedding image {img_src}: {str(e)}")
            return img_tag  # Return original tag on error
    
    # Replace all image references with base64 encoded versions
    return re.sub(img_pattern, replace_image_src, html_content)

# CORS middleware
@web.middleware
async def cors_middleware(request, handler):
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

async def serve_static(request):
    """Serve static files from the frontend directory."""
    path = request.path
    if path == '/':
        path = '/index.html'
    
    # Update the path to point to the frontend directory
    file_path = os.path.join(FRONTEND_DIR, path.lstrip('/'))
    
    if os.path.exists(file_path):
        # Add detailed logging for image requests
        if path.startswith('/images/'):
            logger.info(f"Serving image: {file_path}")
            # Use FileResponse which handles content-type correctly
            return FileResponse(file_path)
        
        logger.info(f"Serving file: {file_path}")
        return FileResponse(file_path)
    else:
        # For images, provide more helpful debugging
        if path.startswith('/images/'):
            logger.warning(f"Image not found: {file_path}")
            # Try to find a similarly named image as fallback
            filename = os.path.basename(path)
            similar_files = []
            for existing_file in os.listdir(IMAGES_DIR):
                if filename.lower() in existing_file.lower():
                    similar_files.append(existing_file)
            
            if similar_files:
                logger.info(f"Found similar images: {similar_files}")
                fallback_path = os.path.join(IMAGES_DIR, similar_files[0])
                logger.info(f"Using fallback image: {fallback_path}")
                return FileResponse(fallback_path)
            
            # If no similar image found, try to serve the placeholder
            placeholder_path = os.path.join(IMAGES_DIR, 'placeholder.png')
            if os.path.exists(placeholder_path):
                logger.info(f"Using placeholder image for: {filename}")
                return FileResponse(placeholder_path)
            
            # If no placeholder, return a 404 with more info
            return web.Response(status=404, text=f'Image not found: {filename}. Available images: {os.listdir(IMAGES_DIR)[:5]}...')
        
        logger.warning(f"File not found: {file_path}")
        return web.Response(status=404, text='Not found')

async def init_app():
    """Initialize the web application."""
    app = web.Application(middlewares=[cors_middleware])
    
    # Copy images to frontend/images directory
    # This is no longer needed since we're embedding images directly as base64
    # copy_images_to_frontend()
    
    # Add routes
    app.router.add_get('/', serve_static)
    app.router.add_get('/{tail:.*}', serve_static)
    
    # Add WebSocket routes
    app.router.add_get('/ws/research', handle_websocket_research)
    app.router.add_get('/ws/crawl', handle_websocket_crawl)
    
    return app

def main():
    """Main entry point."""
    app = asyncio.get_event_loop().run_until_complete(init_app())
    web.run_app(app, host='0.0.0.0', port=8000)

if __name__ == '__main__':
    main() 