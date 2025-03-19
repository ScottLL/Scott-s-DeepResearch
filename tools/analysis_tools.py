"""
Tools for analyzing and processing text content.
"""
from typing import Dict, Any, List, Optional
from .base_tool import BaseTool

class TextSummarizerTool(BaseTool):
    """Tool for summarizing text content."""
    
    def __init__(self):
        super().__init__(
            name="text_summarizer",
            description="Summarizes text content with a focus on key information"
        )
        from analysis.agents import SummarizerAgent
        self.agent = SummarizerAgent()
    
    async def run(self, 
                 text: str, 
                 context: Optional[str] = None, 
                 target_language: Optional[str] = None) -> Dict[str, Any]:
        """
        Summarize text content.
        
        Args:
            text: The text to summarize
            context: Optional query context
            target_language: Optional target language
            
        Returns:
            Dict with summary and metadata
        """
        try:
            summary = await self.agent.summarize_text(text, context, target_language)
            return {
                "success": True,
                "summary": summary,
                "original_length": len(text),
                "summary_length": len(summary) if summary else 0
            }
        except Exception as e:
            self.logger.error(f"Error summarizing text: {e}")
            return {
                "success": False,
                "summary": "",
                "error": str(e)
            }

class QueryAnalysisTool(BaseTool):
    """Tool for analyzing search queries."""
    
    def __init__(self):
        super().__init__(
            name="query_analyzer",
            description="Analyzes search queries to extract components and suggest improvements"
        )
        from analysis.agents import QueryAnalysisAgent
        self.agent = QueryAnalysisAgent()
    
    async def run(self, query: str) -> Dict[str, Any]:
        """
        Analyze a search query.
        
        Args:
            query: The query to analyze
            
        Returns:
            Dict with analysis results
        """
        try:
            analysis = await self.agent.analyze_query(query)
            return {
                "success": True,
                "components": analysis.get("components", []),
                "clarifying_questions": analysis.get("clarifying_questions", []),
                "improved_query": analysis.get("improved_query", query),
                "language": analysis.get("language", "en")
            }
        except Exception as e:
            self.logger.error(f"Error analyzing query: {e}")
            return {
                "success": False,
                "error": str(e)
            } 