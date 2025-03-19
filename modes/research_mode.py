import asyncio
import reporting
from core.crawler import WebCrawler
from analysis import (
    detect_language,
    summarize_text,
    async_analyze_query,
    async_need_more_info,
    async_generate_targeted_queries,
    async_answer_question,
    async_suggest_followup_queries
)
from tools import (
    QueryAnalysisTool,
    TextSummarizerTool,
    WebCrawlerTool,
    ImageRelevanceTool
)
import re

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

async def run_research_mode(query: str, iterations: int, breadth: int, depth: int = 2):
    """Run the deep research process for a given query."""
    crawler = WebCrawler()
    
    # Initialize tools directly for more advanced operations
    query_analysis_tool = QueryAnalysisTool()
    text_summarizer_tool = TextSummarizerTool()
    
    # Use the QueryAnalysisTool to analyze the query
    query_analysis_result = await query_analysis_tool.run(query)
    query_analysis = query_analysis_result if query_analysis_result.get("success", False) else {
        "components": [],
        "clarifying_questions": [],
        "improved_query": query,
        "language": "en"
    }
    
    pages_all = []          # collected pages data (with content and summaries)
    visited_urls = set()    # track visited URLs to avoid duplicates
    followup_queries = []   # store follow-up queries (for logging/reporting)
    search_queries = []     # track all search queries used
    current_answer = ""     # current accumulated answer
    all_summaries = []      # all summaries collected
    current_query = query   # start with the original query
    
    # Detect the language of the query at the beginning
    query_language = detect_language(query)
    print(f"\n** Query language detected: {query_language} **")
    
    # Analyze and improve the initial query
    print("\n** Analyzing query to improve search effectiveness **")
    
    # Use the async function directly and await it
    query_analysis = await async_analyze_query(query)
    
    # Ensure query_analysis is a valid dictionary
    if not isinstance(query_analysis, dict):
        query_analysis = {
            "components": [],
            "clarifying_questions": [],
            "improved_query": query,
            "language": "en"
        }
    
    # Validate all required fields exist and are of the correct type
    components = query_analysis.get("components", [])
    if not isinstance(components, list):
        components = []
    
    clarifying_questions = query_analysis.get("clarifying_questions", [])
    if not isinstance(clarifying_questions, list):
        clarifying_questions = []
    
    enhanced_query = query_analysis.get("improved_query", query)
    if not isinstance(enhanced_query, str) or not enhanced_query.strip():
        enhanced_query = query
    
    # Ensure we don't have list markers or question format in the enhanced query
    if re.search(r'^(\d+\.|\-|\•|\*)\s+', enhanced_query) or enhanced_query.count('?') > 1:
        enhanced_query = query
    
    # Update query_analysis with validated values
    query_analysis = {
        "components": components,
        "clarifying_questions": clarifying_questions,
        "improved_query": enhanced_query,
        "language": query_analysis.get("language", "en")
    }
    
    # Display query analysis
    print("\n=== Query Analysis ===")
    print("Components of your query:")
    components = query_analysis.get("components", [])
    for component in components:
        print(f"• {component}")

    # Directly use the clarifying questions from query analysis
    print("\nClarifying questions to consider:")
    clarifying_questions = query_analysis.get("clarifying_questions", [])
    clarifying_responses = {}

    if clarifying_questions:
        import sys
        
        # Clear any potential input buffer
        try:
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getch()
        except ImportError:
            # Not on Windows, try another approach
            try:
                import termios, tty, fcntl, os
                fd = sys.stdin.fileno()
                flags_save = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, flags_save | os.O_NONBLOCK)
                try:
                    while sys.stdin.read(1):
                        pass
                except:
                    pass
                finally:
                    fcntl.fcntl(fd, fcntl.F_SETFL, flags_save)
            except:
                pass
        
        # Show ALL clarifying questions at once
        for i, question in enumerate(clarifying_questions, 1):
            try:
                # Print the question with more visible formatting
                print(f"\n{i}. {question}")
                print("=" * 50)
                print("Your response (press Enter to skip):")
                print("> ", end="")
                sys.stdout.flush()
                
                # Read directly from stdin
                response = sys.stdin.readline().strip()
                
                # Process response
                if response:
                    clarifying_responses[question] = response
                    print(f"Response recorded: {response}")
                else:
                    print("Skipped")
                
            except Exception as e:
                print(f"Error collecting input: {e}")
                break

        print(f"\nResponses collected: {len(clarifying_responses)}")
    else:
        print("No clarifying questions available.")

    # Clear separation
    print("======================\n")
    
    # Use the proper improved query, not the remaining clarifying questions
    # Make sure to extract the improved query correctly
    enhanced_query = query_analysis.get('improved_query', query) or query
    
    # Validate that enhanced_query is a proper query and not clarifying questions
    if enhanced_query.startswith(("1.", "2.", "3.", "4.", "5.", "6.","7.")):
        # Fallback to original query if enhanced_query appears to be questions
        enhanced_query = query
    
    if clarifying_responses:
        print("\nUser provided additional information:")
        for q, a in clarifying_responses.items():
            print(f"- Q: {q}")
            print(f"  A: {a}")
        print(f"\nContinuing with query: {enhanced_query}")
    else:
        print(f"\nNo additional information provided. Using: {enhanced_query}")
    
    print("======================\n")
    
    # Generate targeted search queries from the enhanced query
    print("\nBreaking down the query into focused search components...")
    # Use async version directly and await it
    initial_targeted_queries = await async_suggest_followup_queries(enhanced_query, [], max_queries=6, target_language=query_language)

    if initial_targeted_queries:
        print("\n→ Research will focus on these specific aspects:")
        for idx, subquery in enumerate(initial_targeted_queries, 1):
            print(f"  {idx}. {subquery}")
        
        print("\nExploring all aspects in parallel...")
    else:
        initial_targeted_queries = [enhanced_query]
        print(f"\nUsing enhanced query: \"{enhanced_query}\"")
    print("======================\n")

    # Start research process
    # Use a counter to keep track of iterations without a fixed loop
    iteration_count = 0
    current_queries = initial_targeted_queries  # Start with initial targeted queries
    
    # Continue research until we have enough information or reach maximum iterations
    while iteration_count < iterations:
        print(f"\n** Research Iteration {iteration_count+1} **")
        
        # Use current queries for this iteration
        print(f"\nExploring {len(current_queries)} queries in parallel:")
        for i, q in enumerate(current_queries, 1):
            print(f"{i}. {q}")
        
        # Create a semaphore to limit concurrent browser instances
        browser_semaphore = asyncio.Semaphore(6)  # Allow 6 concurrent browser instances
        
        async def process_query(query_text):
            """Process a single research query with proper error handling"""
            async with browser_semaphore:  # Limit concurrent browser instances
                try:
                    print(f"\nStarting exploration: \"{query_text}\"")
                    # Initialize the crawler tool
                    crawler_tool = WebCrawlerTool()
                    result = await crawler_tool.run(
                        query_text,
                        mode="explore",
                        depth=depth,
                        breadth=max(1, breadth // len(current_queries)),
                        visited_urls=visited_urls
                    )
                    print(f"Completed exploration: \"{query_text}\"")
                    return result.get("pages", []) if result.get("success", False) else []
                except Exception as e:
                    print(f"Error exploring \"{query_text}\": {e}")
                    return []
        
        # Create tasks for parallel processing
        query_tasks = [process_query(query_text) for query_text in current_queries]
        
        # Execute all tasks in parallel and gather results
        query_results = await asyncio.gather(*query_tasks, return_exceptions=True)
        
        # Combine results, handling any exceptions
        current_pages = []
        for i, result in enumerate(query_results):
            if isinstance(result, Exception):
                print(f"Error processing query '{current_queries[i]}': {result}")
                continue
            current_pages.extend(result)
        
        # Process pages to get summaries in smaller batches to avoid token limits
        # Add chunking for the summarization process
        current_summaries = []
        
        # Process pages in smaller batches to avoid hitting token limits
        MAX_CHUNK_SIZE = 5  # Process 5 pages at a time
        
        for i in range(0, len(current_pages), MAX_CHUNK_SIZE):
            chunk = current_pages[i:i+MAX_CHUNK_SIZE]
            print(f"\nProcessing batch {i//MAX_CHUNK_SIZE + 1}/{(len(current_pages)+MAX_CHUNK_SIZE-1)//MAX_CHUNK_SIZE} ({len(chunk)} pages)")
            
            # Process each page in the current batch
            for page in chunk:
                if page.get('content'):
                    try:
                        # Truncate extremely long content to avoid token limits
                        content = page['content']
                        if len(content) > 100000:  # Roughly 25K tokens max
                            print(f"Truncating very long content ({len(content)} chars)")
                            content = content[:100000] + "... [content truncated due to length]"
                            page['content'] = content
                        
                        summary = summarize_text(
                            content, 
                            context=query, 
                            target_language=query_language
                        )
                        if summary:
                            current_summaries.append(summary)
                            all_summaries.append(summary)
                            pages_all.append(page)
                    except Exception as e:
                        print(f"Error summarizing page: {e}")
        
        # Check if we have enough information - use async directly
        # Only use the most relevant summaries to avoid token limits
        MAX_SUMMARIES_FOR_CHECK = 50
        if len(all_summaries) > MAX_SUMMARIES_FOR_CHECK:
            print(f"\nUsing {MAX_SUMMARIES_FOR_CHECK} most relevant summaries (out of {len(all_summaries)}) for information check")
            # Sort summaries by relevance if possible, or use the most recent ones
            check_summaries = all_summaries[-MAX_SUMMARIES_FOR_CHECK:]
        else:
            check_summaries = all_summaries
        
        more_info_check = await async_need_more_info(query, check_summaries)
        
        # Increment iteration counter
        iteration_count += 1
        
        # If we have enough information, exit the loop
        if not more_info_check["need_more"]:
            print("Research complete: Sufficient information gathered.")
            break
            
        # If we've reached max iterations, exit the loop
        if iteration_count >= iterations:
            print(f"Reached maximum iterations ({iterations}). Proceeding with available information.")
            break
            
        # If there are no missing aspects despite need_more being True, exit the loop
        if not more_info_check["missing_aspects"]:
            print("No specific missing aspects identified. Proceeding with available information.")
            break
            
        # We need more information - display missing aspects
        print("\nNeed more information. Missing aspects:")
        for aspect in more_info_check["missing_aspects"]:
            print(f"- {aspect}")
        
        # Generate targeted queries based on missing aspects - use async directly
        targeted_queries = await async_generate_targeted_queries(
            query, 
            all_summaries,
            more_info_check["missing_aspects"],
            max_queries=3
        )
        
        if not targeted_queries:
            print("Could not generate additional research queries. Ending research.")
            break
        
        print("\nGenerating targeted research queries for next iteration:")
        for i, q in enumerate(targeted_queries, 1):
            print(f"{i}. {q}")
            
        # Update current_queries for the next iteration
        current_queries = targeted_queries
        # Store for reporting
        followup_queries.extend(targeted_queries)
    
    # Now that we have collected all the information, generate and refine the final answer
    print("\n** Generating final answer based on collected information **")
    
    # Initial answer generation - use async directly with summary limiting
    # Only use a subset of summaries to avoid token limits
    MAX_SUMMARIES_FOR_ANSWER = 40
    if len(all_summaries) > MAX_SUMMARIES_FOR_ANSWER:
        print(f"\nUsing {MAX_SUMMARIES_FOR_ANSWER} most relevant summaries (out of {len(all_summaries)}) for answer generation")
        # Sort by relevance if possible, or use the most recent ones
        answer_summaries = all_summaries[-MAX_SUMMARIES_FOR_ANSWER:]
    else:
        answer_summaries = all_summaries
    
    final_answer = await async_answer_question(
        query, 
        answer_summaries,  # Use the limited set of summaries
        model="qwq-32b",
        target_language=query_language
    )
    print("Initial answer generated. Starting refinement process...")
    
    # Refine the answer a few times to improve quality
    refinement_iterations = min(3, iteration_count)  # Use at most 3 refinement iterations
    print(f"Planning {refinement_iterations} total iterations (including initial generation)")

    if refinement_iterations <= 1:
        print("No additional refinement needed - using initial answer")
    else:
        # Multiple refinement iterations
        for i in range(refinement_iterations-1):
            try:
                # Get the previous answer text
                if isinstance(final_answer, dict):
                    previous_answer = final_answer.get('answer_text', '')
                else:
                    previous_answer = str(final_answer)
                    
                print(f"\n*** Refinement Iteration {i+1}/{refinement_iterations-1} ***")
                
                refinement_prompt = f"""
                Based on the information collected, please refine and improve this answer:
                
                PREVIOUS ANSWER:
                {previous_answer}
                
                Please make the answer more comprehensive, accurate, and well-structured.
                Focus on adding any missing important information from the research materials,
                correcting any inaccuracies, and ensuring the answer directly addresses all aspects
                of the original query: "{query}"
                """
                
                print(f"Generating refinement {i+1}...")
                # Use async version directly
                refined_answer = await async_answer_question(
                    refinement_prompt, 
                    all_summaries, 
                    model="qwq-32b"
                )
                
                # Update the final answer with the refined version
                final_answer = refined_answer
                print(f"Refinement iteration {i+1} complete.")
                
                # Debug output to confirm refinement is happening
                if isinstance(final_answer, dict):
                    answer_length = len(final_answer.get('answer_text', ''))
                else:
                    answer_length = len(str(final_answer))
                print(f"Current answer length: {answer_length} characters")
                
            except Exception as e:
                print(f"Error during answer refinement: {e}")
                break

    print("\nFinal answer refinement complete.")

    # Ensure we properly close the initial crawler
    await crawler.close()

    # Save results
    base_name = "research_results"
    if query:
        safe_query = "".join(c for c in query[:50] if c.isalnum() or c in " _-")
        base_name = f"results_{safe_query.strip().replace(' ','_')}" or base_name
    json_path = base_name + ".json"
    md_path = base_name + ".md"
    
    # Before saving, ensure all data is JSON serializable
    data = {
        "query": query,
        "enhanced_query": enhanced_query,
        "components": components,
        "pages": pages_all,
        "summaries": all_summaries,
        "followup_queries": followup_queries,
        "answer": final_answer
    }
    
    # Ensure all elements are JSON serializable
    serializable_data = await ensure_json_serializable(data)
    reporting.save_json(serializable_data, json_path)
    
    # Generate markdown report
    if isinstance(final_answer, dict):
        answer_content = final_answer.get('answer_text', '')
    else:
        answer_content = str(final_answer)
        
    md_content = reporting.generate_markdown_content(
        query=query, 
        url="",  # Add empty URL for research mode
        pages=pages_all, 
        final_answer={"answer_text": answer_content}, 
        target_language=query_language
    )
    reporting.save_markdown(md_content, md_path)
    
    print(f"\nResearch complete. Results saved to {md_path} and {json_path}")
    return md_content 

async def process_images_for_relevance(image_urls, topic):
    image_tool = ImageRelevanceTool()
    result = await image_tool.run(
        urls=image_urls,
        topic=topic,
        threshold=60,  # Min score to consider relevant
        max_concurrent=6,  # Process 6 images in parallel
        top_k=5  # Return top 5 relevant images
    )
    
    if result["success"]:
        relevant_images = result["relevant_images"]
        print(f"Found {len(relevant_images)} relevant images out of {result['total_processed']}")
        return relevant_images
    else:
        print(f"Error processing images: {result.get('error')}")
        return [] 