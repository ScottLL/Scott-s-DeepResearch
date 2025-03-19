# Import and expose all necessary components to maintain backward compatibility
from .utils import detect_language, is_ollama_available
from .base_agent import BaseAnalysisAgent
from .agents import (
    TranslationAgent,
    QueryAnalysisAgent,
    InformationNeedsAgent,
    QueryGenerationAgent,
    AnswerGenerationAgent,
    SummarizerAgent,
    ImageRelevanceAgent
)
from .orchestrator import AnalysisOrchestrator
from .legacy import (
    translate_to_english,
    async_translate_to_english,
    analyze_query, 
    async_analyze_query,
    need_more_info, 
    async_need_more_info,
    generate_targeted_queries, 
    async_generate_targeted_queries,
    answer_question, 
    async_answer_question,
    suggest_followup_queries, 
    async_suggest_followup_queries,
    summarize_text,
    async_summarize_text,
    summarize_pages,
    async_summarize_pages,
    analyze_image_relevance,
    async_analyze_image_relevance
)

# For direct import of the qwq_stream_complete utility
from .clients import qwq_stream_complete 