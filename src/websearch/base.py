"""
Base classes for web search providers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import uuid


@dataclass
class SearchResult:
    """Represents a single search result"""
    url: str
    title: str
    content: str  # Main content/summary
    snippet: Optional[str] = None  # Short snippet if available
    page_age: Optional[str] = None  # Published date
    site_name: Optional[str] = None  # Website name
    site_icon: Optional[str] = None  # Favicon URL


@dataclass
class SearchQuery:
    """Represents a search query with parameters"""
    query: str
    max_results: int = 5
    allowed_domains: Optional[List[str]] = None
    blocked_domains: Optional[List[str]] = None
    user_location: Optional[Dict[str, str]] = None
    freshness: str = "noLimit"  # noLimit, day, week, month, year


class WebSearchProvider(ABC):
    """Abstract base class for web search providers"""

    name: str
    description: str

    @abstractmethod
    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute search and return results"""
        pass

    @classmethod
    @abstractmethod
    def get_required_config(cls) -> List[str]:
        """Return list of required configuration keys"""
        pass

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate that required configuration is present"""
        required = self.__class__.get_required_config()
        return all(key in config for key in required)


class ResponseFormatter(ABC):
    """Abstract base for formatting search responses"""

    @abstractmethod
    def format_search_response(
        self,
        original_query: str,
        search_results: List[SearchResult],
        tool_use_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format search results for Claude response"""
        pass

    def generate_tool_use_id(self) -> str:
        """Generate a unique tool use ID"""
        return f"srvtoolu_{uuid.uuid4().hex[:16]}"