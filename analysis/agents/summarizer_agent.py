from typing import List, Dict, Any, Optional
import asyncio
from ..base_agent import BaseAnalysisAgent
from ..utils import detect_language

class SummarizerAgent(BaseAnalysisAgent):
    """Agent for summarizing text content with a focus on extracting key information."""
    
    async def summarize_text(self, 
                           text: str, 
                           context: Optional[str] = None, 
                           target_language: Optional[str] = None) -> str:
        """
        Summarize text content into a concise summary focused on key query aspects.
        
        Args:
            text: Text content to summarize
            context: Optional query context for better summarization
            target_language: Optional target language for the summary (defaults to text language)
        
        Returns:
            String summary of the text
        """
        async with self.state_context("SUMMARIZING"):
            # Handle case where text might be an asyncio.Task
            if isinstance(text, asyncio.Task):
                try:
                    text = await text
                except Exception as e:
                    print(f"Error awaiting text task: {e}")
                    return ""
            
            if not text or not isinstance(text, str) or text.isspace():
                return ""
                
            # Handle case where context might be an asyncio.Task
            if isinstance(context, asyncio.Task):
                try:
                    context = await context
                except Exception as e:
                    print(f"Error awaiting context task: {e}")
                    context = None
                
            # Detect the language of the text
            try:
                source_lang = detect_language(text)
            except:
                source_lang = "en"  # Default to English if detection fails
            
            # Detect context language if provided
            context_lang = None
            if context:
                try:
                    context_lang = detect_language(context)
                except:
                    context_lang = "en"
            
            # Determine target language (priority: explicitly specified, context language, text language)
            output_lang = target_language or context_lang or source_lang
            
            # Set system message based on languages
            if output_lang != source_lang:
                system_message = f"You are a precise summarization assistant that extracts key information from text. Summarize the content in {output_lang} language, translating from {source_lang} if needed. Focus on extracting time periods, main objects, key attributes, and goals from the content. Assess if the content addresses the query needs."
            else:
                system_message = f"You are a precise summarization assistant that extracts key information from text. Your summary must be in {output_lang} language. Focus on extracting time periods, main objects, key attributes, and goals from the content. Assess if the content addresses the query needs."
            
            # Create more targeted prompt that focuses on key aspects
            if context:
                prompt = (
                    f"Summarize the following content in relation to this query: '{context}'\n\n"
                    f"Focus your summary on:\n"
                    f"1. Time periods, dates, or temporal information mentioned\n"
                    f"2. Main objects, entities, or subjects discussed\n"
                    f"3. Key attributes, properties, or characteristics described\n"
                    f"4. Goals, purposes, or objectives mentioned\n\n"
                    f"Also briefly indicate whether the content directly addresses the query needs.\n\n"
                    f"Content to summarize:\n{text}"
                )
            else:
                prompt = (
                    f"Summarize the following content:\n\n"
                    f"Focus your summary on:\n"
                    f"1. Time periods, dates, or temporal information mentioned\n"
                    f"2. Main objects, entities, or subjects discussed\n"
                    f"3. Key attributes, properties, or characteristics described\n"
                    f"4. Goals, purposes, or objectives mentioned\n\n"
                    f"Content to summarize:\n{text}"
                )
            
            try:
                messages = [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ]
                
                summary = await self.execute(messages, temperature=0.5, max_tokens=150)
                return summary
            except Exception as e:
                print(f"[Summarizer] Error summarizing text: {e}")
                return ""
    
    async def summarize_pages(self, 
                            pages: List[Dict[str, Any]], 
                            context: Optional[str] = None, 
                            num_results: int = 5, 
                            target_language: Optional[str] = None) -> List[str]:
        """
        Summarize multiple pages and return summaries.
        
        Args:
            pages: List of page dictionaries with content
            context: Optional query context for better summarization
            num_results: Maximum number of pages to summarize
            target_language: Target language for summaries
        
        Returns:
            List of summary strings
        """
        # Handle case where pages might be an asyncio.Task
        if isinstance(pages, asyncio.Task):
            try:
                pages = await pages
            except Exception as e:
                print(f"Error awaiting pages task: {e}")
                return []
        
        # Handle case where context might be an asyncio.Task
        if isinstance(context, asyncio.Task):
            try:
                context = await context
            except Exception as e:
                print(f"Error awaiting context task: {e}")
                context = None
        
        summaries = []
        pages_to_process = pages[:num_results] if num_results < len(pages) else pages
        
        # Detect context language if provided
        context_lang = None
        if context:
            try:
                context_lang = detect_language(context)
            except:
                context_lang = "en"
        
        # Use context language as target language if not specified
        output_lang = target_language or context_lang or "en"
        
        for page in pages_to_process:
            if not page:
                continue
                
            # Handle case where page might be an asyncio.Task
            if isinstance(page, asyncio.Task):
                try:
                    page = await page
                except Exception as e:
                    print(f"Error awaiting page task: {e}")
                    continue
            
            content = page.get('content')
            
            # Handle case where content might be an asyncio.Task
            if isinstance(content, asyncio.Task):
                try:
                    content = await content
                except Exception as e:
                    print(f"Error awaiting content task: {e}")
                    content = None
            
            if not content:
                continue
                
            try:
                summary = await self.summarize_text(
                    content, 
                    context=context, 
                    target_language=output_lang
                )
                if summary:
                    summaries.append(summary)
            except Exception as e:
                print(f"Error summarizing page {page.get('url', 'unknown')}: {e}")
        
        return summaries 