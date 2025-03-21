// DOM Elements
const modeButtons = document.querySelectorAll('.mode-btn');
const researchInput = document.querySelector('.research-input');
const crawlInput = document.querySelector('.crawl-input');
const startResearchBtn = document.getElementById('startResearch');
const startCrawlBtn = document.getElementById('startCrawl');
const progressSection = document.querySelector('.progress-section');
const progressFill = document.querySelector('.progress-fill');
const progressText = document.querySelector('.progress-text');
const terminalOutput = document.querySelector('.terminal-output');
const resultsSection = document.querySelector('.results-section');
const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');
const presetMode = document.getElementById('presetMode');
const depthSlider = document.getElementById('depth');
const breadthSlider = document.getElementById('breadth');
const iterationsSlider = document.getElementById('iterations');
const maxPagesSlider = document.getElementById('maxPages');
const sidebar = document.querySelector('.sidebar');
const mainContent = document.querySelector('.main-content');

// State Management
let currentMode = 'research';
let currentProgress = 0;
let researchResults = null;
let currentPhase = 'initial'; // 'initial', 'questions', 'research'
let queryAnalysis = null;
let clarifyingQuestions = [];
let clarifyingResponses = {};
let isMobile = window.innerWidth <= 768;

// Event Listeners

// Mode Selection
modeButtons.forEach(button => {
    button.addEventListener('click', () => {
        const mode = button.dataset.mode;
        setMode(mode);
    });
});

// Preset Mode Change
presetMode.addEventListener('change', () => {
    updateParametersFromPreset(presetMode.value);
});

// Slider Value Updates
[depthSlider, breadthSlider, iterationsSlider, maxPagesSlider].forEach(slider => {
    if (slider) {
        slider.addEventListener('input', (e) => {
            const valueDisplay = e.target.nextElementSibling;
            valueDisplay.textContent = e.target.value;
            updateSliderRangeDisplay(e.target);
        });
    }
});

// Tab Switching
tabButtons.forEach(button => {
    button.addEventListener('click', () => {
        const tab = button.dataset.tab;
        switchTab(tab);
    });
});

// Start Research
startResearchBtn.addEventListener('click', async () => {
    const query = document.getElementById('researchQuery').value.trim();
    if (!query) {
        showError('Please enter a research query');
        return;
    }
    await startResearch(query);
});

// Start Crawl
startCrawlBtn.addEventListener('click', async () => {
    const url = document.getElementById('crawlUrl').value.trim();
    if (!url) {
        showError('Please enter a URL');
        return;
    }
    if (!isValidUrl(url)) {
        showError('Please enter a valid URL');
        return;
    }
    await startCrawl(url);
});

// Window resize
window.addEventListener('resize', () => {
    checkMobileView();
});

// Functions

function checkMobileView() {
    const wasMobile = isMobile;
    isMobile = window.innerWidth <= 768;
    
    // If transitioning between mobile and desktop
    if (wasMobile !== isMobile) {
        adjustLayoutForMobile();
    }
}

function adjustLayoutForMobile() {
    if (isMobile) {
        // Mobile layout adjustments
        if (!document.querySelector('.sidebar-toggle')) {
            addMobileToggle();
        }
    } else {
        // Desktop layout adjustments
        const toggle = document.querySelector('.sidebar-toggle');
        if (toggle) {
            toggle.remove();
        }
        
        // Reset sidebar display when returning to desktop
        sidebar.style.display = '';
        mainContent.style.marginLeft = '280px';
    }
}

function addMobileToggle() {
    const toggle = document.createElement('button');
    toggle.className = 'sidebar-toggle';
    toggle.innerHTML = '<i class="fas fa-bars"></i>';
    toggle.addEventListener('click', toggleMobileSidebar);
    
    const header = document.querySelector('header');
    if (header) {
        header.insertBefore(toggle, header.firstChild);
    }
}

