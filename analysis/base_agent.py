from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from .clients import client, deepseek_client, qwq_client, ollama_client, qwq_stream_complete
from .utils import is_ollama_available

# Base Agent Class
class BaseAnalysisAgent:
    """
    Base class for all analysis agents with common functionality.
    """
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.state = "INITIALIZED"
        self.memory = []  # Simple memory for tracking agent operations
    
    @asynccontextmanager
    async def state_context(self, new_state: str):
        """Context manager for handling state transitions"""
        old_state = self.state
        self.state = new_state
        try:
            yield
        finally:
            self.state = old_state
    
    def select_client(self):
        """Select the appropriate client based on the model"""
        if self.model == "deepseek-reasoner":
            return deepseek_client
        elif self.model == "qwq-32b":
            return qwq_client
        elif self.model.startswith("ollama:") or (self.model == "qwq:32b" and is_ollama_available()):
            return ollama_client
        else:
            return client
    
    async def execute(self, 
                     messages: List[Dict[str, str]], 
                     temperature: float = 0.0,
                     max_tokens: int = 1500) -> str:
        """
        Execute a request to the language model
        """
        api_client = self.select_client()
        
        # Handle QWQ-32B streaming mode specially
        if self.model == "qwq-32b":
            return qwq_stream_complete(api_client, messages, self.model, temperature, max_tokens)
        
        # Standard execution for other models
        try:
            response = api_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[Analysis] Error in model execution: {e}")
            return "" 