import os
import streamlit as st
import asyncio
import sys
import markdown
import queue
import time
import builtins
from threading import Thread, Event
import base64
import re
from PIL import Image
import io
from bs4 import BeautifulSoup
import json
import openai
import logging
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager
import streamlit.cli as stcli

# Load environment variables from .env file
load_dotenv()

# Configure logging to reduce noise
logging.basicConfig(level=logging.ERROR)  # Only show ERROR level and above
# Disable specific loggers that are too verbose
for logger_name in ['matplotlib', 'PIL', 'streamlit', 'asyncio']:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Add warning suppression and PyTorch safeguard
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
# Suppress specific Streamlit warnings about missing ScriptRunContext
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
os.environ["PYTORCH_JIT"] = "0"  # Disable PyTorch JIT compilation
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Disable tokenizers parallelism warnings
os.environ["STREAMLIT_DISABLE_WATCHER"] = "true"  # Disable Streamlit's module watcher
os.environ["STREAMLIT_LOG_LEVEL"] = "error"  # Only show error-level logs from Streamlit
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"  # Disable usage statistics

# Define AlwaysAllStdin class
class AlwaysAllStdin:
    def readline(self, *args, **kwargs):
        return "all\n"
    
    def read(self, *args, **kwargs):
        return "all"
        
    def flush(self):
        pass

# Import modules from main.py
from main import run_research_mode, run_crawl_mode

# Define the isolated function at module level for multiprocessing
# This needs to be at the module level for pickle to work correctly
def isolated_crawler_run_mp(url, max_pages, crawl_depth, mp_message_queue, mp_result_queue):
    """Process-isolated function to run the crawler in a separate Python process.
    This MUST be at the module level (not nested) for multiprocessing to work."""
    # This function runs in a completely separate process with its own Python interpreter
    import os
    import sys
    import importlib
    import asyncio
    import io
    
    # Set environment variables for the subprocess
    os.environ["PYTORCH_JIT"] = "0"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    # Custom function to send messages back to the main process
    def send_message(text):
        if text and text.strip():
            mp_message_queue.put(text)
    
    # Replace stdout to capture output
    class CustomStdout:
        def write(self, text):
            if text:
                send_message(text)
            return len(text)
        
        def flush(self):
            pass
    
    # Redirect stdout
    sys.stdout = CustomStdout()
    sys.stderr = CustomStdout()
    
    try:
        send_message(f"Starting crawl of {url} in separate process")
        
        # Dynamically import the crawl module in the subprocess
        # This ensures PyTorch is only loaded in this process
        crawl_mode = importlib.import_module("modes.crawl_mode")
        
        # Create a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the crawler function with raw_only=True to skip analysis
        result = loop.run_until_complete(
            crawl_mode.run_crawl_mode(
                url=url,
                max_pages=max_pages,
                crawl_depth=crawl_depth,
                raw_only=True  # Add this parameter to indicate we only want raw content
            )
        )
        
        # Clean up the loop
        loop.close()
        
        # Send result back to the main process
        mp_result_queue.put(result)
        send_message("Crawl complete. Raw content sent to main process.")
        
    except Exception as e:
        error_msg = f"Process error crawling {url}: {str(e)}"
        send_message(error_msg)
        mp_result_queue.put(f"Error: {str(e)}")

# Add this function to handle converting local images to base64
def convert_md_with_embedded_images(md_content):
    # Regular expression to find image tags in markdown
    img_pattern = r'!\[(.*?)\]\((.*?)\)'
    
    def replace_image_path(match):
        alt_text = match.group(1)
        img_path = match.group(2)
        
        # If it's a URL, keep it as is
        if img_path.startswith('http'):
            return f'![{alt_text}]({img_path})'
        
        # Otherwise try to load the local file
        try:
            # Handle spaces and special characters in the file path
            img_path = img_path.replace('\\', '/')
            
            # First try direct path
            if os.path.exists(img_path):
                with open(img_path, "rb") as img_file:
                    img_bytes = img_file.read()
                    img_format = os.path.splitext(img_path)[1].lstrip('.')
                    if not img_format:
                        img_format = 'png'  # Default format if none detected
                    img_base64 = base64.b64encode(img_bytes).decode()
                    return f'<img src="data:image/{img_format};base64,{img_base64}" alt="{alt_text}" style="max-width:100%;">'
            
            # If direct access fails, return a placeholder
            st.warning(f"Image not found: {img_path}")
            return f'<p><i>Image not found: {img_path}</i></p>'
        except Exception as e:
            st.warning(f"Error loading image {img_path}: {str(e)}")
            return f'<p><i>Image not found: {img_path}</i></p>'
    
    # Replace all image references with base64 encoded versions
    md_content_with_images = re.sub(img_pattern, replace_image_path, md_content)
    return md_content_with_images

