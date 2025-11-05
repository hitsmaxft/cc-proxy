"""
Web Search Plugin System for CC-Proxy

Provides extensible web search functionality supporting multiple providers
including Bocha, OpenRouter, and future search providers.
"""

from .base import WebSearchProvider, SearchQuery, SearchResult, ResponseFormatter
from .registry import WebSearchRegistry, registry
from .response_formatter import ClaudeResponseFormatter
from .providers.bocha import BochaProvider

__all__ = [
    "WebSearchProvider",
    "SearchQuery",
    "SearchResult",
    "ResponseFormatter",
    "WebSearchRegistry",
    "registry",
    "ClaudeResponseFormatter",
    "BochaProvider"
]