import asyncio
from typing import List, Dict, Any, Optional
from .agents import (
    TranslationAgent,
    QueryAnalysisAgent,
    InformationNeedsAgent,
    QueryGenerationAgent,
    AnswerGenerationAgent,
    SummarizerAgent,
    ImageRelevanceAgent
)

# Legacy function adapters to maintain compatibility with existing code
async def async_translate_to_english(text: str, target_lang: str, model: str = "gpt-4o-mini") -> str:
    """Async version of translate_to_english"""
    agent = TranslationAgent(model)
    return await agent.translate(text, target_lang)

def translate_to_english(text: str, target_lang: str, model: str = "gpt-4o-mini") -> str:
    """Legacy adapter for translate_to_english function"""
    # Check if we're already in an event loop
    if asyncio.get_event_loop().is_running():
        # Create a future and run it in the current loop
        return asyncio.create_task(async_translate_to_english(text, target_lang, model))
    else:
        # Not in an event loop, safe to use asyncio.run()
        return asyncio.run(async_translate_to_english(text, target_lang, model))

async def async_analyze_query(query: str, model: str = "qwq-32b") -> Dict[str, Any]:
    """Async version of analyze_query"""
    agent = QueryAnalysisAgent(model)
    return await agent.analyze_query(query)

def analyze_query(query: str, model: str = "qwq-32b") -> Dict[str, Any]:
    """Legacy adapter for analyze_query function"""
    if asyncio.get_event_loop().is_running():
        return asyncio.create_task(async_analyze_query(query, model))
    else:
        return asyncio.run(async_analyze_query(query, model))

async def async_need_more_info(question: str, summaries: List[str], model: str = "qwq-32b") -> Dict[str, Any]:
    """Async version of need_more_info"""
    agent = InformationNeedsAgent(model)
    return await agent.need_more_info(question, summaries)

def need_more_info(question: str, summaries: List[str], model: str = "qwq-32b") -> Dict[str, Any]:
    """Legacy adapter for need_more_info function"""
    if asyncio.get_event_loop().is_running():
        return asyncio.create_task(async_need_more_info(question, summaries, model))
    else:
        return asyncio.run(async_need_more_info(question, summaries, model))

async def async_generate_targeted_queries(
    question: str, 
    summaries: List[str], 
    missing_aspects: List[str], 
    max_queries: int = 3, 
    model: str = "qwq-32b"
) -> List[str]:
    """Async version of generate_targeted_queries"""
    agent = QueryGenerationAgent(model)
    return await agent.generate_targeted_queries(question, summaries, missing_aspects, max_queries)

def generate_targeted_queries(
    question: str, 
    summaries: List[str], 
    missing_aspects: List[str], 
    max_queries: int = 3, 
    model: str = "qwq-32b"
) -> List[str]:
    """Legacy adapter for generate_targeted_queries function"""
    if asyncio.get_event_loop().is_running():
        return asyncio.create_task(async_generate_targeted_queries(question, summaries, missing_aspects, max_queries, model))
    else:
        return asyncio.run(async_generate_targeted_queries(question, summaries, missing_aspects, max_queries, model))

async def async_answer_question(
    question: str, 
    summaries: List[str], 
    model: str = "qwq-32b", 
    target_language: str = None
) -> Dict[str, Any]:
    """Async version of answer_question"""
    agent = AnswerGenerationAgent(model)
    return await agent.answer_question(question, summaries, target_language)

def answer_question(
    question: str, 
    summaries: List[str], 
    model: str = "qwq-32b", 
    target_language: str = None
) -> Dict[str, Any]:
    """Legacy adapter for answer_question function"""
    if asyncio.get_event_loop().is_running():
        return asyncio.create_task(async_answer_question(question, summaries, model, target_language))
    else:
        return asyncio.run(async_answer_question(question, summaries, model, target_language))

