"""
Response Formatter - Formats search results for Claude API responses
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import SearchResult, ResponseFormatter
import logging

logger = logging.getLogger(__name__)


class ClaudeResponseFormatter(ResponseFormatter):
    """Format search results for Claude API responses with proper structure"""

    def format_search_response(
        self,
        original_query: str,
        search_results: List[SearchResult],
        tool_use_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format search results in Claude-compatible API format"""

        # Generate unique tool use ID if not provided
        if not tool_use_id:
            tool_use_id = self.generate_tool_use_id()

        logger.info(f"Formatting {len(search_results)} search results for query: '{original_query}'")

        # Build search tool results
        search_content = []
        for i, result in enumerate(search_results[:5]):  # Limit to 5 results max
            try:
                search_item = {
                    "type": "web_search_result",
                    "url": result.url,
                    "title": result.title,
                    "encrypted_content": result.content,  # Bocha summary content
                    "page_age": result.page_age or ""
                }

                # Add optional fields if present
                if result.site_name:
                    search_item["site_name"] = result.site_name

                search_content.append(search_item)

            except Exception as e:
                logger.warning(f"Error formatting search result {i}: {e}")
                continue

        # Build complete Claude-compatible response
        response = {
            "role": "assistant",
            "content": [
                # Claude's decision to search
                {
                    "type": "text",
                    "text": f"I'll search for '{original_query}'."
                },
                # The search tool use
                {
                    "type": "server_tool_use",
                    "id": tool_use_id,
                    "name": "web_search",
                    "input": {
                        "query": original_query
                    }
                },
                # Search results
                {
                    "type": "web_search_tool_result",
                    "tool_use_id": tool_use_id,
                    "content": search_content
                },
                # Claude's response based on results
                {
                    "type": "text",
                    "text": f"Based on the search results, I found {len(search_content)} relevant sources."
                }
            ],
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "usage": {
                "input_tokens": 0,  # Will be calculated
                "output_tokens": 0,  # Will be calculated
                "server_tool_use": {
                    "web_search_requests": 1
                }
            },
            "stop_reason": "end_turn"
        }

        logger.debug(f"Formatted response with {len(search_content)} results")
        return response

    def format_search_response_with_citations(
        self,
        original_query: str,
        search_results: List[SearchResult],
        tool_use_id: Optional[str] = None,
        generated_response: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format response with citations (future enhancement)"""

        base_response = self.format_search_response(
            original_query=original_query,
            search_results=search_results,
            tool_use_id=tool_use_id
        )

        # Add citations if response is provided
        if generated_response:
            # This would be used for future LLM-augmented responses
            # For now, we'll just add the basic response
            pass

        return base_response


class EnhancedClaudeResponseFormatter(ClaudeResponseFormatter):
    """Enhanced formatter with additional features"""

    def format_detailed_response(
        self,
        original_query: str,
        search_results: List[SearchResult],
        tool_use_id: Optional[str] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """Format detailed response with additional metadata"""

        response = super().format_search_response(
            original_query=original_query,
            search_results=search_results,
            tool_use_id=tool_use_id
        )

        if include_metadata and search_results:
            # Add statistics about search results
            domains = list(set(result.url.split('/')[2] for result in search_results if result.url))
            dates = [result.page_age for result in search_results if result.page_age]

            # Add search statistics to the text response
            stats_text = f"\n\nSearch covered {len(domains)} domains"
            if dates:
                stats_text += f" with results from {min(dates).split()[2]} to {max(dates).split()[2]}"

            # Update the final text response with stats
            if response["content"] and response["content"][-1]["type"] == "text":
                response["content"][-1]["text"] += stats_text

        return response