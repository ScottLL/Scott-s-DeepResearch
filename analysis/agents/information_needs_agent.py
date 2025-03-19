from typing import Dict, Any, List
from ..base_agent import BaseAnalysisAgent
from ..utils import detect_language
import asyncio

class InformationNeedsAgent(BaseAnalysisAgent):
    """Agent for determining if more information is needed to answer a question."""
    
    async def need_more_info(self, question: str, summaries: List[str]) -> Dict[str, Any]:
        """
        Determine if the provided summaries are sufficient to answer the question.
        Returns a dict with 'need_more' boolean and 'missing_aspects' list identifying what information is missing.
        """
        async with self.state_context("ASSESSING_INFO_NEEDS"):
            # Detect question language
            lang = detect_language(question)
            
            # Ensure all summaries are strings and not tasks
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
            
            info_block = "\n".join(f"- {s}" for s in processed_summaries if s)
            prompt = (
                f"Question: {question}\n\n"
                f"Information gathered:\n{info_block}\n\n"
                f"Part 1: Is this information enough to fully answer the question? Respond with YES or NO only.\n\n"
                f"Part 2: If you answered NO, briefly identify the key aspects of the question that are not addressed by the current information. "
                f"The key aspects should be short but contain key information easy for searching such that '2023 Maybach exterior design' but not like 'Detailed trends and characteristics of the exterior design for each model (E-Class, S-Class, Maybach) from 2023 to 2025.' "
                f"List specifically what is missing in bullet points. If you answered YES, write 'COMPLETE'."
            )
            
            messages = [
                {"role": "system", "content": "You are an expert researcher helping determine if enough data is collected and what specific information is still needed."},
                {"role": "user", "content": prompt}
            ]
            
            full_answer = await self.execute(messages)
            
            # Parse the answer into parts
            parts = full_answer.split("Part 2:")
            if len(parts) > 1:
                part1 = parts[0].strip()
                part2 = parts[1].strip()
                
                # Check if we need more information
                need_more = "YES" not in part1.upper() or "NO" in part1.upper()
                
                # Extract missing aspects
                missing_aspects = []
                if part2.upper() != "COMPLETE":
                    for line in part2.split('\n'):
                        line = line.strip()
                        if line.startswith('- '):
                            missing_aspects.append(line[2:])
                        elif line.startswith('• '):
                            missing_aspects.append(line[2:])
                
                return {
                    "need_more": need_more,
                    "missing_aspects": missing_aspects
                }
            else:
                # Fallback parsing if the output format is unexpected
                need_more = "YES" not in full_answer.upper() or "NO" in full_answer.upper()
                
                # Try to extract anything that looks like missing aspects
                missing_aspects = []
                for line in full_answer.split('\n'):
                    line = line.strip()
                    if (line.startswith('- ') or line.startswith('• ')) and not line.upper().startswith("- YES") and not line.upper().startswith("- NO"):
                        missing_aspects.append(line[2:])
                
                return {
                    "need_more": need_more,
                    "missing_aspects": missing_aspects
                } 