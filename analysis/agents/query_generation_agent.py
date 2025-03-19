import re
from typing import List
from ..base_agent import BaseAnalysisAgent
from ..utils import detect_language
import asyncio

class QueryGenerationAgent(BaseAnalysisAgent):
    """Agent for generating targeted search queries."""
    
    async def generate_targeted_queries(self, 
                                      question: str, 
                                      summaries: List[str], 
                                      missing_aspects: List[str], 
                                      max_queries: int = 3) -> List[str]:
        """
        Generate targeted search queries to find information about missing aspects.
        
        Args:
            question: The research question
            summaries: List of text summaries collected during research
            missing_aspects: List of aspects identified as missing from current information
            max_queries: Maximum number of queries to generate (default: 3)
            
        Returns:
            List of targeted search queries
        """
        async with self.state_context("GENERATING_QUERIES"):
            # Detect language of the question
            lang = detect_language(question)
            
            all_queries = []
            
            # Generate queries in original language
            if missing_aspects:
                # Calculate how many queries to generate in original language
                orig_lang_queries = max_queries
                
                # Process summaries to ensure they're strings, not tasks
                processed_summaries = []
                for summary in summaries:
                    # Handle case where summary might be an asyncio.Task
                    if isinstance(summary, asyncio.Task):
                        try:
                            # Await the task to get the actual string
                            summary = await summary
                        except Exception as e:
                            print(f"Error awaiting summary task: {e}")
                            continue
                    
                    # Now summary should be a string
                    if summary and isinstance(summary, str) and len(summary.strip()) > 0:
                        processed_summaries.append(summary)
                
                # Create an information block from existing summaries
                info_block = "\n".join(f"- {s}" for s in processed_summaries if s)
                
                # Prepare information about what's missing
                missing_info_block = "\n".join(f"- {aspect}" for aspect in missing_aspects if aspect)
                
                # Helper info to guide query formation
                target_objects_info = ""
                time_periods_info = ""
                attributes_info = ""
                
                # Check if query involves specific objects
                if any(keyword in question.lower() for keyword in ['vs', 'versus', 'compare', 'comparison', 'difference']):
                    target_objects_info = "Focus on generating queries for each specific object being compared.\n"
                
                # Check if query involves time periods
                if any(keyword in question.lower() for keyword in ['year', 'annual', 'monthly', 'history', 'trend', 'evolution', 'development']):
                    time_periods_info = "Include specific time periods in your queries (e.g., '2020-2022').\n"
                
                # Check if query involves attributes or metrics
                if any(keyword in question.lower() for keyword in ['rate', 'percentage', 'statistics', 'number', 'count', 'measure']):
                    attributes_info = "Include specific measurable attributes in your queries.\n"
                
                prompt = (
                    f"Original research question: {question}\n\n"
                    f"Information already collected:\n{info_block}\n\n"
                    f"Missing information that needs to be researched:\n{missing_info_block}\n\n"
                    f"Generate {orig_lang_queries} ULTRA-SPECIFIC search queries that:\n"
                    f"1. Are CONCISE (3-8 words)\n"
                    f"2. Target precise facts or specific data points addressing the missing information\n"
                    f"3. Use exact names, specific models, years, or technical terms\n"
                    f"4. Cover different time periods if the question involves trend analysis\n"
                    f"5. Would work effectively as direct inputs to search engines\n\n"
                    f"{target_objects_info}"
                    f"{time_periods_info}"
                    f"{attributes_info}\n"
                    f"Format your response as a numbered list of search queries ONLY (no explanations):\n"
                    f"1. [Query 1]\n2. [Query 2]\n3. [Query 3]\n...\n\n"
                    f"All queries must be in the same language as the original question ({lang})."
                )
                
                messages = [
                    {"role": "system", "content": "You are an expert at generating research queries..."},
                    {"role": "user", "content": prompt}
                ]
                
                result = await self.execute(messages, temperature=0.7)
                
                # Parse the numbered list into individual queries
                orig_lang_results = []
                for line in result.split('\n'):
                    line = line.strip()
                    # Match lines that start with a number followed by a period and space
                    if re.match(r'^\d+\.\s+', line):
                        # Remove the number and period prefix
                        query = re.sub(r'^\d+\.\s+', '', line).strip()
                        if query:
                            orig_lang_results.append(query)
                
                # Fallback if parsing failed
                if not orig_lang_results and result:
                    # Just split by newlines as a fallback
                    orig_lang_results = [line.strip() for line in result.split('\n') if line.strip()]
                
                all_queries.extend(orig_lang_results[:orig_lang_queries])
            
            # Limit to max_queries
            return all_queries[:max_queries] 