"""
Core functionality for web crawling, searching, and content extraction.
This module contains the fundamental implementations used by the tools interfaces.
"""

from .crawler import WebCrawler
from .search import search_with_google, direct_baidu_search
from .link_utils import explore_page_links
# from .extraction import extract_content

__all__ = [
    'WebCrawler',
    'search_with_google', 
    'direct_baidu_search',
    'explore_page_links',
    # 'extract_content'
] 