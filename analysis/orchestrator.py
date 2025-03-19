from typing import List, Dict, Any
from .base_agent import BaseAnalysisAgent
from .agents import (
    TranslationAgent,
    QueryAnalysisAgent,
    InformationNeedsAgent,
    QueryGenerationAgent,
    AnswerGenerationAgent
)

class AnalysisOrchestrator:
    """
    Coordinates multiple analysis agents to perform complex research tasks.
    """
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.translation_agent = TranslationAgent(model)
        self.query_analysis_agent = QueryAnalysisAgent(model)
        self.info_needs_agent = InformationNeedsAgent(model)
        self.query_generation_agent = QueryGenerationAgent(model)
        self.answer_generation_agent = AnswerGenerationAgent(model)
    
    async def run_full_research_cycle(self, 
                                     question: str, 
                                     summaries: List[str],
                                     max_queries: int = 3) -> Dict[str, Any]:
        """
        Execute a full research cycle:
        1. Analyze the query
        2. Determine if more information is needed
        3. Generate targeted queries if needed
        4. Generate a comprehensive answer
        """
        # Analyze the query
        query_analysis = await self.query_analysis_agent.analyze_query(question)
        
        # Check if we need more information
        info_needs = await self.info_needs_agent.need_more_info(question, summaries)
        
        # Generate targeted queries if needed
        queries = []
        if info_needs["need_more"]:
            queries = await self.query_generation_agent.generate_targeted_queries(
                question, 
                summaries, 
                info_needs["missing_aspects"],
                max_queries
            )
        
        # Generate an answer with the available information
        answer = await self.answer_generation_agent.answer_question(
            question, 
            summaries, 
            target_language=query_analysis.get("language")
        )
        
        return {
            "query_analysis": query_analysis,
            "info_needs": info_needs,
            "queries": queries,
            "answer": answer
        } 