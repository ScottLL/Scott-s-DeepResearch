# analysis/agents/image_relevance_agent.py
from typing import Dict, Any, List, Optional
from ..base_agent import BaseAnalysisAgent
import asyncio
import re
import base64
import os

class ImageRelevanceAgent(BaseAnalysisAgent):
    """Agent for determining relevance between images and topics."""
    
    async def analyze_image_relevance(self, 
                                     image_url: str, 
                                     topic: str,
                                     image_content: Optional[str] = None,
                                     image_description: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze if an image is relevant to a specific topic.
        
        Args:
            image_url: URL of the image
            topic: The topic to check relevance against
            image_content: Base64 encoded image content (optional)
            image_description: Text description of image if available (optional)
            
        Returns:
            Dict with relevance score and analysis
        """
        print(f"[DEBUG] ImageRelevanceAgent.analyze_image_relevance called")
        print(f"[DEBUG]   - Model: {self.model}")
        print(f"[DEBUG]   - URL: {image_url}")
        print(f"[DEBUG]   - Topic: {topic}")
        print(f"[DEBUG]   - Image content provided: {image_content is not None}")
        print(f"[DEBUG]   - Description provided: {image_description is not None}")
        
        async with self.state_context("ANALYZING_IMAGE_RELEVANCE"):
            # Determine if we're using a model that supports image input
            supports_image_input = "vision" in self.model.lower() or "gpt-4o-mini" in self.model.lower()
            print(f"[DEBUG] Using model that supports image input: {supports_image_input}")
            
            if supports_image_input and image_content:
                print(f"[DEBUG] Sending image content to vision-capable model")
                # For models supporting image input (like GPT-4V)
                messages = [
                    {"role": "system", "content": "You are an expert at analyzing image relevance to topics. Provide a detailed assessment of how relevant the image is to the given topic."},
                    {"role": "user", "content": [
                        {"type": "text", "text": f"How relevant is this image to the topic: '{topic}'? Provide a relevance score from 0-100 and explain your reasoning. If the image contains QR code or text or links, it should not consider related image. Format your response with 'RELEVANCE_SCORE: [number]' at the beginning."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_content}"}}
                    ]}
                ]
            else:
                print(f"[DEBUG] Using text-only approach (no image content or non-vision model)")
                # For text-only models, use image URL and description
                image_info = f"Image URL: {image_url}"
                if image_description:
                    image_info += f"\nImage description: {image_description}"
                
                messages = [
                    {"role": "system", "content": "You are an expert at analyzing image relevance based on image descriptions and context."},
                    {"role": "user", "content": f"Based on the following image information:\n\n{image_info}\n\nHow relevant is this image to the topic: '{topic}'? Provide a relevance score from 0-100 and explain your reasoning. If the image contains QR code or text or links, it should not consider related image. Format your response with 'RELEVANCE_SCORE: [number]' at the beginning."}
                ]
            
            try:
                print(f"[DEBUG] Executing LLM call")
                result = await self.execute(messages, temperature=0.3)
                print(f"[DEBUG] LLM returned result (length: {len(result)})")
                print(f"[DEBUG] First 100 chars of result: {result[:100]}")
                
                # Extract relevance score
                score_match = re.search(r'RELEVANCE_SCORE:\s*(\d+)', result)
                relevance_score = int(score_match.group(1)) if score_match else 50
                print(f"[DEBUG] Extracted relevance score: {relevance_score}")
                
                is_relevant = relevance_score >= 70
                print(f"[DEBUG] Image is relevant: {is_relevant} (threshold: 70)")
                
                return {
                    "success": True,
                    "relevance_score": relevance_score,
                    "analysis": result,
                    "is_relevant": is_relevant,
                    "topic": topic,
                    "image_url": image_url
                }
                
            except Exception as e:
                print(f"[DEBUG] Error in ImageRelevanceAgent: {e}")
                print(f"[Image Relevance] Error: {e}")
                return {
                    "success": False,
                    "relevance_score": 0,
                    "analysis": f"Error analyzing image relevance: {str(e)}",
                    "is_relevant": False,
                    "topic": topic,
                    "image_url": image_url,
                    "error": str(e)
                }
    
    async def batch_analyze_images(self, 
                                  images: List[Dict[str, str]], 
                                  topic: str,
                                  max_concurrent: int = 4) -> List[Dict[str, Any]]:
        """
        Analyze multiple images in parallel to determine relevance to a topic.
        
        Args:
            images: List of dicts with image info (requires 'url' key, optional 'content' and 'description')
            topic: The topic to check relevance against
            max_concurrent: Maximum number of concurrent image analyses
            
        Returns:
            List of dicts with relevance results for each image
        """
        # Create a semaphore to limit concurrent API calls
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _analyze_single_image(image_info):
            """Process a single image with semaphore control"""
            async with semaphore:
                try:
                    image_url = image_info.get('url')
                    image_content = image_info.get('content')
                    image_description = image_info.get('description')
                    
                    result = await self.analyze_image_relevance(
                        image_url=image_url,
                        topic=topic,
                        image_content=image_content,
                        image_description=image_description
                    )
                    
                    # Add the image info to the result
                    result['image_info'] = image_info
                    return result
                except Exception as e:
                    print(f"Error analyzing image {image_info.get('url')}: {str(e)}")
                    return {
                        "success": False,
                        "relevance_score": 0,
                        "is_relevant": False,
                        "error": str(e),
                        "image_info": image_info
                    }
        
        # Create tasks for each image
        tasks = [_analyze_single_image(image) for image in images]
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results to handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Exception in image analysis: {result}")
                processed_results.append({
                    "success": False,
                    "relevance_score": 0,
                    "is_relevant": False,
                    "error": str(result),
                    "image_info": images[i] if i < len(images) else {"url": "unknown"}
                })
            else:
                processed_results.append(result)
        
        return processed_results