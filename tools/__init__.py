"""
Tools package for search, extraction, and analysis capabilities.
"""
from typing import Dict, Type, List

# First import the base tool class and registry
from .base_tool import BaseTool, WebCrawlerTool
from .tool_registry import ToolRegistry

# Then import tool implementations
from .search_tools import GoogleSearchTool, BaiduSearchTool
from .extraction_tools import ContentExtractionTool
from .link_tools import LinkExplorationTool
from .analysis_tools import TextSummarizerTool, QueryAnalysisTool
from .utility_tools import LanguageDetectionTool, ModelAvailabilityTool
from .image_tools import ImageRelevanceTool

# Register all tools
ToolRegistry.register(GoogleSearchTool())
ToolRegistry.register(BaiduSearchTool())
ToolRegistry.register(ContentExtractionTool())
ToolRegistry.register(LinkExplorationTool())
ToolRegistry.register(TextSummarizerTool())
ToolRegistry.register(QueryAnalysisTool())
ToolRegistry.register(LanguageDetectionTool())
ToolRegistry.register(ModelAvailabilityTool())
ToolRegistry.register(ImageRelevanceTool())

# Utility functions that use the tools but present a simpler interface
async def detect_language(text: str) -> str:
    """
    Detect the language of the input text.
    Returns the language code (e.g., 'en' for English, 'es' for Spanish).
    """
    tool = ToolRegistry.get_tool("language_detection")
    result = await tool.run(text)
    return result.get("language", "en")

async def is_ollama_available() -> bool:
    """
    Check if Ollama server is reachable.
    Returns True if available, False otherwise.
    """
    tool = ToolRegistry.get_tool("model_availability")
    result = await tool.run(service="ollama")
    return result.get("services", {}).get("ollama", {}).get("available", False)

# Export all tools
__all__ = [
    'BaseTool',
    'WebCrawlerTool',
    'ToolRegistry',
    'GoogleSearchTool',
    'BaiduSearchTool',
    'ContentExtractionTool',
    'LinkExplorationTool',
    'TextSummarizerTool',
    'QueryAnalysisTool',
    'LanguageDetectionTool',
    'ModelAvailabilityTool',
    'ImageRelevanceTool',
    'detect_language',
    'is_ollama_available'
] 