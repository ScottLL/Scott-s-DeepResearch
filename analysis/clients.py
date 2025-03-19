import os
from typing import List, Dict, Any
import logging

try:
    from openai import OpenAI
    # Initialize OpenAI client
    openai_api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=openai_api_key)
    
    # Initialize DeepSeek client
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    deepseek_client = OpenAI(
        api_key=deepseek_api_key,
        base_url="https://api.deepseek.com"
    )
    
    # Initialize Aliyun QWQ-32B client
    dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
    qwq_client = OpenAI(
        api_key=dashscope_api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    
    # Initialize Ollama client for local models
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    ollama_client = OpenAI(
        base_url=ollama_base_url
    )
except ImportError as e:
    raise ImportError("openai.ChatCompletion is not available. Please run `openai migrate` or install openai==0.28") from e

# Utility function to handle QWQ-32B streaming responses
def qwq_stream_complete(client, messages, model="qwq-32b", temperature=0.0, max_tokens=1500):
    """
    Get streaming completion from QWQ model and return the concatenated result
    
    Args:
        client: The OpenAI client
        messages: List of message dictionaries
        model: Model name (default: qwq-32b)
        temperature: Temperature for generation
        max_tokens: Maximum number of tokens
        
    Returns:
        Collected content from the model response
    """
    reasoning_content = ""
    content = ""
    is_answering = False
    
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,  # QWQ-32B requires stream mode
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        for chunk in completion:
            # If chunk.choices is empty, continue (usage info)
            if not chunk.choices:
                continue
                
            delta = chunk.choices[0].delta
            # Process reasoning content
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                reasoning_content += delta.reasoning_content
            else:
                # Process answer content
                if hasattr(delta, 'content') and delta.content is not None:
                    content += delta.content
        
        return content  # Return just the content for compatibility with existing code
    except Exception as e:
        print(f"Error with QWQ streaming: {e}")
        return "" 