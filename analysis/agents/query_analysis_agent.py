import re
from typing import Dict, Any
from ..base_agent import BaseAnalysisAgent
from ..utils import detect_language

class QueryAnalysisAgent(BaseAnalysisAgent):
    """Agent for analyzing queries and extracting structured information."""
    
    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze a research query to extract components, generate clarifying questions,
        and suggest an improved query formulation.
        """
        async with self.state_context("ANALYZING_QUERY"):
            try:
                # Detect language of the query
                query_lang = detect_language(query)
                
                prompt = (
                    f"Analyze this research query and break it down into components:\n\n"
                    f"QUERY: {query}\n\n"
                    f"Please provide the following analysis:\n"
                    f"1. COMPONENTS: List the main components of this query (objects, timeframes, attributes, etc.)\n"
                    f"2. CLARIFYING_QUESTIONS: What clarifying questions would help refine this query? List them clearly with one question per line, each preceded by a bullet point or number.\n"
                    f"3. IMPROVED_QUERY: Suggest an improved version of this query that would yield better search results\n\n"
                    f"Your analysis should be in the same language as the original query ({query_lang})."
                )
                
                messages = [
                    {"role": "system", "content": "You are an expert at analyzing research queries to improve search effectiveness."},
                    {"role": "user", "content": prompt}
                ]
                
                analysis_text = await self.execute(messages)
                
                # Parse the response to extract structured information
                components = []
                clarifying_questions = []
                improved_query = query
                
                # Try to find the COMPONENTS section
                components_match = re.search(r'(?:COMPONENTS:|1\.)[^\n]*\n(.*?)(?:CLARIFYING_QUESTIONS:|2\.)', analysis_text, re.DOTALL)
                if components_match:
                    components_section = components_match.group(1).strip()
                
                # Try to find the CLARIFYING_QUESTIONS section  
                questions_match = re.search(r'(?:CLARIFYING_QUESTIONS:|2\.)[^\n]*\n(.*?)(?:IMPROVED_QUERY:|3\.)', analysis_text, re.DOTALL)
                if questions_match:
                    questions_section = questions_match.group(1).strip()
                
                # Extract components
                for line in components_section.split('\n'):
                    line = line.strip()
                    if line and (line.startswith('- ') or line.startswith('• ') or re.match(r'^\d+\.\s+', line)):
                        # Remove bullet points or numbering
                        component = re.sub(r'^(?:- |• |\d+\.\s+)', '', line).strip()
                        if component:
                            components.append(component)
                
                # Extract clarifying questions 
                for line in questions_section.split('\n'):
                    line = line.strip()
                    if line and ('?' in line or '？' in line):  # Support both Western and Chinese question marks
                        # Remove bullet points or numbering
                        question = re.sub(r'^(?:- |• |\d+\.\s+)', '', line).strip()
                        if question:
                            clarifying_questions.append(question)
                
                # Completely new approach to extract improved query
                # First try to find a dedicated improved query section
                improved_section = re.search(r'(?:IMPROVED_QUERY:|3\.)[^\n]*\n(.*?)(?=\n\n|\Z)', analysis_text, re.DOTALL)
                
                if improved_section:
                    candidate_query = improved_section.group(1).strip()
                    
                    # Filter out anything that looks like a list or instructions
                    if not re.match(r'^\d+\.|\-\s+|\•\s+', candidate_query) and len(candidate_query.split('\n')) <= 3:
                        improved_query = candidate_query
                    else:
                        # If we have a multiline response or list-like format, just use the first line that looks like a query
                        for line in candidate_query.split('\n'):
                            clean_line = line.strip()
                            # Skip if line starts with list markers or is too short
                            if not re.match(r'^\d+\.|\-\s+|\•\s+', clean_line) and len(clean_line) > 10:
                                improved_query = clean_line
                                break
                
                # Safeguard: If no proper improved query found, use the original query
                if not improved_query or improved_query == "" or any(q in improved_query for q in clarifying_questions):
                    improved_query = query
                    
                # Final validation to ensure we don't have question lists
                if re.match(r'^\d+\.|\?|\？|\-\s+|\•\s+', improved_query):
                    improved_query = query
                
                return {
                    "components": components,
                    "clarifying_questions": clarifying_questions[:5],  # Limit to 5 questions
                    "improved_query": improved_query,
                    "language": query_lang
                }
            except Exception as e:
                print(f"[Query Analysis] Error: {e}")
                return {
                    "components": [],
                    "clarifying_questions": [],
                    "improved_query": query,
                    "language": "en",
                    "error": str(e)
                } 