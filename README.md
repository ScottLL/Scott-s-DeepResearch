# 🔍 Deep Research Agent

A powerful research agent that can perform comprehensive, in-depth investigations on any topic or analyze specific websites. The tool uses advanced web crawling techniques and AI to gather, synthesize, and present information in a structured format.

## Features

- **Two Modes**: Research mode for investigating topics and Crawl mode for analyzing specific websites
- **Clarifying Questions**: The app asks intelligent questions to better understand your research needs
- **Real-time Progress**: View the research process as it happens with live logs
- **Rich Results**: View research results as formatted markdown, HTML, or download for later use
- **Customizable Parameters**: Control the depth and breadth of research
- **Structured Output**: Results are saved in both Markdown and JSON formats

## Requirements

- Python 3.8+
- OpenAI API key
- Required packages (see installation section)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/deep-research-agent.git
cd deep-research-agent
```

2. Install required packages:
```bash
pip install -r requirements.txt

# or Install required packages using the Makefile:
make install
```

3. Create a `.env` file in the project root and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## Usage

### Web Interface (Streamlit)

Run the web interface with:

```bash
streamlit run app.py
# or use the make command
make run
```

This will launch a browser-based interface at `http://localhost:8501` where you can:

#### Research Mode
1. Select "Research Query" mode in the sidebar
2. Enter your research question in the text area
3. Adjust the research parameters in the sidebar (depth, breadth, iterations)
4. Click "Start Research"
5. Answer the clarifying questions (if any)
6. Watch the research process in real-time
7. View and download the results

#### Website Crawl Mode
1. Select "Website Crawl" mode in the sidebar
2. Enter the URL you want to analyze
3. Adjust the crawl parameters in the sidebar (depth, max pages)
4. Click "Start Crawling"
5. Watch the crawling process in real-time
6. View and download the results

### Command Line Interface

For the command line interface, use main.py with appropriate arguments:

#### Research Mode
```bash
python main.py --query "your research question here" --depth 2 --breadth 5 --iterations 3
```

#### Website Crawl Mode
```bash
python main.py --url "https://example.com" --depth 2 --breadth 5
```

### Example Command
```bash
python main.py --query "想调研一下奔驰汽车E级，S级，以及迈巴赫这些所有型号的车车，23-25年的外观，内置，体验上的趋势特点以及变化，想通过的出来的结论用到洗衣机的外观设计上" --depth 3 --breadth 6
```

## Parameters

- `--query` / `-q`: The research question or topic to investigate
- `--url` / `-u`: Starting URL for website crawling (alternative to query)
- `--depth` / `-d`: How many levels deep to crawl from each page (default: 2)
- `--breadth` / `-b`: Number of top results to explore or max pages for website crawl (default: 5)
- `--iterations` / `-i`: Number of research cycles to perform (default: 3, research mode only)

## Tips for Better Results

- Be specific in your research questions
- Provide answers to clarifying questions for more focused research
- Adjust depth and breadth based on your needs:
  - Higher depth explores more links from each page
  - Higher breadth analyzes more search results per query
  - More iterations enable more thorough research

## Output

The tool generates two output files:
- A Markdown file with formatted research findings
- A JSON file containing raw data for further processing

## How It Works

The Deep Research Agent uses a combination of web crawling (via Crawl4AI) and large language models to:
1. Perform initial searches based on your query
2. Extract relevant information from search results
3. Generate follow-up questions to dive deeper
4. Synthesize findings into a comprehensive report

## Troubleshooting

- If the app fails to start, check that you have set the OPENAI_API_KEY properly
- If research seems slow, try reducing depth and breadth parameters
- If you encounter errors, check the console output for more details

## Additional Make Commands
```bash
make run - Run the Streamlit web application
make research - Run the Deep Research Agent from command line
make clean - Clean up cached files and temporary data
make help - Show all available Make commands
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.