function toggleMobileSidebar() {
    const overlay = document.querySelector('.sidebar-overlay');
    
    if (sidebar.classList.contains('open')) {
        // Close sidebar
        sidebar.classList.remove('open');
        sidebar.style.transform = 'translateX(-100%)';
        overlay.classList.remove('active');
        document.body.style.overflow = 'auto';
    } else {
        // Open sidebar
        sidebar.classList.add('open');
        sidebar.style.transform = 'translateX(0)';
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function setMode(mode) {
    currentMode = mode;
    
    // Update mode buttons
    modeButtons.forEach(button => {
        button.classList.toggle('active', button.dataset.mode === mode);
    });
    
    // Update input sections
    researchInput.style.display = mode === 'research' ? 'block' : 'none';
    crawlInput.style.display = mode === 'crawl' ? 'block' : 'none';
    
    // Update parameter visibility
    document.querySelectorAll('.research-only').forEach(el => {
        el.style.display = mode === 'research' ? 'block' : 'none';
    });
    document.querySelectorAll('.crawl-only').forEach(el => {
        el.style.display = mode === 'crawl' ? 'block' : 'none';
    });
}

function updateParametersFromPreset(preset) {
    const presets = {
        quick: { depth: 1, breadth: 1, iterations: 1 },
        standard: { depth: 2, breadth: 4, iterations: 3 },
        deep: { depth: 3, breadth: 7, iterations: 4 },
        comprehensive: { depth: 5, breadth: 10, iterations: 5 }
    };
    
    if (preset === 'custom') {
        // Enable all sliders
        [depthSlider, breadthSlider, iterationsSlider, maxPagesSlider].forEach(slider => {
            if (slider) slider.disabled = false;
        });
        return;
    }
    
    const values = presets[preset];
    if (!values) return;
    
    // Update sliders
    depthSlider.value = values.depth;
    depthSlider.nextElementSibling.textContent = values.depth;
    
    if (currentMode === 'research') {
        breadthSlider.value = values.breadth;
        breadthSlider.nextElementSibling.textContent = values.breadth;
        iterationsSlider.value = values.iterations;
        iterationsSlider.nextElementSibling.textContent = values.iterations;
    } else {
        maxPagesSlider.value = values.breadth;
        maxPagesSlider.nextElementSibling.textContent = values.breadth;
    }
    
    // Disable sliders for non-custom presets
    [depthSlider, breadthSlider, iterationsSlider, maxPagesSlider].forEach(slider => {
        if (slider) slider.disabled = true;
    });
}

function switchTab(tab) {
    // Update tab buttons
    tabButtons.forEach(button => {
        button.classList.toggle('active', button.dataset.tab === tab);
    });
    
    // Update tab contents - first hide all
    tabContents.forEach(content => {
        content.style.display = 'none';
        content.classList.remove('active');
    });
    
    // Then show the active one
    const activeContent = document.getElementById(`${tab}-content`);
    if (activeContent) {
        activeContent.style.display = 'block';
        activeContent.classList.add('active');
    }
    
    // Update content based on tab
    if (researchResults) {
        updateTabContent(tab);
    }
}

function updateTabContent(tab) {
    const content = document.getElementById(`${tab}-content`);
    
    if (!content || !researchResults) return;
    
    switch (tab) {
        case 'report':
            // Process HTML to fix image paths before setting the content
            const processedHtml = processHtmlContent(researchResults.html || '<p>No HTML content available</p>');
            content.innerHTML = processedHtml;
            break;
        case 'markdown':
            // Create a styled pre element for better display of markdown
            const markdownContent = researchResults.markdown || 'No markdown content available';
            
            // Process the markdown to fix image paths if needed
            const processedMarkdown = processMarkdownImages(markdownContent);
            
            content.innerHTML = `
                <pre class="markdown-display">${processedMarkdown}</pre>
            `;
            break;
        case 'download':
            // Create download buttons for available content
            let downloadHTML = '<div class="download-buttons">';
            
            if (researchResults.markdown) {
                downloadHTML += `
                    <button onclick="downloadFile('markdown')" class="action-btn">
                        <i class="fas fa-download"></i> Download Markdown
                    </button>
                `;
            }
            
            if (researchResults.json && Object.keys(researchResults.json).length > 0) {
                downloadHTML += `
                    <button onclick="downloadFile('json')" class="action-btn">
                        <i class="fas fa-download"></i> Download JSON
                    </button>
                `;
            }
            
            downloadHTML += '</div>';
            content.innerHTML = downloadHTML;
            break;
        case 'preview':
            const previewHtml = processHtmlContent(researchResults.html || '<p>No HTML content available</p>');
            content.innerHTML = previewHtml;
            break;
    }
    
    // Ensure content is visible
    content.style.display = 'block';
    
    // Scroll to the top of the content
    content.scrollTop = 0;
}

// Helper function to check if an image is a data URL
function isDataUrl(url) {
    return url && url.startsWith('data:image/');
}

// Function to process markdown image paths
function processMarkdownImages(markdown) {
    // No need to modify image paths as they are now directly embedded as base64
    // Just return the markdown as is
    return markdown;
}

// Function to process HTML content
function processHtmlContent(html) {
    if (!html) return '<p>No content available</p>';
    
    // Create a DOM parser to process the HTML
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    
    // Find all image elements
    const images = doc.querySelectorAll('img');
    images.forEach(img => {
        const src = img.getAttribute('src');
        if (src && !isDataUrl(src)) {
            // Set error handling for non-data URL images
            img.setAttribute('onerror', "this.onerror=null; this.src='data:image/png;base64,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'; this.alt='Image not available';");
        }
    });
    
    // Return the processed HTML
    return doc.body.innerHTML;
}

async function startResearch(query) {
    try {
        // Show progress section
        progressSection.style.display = 'block';
        resultsSection.style.display = 'none';
        terminalOutput.innerHTML = '';
        currentProgress = 0;
        updateProgress();
        
        // Reset state for a new research session
        currentPhase = 'initial';
        queryAnalysis = null;
        clarifyingQuestions = [];
        clarifyingResponses = {};
        
        // Update UI to show we're analyzing the query
        appendToTerminal("Analyzing your query...");
        
        try {
            // Connect to WebSocket
            const ws = new WebSocket(`ws://${window.location.host}/ws/research`);
            
            // Set a connection timeout
            const connectionTimeout = setTimeout(() => {
                if (ws.readyState !== WebSocket.OPEN) {
                    ws.close();
                    throw new Error("Connection timeout - using fallback mode");
                }
            }, 3000);
            
            ws.onopen = () => {
                clearTimeout(connectionTimeout);
                console.log("WebSocket connection opened");
                
                // Send the initial query for analysis
                ws.send(JSON.stringify({
                    action: 'analyze_query',
                    query: query
                }));
            };
            
            ws.onmessage = (event) => {
                console.log("Received message:", event.data);
                const data = JSON.parse(event.data);
                
                // Handle different message types
                switch (data.type) {
                    case 'clarifying_questions':
                        handleClarifyingQuestions(data, query, ws);
                        break;
                        
                    case 'progress':
                    case 'message':
                    case 'complete':
                    case 'error':
                        handleWebSocketMessage(data);
                        break;
                }
            };
            
            ws.onerror = (error) => {
                console.error("WebSocket error:", error);
                clearTimeout(connectionTimeout);
                throw new Error("WebSocket error - using fallback mode");
            };
            
            ws.onclose = () => {
                console.log('WebSocket connection closed');
            };
        } catch (wsError) {
            console.warn("WebSocket connection failed, using fallback mode:", wsError);
            appendToTerminal("⚠️ Server connection failed. Using fallback simulation mode.");
            simulateResearchProgress(query);
        }
        
    } catch (error) {
        console.error("Error in startResearch:", error);
        showError('Failed to start research: ' + error.message);
    }
}

async function startCrawl(url) {
    try {
        // Show progress section
        progressSection.style.display = 'block';
        resultsSection.style.display = 'none';
        terminalOutput.innerHTML = '';
        currentProgress = 0;
        updateProgress();
        
        // Log initial message
        appendToTerminal(`Starting crawl of ${url}`);
        
        // Prepare parameters
        const params = {
            url,
            depth: parseInt(depthSlider.value),
            max_pages: parseInt(maxPagesSlider.value)
        };
        
        console.log("Crawler parameters:", params);
        
        try {
            // Start WebSocket connection for real-time updates
            const ws = new WebSocket(`ws://${window.location.host}/ws/crawl`);
            
            // Set a connection timeout
            const connectionTimeout = setTimeout(() => {
                if (ws.readyState !== WebSocket.OPEN) {
                    ws.close();
                    throw new Error("Connection timeout - using fallback mode");
                }
            }, 3000);
            
            ws.onopen = () => {
                clearTimeout(connectionTimeout);
                console.log("WebSocket connection opened, sending parameters:", params);
                appendToTerminal("Connection established. Starting web crawler...");
                // Send initial request AFTER connection is open
                ws.send(JSON.stringify(params));
            };
            
            ws.onmessage = (event) => {
                console.log("Received crawler message:", event.data);
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
            
            ws.onerror = (error) => {
                console.error("WebSocket error:", error);
                clearTimeout(connectionTimeout);
                throw new Error("WebSocket error - using fallback mode");
            };
            
            ws.onclose = () => {
                console.log('WebSocket connection closed');
            };
        } catch (wsError) {
            console.warn("WebSocket connection failed, using fallback mode:", wsError);
            appendToTerminal("⚠️ Server connection failed. Using fallback simulation mode.");
            simulateCrawlProgress(url);
        }
        
    } catch (error) {
        console.error("Error in startCrawl:", error);
        showError('Failed to start crawling: ' + error.message);
    }
}

function updateProgress() {
    // Make sure progress fill element exists
    if (!progressFill) return;
    
    progressFill.style.width = `${currentProgress}%`;
    progressText.textContent = `Processing... ${currentProgress}%`;
}

function appendToTerminal(message) {
    const line = document.createElement('div');
    line.textContent = message;
    terminalOutput.appendChild(line);
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
}

function handleWebSocketMessage(data) {
    console.log("Processing WebSocket message:", data);
    switch (data.type) {
        case 'progress':
            currentProgress = data.progress;
            updateProgress();
            break;
        case 'message':
            appendToTerminal(data.message);
            break;
        case 'complete':
            console.log("Received COMPLETE message with results:", data.results);
            handleResearchComplete(data.results);
            break;
        case 'error':
            showError(data.error);
            break;
    }
}

function handleResearchComplete(results) {
    console.log("handleResearchComplete called with results:", results);
    researchResults = results;
    progressSection.style.display = 'none';
    resultsSection.style.display = 'block';
    
    // Make sure tabs are properly displayed
    document.querySelectorAll('.tabs-container').forEach(container => {
        container.style.display = 'flex';
    });
    
    // Update the results header based on current mode
    document.querySelector('.results-header h2').textContent = 
        currentMode === 'research' ? 'Research Results' : 'Website Crawl Results';
    
    // Add a message to the terminal indicating completion
    appendToTerminal("✅ Processing complete! Results are ready to view.");
    
    // If source file is included, log it for debugging
    if (results.source_file) {
        appendToTerminal(`Report loaded from: ${results.source_file}`);
    }
    
    // Update all tab contents
    ['report', 'markdown', 'download', 'preview'].forEach(tab => {
        updateTabContent(tab);
    });
    
    // Select the report tab by default
    const reportTab = document.querySelector('[data-tab="report"]');
    if (reportTab) {
        reportTab.click();
    }
}

function downloadFile(type) {
    if (!researchResults) return;
    
    const content = type === 'markdown' ? researchResults.markdown : JSON.stringify(researchResults.json, null, 2);
    const blob = new Blob([content], { type: type === 'markdown' ? 'text/markdown' : 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `research_results.${type}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    errorDiv.style.backgroundColor = '#e74c3c';
    errorDiv.style.color = 'white';
    errorDiv.style.padding = '1rem';
    errorDiv.style.borderRadius = '8px';
    errorDiv.style.marginBottom = '1rem';
    errorDiv.style.textAlign = 'center';
    
    mainContent.insertBefore(errorDiv, mainContent.firstChild);
    
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

function isValidUrl(url) {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
}

// Add a new function to handle clarifying questions
function handleClarifyingQuestions(data, query, ws) {
    // Save the query analysis and questions
    queryAnalysis = data.query_analysis;
    clarifyingQuestions = data.questions;
    
    if (clarifyingQuestions && clarifyingQuestions.length > 0) {
        // Clear the terminal output
        terminalOutput.innerHTML = '';
        
        // Create a form to collect responses
        let questionsHTML = `
            <div class="clarifying-questions">
                <h3>Please answer these questions:</h3>
                <form id="clarifyingQuestionsForm">
        `;
        
        // Add each question
        clarifyingQuestions.forEach((question, index) => {
            questionsHTML += `
                <div class="question-group">
                    <label for="q_${index}">${question}</label>
                    <textarea id="q_${index}" class="question-response" 
                              placeholder="Your answer..."></textarea>
                </div>
            `;
        });
        
        // Add submit button
        questionsHTML += `
                <button type="submit" class="action-btn">
                    <i class="fas fa-paper-plane"></i> Continue
                </button>
                </form>
            </div>
        `;
        
        // Display the questions
        terminalOutput.innerHTML = questionsHTML;
        
        // Add submit event handler
        document.getElementById('clarifyingQuestionsForm').addEventListener('submit', (e) => {
            e.preventDefault();
            
            // Collect responses
            clarifyingResponses = {};
            clarifyingQuestions.forEach((question, index) => {
                const response = document.getElementById(`q_${index}`).value.trim();
                if (response) {
                    clarifyingResponses[question] = response;
                }
            });
            
            // Clear the form
            terminalOutput.innerHTML = '';
            appendToTerminal("Starting research with your responses...");
            
            // Send the research request with responses
            ws.send(JSON.stringify({
                action: 'start_research',
                query: query,
                query_analysis: queryAnalysis,
                clarifying_responses: clarifyingResponses,
                depth: parseInt(depthSlider.value),
                breadth: parseInt(breadthSlider.value),
                iterations: parseInt(iterationsSlider.value)
            }));
        });
    } else {
        // No questions needed, proceed directly to research
        appendToTerminal("No clarifying questions needed. Proceeding directly to research...");
        
        // Send the research request without waiting for responses
        ws.send(JSON.stringify({
            action: 'start_research',
            query: query,
            query_analysis: queryAnalysis,
            clarifying_responses: {},
            depth: parseInt(depthSlider.value),
            breadth: parseInt(breadthSlider.value),
            iterations: parseInt(iterationsSlider.value)
        }));
    }
}

// Add some CSS styles for the clarifying questions form
document.head.insertAdjacentHTML('beforeend', `
<style>
.clarifying-questions {
    background-color: #f0f8ff;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 20px;
    color: #2c3e50;
}

.clarifying-questions h3 {
    margin-bottom: 15px;
    color: #2c3e50;
    font-size: 1.1rem;
}

.question-group {
    margin-bottom: 2px;
    border-bottom: 1px solid rgba(0,0,0,0.05);
    padding-bottom: 2px;
}

.question-group:last-child {
    border-bottom: none;
}

.question-group label {
    display: block;
    margin-bottom: 1px;
    font-weight: 600;
    color: #2c3e50;
}

.question-response {
    width: 100%;
    min-height: 60px;
    padding: 8px;
    border: 1px solid #bbd6f8;
    border-radius: 4px;
    font-family: inherit;
    resize: vertical;
    background-color: white;
    color: #333;
}

.question-response:focus {
    border-color: #3498db;
    outline: none;
    box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
}

.clarifying-questions .action-btn {
    margin-top: 3px;
}
</style>
`);

// Add some CSS styles for the markdown display
document.head.insertAdjacentHTML('beforeend', `
<style>
.markdown-display {
    background-color: #f8f9fa;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 15px;
    white-space: pre-wrap;
    font-family: 'Courier New', monospace;
    font-size: 14px;
    line-height: 1.5;
    max-height: 600px;
    overflow-y: auto;
    color: #333;
}

.results-header h2 {
    margin-bottom: 15px;
}

.tab-content {
    padding: 20px;
    display: none;
}

.tab-content.active {
    display: block;
}

.tabs-container {
    display: flex;
    border-bottom: 1px solid #ddd;
    margin-bottom: 10px;
}

.tab-btn {
    padding: 10px 15px;
    cursor: pointer;
    border: 1px solid transparent;
    border-bottom: none;
    margin-right: 5px;
}

.tab-btn.active {
    border-color: #ddd;
    border-radius: 5px 5px 0 0;
    background-color: #fff;
    position: relative;
}

.tab-btn.active::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    right: 0;
    height: 2px;
    background-color: white;
}

.download-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}

.download-buttons .action-btn {
    padding: 8px 12px;
    border-radius: 4px;
    background-color: #007bff;
    color: white;
    border: none;
    cursor: pointer;
}
</style>
`);

// Add styles for mobile toggle
document.head.insertAdjacentHTML('beforeend', `
<style>
.sidebar-toggle {
    display: none;
    background: none;
    border: none;
    font-size: 1.5rem;
    color: #2c3e50;
    cursor: pointer;
    position: absolute;
    left: 1rem;
    top: 1rem;
    z-index: 101;
}

@media (max-width: 768px) {
    .sidebar-toggle {
        display: block;
    }
    
    header {
        position: relative;
        padding-top: 1rem;
    }
}
</style>
`);

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Set initial mode
    setMode('research');
    
    // Update parameter displays
    [depthSlider, breadthSlider, iterationsSlider, maxPagesSlider].forEach(slider => {
        if (slider) {
            updateSliderRangeDisplay(slider);
        }
    });
    
    // Add mobile toggle for small screens
    const sidebarToggle = document.createElement('button');
    sidebarToggle.className = 'sidebar-toggle';
    sidebarToggle.innerHTML = '<i class="fas fa-bars"></i>';
    sidebarToggle.addEventListener('click', toggleMobileSidebar);
    document.body.appendChild(sidebarToggle);
    
    // Create overlay element
    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    overlay.addEventListener('click', toggleMobileSidebar);
    document.body.appendChild(overlay);
    
    // Set up initial sidebar state based on screen size
    if (window.innerWidth <= 768) {
        sidebar.style.transform = 'translateX(-100%)';
    } else {
        sidebar.style.transform = 'translateX(0)';
    }
    
    // Handle window resize
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768) {
            sidebar.style.transform = 'translateX(0)';
            document.querySelector('.sidebar-overlay').classList.remove('active');
            document.body.style.overflow = 'hidden';
        } else if (window.innerWidth <= 768 && !sidebar.classList.contains('open')) {
            sidebar.style.transform = 'translateX(-100%)';
        }
    });
});

// Function to update slider display with min-max range
function updateSliderRangeDisplay(slider) {
    const min = slider.min;
    const max = slider.max;
    const valueDisplay = slider.nextElementSibling;
    
    // Show the current value with min-max range
    valueDisplay.innerHTML = `<span class="current-value">${slider.value}</span> <span class="range-display">(${min}-${max})</span>`;
}

// Fallback simulation functions
function simulateResearchProgress(query) {
    let progress = 0;
    const interval = setInterval(() => {
        progress += 5;
        currentProgress = progress;
        updateProgress();
        
        if (progress % 20 === 0) {
            appendToTerminal(`Processing research for: "${query}"... ${progress}% complete`);
        }
        
        if (progress >= 100) {
            clearInterval(interval);
            setTimeout(() => {
                // Create demo results
                const demoResults = {
                    html: `<h1>Research Results for "${query}"</h1><p>This is a simulated result for demonstration purposes.</p><p>Note: Using fallback mode as the server is not available.</p>`,
                    markdown: `# Research Results for "${query}"\nThis is a simulated result for demonstration purposes.\n\n> Note: Using fallback mode as the server is not available.`,
                    json: { query, results: "Simulated results (fallback mode)" }
                };
                handleResearchComplete(demoResults);
            }, 500);
        }
    }, 200);
}

function simulateCrawlProgress(url) {
    let progress = 0;
    const interval = setInterval(() => {
        progress += 5;
        currentProgress = progress;
        updateProgress();
        
        if (progress % 15 === 0) {
            appendToTerminal(`Crawling ${url}... ${progress}% complete`);
        }
        
        if (progress >= 100) {
            clearInterval(interval);
            setTimeout(() => {
                // Create demo results
                const demoResults = {
                    html: `<h1>Crawl Results for "${url}"</h1><p>This is a simulated crawl result for demonstration purposes.</p><p>Note: Using fallback mode as the server is not available.</p>`,
                    markdown: `# Crawl Results for "${url}"\nThis is a simulated crawl result for demonstration purposes.\n\n> Note: Using fallback mode as the server is not available.`,
                    json: { url, results: "Simulated crawl results (fallback mode)" }
                };
                handleResearchComplete(demoResults);
            }, 500);
        }
    }, 200);
} 