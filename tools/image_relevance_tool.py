# tools/image_relevance_tool.py
from typing import Dict, Any, List, Optional
from .base_tool import BaseTool
from analysis.agents import ImageRelevanceAgent
import asyncio
import base64
import requests
from io import BytesIO

class ImageRelevanceTool(BaseTool):
    """Tool for analyzing the relevance of images to a topic."""
    
    def __init__(self):
        super().__init__()
        self.agent = ImageRelevanceAgent()
    
    async def run(self, 
                 urls: List[str] = None,
                 topic: str = "",
                 threshold: int = 60,
                 max_concurrent: int = 4,
                 top_k: int = 5,
                 download_images: bool = True) -> Dict[str, Any]:
        """
        Analyze multiple images in parallel to determine relevance to a topic.
        
        Args:
            urls: List of image URLs to analyze
            topic: Topic to check relevance against
            threshold: Minimum relevance score (0-100) to consider an image relevant
            max_concurrent: Maximum number of concurrent image analyses
            top_k: Maximum number of relevant images to return
            download_images: Whether to download image content for better analysis
            
        Returns:
            Dict with relevant images and their scores
        """
        if not urls:
            return {"success": False, "error": "No image URLs provided"}
        
        if not topic:
            return {"success": False, "error": "No topic provided"}
        
        try:
            print(f"[DEBUG] Processing {len(urls)} images in parallel (max_concurrent={max_concurrent})")
            
            # Prepare image information
            image_info_list = []
            
            # Download images concurrently if needed
            if download_images:
                image_info_list = await self._download_images_parallel(urls, max_concurrent)
            else:
                image_info_list = [{"url": url} for url in urls]
            
            # Use the batch analysis method
            results = await self.agent.batch_analyze_images(
                images=image_info_list,
                topic=topic,
                max_concurrent=max_concurrent
            )
            
            # Filter and sort by relevance
            relevant_images = [r for r in results if r.get("relevance_score", 0) >= threshold]
            relevant_images.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            # Take top_k images
            top_relevant = relevant_images[:top_k] if top_k > 0 else relevant_images
            
            return {
                "success": True,
                "relevant_images": top_relevant,
                "total_processed": len(results),
                "total_relevant": len(relevant_images),
                "returned_count": len(top_relevant)
            }
            
        except Exception as e:
            print(f"Error in ImageRelevanceTool: {e}")
            return {"success": False, "error": str(e)}
    
    async def _download_images_parallel(self, urls: List[str], max_concurrent: int = 4) -> List[Dict[str, str]]:
        """Download multiple images in parallel and convert to base64."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _download_single_image(url):
            async with semaphore:
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        image_data = response.content
                        # Convert to base64
                        base64_data = base64.b64encode(image_data).decode('utf-8')
                        return {"url": url, "content": base64_data}
                    else:
                        print(f"Error downloading image {url}: HTTP {response.status_code}")
                        return {"url": url}
                except Exception as e:
                    print(f"Error downloading image {url}: {e}")
                    return {"url": url}
        
        # Create tasks for each URL
        tasks = [_download_single_image(url) for url in urls]
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Exception downloading image: {result}")
                processed_results.append({"url": urls[i] if i < len(urls) else "unknown"})
            else:
                processed_results.append(result)
        
        return processed_results