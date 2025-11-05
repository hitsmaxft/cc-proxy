"""
Bocha Web Search Provider

Integration with Bocha AI's web search API
"""

import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from ..base import WebSearchProvider, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class BochaProvider(WebSearchProvider):
    """Bocha AI web search provider implementation"""

    name = "bocha.websearch"
    description = "Bocha AI web search provider"

    def __init__(self, api_key: str, base_url: str = "https://api.bochaai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')  # Remove trailing slash
        logger.info(f"Initialized Bocha provider with base_url: {self.base_url}")

    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute Bocha web search with real API response format"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "query": query.query,
            "count": min(query.max_results, 10),
            "summary": True,
            "freshness": query.freshness
        }

        # Add domain filtering if specified
        if query.allowed_domains:
            payload["domains"] = query.allowed_domains

        logger.info(f"Executing Bocha search for query: {query.query}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/web-search",
                    headers=headers,
                    json=payload
                )

                # Log response status for debugging
                logger.debug(f"Bocha API response status: {response.status_code}")

                response.raise_for_status()
                api_response = response.json()

                # Check API response code
                if api_response.get("code") != 200:
                    error_msg = api_response.get("msg", "Unknown error")
                    logger.warning(f"Bocha API returned error code {api_response.get('code')}: {error_msg}")
                    return []

                return self._parse_response(api_response)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error in Bocha search: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Bocha search: {e}")
            raise

    def _parse_response(self, api_response: Dict[str, Any]) -> List[SearchResult]:
        """Parse Bocha API response into SearchResult objects"""
        results = []

        try:
            data = api_response.get("data", {})
            web_pages = data.get("webPages", {})
            search_results = web_pages.get("value", [])

            logger.info(f"Received {len(search_results)} results from Bocha API")

            for item in search_results:
                try:
                    # Extract and format date information
                    publish_date = item.get("datePublished")
                    page_age = self._format_date(publish_date)

                    # Create search result
                    result = SearchResult(
                        url=item.get("url", ""),
                        title=item.get("name", ""),
                        content=item.get("summary", item.get("snippet", "")),
                        snippet=item.get("snippet", ""),
                        page_age=page_age,
                        site_name=item.get("siteName"),
                        site_icon=item.get("siteIcon")
                    )
                    results.append(result)

                except Exception as e:
                    logger.warning(f"Error parsing individual search result: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error parsing Bocha response: {e}")

        return results

    def _format_date(self, date_str: Optional[str]) -> Optional[str]:
        """Format ISO date string for Claude response"""
        if not date_str:
            return None

        try:
            # Handle ISO format dates from Bocha
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime("%B %d, %Y")
        except (ValueError, AttributeError):
            # If parsing fails, return original string
            return date_str

    @classmethod
    def get_required_config(cls) -> List[str]:
        """Return required configuration keys"""
        return ["api_key"]