import os, sys, argparse, asyncio
# Import modules
from core.crawler import WebCrawler
from analysis import (
    is_ollama_available,
    detect_language,
    # New agent classes 
    TranslationAgent,
    QueryAnalysisAgent,
    InformationNeedsAgent,
    QueryGenerationAgent,
    AnswerGenerationAgent,
    SummarizerAgent,
    AnalysisOrchestrator,
    # For summarization
    summarize_text,
    summarize_pages,
    # Use async versions directly
    async_analyze_query,
    async_need_more_info,
    async_generate_targeted_queries,
    async_answer_question,
    async_suggest_followup_queries
)
# Import tools
from tools import (
    GoogleSearchTool,
    BaiduSearchTool,
    ContentExtractionTool,
    LinkExplorationTool,
    TextSummarizerTool,
    QueryAnalysisTool,
    WebCrawlerTool  # Add the new tool import
)
import reporting
# Import modes
from modes.research_mode import run_research_mode
from modes.crawl_mode import run_crawl_mode

async def ensure_json_serializable(data):
    """
    Recursively ensures all elements in the data structure are JSON serializable
    by resolving any asyncio.Task objects.
    """
    if isinstance(data, asyncio.Task):
        try:
            return await data
        except Exception as e:
            print(f"Error awaiting task: {e}")
            return str(e)  # Return error as string to maintain structure
    elif isinstance(data, dict):
        return {k: await ensure_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [await ensure_json_serializable(item) for item in data]
    elif isinstance(data, set):
        return [await ensure_json_serializable(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(await ensure_json_serializable(item) for item in data)
    else:
        return data

async def main():
    parser = argparse.ArgumentParser(description='AI Web Research Tool')
    parser.add_argument('query', nargs='?', default='', help='The research query or URL to explore')
    parser.add_argument('--mode', '-m', choices=['research', 'crawl'], default='research', 
                      help='Mode: research (default) or crawl a specific site')
    parser.add_argument('--iterations', '-i', type=int, default=3, 
                      help='Maximum research iterations (default: 3)')
    parser.add_argument('--breadth', '-b', type=int, default=3, 
                      help='Search breadth - number of pages per query (default: 3)')
    parser.add_argument('--depth', '-d', type=int, default=2, 
                      help='Search depth or crawl depth (default: 2)')
    parser.add_argument('--max-pages', type=int, default=20, 
                      help='Maximum pages to crawl in crawl mode (default: 20)')
    parser.add_argument('--no-images', action='store_true', 
                      help='Disable image downloads in reports')
    
    args = parser.parse_args()
    
    query = args.query
    
    # Check if no query provided
    if not query:
        query = input("Enter your research query or a URL to crawl: ")
    
    # Detect if query is a URL
    if query.startswith(('http://', 'https://')) and args.mode == 'research':
        print("URL detected. Switching to crawl mode.")
        args.mode = 'crawl'
    
    # Run in appropriate mode
    if args.mode == 'research':
        result = await run_research_mode(query, args.iterations, args.breadth, args.depth)
    else:  # crawl mode
        result = await run_crawl_mode(query, args.max_pages, args.depth)
        
    # Print completion message
    print("\nTask completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
