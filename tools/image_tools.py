"""
Tools for image analysis and processing.
"""
import base64
import requests
import logging
from typing import Dict, Any, Optional
from .base_tool import BaseTool

class ImageRelevanceTool(BaseTool):
    """Tool for determining if images are relevant to a topic."""
    
    def __init__(self):
        super().__init__(
            name="image_relevance",
            description="Determines if images are relevant to a specific topic"
        )
        from analysis.agents import ImageRelevanceAgent
        self.agent = ImageRelevanceAgent("gpt-4o-mini")  # Use vision model by default
        
    async def download_image(self, url: str) -> Optional[str]:
        """Download image and convert to base64."""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return base64.b64encode(response.content).decode('utf-8')
            return None
        except Exception as e:
            self.logger.error(f"Error downloading image from {url}: {e}")
            return None
    
    async def run(self, 
                image_url: str, 
                topic: str, 
                image_description: Optional[str] = None,
                download_image: bool = True,
                image_content: Optional[str] = None) -> Dict[str, Any]:
        """
        Determine if an image is relevant to a specific topic.
        
        Args:
            image_url: URL of the image to analyze
            topic: The topic to determine relevance against
            image_description: Optional text description of the image
            download_image: Whether to download the image for analysis (True) or just use the URL (False)
            image_content: Optional pre-downloaded base64 image content
            
        Returns:
            Dict containing relevance information
        """
        print(f"[DEBUG] ImageRelevanceTool.run called")
        print(f"[DEBUG]   - URL: {image_url}")
        print(f"[DEBUG]   - Topic: {topic}")
        print(f"[DEBUG]   - Download image: {download_image}")
        print(f"[DEBUG]   - Image content provided: {image_content is not None}")
        
        try:
            # If image_content wasn't provided and download_image is True, download it now
            if image_content is None and download_image:
                print(f"[DEBUG] No image content provided, downloading...")
                image_content = await self.download_image(image_url)
                print(f"[DEBUG] Download complete, content length: {len(image_content) if image_content else 'None'}")
            
            print(f"[DEBUG] Calling ImageRelevanceAgent.analyze_image_relevance")
            result = await self.agent.analyze_image_relevance(
                image_url=image_url,
                topic=topic,
                image_content=image_content,
                image_description=image_description
            )
            
            print(f"[DEBUG] Agent returned result: {result.get('success')}")
            print(f"[DEBUG] Relevance score: {result.get('relevance_score')}")
            print(f"[DEBUG] Is relevant: {result.get('is_relevant')}")
            
            return {
                "success": True,
                "is_relevant": result.get("is_relevant", False),
                "relevance_score": result.get("relevance_score", 0),
                "analysis": result.get("analysis", ""),
                "image_url": image_url,
                "topic": topic
            }
        except Exception as e:
            print(f"[DEBUG] Error in ImageRelevanceTool.run: {e}")
            self.logger.error(f"Error analyzing image relevance: {e}")
            return {
                "success": False,
                "is_relevant": False,
                "relevance_score": 0,
                "analysis": f"Error analyzing image relevance: {str(e)}",
                "image_url": image_url,
                "topic": topic,
                "error": str(e)
            }
