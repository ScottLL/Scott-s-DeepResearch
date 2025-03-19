from typing import Dict, Any, List
from ..base_agent import BaseAnalysisAgent
from ..utils import detect_language
import asyncio

class AnswerGenerationAgent(BaseAnalysisAgent):
    """Agent for generating comprehensive answers to questions."""
    
    async def answer_question(self, question: str, summaries: List[str], target_language: str = None) -> Dict[str, Any]:
        """
        Generate a comprehensive answer to a question based on the provided summaries.
        Ensures the answer is in the target language if specified.
        """
        async with self.state_context("GENERATING_ANSWER"):
            # Detect question language if target language not provided
            if not target_language:
                target_language = detect_language(question)
            
            # Prepare research materials - ensure all summaries are strings and not tasks
            research_materials = []
            for i, summary in enumerate(summaries, 1):
                # Handle case where summary might be an asyncio.Task
                if isinstance(summary, asyncio.Task):
                    try:
                        # Await the task to get the actual string
                        summary = await summary
                    except Exception as e:
                        print(f"Error awaiting summary task: {e}")
                        continue
                
                # Now summary should be a string - check if it's valid
                if summary and isinstance(summary, str) and len(summary.strip()) > 0:
                    research_materials.append(f"Source {i}: {summary}")
            
            research_block = "\n\n".join(research_materials)
            
            if target_language == "en":
                prompt = (
                    f"Question: {question}\n\n"
                    f"Research Materials:\n{research_block}\n\n"
                    f"Based on the above research materials, provide a comprehensive, factual answer to the question. "
                    f"Include all relevant information from the sources. "
                    f"Structure your answer with clear paragraphs and appropriate formatting. "
                    f"If the information is insufficient to fully answer the question, clearly state what's missing."
                )
            else:
                prompt = (
                    f"Question: {question}\n\n"
                    f"Research Materials:\n{research_block}\n\n"
                    f"Based on the above research materials, provide a comprehensive, factual answer to the question. "
                    f"Include all relevant information from the sources. "
                    f"Structure your answer with clear paragraphs and appropriate formatting. "
                    f"Your answer must be in {target_language} language. "
                    f"If the information is insufficient to fully answer the question, clearly state what's missing."
                )
            
            messages = [
                {"role": "system", "content": f"You are an expert researcher who provides comprehensive answers based on provided materials. Your answers should be well-structured, factual, and in {target_language} language."},
                {"role": "user", "content": prompt}
            ]
            
            answer_text = await self.execute(messages, temperature=0.3, max_tokens=10000)
            
            return {
                "answer_text": answer_text,
                "language": target_language,
                "sources_count": len(summaries),
                "question": question
            } 