# Add this new function to handle markdown rendering safely
def safe_render_markdown(md_content):
    """Generate HTML file for download and display content as plain text"""
    
    try:
        # Generate HTML file for download
        import markdown
        import tempfile
        import os
        
        # Pre-process problematic patterns
        processed_md = md_content
        processed_md = re.sub(r'!\[!', r'![', processed_md)
        processed_md = re.sub(r'!\[;\]', r'![Image]', processed_md)
        
        # Convert markdown to HTML 
        html_content = markdown.markdown(
            processed_md, 
            extensions=['tables', 'nl2br', 'fenced_code', 'codehilite']
        )
        
        # Create HTML document
        full_html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Research Report</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    line-height: 1.6; 
                    max-width: 800px; 
                    margin: 0 auto; 
                    padding: 20px; 
                }}
                img {{ 
                    max-width: 100%; 
                    height: auto; 
                    display: block;
                    margin: 20px auto;
                }}
                h1, h2, h3, h4, h5, h6 {{ 
                    margin-top: 24px; 
                    margin-bottom: 16px; 
                }}
                p {{ margin-bottom: 16px; }}
                .img-caption {{ 
                    font-style: italic; 
                    text-align: center; 
                    margin-top: -15px; 
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>"""
        
        # Save to temp file
        temp_dir = tempfile.gettempdir()
        html_file_path = os.path.join(temp_dir, "report_preview.html")
        
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        
        # DISPLAY SECTION - No markdown rendering at all
        
        # Use plain text for all UI elements
        st.text("--- RESEARCH REPORT PREVIEW ---")
        st.text("Download the HTML version for proper formatting and images:")
        
        # Create download button for the HTML
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_data = f.read()
            st.download_button(
                label="Download Complete HTML Report",
                data=html_data,
                file_name="report_preview.html",
                mime="text/html"
            )
        
        st.text("-------------")
        st.text("CONTENT PREVIEW (PLAIN TEXT VERSION):")
        st.text("-------------")
        
        # Replace markdown formatting with simple text equivalents
        plain_text = re.sub(r'!\[.*?\]\(.*?\)', '[IMAGE]', md_content)  # Replace images
        plain_text = re.sub(r'<[^>]*>', '', plain_text)  # Remove HTML tags
        
        # Limit preview length to prevent performance issues
        max_length = 6000  # About 2-3 pages of text
        if len(plain_text) > max_length:
            preview_text = plain_text[:max_length] + "\n\n[... Content truncated. Download the HTML report for the complete version ...]"
        else:
            preview_text = plain_text
        
        # Display in chunks to avoid rendering issues with very long text
        chunk_size = 2000  # Split into ~2000 character chunks
        for i in range(0, len(preview_text), chunk_size):
            chunk = preview_text[i:i+chunk_size]
            st.text_area(
                label=f"Part {i//chunk_size + 1}", 
                value=chunk,
                height=min(300, len(chunk.split('\n'))*20)
            )
        
        return True
    except Exception as e:
        st.error(f"Error: {str(e)}")
        
        # Ultra-minimal fallback
        st.text_area(label="Raw content:", value=md_content[:5000], height=300)
        if len(md_content) > 5000:
            st.text("[Content truncated due to length]")
        
        return False

# Configure page settings
st.set_page_config(
    page_title="Deep Research Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Check for API key
def check_api_key():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("⚠️ OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        st.info("You can add this to your .env file or set it in your environment.")
        return False
    return True

# Custom CSS
st.markdown("""
<style>
    .stProgress .st-bo {
        background-color: #1c83e1;
    }
    .stTextArea textarea {
        font-family: monospace;
    }
    .result-container {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    .source-link {
        color: #1c83e1;
        text-decoration: none;
    }
    .source-link:hover {
        text-decoration: underline;
    }
    /* Add styles to fix bullet points */
    ul, ol {
        padding-left: 20px;
        margin-bottom: 10px;
    }
    ul li, ol li {
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Create a global message queue for thread-safe communication
message_queue = queue.Queue()

# Initialize session state variables if they don't exist
if 'research_phase' not in st.session_state:
    st.session_state['research_phase'] = 'initial'  # Can be 'initial', 'questions', 'research', or 'crawling'
if 'clarifying_responses' not in st.session_state:
    st.session_state['clarifying_responses'] = {}
if 'query_analysis' not in st.session_state:
    st.session_state['query_analysis'] = None
if 'current_query' not in st.session_state:
    st.session_state['current_query'] = ""
if 'current_url' not in st.session_state:
    st.session_state['current_url'] = ""
if 'all_clarifying_questions' not in st.session_state:
    st.session_state['all_clarifying_questions'] = []
if 'preset_mode' not in st.session_state:
    st.session_state['preset_mode'] = "Standard Research"  # Default preset mode
if 'mode' not in st.session_state:
    st.session_state['mode'] = "Research Query"  # Default mode

# Helper function to run async tasks
def run_async(coro, event):
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Redirect stdout to capture print statements
        original_stdout = sys.stdout
        
        # Custom print function to add to queue instead of updating UI directly
        def custom_print(*args, **kwargs):
            message = " ".join(map(str, args))
            message_queue.put(message)
            
        sys.stdout.write = custom_print
        
        # Run the coroutine
        result = loop.run_until_complete(coro)
        return result
    except Exception as e:
        # Log any errors
        message_queue.put(f"Error in async execution: {str(e)}")
        return None
    finally:
        # Restore stdout
        sys.stdout.write = original_stdout
        # Clean up the loop
        loop.close()
        asyncio.set_event_loop(None)  # Clear the thread's event loop reference
        event.set()  # Signal completion regardless of success or failure

# App title and description
st.title("🔍 Deep Research Agent")
st.markdown("""
This tool helps you perform deep research on any topic or analyze specific websites.
Enter a query or URL below to get started!
""")

# Sidebar with mode selection and parameters
with st.sidebar:
    st.header("Research Settings")
    
    mode = st.radio("Mode", ["Research Query", "Website Crawl"], key="mode")
    
    # Add preset research mode selector
    st.subheader("Research Depth")
    preset_options = ["Quick Overview", "Standard Research", "Deep Dive", "Comprehensive Analysis", "Custom"]
    
    # Use the key parameter to let Streamlit handle the session state directly
    # This prevents the need to click twice
    preset_mode = st.radio(
        "Select a preset research mode",
        preset_options,
        key="preset_mode",  # This directly links to session state
        help="Choose a preset or select 'Custom' to manually set parameters"
    )
    
    # Set parameters based on preset mode
    if preset_mode == "Quick Overview":
        # Shallow and narrow - for quick insights
        preset_depth = 1
        preset_breadth_research = 1
        preset_breadth_crawl = 1
        preset_iterations = 1
        description = "Fast, surface-level research that provides a quick overview of a topic. Best for initial exploration or time-sensitive research."
        time_estimate = "⏱️ Fastest (2-5 minutes)"
    elif preset_mode == "Standard Research":
        # Balanced settings - default
        preset_depth = 2
        preset_breadth_research = 4
        preset_breadth_crawl = 4
        preset_iterations = 3
        description = "Balanced research depth and breadth for most general inquiries. Good for everyday research tasks."
        time_estimate = "⏱️ Average (5-10 minutes)"
    elif preset_mode == "Deep Dive":
        # Deeper with moderate breadth
        preset_depth = 3
        preset_breadth_research = 7
        preset_breadth_crawl = 10
        preset_iterations = 4
        description = "Thorough exploration of a specific topic with deeper analysis. Ideal for academic research or detailed understanding."
        time_estimate = "⏱️ Longer (10-20 minutes)"
    elif preset_mode == "Comprehensive Analysis":
        # Maximum depth and breadth
        preset_depth = 5
        preset_breadth_research = 10
        preset_breadth_crawl = 20
        preset_iterations = 5
        description = "Exhaustive research that explores multiple aspects of a topic in detail. Best for in-depth analysis or literature reviews."
        time_estimate = "⏱️ Longest (20+ minutes)"
    else:  # Custom
        # Use the current slider values or defaults
        preset_depth = 2
        preset_breadth_research = 5
        preset_breadth_crawl = 5
        preset_iterations = 3
        description = "Customize the parameters to your specific research needs."
        time_estimate = "⏱️ Varies based on settings"
    
    st.info(f"**{preset_mode}**: {description}\n\n{time_estimate}")
    
    # Add a visual indicator of the research depth
    col1, col2, col3, col4, col5 = st.columns(5)
    depth_indicators = ["🔍"] * 5
    
    # Highlight the filled dots based on preset_depth
    if preset_mode != "Custom":
        for i in range(preset_depth):
            depth_indicators[i] = "🔎"
            
    with col1:
        st.write(depth_indicators[0])
    with col2:
        st.write(depth_indicators[1])
    with col3:
        st.write(depth_indicators[2])
    with col4:
        st.write(depth_indicators[3])
    with col5:
        st.write(depth_indicators[4])
        
    # Add parameter explanation in an expander
    with st.expander("💡 Understanding research parameters"):
        st.markdown("""
        These parameters control how the AI conducts research:
        
        **Crawl Depth** determines how many links deep the AI will follow from each page:
        - Depth 1: Only analyzes the initial pages
        - Depth 2-3: Follows links from initial pages to get better context
        - Depth 4-5: Explores multiple levels of links for comprehensive coverage
        
        **Search Breadth** (Research mode) determines how many search results to analyze per query:
        - Lower values (1-3): Focus on just top results
        - Medium values (4-7): Balanced coverage of top results
        - Higher values (8-10): Wide coverage of many results
        
        **Max Pages** (Website Crawl mode) limits the total number of pages analyzed from a website:
        - Lower values (1-5): Analyze just a few key pages
        - Medium values (6-10): Moderate coverage of the site
        - Higher values (11-20): Extensive site coverage
        
        **Research Iterations** controls how many cycles of research the AI performs:
        - More iterations = more thorough research but longer processing time
        
        Time estimates are approximate and may vary based on server load and complexity of the topic.
        
        ### Preset Mode Comparison
        
        | Preset | Depth | Breadth (Research) | Max Pages (Crawl) | Iterations | Use Case |
        |--------|-------|-------------------|------------------|------------|----------|
        | Quick Overview | 1 | 1 | 1 | 1 | Initial research, time-sensitive |
        | Standard Research | 2 | 4 | 5 | 3 | General purpose research |
        | Deep Dive | 3 | 7 | 10 | 4 | Academic or thorough topic analysis |
        | Comprehensive | 5 | 10 | 20 | 5 | Exhaustive analysis, literature reviews |
        """)
        
    # Parameters that apply to both modes
    disabled = preset_mode != "Custom"
    depth = st.slider("Crawl Depth", min_value=1, max_value=5, value=preset_depth, 
                     help="How many levels deep to crawl from each page.",
                     disabled=disabled)
    
    # If sliders are disabled, set the values directly
    if disabled:
        depth = preset_depth
    
    # Parameters specific to research mode
    if mode == "Research Query":
        breadth = st.slider("Search Breadth", min_value=1, max_value=10, value=preset_breadth_research, 
                           help="Number of top search results to explore per query.",
                           disabled=disabled)
        iterations = st.slider("Research Iterations", min_value=1, max_value=5, value=preset_iterations,
                             help="Number of research cycles to perform.",
                             disabled=disabled)
        
        # If sliders are disabled, set the values directly
        if disabled:
            breadth = preset_breadth_research
            iterations = preset_iterations
    else:  # Website crawl mode
        breadth = st.slider("Max Pages", min_value=1, max_value=20, value=preset_breadth_crawl,
                           help="Maximum number of pages to crawl from the site.",
                           disabled=disabled)
        
        # If sliders are disabled, set the values directly
        if disabled:
            breadth = preset_breadth_crawl
    
    st.info("💡 Tip: Higher depth and breadth values will produce more comprehensive results but take longer.")

# Main input area - only show if we're in initial phase
if st.session_state['research_phase'] == 'initial':
    if mode == "Research Query":
        query = st.text_area("Enter your research question:", height=100, 
                             placeholder="Example: What are the key differences between electric and hydrogen vehicles?")
        
        def on_start_research():
            if query:  # Only save if query is not empty
                st.session_state['current_query'] = query
                st.session_state['research_phase'] = 'questions'
        
        submit_button = st.button("🔍 Start Research", type="primary", 
                                 disabled=not check_api_key(), 
                                 on_click=on_start_research)
        
        # Display example queries
        with st.expander("Example research queries"):
            st.markdown("""
            - What are the latest advancements in quantum computing?
            - How has climate change affected marine ecosystems in the past 5 years?
            - Compare the economic policies of the current US administration with the previous one
            - What are the benefits and challenges of implementing a four-day work week?
            """)
    else:  # Website crawl mode
        url = st.text_input("Enter website URL:", placeholder="https://example.com")
        
        def on_start_crawling():
            if url and url.startswith(('http://', 'https://')):  # Only save if URL is valid
                st.session_state['current_url'] = url
                st.session_state['research_phase'] = 'crawling'  # Use a specific phase for crawling
        
        submit_button = st.button("🕸️ Start Crawling", type="primary", 
                                 disabled=not check_api_key(),
                                 on_click=on_start_crawling)
        
        # Display example websites
        with st.expander("Example websites to crawl"):
            st.markdown("""
            - https://news.ycombinator.com/
            - https://en.wikipedia.org/wiki/Artificial_intelligence
            - https://www.nasa.gov/missions/
            - https://www.whitehouse.gov/briefing-room/
            """)

        st.info("The crawler will extract and return only the raw text content from the website without generating summaries or analysis. This provides faster results and complete, unprocessed content.")

# Clarifying questions phase
elif st.session_state['research_phase'] == 'questions':
    progress_placeholder = st.empty()
    
    with progress_placeholder.container():
        st.markdown("### 🔄 Analyzing your query...")
        
        # Get the query from session state
        query = st.session_state['current_query']
        
        # If we haven't analyzed the query yet, do it now
        if st.session_state['query_analysis'] is None:
            import sys
            from modes.research_mode import async_analyze_query
            import asyncio
            
            # Run query analysis asynchronously
            query_analysis = asyncio.run(async_analyze_query(query))
            st.session_state['query_analysis'] = query_analysis
            
            # Store the full list of clarifying questions
            all_questions = query_analysis.get("clarifying_questions", [])
            st.session_state['all_clarifying_questions'] = all_questions
        else:
            query_analysis = st.session_state['query_analysis']
            all_questions = st.session_state['all_clarifying_questions']
        
        if all_questions:
            st.markdown("### ❓ Please answer these clarifying questions to improve your results:")
            
            # Create a form
            with st.form(key="clarifying_form"):
                responses = {}
                for i, question in enumerate(all_questions):
                    response = st.text_area(f"Question {i+1}: {question}", 
                                            key=f"q_{i}", 
                                            help="Leave blank to skip")
                    if response:
                        responses[question] = response
                
                # Submit button for the form
                submitted = st.form_submit_button("Continue Research")
                
                if submitted:
                    st.session_state['clarifying_responses'] = responses
                    st.session_state['research_phase'] = 'research'
                    st.rerun()
            
            # Add a back button outside the form
            if st.button("← Back to Query"):
                st.session_state['research_phase'] = 'initial'
                st.session_state['query_analysis'] = None
                st.session_state['clarifying_responses'] = {}
                st.session_state['all_clarifying_questions'] = []
                st.rerun()
        else:
            # No clarifying questions needed, proceed directly to research
            st.write("No clarifying questions needed. Proceeding directly to research...")
            st.session_state['research_phase'] = 'research'
            st.rerun()

# Website crawling phase
elif st.session_state['research_phase'] == 'crawling':
    progress_placeholder = st.empty()
    results_placeholder = st.empty()
    
    with progress_placeholder.container():
        st.markdown("### 🕸️ Crawling website...")
        
        # Get URL from session state
        url = st.session_state.get('current_url', '')
        
        # Display what we're working with
        st.write(f"Crawling website: {url}")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Create a placeholder for terminal-like output
        terminal = st.empty()
        output_lines = []
        
        try:
            # Create a queue for the result
            result_queue = queue.Queue()
            
            # Import multiprocessing for complete isolation
            import multiprocessing as mp
            from multiprocessing import Queue
            
            # Create multiprocessing queues for cross-process communication
            mp_message_queue = mp.Queue()
            mp_result_queue = mp.Queue()
            
            # Create and start the separate process using the module-level function
            crawler_process = mp.Process(
                target=isolated_crawler_run_mp,  # Use the module-level function
                args=(url, breadth, depth, mp_message_queue, mp_result_queue),
                daemon=True
            )
            
            # Start the process
            crawler_process.start()
            
            # Function to transfer messages from the MP queue to our message queue
            def transfer_messages():
                try:
                    while not mp_message_queue.empty():
                        msg = mp_message_queue.get_nowait()
                        message_queue.put(msg)
                except:
                    pass
            
            # Update progress while waiting for completion
            progress_value = 10
            md_content = None
            process_timeout = 600  # 10 minute timeout
            start_time = time.time()
            process_alive = True
            
            while process_alive and (time.time() - start_time) < process_timeout:
                # Check if process is still running
                process_alive = crawler_process.is_alive()
                
                # Update progress
                progress_value = min(95, progress_value + 0.5)
                status_text.text(f"Crawling website: {url} - This may take several minutes...")
                progress_bar.progress(int(progress_value))
                
                # Transfer messages from MP queue to our message queue
                transfer_messages()
                
                # Display messages
                while not message_queue.empty():
                    try:
                        message = message_queue.get_nowait()
                        output_lines.append(message)
                        terminal.code("\n".join(output_lines), language="bash")
                    except queue.Empty:
                        break
                
                # Check for results without blocking
                try:
                    if not mp_result_queue.empty():
                        # We have a result, break the loop
                        break
                except:
                    pass
                    
                time.sleep(0.1)
            
            # One final check for messages
            transfer_messages()
            while not message_queue.empty():
                try:
                    message = message_queue.get_nowait()
                    output_lines.append(message)
                except queue.Empty:
                    break
            
            # Update terminal one last time
            if output_lines:
                terminal.code("\n".join(output_lines), language="bash")
            
            # Try to get the result from the queue
            try:
                if not mp_result_queue.empty():
                    md_content = mp_result_queue.get_nowait()
                    output_lines.append(f"Retrieved result from process")
                else:
                    output_lines.append(f"No result received from process")
            except Exception as e:
                output_lines.append(f"Error retrieving result: {str(e)}")
            
            # Find the result files based on the output lines
            md_filename = None
            json_filename = None
            for line in output_lines:
                if ".md" in line and "saved to" in line:
                    parts = line.split()
                    for part in parts:
                        if part.endswith(".md"):
                            md_filename = part
                            md_path = part
                if ".json" in line and "saved to" in line:
                    parts = line.split()
                    for part in parts:
                        if part.endswith(".json"):
                            json_filename = part
                            json_path = part
            
            # If we couldn't extract from logs, create a default name
            if not md_filename:
                # Create a default base name using the domain
                import re
                domain = re.sub(r'^https?://', '', url)
                domain = domain.split('/')[0]  # Get just the domain part
                base_name = f"crawl_{domain.replace('.', '_')}"
                
                md_path = f"{base_name}.md"
                json_path = f"{base_name}.json"
                
                # If we have md_content but no file, save it to a file
                if md_content and isinstance(md_content, str):
                    try:
                        with open(md_path, "w", encoding="utf-8") as f:
                            f.write(md_content)
                        output_lines.append(f"Saved content to {md_path}")
                    except Exception as e:
                        output_lines.append(f"Error saving content to file: {str(e)}")
            
            # Terminate the process if it's still running
            if crawler_process.is_alive():
                output_lines.append("Terminating crawler process...")
                crawler_process.terminate()
                crawler_process.join(timeout=5)
                if crawler_process.is_alive():
                    crawler_process.kill()  # Force kill if terminate didn't work
            
            # Clear the progress placeholder completely
            progress_placeholder.empty()
            
            # Display the results at the top of the page
            if 'md_path' in locals() and os.path.exists(md_path):
                # Read the markdown file directly
                with open(md_path, "r", encoding="utf-8") as f:
                    md_content = f.read()
                
                # Display a title
                st.title("🕸️ Website Crawl Results")
                
                # Display results similar to research mode
                with results_placeholder.container():
                    st.markdown("## 📊 Raw Content Results")
                    
                    # Create tabs for different views
                    tab1, tab2, tab3, tab4 = st.tabs(["Content", "Raw Markdown", "Download", "HTML Preview"])
                    
                    with tab1:
                        try:
                            # Convert markdown with embedded images
                            md_content_with_images = convert_md_with_embedded_images(md_content)
                            
                            # Pre-process problematic patterns
                            md_content_with_images = re.sub(r'!\[!', r'![', md_content_with_images)
                            md_content_with_images = re.sub(r'!\[;\]', r'![Image]', md_content_with_images)
                            caption_pattern = r'\*(Image from \[Source \d+\].*?)\*'
                            md_content_with_images = re.sub(caption_pattern, r'<div class="img-caption">\1</div>', md_content_with_images)
                            
                            # Split content into manageable chunks at paragraph breaks
                            max_chunk_size = 10000
                            chunks = []
                            current_chunk = ""
                            
                            # Split at paragraph markers
                            paragraphs = md_content_with_images.split("\n\n")
                            
                            for para in paragraphs:
                                if len(current_chunk) + len(para) > max_chunk_size:
                                    chunks.append(current_chunk)
                                    current_chunk = para + "\n\n"
                                else:
                                    current_chunk += para + "\n\n"
                                    
                            # Add the last chunk if it has content
                            if current_chunk:
                                chunks.append(current_chunk)
                            
                            # Display each chunk separately
                            for i, chunk in enumerate(chunks):
                                # Convert to HTML
                                chunk_html = markdown.markdown(
                                    chunk,
                                    extensions=['markdown.extensions.fenced_code', 'markdown.extensions.tables']
                                )
                                
                                # Create a container for each chunk
                                with st.container():
                                    st.markdown(chunk_html, unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Error rendering markdown: {str(e)}")
                            st.text_area("Content (couldn't render properly):", md_content, height=500)
                    
                    with tab2:
                        st.text_area("Markdown Content", md_content, height=500)
                    
                    with tab3:
                        st.download_button(
                            label="Download Markdown Report",
                            data=md_content,
                            file_name=md_path,
                            mime="text/markdown",
                        )
                        if os.path.exists(json_path):
                            with open(json_path, 'r', encoding='utf-8') as f:
                                json_content = f.read()
                            st.download_button(
                                label="Download JSON Data",
                                data=json_content,
                                file_name=json_path,
                                mime="application/json",
                            )
                    
                    with tab4:
                        # Generate HTML preview
                        safe_render_markdown(md_content)
            else:
                # If we can't find the file, display a message
                st.warning("Could not find the generated report. Check the terminal output for details.")
            
            # Reset session state
            st.session_state['research_phase'] = 'initial'
            st.session_state['current_url'] = ""
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            # Reset session state on error
            st.session_state['research_phase'] = 'initial'

# Research phase
elif st.session_state['research_phase'] == 'research':
    progress_placeholder = st.empty()
    results_placeholder = st.empty()
    
    with progress_placeholder.container():
        st.markdown("### 🔄 Processing...")
        
        # Get query from session state
        query = st.session_state['current_query']
        
        # Get query analysis and questions from session state
        query_analysis = st.session_state.get('query_analysis', None)
        clarifying_responses = st.session_state.get('clarifying_responses', {})
        
        # Display what we're working with
        st.write(f"Researching: {query}")
        st.write(f"Using {len(clarifying_responses)} clarifying responses")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Create a placeholder for terminal-like output
        terminal = st.empty()
        output_lines = []
        
        try:
            # Create event to signal completion
            done_event = Event()
            
            # Run research mode in a separate thread
            status_text.text(f"Researching: {query}")
            progress_bar.progress(10)
            
            # Store original functions and modules
            original_stdin = sys.stdin
            original_input = builtins.input
            original_print = builtins.print
            
            # Import needed modules
            from modes.research_mode import run_research_mode
            import analysis
            
            # Create a wrapped version of run_research_mode that skips the initial analysis
            async def wrapped_run_research_mode(query, iterations, breadth, depth):
                # Import all needed modules
                crawler = sys.modules['core.crawler'].WebCrawler()
                
                # Skip directly to the research part, bypassing query analysis and clarifying questions
                pages_all = []             # collected pages data
                visited_urls = set()       # track visited URLs
                followup_queries = []      # store follow-up queries
                search_queries = []        # track all search queries
                current_answer = ""        # current accumulated answer
                all_summaries = []         # all summaries collected
                
                # Get language from existing analysis or detect it
                query_language = query_analysis.get('language', 'en') if query_analysis else analysis.detect_language(query)
                message_queue.put(f"\n** Using previously detected language: {query_language} **")
                
                # Get the enhanced query from existing analysis
                enhanced_query = query_analysis.get('improved_query', query) or query
                
                # Make sure enhanced_query is a string and not a list, dict, or other complex type
                if not isinstance(enhanced_query, str) or len(enhanced_query.strip()) == 0:
                    enhanced_query = query
                
                # Additional validation to ensure we don't have numbered lists or questions
                if re.match(r'^\d+\.|\?|\-\s+|\•\s+', enhanced_query.strip()):
                    enhanced_query = query
                
                message_queue.put("\n=== Using Previous Query Analysis ===")
                message_queue.put("Components of your query:")
                components = query_analysis.get("components", [])
                for component in components:
                    message_queue.put(f"• {component}")
                
                # Skip clarifying questions - use the responses we already have
                message_queue.put("\nUsing previously collected responses:")
                for q, a in clarifying_responses.items():
                    message_queue.put(f"- Q: {q}")
                    message_queue.put(f"  A: {a}")
                
                message_queue.put(f"\nContinuing with query: {enhanced_query}")
                message_queue.put("======================\n")
                
                # Generate targeted search queries
                message_queue.put("\nBreaking down the query into focused search components...")
                initial_targeted_queries = await analysis.async_suggest_followup_queries(
                    enhanced_query, [], max_queries=6, target_language=query_language
                )
                
                if initial_targeted_queries:
                    message_queue.put("\n→ Research will focus on these specific aspects:")
                    for idx, subquery in enumerate(initial_targeted_queries, 1):
                        message_queue.put(f"  {idx}. {subquery}")
                    message_queue.put("\nExploring all aspects in parallel...")
                else:
                    initial_targeted_queries = [enhanced_query]
                    message_queue.put(f"\nUsing enhanced query: \"{enhanced_query}\"")
                message_queue.put("======================\n")
                
                # Continue with the rest of the research_mode code...
                iteration_count = 0
                current_queries = initial_targeted_queries
                
                while iteration_count < iterations:
                    message_queue.put(f"\n** Research Iteration {iteration_count+1} **")
                    
                    # Use updated wording to match parallel nature of the process
                    message_queue.put(f"\nExploring {len(current_queries)} queries in parallel:")
                    for i, q in enumerate(current_queries, 1):
                        message_queue.put(f"{i}. {q}")
                    
                    # Create a semaphore to limit concurrent browser instances
                    browser_semaphore = asyncio.Semaphore(3)  # Allow 3 concurrent browser instances - adjust if needed
                    
                    async def process_query(query_text):
                        """Process a single research query with proper error handling"""
                        async with browser_semaphore:  # Limit concurrent browser instances
                            try:
                                message_queue.put(f"\nStarting exploration: \"{query_text}\"")
                                # Initialize the crawler tool
                                crawler_tool = sys.modules['tools'].WebCrawlerTool()
                                result = await crawler_tool.run(
                                    query_text,
                                    mode="explore",
                                    depth=depth,
                                    breadth=max(1, breadth // len(current_queries)),
                                    visited_urls=visited_urls
                                )
                                message_queue.put(f"Completed exploration: \"{query_text}\"")
                                return result.get("pages", []) if result.get("success", False) else []
                            except Exception as e:
                                message_queue.put(f"Error exploring \"{query_text}\": {e}")
                                return []
                    
                    # Create tasks for parallel processing
                    query_tasks = [process_query(query_text) for query_text in current_queries]
                    
                    # Execute all tasks in parallel and gather results
                    query_results = await asyncio.gather(*query_tasks, return_exceptions=True)
                    
                    # Combine results, handling any exceptions
                    current_pages = []
                    for i, result in enumerate(query_results):
                        if isinstance(result, Exception):
                            message_queue.put(f"Error processing query '{current_queries[i]}': {result}")
                            continue
                        current_pages.extend(result)
                    
                    # Process pages to get summaries in smaller batches to avoid token limits
                    current_summaries = []
                    
                    # Process pages in smaller batches to avoid hitting token limits
                    MAX_CHUNK_SIZE = 5  # Process 5 pages at a time
                    
                    for i in range(0, len(current_pages), MAX_CHUNK_SIZE):
                        chunk = current_pages[i:i+MAX_CHUNK_SIZE]
                        message_queue.put(f"\nProcessing batch {i//MAX_CHUNK_SIZE + 1}/{(len(current_pages)+MAX_CHUNK_SIZE-1)//MAX_CHUNK_SIZE} ({len(chunk)} pages)")
                        
                        # Process each page in the current batch
                        for page in chunk:
                            if page.get('content'):
                                try:
                                    # Truncate extremely long content to avoid token limits
                                    content = page['content']
                                    if len(content) > 100000:  # Roughly 25K tokens max
                                        message_queue.put(f"Truncating very long content ({len(content)} chars)")
                                        content = content[:100000] + "... [content truncated due to length]"
                                        page['content'] = content
                                    
                                    summary = analysis.summarize_text(
                                        content, 
                                        context=query, 
                                        target_language=query_language
                                    )
                                    if summary:
                                        current_summaries.append(summary)
                                        all_summaries.append(summary)
                                        pages_all.append(page)
                                except Exception as e:
                                    message_queue.put(f"Error summarizing page: {e}")
                    
                    # Check if we have enough information - use async directly
                    # Only use the most relevant summaries to avoid token limits
                    MAX_SUMMARIES_FOR_CHECK = 50
                    if len(all_summaries) > MAX_SUMMARIES_FOR_CHECK:
                        message_queue.put(f"\nUsing {MAX_SUMMARIES_FOR_CHECK} most relevant summaries (out of {len(all_summaries)}) for information check")
                        # Sort summaries by relevance if possible, or use the most recent ones
                        check_summaries = all_summaries[-MAX_SUMMARIES_FOR_CHECK:]
                    else:
                        check_summaries = all_summaries
                    
                    more_info_check = await analysis.async_need_more_info(query, check_summaries)
                    
                    # Increment iteration counter
                    iteration_count += 1
                    
                    # Check conditions to exit loop
                    if not more_info_check["need_more"]:
                        message_queue.put("Research complete: Sufficient information gathered.")
                        break
                    
                    if iteration_count >= iterations:
                        message_queue.put(f"Reached maximum iterations ({iterations}). Proceeding with available information.")
                        break
                    
                    if not more_info_check["missing_aspects"]:
                        message_queue.put("No specific missing aspects identified. Proceeding with available information.")
                        break
                    
                    # We need more information - display missing aspects
                    message_queue.put("\nNeed more information. Missing aspects:")
                    for aspect in more_info_check["missing_aspects"]:
                        message_queue.put(f"- {aspect}")
                    
                    # Generate targeted queries based on missing aspects
                    targeted_queries = await analysis.async_generate_targeted_queries(
                        query, 
                        all_summaries,
                        more_info_check["missing_aspects"],
                        max_queries=3
                    )
                    
                    if not targeted_queries:
                        message_queue.put("Could not generate additional research queries. Ending research.")
                        break
                    
                    message_queue.put("\nGenerating targeted research queries for next iteration:")
                    for i, q in enumerate(targeted_queries, 1):
                        message_queue.put(f"{i}. {q}")
                        
                    # Update current_queries for the next iteration
                    current_queries = targeted_queries
                    # Store for reporting
                    followup_queries.extend(targeted_queries)
                
                # Now that we have collected all the information, generate and refine the final answer
                message_queue.put("\n** Generating final answer based on collected information **")
                
                # Initial answer generation - use async directly with summary limiting
                # Only use a subset of summaries to avoid token limits
                MAX_SUMMARIES_FOR_ANSWER = 40
                if len(all_summaries) > MAX_SUMMARIES_FOR_ANSWER:
                    message_queue.put(f"\nUsing {MAX_SUMMARIES_FOR_ANSWER} most relevant summaries (out of {len(all_summaries)}) for answer generation")
                    # Sort by relevance if possible, or use the most recent ones
                    answer_summaries = all_summaries[-MAX_SUMMARIES_FOR_ANSWER:]
                else:
                    answer_summaries = all_summaries
                
                final_answer = await analysis.async_answer_question(
                    query, 
                    answer_summaries,  # Use the limited set of summaries
                    model="qwq-32b",
                    target_language=query_language
                )
                
                # Refine the answer a few times to improve quality
                refinement_iterations = min(3, iteration_count)
                message_queue.put(f"Planning {refinement_iterations} total iterations (including initial generation)")
                
                if refinement_iterations <= 1:
                    message_queue.put("No additional refinement needed - using initial answer")
                else:
                    # Multiple refinement iterations
                    for i in range(refinement_iterations-1):
                        try:
                            # Get the previous answer text
                            if isinstance(final_answer, dict):
                                previous_answer = final_answer.get('answer_text', '')
                            else:
                                previous_answer = str(final_answer)
                            
                            message_queue.put(f"\n*** Refinement Iteration {i+1}/{refinement_iterations-1} ***")
                            
                            refinement_prompt = f"""
                            Based on the information collected, please refine and improve this answer:
                            
                            PREVIOUS ANSWER:
                            {previous_answer}
                            
                            Please make the answer more comprehensive, accurate, and well-structured.
                            Focus on adding any missing important information from the research materials,
                            correcting any inaccuracies, and ensuring the answer directly addresses all aspects
                            of the original query: "{query}"
                            """
                            
                            message_queue.put(f"Generating refinement {i+1}...")
                            # Use async version directly
                            refined_answer = await analysis.async_answer_question(
                                refinement_prompt, 
                                all_summaries, 
                                model="qwq-32b"
                            )
                            
                            # Update the final answer with the refined version
                            final_answer = refined_answer
                            message_queue.put(f"Refinement iteration {i+1} complete.")
                            
                            # Debug output to confirm refinement is happening
                            if isinstance(final_answer, dict):
                                answer_length = len(final_answer.get('answer_text', ''))
                            else:
                                answer_length = len(str(final_answer))
                            message_queue.put(f"Current answer length: {answer_length} characters")
                            
                        except Exception as e:
                            message_queue.put(f"Error during answer refinement: {e}")
                            break
                
                message_queue.put("\nFinal answer refinement complete.")
                
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
                
                # Fix the module import error by directly importing the function
                # Instead of: serializable_data = await sys.modules['modes.research_mode'].ensure_json_serializable(data)
                from modes.research_mode import ensure_json_serializable
                serializable_data = await ensure_json_serializable(data)
                
                # Alternative approach if the above fails:
                if 'serializable_data' not in locals():
                    # Fallback implementation of ensure_json_serializable
                    async def local_ensure_json_serializable(data):
                        if isinstance(data, asyncio.Task):
                            try:
                                return await data
                            except Exception as e:
                                message_queue.put(f"Error awaiting task: {e}")
                                return str(e)
                        elif isinstance(data, dict):
                            return {k: await local_ensure_json_serializable(v) for k, v in data.items()}
                        elif isinstance(data, list):
                            return [await local_ensure_json_serializable(item) for item in data]
                        elif isinstance(data, set):
                            return [await local_ensure_json_serializable(item) for item in data]
                        elif isinstance(data, tuple):
                            return tuple(await local_ensure_json_serializable(item) for item in data)
                        else:
                            return data
                            
                    serializable_data = await local_ensure_json_serializable(data)
                
                # Fix reporting module import
                import reporting
                
                # Save the data
                reporting.save_json(serializable_data, json_path)
                
                # Generate markdown report
                if isinstance(final_answer, dict):
                    answer_content = final_answer.get('answer_text', '')
                else:
                    answer_content = str(final_answer)
                    
                md_content = sys.modules['reporting'].generate_markdown_content(
                    query=query, 
                    url="",  # Add empty URL for research mode
                    pages=pages_all, 
                    final_answer={"answer_text": answer_content}, 
                    target_language=query_language
                )
                sys.modules['reporting'].save_markdown(md_content, md_path)
                
                message_queue.put(f"\nResearch complete. Results saved to {md_path} and {json_path}")
                return md_content
                
            # Custom print function that sends to our message queue
            def custom_print(*args, **kwargs):
                message = " ".join(map(str, args))
                message_queue.put(message)
            
            # Install our hooks
            sys.stdin = AlwaysAllStdin()
            builtins.input = lambda *args: "all"  # Simplified input hook
            builtins.print = custom_print
            
            # Start our wrapped research in a thread
            thread = Thread(
                target=run_async, 
                args=(wrapped_run_research_mode(query, iterations, breadth, depth), done_event)
            )
            
            thread.start()
            
            # Update progress while waiting for completion
            progress_value = 10
            md_content = None  # Store the markdown content
            
            while not done_event.is_set():
                # Update progress
                progress_value = min(95, progress_value + 0.5)
                status_text.text(f"Researching: {query} - This may take several minutes...")
                progress_bar.progress(int(progress_value))
                
                # Check for new messages
                while not message_queue.empty():
                    try:
                        message = message_queue.get_nowait()
                        output_lines.append(message)
                        terminal.code("\n".join(output_lines), language="bash")
                    except queue.Empty:
                        break
                
                time.sleep(0.1)
            
            # Final message check
            while not message_queue.empty():
                try:
                    message = message_queue.get_nowait()
                    output_lines.append(message)
                except queue.Empty:
                    break
            
            # Update terminal one last time
            if output_lines:
                terminal.code("\n".join(output_lines), language="bash")
            
            # Wait for thread to fully terminate
            thread.join()
            
            # Restore original functions
            sys.stdin = original_stdin
            builtins.input = original_input
            builtins.print = original_print
            
            # Find the result files based on the output lines
            md_filename = None
            json_filename = None
            for line in output_lines:
                if ".md" in line and "saved to" in line:
                    parts = line.split()
                    for part in parts:
                        if part.endswith(".md"):
                            md_filename = part
                            md_path = part
                if ".json" in line and "saved to" in line:
                    parts = line.split()
                    for part in parts:
                        if part.endswith(".json"):
                            json_filename = part
                            json_path = part
            
            # If we couldn't extract from logs, create a default name
            if not md_filename:
                # Create a default base name
                base_name = "research_results"
                
                try:
                    # Get mode safely
                    current_mode = locals().get('mode', None)
                    
                    if current_mode == "Research Query":
                        # Use query if it exists
                        if 'query' in locals():
                            query_value = locals().get('query', '')
                            safe_query = "".join(c for c in query_value[:50] if c.isalnum() or c in " _-")
                            base_name = f"results_{safe_query.strip().replace(' ','_')}"
                    elif current_mode == "Website Crawl":
                        # Use url if it exists
                        if 'url' in locals():
                            url_value = locals().get('url', '')
                            domain = url_value.split('//')[-1].split('/')[0]
                            base_name = f"crawl_{domain}"
                except:
                    # If anything fails, just use the default
                    pass
                
                md_path = f"{base_name}.md"
                json_path = f"{base_name}.json"
            
            # Clear the progress placeholder completely
            progress_placeholder.empty()
            
            # Display the results at the top of the page
            if 'md_path' in locals() and os.path.exists(md_path):
                # Read the markdown file directly
                with open(md_path, "r", encoding="utf-8") as f:
                    md_content = f.read()
                
                # Display a title
                st.title("🔍 Research Results")
                
                # Display results
                with results_placeholder.container():
                    st.markdown("## 📊 Results")
                    
                    # Create tabs for different views
                    tab1, tab2, tab3, tab4 = st.tabs(["Report", "Raw Markdown", "Download", "HTML Preview"])
                    
                    with tab1:
                        try:
                            # Convert markdown with embedded images
                            md_content_with_images = convert_md_with_embedded_images(md_content)
                            
                            # Pre-process problematic patterns
                            md_content_with_images = re.sub(r'!\[!', r'![', md_content_with_images)
                            md_content_with_images = re.sub(r'!\[;\]', r'![Image]', md_content_with_images)
                            caption_pattern = r'\*(Image from \[Source \d+\].*?)\*'
                            md_content_with_images = re.sub(caption_pattern, r'<div class="img-caption">\1</div>', md_content_with_images)
                            
                            # Instead of using st.markdown directly, split content into smaller chunks
                            # to avoid the ElementNode error
                            max_chunk_size = 10000  # Try a smaller chunk size
                            
                            # Split content into manageable chunks at paragraph breaks
                            chunks = []
                            current_chunk = ""
                            
                            # Split at paragraph markers
                            paragraphs = md_content_with_images.split("\n\n")
                            
                            for para in paragraphs:
                                if len(current_chunk) + len(para) > max_chunk_size:
                                    chunks.append(current_chunk)
                                    current_chunk = para + "\n\n"
                                else:
                                    current_chunk += para + "\n\n"
                                    
                            # Add the last chunk if it has content
                            if current_chunk:
                                chunks.append(current_chunk)
                            
                            # Display each chunk separately
                            for i, chunk in enumerate(chunks):
                                # Convert to HTML
                                chunk_html = markdown.markdown(
                                    chunk,
                                    extensions=['markdown.extensions.fenced_code', 'markdown.extensions.tables']
                                )
                                
                                # Create a container for each chunk
                                with st.container():
                                    st.markdown(chunk_html, unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Error rendering markdown: {str(e)}")
                            st.text_area("Content (couldn't render properly):", md_content, height=500)
                    
                    with tab2:
                        st.text_area("Markdown Content", md_content, height=500)
                    
                    with tab3:
                        st.download_button(
                            label="Download Markdown Report",
                            data=md_content,
                            file_name=md_path,
                            mime="text/markdown",
                        )
                        if os.path.exists(json_path):
                            with open(json_path, 'r', encoding='utf-8') as f:
                                json_content = f.read()
                            st.download_button(
                                label="Download JSON Data",
                                data=json_content,
                                file_name=json_path,
                                mime="application/json",
                            )
                    
                    with tab4:
                        # Generate HTML file for download
                        try:
                            import tempfile
                            
                            # Convert markdown to HTML 
                            html_content = markdown.markdown(
                                md_content, 
                                extensions=['tables', 'nl2br', 'fenced_code', 'codehilite']
                            )
                            
                            # Create HTML document
                            full_html = f"""<!DOCTYPE html>
                            <html>
                            <head>
                                <meta charset="UTF-8">
                                <title>Research Report</title>
                                <style>
                                    body {{ 
                                        font-family: Arial, sans-serif; 
                                        line-height: 1.6; 
                                        max-width: 800px; 
                                        margin: 0 auto; 
                                        padding: 20px; 
                                    }}
                                    img {{ 
                                        max-width: 100%; 
                                        height: auto; 
                                        display: block;
                                        margin: 20px auto;
                                    }}
                                    h1, h2, h3, h4, h5, h6 {{ 
                                        margin-top: 24px; 
                                        margin-bottom: 16px; 
                                    }}
                                    p {{ margin-bottom: 16px; }}
                                    .img-caption {{ 
                                        font-style: italic; 
                                        text-align: center; 
                                        margin-top: -15px; 
                                        margin-bottom: 20px;
                                    }}
                                </style>
                            </head>
                            <body>
                                {html_content}
                            </body>
                            </html>"""
                            
                            # Save to temp file
                            temp_dir = tempfile.gettempdir()
                            html_file_path = os.path.join(temp_dir, "report_preview.html")
                            
                            with open(html_file_path, "w", encoding="utf-8") as f:
                                f.write(full_html)
                            
                            # Create download button for the HTML
                            with open(html_file_path, "r", encoding="utf-8") as f:
                                html_data = f.read()
                                st.download_button(
                                    label="Download Complete HTML Report",
                                    data=html_data,
                                    file_name="report_preview.html",
                                    mime="text/html"
                                )
                                
                            st.info("Download the HTML report for the best viewing experience with proper formatting and images.")
                        except Exception as e:
                            st.error(f"Error generating HTML: {str(e)}")
            else:
                # If we can't find the file, display a message
                st.warning("Could not find the generated report. Check the terminal output for details.")
            
            # Reset session state
            st.session_state['research_phase'] = 'initial'
            st.session_state['query_analysis'] = None
            st.session_state['current_query'] = ""
            st.session_state['clarifying_responses'] = {}
            
        except Exception as e:
            # Restore original functions in case of error
            if 'original_stdin' in locals():
                sys.stdin = original_stdin
            if 'original_input' in locals():
                builtins.input = original_input
            if 'original_print' in locals():
                builtins.print = original_print
                
            st.error(f"An error occurred: {str(e)}")
            # Reset session state on error
            st.session_state['research_phase'] = 'initial'
            st.session_state['query_analysis'] = None

# Add a reset button that's always visible
if st.session_state['research_phase'] != 'initial':
    if st.button("Reset"):
        st.session_state['research_phase'] = 'initial'
        st.session_state['query_analysis'] = None
        st.session_state['current_query'] = ""
        st.session_state['clarifying_responses'] = {}
        st.session_state['all_clarifying_questions'] = []
        st.session_state['preset_mode'] = "Standard Research"  # Default preset mode
        st.session_state['mode'] = "Research Query"  # Default mode
        st.rerun()

# Footer
st.markdown("---")
st.markdown("Built with Streamlit and Crawl4AI 🚀")

# Install playwright browsers on first run
if 'playwright_installed' not in st.session_state:
    import subprocess
    subprocess.run(['playwright', 'install'])
    subprocess.run(['playwright', 'install-deps'])
    st.session_state.playwright_installed = True

# Initialize playwright in a proper way
@st.cache_resource
def get_playwright():
    return sync_playwright().start()

# Get the browser instance
try:
    playwright = get_playwright()
    browser = playwright.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage']
    )
except Exception as e:
    st.error(f"Failed to initialize Playwright: {str(e)}")

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        
    async def start(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    @asynccontextmanager
    async def get_context(self):
        try:
            context = await self.browser.new_context()
            yield context
        finally:
            await context.close()

# Initialize the browser manager in Streamlit's session state
if 'browser_manager' not in st.session_state:
    # Install playwright on first run
    import subprocess
    subprocess.run(['playwright', 'install'], check=True)
    subprocess.run(['playwright', 'install-deps'], check=True)
    
    # Create browser manager
    st.session_state.browser_manager = BrowserManager()
    # Initialize the browser
    asyncio.run(st.session_state.browser_manager.start())

# Ensure cleanup on session end
def cleanup():
    if 'browser_manager' in st.session_state:
        asyncio.run(st.session_state.browser_manager.stop())
        del st.session_state.browser_manager

# Register cleanup
import atexit
atexit.register(cleanup)

async def crawl_url(url):
    browser_manager = st.session_state.browser_manager
    async with browser_manager.get_context() as context:
        page = await context.new_page()
        try:
            await page.goto(url, timeout=30000)
            content = await page.content()
            return content
        except Exception as e:
            st.error(f"Error crawling {url}: {str(e)}")
            return None
        finally:
            await page.close()

# Use it in your Streamlit app
if st.button("Crawl"):
    url = st.text_input("Enter URL")
    if url:
        content = asyncio.run(crawl_url(url))
        if content:
            st.write("Crawling successful!")

if __name__ == "__main__":
    try:
        sys.exit(stcli.main())
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        sys.exit(1)