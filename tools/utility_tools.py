"""
Utility tools for language detection and model availability checks.
"""
import logging
import requests
from typing import Dict, Any, Optional, List

from .base_tool import BaseTool

class LanguageDetectionTool(BaseTool):
    """Tool for detecting the language of text content."""
    
    def __init__(self):
        super().__init__(
            name="language_detection",
            description="Detects the language of text content"
        )
    
    async def run(self, text: str) -> Dict[str, Any]:
        """
        Detect the language of the input text.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dict with detected language and metadata
        """
        try:
            from langdetect import detect, LangDetectException, detect_langs
            
            # First try to get language with confidence scores
            try:
                lang_probabilities = detect_langs(text)
                primary_language = lang_probabilities[0].lang
                confidence = lang_probabilities[0].prob
                
                # Get all languages with a reasonable probability
                other_languages = [
                    {"lang": l.lang, "probability": l.prob} 
                    for l in lang_probabilities[1:] 
                    if l.prob > 0.05  # Only include languages with >5% probability
                ]
                
                return {
                    "success": True,
                    "language": primary_language,
                    "confidence": confidence,
                    "alternative_languages": other_languages
                }
            except:
                # Fall back to simple detection
                language = detect(text)
                return {
                    "success": True,
                    "language": language,
                    "confidence": None,
                    "alternative_languages": []
                }
                
        except (ImportError, LangDetectException) as e:
            if isinstance(e, ImportError):
                self.logger.warning("langdetect not available. Install with: pip install langdetect")
            else:
                self.logger.error(f"Language detection error: {e}")
                
            # Default to English if detection fails
            return {
                "success": False,
                "language": "en",  # Default to English
                "confidence": None,
                "alternative_languages": [],
                "error": str(e)
            }

class ModelAvailabilityTool(BaseTool):
    """Tool for checking availability of LLM models and services."""
    
    def __init__(self):
        super().__init__(
            name="model_availability",
            description="Checks availability of language models and services"
        )
        from analysis.clients import ollama_base_url, openai_api_key
        self.ollama_base_url = ollama_base_url
        self.openai_api_key = openai_api_key
    
    async def run(self, service: str = "all") -> Dict[str, Any]:
        """
        Check availability of language model services.
        
        Args:
            service: Which service to check ("all", "ollama", "openai", etc.)
            
        Returns:
            Dict with service availability status
        """
        results = {}
        
        # Check Ollama
        if service in ["all", "ollama"]:
            try:
                response = requests.get(self.ollama_base_url.replace("/v1", "/api/tags"), timeout=5)
                ollama_available = response.status_code == 200
                models = response.json().get("models", []) if ollama_available else []
                
                results["ollama"] = {
                    "available": ollama_available,
                    "models": [model.get("name") for model in models],
                    "url": self.ollama_base_url
                }
            except Exception as e:
                results["ollama"] = {
                    "available": False,
                    "error": str(e),
                    "url": self.ollama_base_url
                }
        
        # Check OpenAI
        if service in ["all", "openai"]:
            try:
                # Only check if API key is available
                if self.openai_api_key:
                    from openai import OpenAI
                    client = OpenAI(api_key=self.openai_api_key)
                    # Lightweight request to check API availability
                    models = client.models.list()
                    model_names = [model.id for model in models.data]
                    
                    results["openai"] = {
                        "available": True,
                        "models": model_names
                    }
                else:
                    results["openai"] = {
                        "available": False,
                        "error": "No API key configured"
                    }
            except Exception as e:
                results["openai"] = {
                    "available": False,
                    "error": str(e)
                }
        
        # Add overall availability status
        if service == "all":
            results["any_available"] = any(
                results.get(s, {}).get("available", False) 
                for s in ["ollama", "openai"]
            )
        
        return {
            "success": True,
            "services": results
        } 