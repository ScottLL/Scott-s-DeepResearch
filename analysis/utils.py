import requests
import re
from langdetect import detect, LangDetectException
from .clients import ollama_base_url

def detect_language(text: str) -> str:
    """
    Detect the language of the input text.
    Returns the language code (e.g., 'en' for English, 'es' for Spanish).
    """
    try:
        return detect(text)
    except LangDetectException:
        return 'en'  # Default to English if detection fails

def is_ollama_available():
    """Check if Ollama server is reachable"""
    try:
        response = requests.get(ollama_base_url.replace("/v1", "/api/tags"))
        return response.status_code == 200
    except:
        return False 