# Function for suggesting follow-up queries
async def async_suggest_followup_queries(
    question: str, 
    summaries: List[str], 
    max_queries: int = 3, 
    target_language: str = None,
    model: str = "qwq-32b"
) -> List[str]:
    """
    Generate follow-up queries based on the question and collected summaries.
    
    Args:
        question: The original research question
        summaries: List of text summaries collected so far
        max_queries: Maximum number of queries to generate
        target_language: Target language for queries
        model: The model to use
    
    Returns:
        List of suggested follow-up queries
    """
    # Use a simpler approach by delegating to InformationNeedsAgent and QueryGenerationAgent
    info_needs_agent = InformationNeedsAgent(model)
    query_gen_agent = QueryGenerationAgent(model)
    
    # First, determine what information is missing
    info_needs = await info_needs_agent.need_more_info(question, summaries)
    
    # If we need more info, generate targeted queries
    if info_needs["need_more"]:
        return await query_gen_agent.generate_targeted_queries(
            question,
            summaries,
            info_needs["missing_aspects"],
            max_queries
        )
    
    return []  # No queries needed if information is sufficient

def suggest_followup_queries(
    question: str, 
    summaries: List[str], 
    max_queries: int = 3, 
    target_language: str = None,
    model: str = "qwq-32b"
) -> List[str]:
    """Legacy adapter for suggest_followup_queries function"""
    if asyncio.get_event_loop().is_running():
        return asyncio.create_task(async_suggest_followup_queries(question, summaries, max_queries, target_language, model))
    else:
        return asyncio.run(async_suggest_followup_queries(question, summaries, max_queries, target_language, model))

# Add summarizer legacy functions
async def async_summarize_text(text: str, 
                             context: Optional[str] = None, 
                             target_language: Optional[str] = None, 
                             model: str = "gpt-4o-mini") -> str:
    """Async version of summarize_text"""
    agent = SummarizerAgent(model)
    return await agent.summarize_text(text, context, target_language)

def summarize_text(text: str, 
                  context: Optional[str] = None, 
                  target_language: Optional[str] = None, 
                  model: str = "gpt-4o-mini") -> str:
    """Legacy adapter for summarize_text function"""
    if asyncio.get_event_loop().is_running():
        return asyncio.create_task(async_summarize_text(text, context, target_language, model))
    else:
        return asyncio.run(async_summarize_text(text, context, target_language, model))

async def async_summarize_pages(pages: List[Dict[str, Any]], 
                              context: Optional[str] = None, 
                              num_results: int = 5, 
                              target_language: Optional[str] = None,
                              model: str = "gpt-4o-mini") -> List[str]:
    """Async version of summarize_pages"""
    agent = SummarizerAgent(model)
    return await agent.summarize_pages(pages, context, num_results, target_language)

def summarize_pages(pages: List[Dict[str, Any]], 
                   context: Optional[str] = None, 
                   num_results: int = 5, 
                   target_language: Optional[str] = None,
                   model: str = "gpt-4o-mini") -> List[str]:
    """Legacy adapter for summarize_pages function"""
    if asyncio.get_event_loop().is_running():
        return asyncio.create_task(async_summarize_pages(pages, context, num_results, target_language, model))
    else:
        return asyncio.run(async_summarize_pages(pages, context, num_results, target_language, model))

async def async_analyze_image_relevance(
    image_url: str, 
    topic: str,
    image_content: Optional[str] = None,
    image_description: Optional[str] = None, 
    model: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """Async version of analyze_image_relevance"""
    agent = ImageRelevanceAgent(model)
    return await agent.analyze_image_relevance(image_url, topic, image_content, image_description)

def analyze_image_relevance(
    image_url: str, 
    topic: str,
    image_content: Optional[str] = None,
    image_description: Optional[str] = None, 
    model: str = "gpt-4o-mini"
) -> Dict[str, Any]:
    """Legacy adapter for analyze_image_relevance function"""
    if asyncio.get_event_loop().is_running():
        return asyncio.create_task(async_analyze_image_relevance(image_url, topic, image_content, image_description, model))
    else:
        return asyncio.run(async_analyze_image_relevance(image_url, topic, image_content, image_description, model)) 