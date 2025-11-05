"""
Web Search API Handler

Handles web search requests that bypass LLM providers
"""

from typing import Dict, Any, Optional, List
from fastapi import HTTPException
import logging

from src.models.claude import ClaudeMessagesRequest, ClaudeTool
from src.websearch.registry import registry
from src.websearch.base import SearchQuery
from src.websearch.response_formatter import ClaudeResponseFormatter
from src.core.config import config

logger = logging.getLogger(__name__)


class WebSearchHandler:
    """Handle web search requests that bypass LLM providers"""

    def __init__(self):
        self.formatter = ClaudeResponseFormatter()

    def detect_web_search_request(self, claude_request: ClaudeMessagesRequest) -> Optional[ClaudeTool]:
        """Detect if request contains web search tool and return the tool"""
        if not claude_request.tools:
            return None

        for tool in claude_request.tools:
            if tool.type == "web_search_20250305":
                return tool

        return None

    async def handle_web_search_request(
        self,
        claude_request: ClaudeMessagesRequest,
        provider_config: dict,
        web_search_config: str
    ) -> Optional[Dict[str, Any]]:
        """Handle web search request and return formatted response"""

        logger.info(f"Handling web search request with provider: {web_search_config}")

        # Detect web search tool
        search_tool = self.detect_web_search_request(claude_request)
        if not search_tool:
            logger.warning("No web search tool found in request")
            return None

        # Get provider from registry
        provider = registry.get_provider(web_search_config, provider_config)
        if not provider:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown web search provider: {web_search_config}"
            )

        # Extract search query from tool input
        query_input = self._extract_query_input(search_tool)
        if not query_input.get("query"):
            raise HTTPException(
                status_code=400,
                detail="Web search tool missing required 'query' parameter"
            )

        # Build search query
        search_query = SearchQuery(
            query=query_input["query"],
            max_results=query_input.get("max_uses", 5),
            allowed_domains=query_input.get("allowed_domains", []),
            blocked_domains=query_input.get("blocked_domains", []),
            user_location=query_input.get("user_location"),
            freshness=query_input.get("freshness", "noLimit")
        )

        try:
            # Execute search
            logger.info(f"Executing search for query: {search_query.query}")
            results = await provider.search(search_query)

            if not results:
                logger.warning(f"No results found for query: {search_query.query}")
                # Return empty results response
                return self._format_empty_response(search_query.query)

            # Format response
            response = self.formatter.format_search_response(
                original_query=search_query.query,
                search_results=results,
                tool_use_id=None
            )

            logger.info(f"Successfully formatted response with {len(results)} results")
            return response

        except Exception as e:
            logger.error(f"Error handling web search request: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Web search failed: {str(e)}"
            )

    def _extract_query_input(self, search_tool: ClaudeTool) -> Dict[str, Any]:
        """Extract query input from web search tool"""
        # Handle different ways the query might be provided
        if hasattr(search_tool, 'input_schema'):
            return search_tool.input_schema or {}
        elif hasattr(search_tool, 'input'):
            return search_tool.input or {}
        else:
            return {}

    def _format_empty_response(self, query: str) -> Dict[str, Any]:
        """Format response for empty search results"""
        import uuid

        return {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": f"I searched for '{query}' but didn't find any relevant results."
                },
                {
                    "type": "server_tool_use",
                    "id": self.formatter.generate_tool_use_id(),
                    "name": "web_search",
                    "input": {
                        "query": query
                    }
                },
                {
                    "type": "web_search_tool_result",
                    "tool_use_id": self.formatter.generate_tool_use_id(),
                    "content": []
                },
                {
                    "type": "text",
                    "text": "Please try refining your search terms or use different keywords."
                }
            ],
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "server_tool_use": {
                    "web_search_requests": 1
                }
            },
            "stop_reason": "end_turn"
        }


def get_web_search_provider_config(provider_name: str) -> Dict[str, Any]:
    """Get configuration for web search provider from global config"""
    # Try to get from web_search_providers section
    if hasattr(config, 'web_search_providers'):
        return config.web_search_providers.get(provider_name, {})

    # Fallback to direct config
    return {}


def should_use_web_search_bypass(provider_name: str) -> bool:
    """Check if provider should use web search bypass"""
    # Get provider configuration
    for provider in config.provider:
        if provider.get("name") == provider_name:
            web_search_config = provider.get("web_search", "")
            return web_search_config.startswith("bocha.") or web_search_config == "direct"

    return False