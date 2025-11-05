"""
Tests for Web Search Plugin System
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.websearch.base import SearchQuery, SearchResult
from src.websearch.providers.bocha import BochaProvider
from src.websearch.response_formatter import ClaudeResponseFormatter
from src.websearch.registry import registry
from src.api.web_search import WebSearchHandler
from src.models.claude import ClaudeMessagesRequest, ClaudeMessage, ClaudeTool, ClaudeContentBlockText


class TestWebSearchProvider:
    """Test web search provider functionality"""

    def test_search_query_creation(self):
        """Test SearchQuery dataclass creation"""
        query = SearchQuery(
            query="test query",
            max_results=5,
            allowed_domains=["example.com"],
            user_location={"country": "US"}
        )
        assert query.query == "test query"
        assert query.max_results == 5
        assert query.allowed_domains == ["example.com"]
        assert query.user_location == {"country": "US"}

    def test_search_result_creation(self):
        """Test SearchResult dataclass creation"""
        result = SearchResult(
            url="https://example.com",
            title="Test Title",
            content="Test content",
            page_age="January 1, 2024"
        )
        assert result.url == "https://example.com"
        assert result.title == "Test Title"
        assert result.content == "Test content"
        assert result.page_age == "January 1, 2024"


class TestBochaProvider:
    """Test Bocha web search provider"""

    @pytest.fixture
    def bocha_provider(self):
        """Create a Bocha provider for testing"""
        return BochaProvider(api_key="test-key", base_url="https://test.api.com")

    def test_provider_initialization(self, bocha_provider):
        """Test Bocha provider initialization"""
        assert bocha_provider.name == "bocha.websearch"
        assert bocha_provider.api_key == "test-key"
        assert bocha_provider.base_url == "https://test.api.com"

    def test_required_config(self, bocha_provider):
        """Test required configuration keys"""
        required = bocha_provider.get_required_config()
        assert "api_key" in required

    @pytest.mark.asyncio
    async def test_bocha_search_success(self, bocha_provider):
        """Test successful Bocha search"""
        mock_response = {
            "code": 200,
            "data": {
                "webPages": {
                    "value": [
                        {
                            "url": "https://example.com",
                            "name": "Test Result",
                            "summary": "Test summary content",
                            "snippet": "Test snippet",
                            "datePublished": "2024-01-01T00:00:00Z",
                            "siteName": "Example Site"
                        }
                    ]
                }
            }
        }

        query = SearchQuery(query="test query", max_results=5)

        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_post.return_value.__aenter__.return_value = mock_response_obj

            results = await bocha_provider.search(query)

            assert len(results) == 1
            assert results[0].url == "https://example.com"
            assert results[0].title == "Test Result"
            assert results[0].content == "Test summary content"
            assert results[0].page_age == "January 01, 2024"

    @pytest.mark.asyncio
    async def test_bocha_search_api_error(self, bocha_provider):
        """Test Bocha search with API error"""
        mock_response = {
            "code": 400,
            "msg": "Bad request"
        }

        query = SearchQuery(query="test query", max_results=5)

        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_post.return_value.__aenter__.return_value = mock_response_obj

            results = await bocha_provider.search(query)

            assert len(results) == 0  # Should return empty results on API error

    def test_date_formatting(self, bocha_provider):
        """Test date formatting functionality"""
        # Test valid ISO date
        formatted = bocha_provider._format_date("2024-01-15T10:30:00Z")
        assert formatted == "January 15, 2024"

        # Test invalid date
        formatted = bocha_provider._format_date("invalid-date")
        assert formatted == "invalid-date"

        # Test None
        formatted = bocha_provider._format_date(None)
        assert formatted is None


class TestResponseFormatter:
    """Test Claude response formatter"""

    @pytest.fixture
    def formatter(self):
        """Create a response formatter for testing"""
        return ClaudeResponseFormatter()

    @pytest.fixture
    def sample_results(self):
        """Create sample search results"""
        return [
            SearchResult(
                url="https://example1.com",
                title="Result 1",
                content="Content 1",
                page_age="January 1, 2024"
            ),
            SearchResult(
                url="https://example2.com",
                title="Result 2",
                content="Content 2",
                page_age="February 1, 2024"
            )
        ]

    def test_format_search_response(self, formatter, sample_results):
        """Test formatting search response"""
        response = formatter.format_search_response(
            original_query="test query",
            search_results=sample_results,
            tool_use_id="test_tool_id"
        )

        # Check response structure
        assert response["role"] == "assistant"
        assert len(response["content"]) == 4  # text + tool_use + tool_result + text

        # Check first content block (text)
        assert response["content"][0]["type"] == "text"
        assert "test query" in response["content"][0]["text"]

        # Check tool use block
        tool_use = response["content"][1]
        assert tool_use["type"] == "server_tool_use"
        assert tool_use["id"] == "test_tool_id"
        assert tool_use["name"] == "web_search"
        assert tool_use["input"]["query"] == "test query"

        # Check tool result block
        tool_result = response["content"][2]
        assert tool_result["type"] == "web_search_tool_result"
        assert tool_result["tool_use_id"] == "test_tool_id"
        assert len(tool_result["content"]) == 2

        # Check search results in tool result
        search_item = tool_result["content"][0]
        assert search_item["type"] == "web_search_result"
        assert search_item["url"] == "https://example1.com"
        assert search_item["title"] == "Result 1"
        assert search_item["encrypted_content"] == "Content 1"

        # Check final text block
        assert response["content"][3]["type"] == "text"
        assert "2 relevant sources" in response["content"][3]["text"]

    def test_generate_tool_use_id(self, formatter):
        """Test tool use ID generation"""
        tool_id = formatter.generate_tool_use_id()
        assert tool_id.startswith("srvtoolu_")
        assert len(tool_id) == len("srvtoolu_") + 16  # srvtoolu_ + 16 char hex


class TestWebSearchHandler:
    """Test web search handler"""

    @pytest.fixture
    def handler(self):
        """Create a web search handler for testing"""
        return WebSearchHandler()

    @pytest.fixture
    def sample_claude_request(self):
        """Create a sample Claude request with web search tool"""
        tool = ClaudeTool(
            name="web_search",
            description="Web search tool",
            type="web_search_20250305",
            input_schema={
                "query": "test query",
                "max_uses": 5
            }
        )

        message = ClaudeMessage(
            role="user",
            content=[
                ClaudeContentBlockText(
                    type="text",
                    text="Search for information about test query"
                )
            ]
        )

        return ClaudeMessagesRequest(
            model="Bocha-Direct:any-model",
            max_tokens=1000,
            messages=[message],
            tools=[tool]
        )

    def test_detect_web_search_request(self, handler, sample_claude_request):
        """Test web search request detection"""
        detected_tool = handler.detect_web_search_request(sample_claude_request)
        assert detected_tool is not None
        assert detected_tool.name == "web_search"
        assert detected_tool.type == "web_search_20250305"

    def test_detect_web_search_request_no_tools(self, handler):
        """Test web search request detection with no tools"""
        request = ClaudeMessagesRequest(
            model="test-model",
            max_tokens=1000,
            messages=[
                ClaudeMessage(
                    role="user",
                    content="No tools here"
                )
            ],
            tools=None
        )

        detected_tool = handler.detect_web_search_request(request)
        assert detected_tool is None

    def test_extract_query_input(self, handler):
        """Test query input extraction"""
        tool = ClaudeTool(
            name="web_search",
            input_schema={
                "query": "test query",
                "max_uses": 5
            }
        )

        query_input = handler._extract_query_input(tool)
        assert query_input["query"] == "test query"
        assert query_input["max_uses"] == 5

    @pytest.mark.asyncio
    async def test_handle_web_search_request_success(self, handler, sample_claude_request):
        """Test successful web search request handling"""
        provider_config = {"api_key": "test-key"}
        web_search_config = "bocha.websearch"

        # Mock the provider
        mock_provider = AsyncMock()
        mock_provider.search.return_value = [
            SearchResult(
                url="https://example.com",
                title="Test Result",
                content="Test content"
            )
        ]

        with patch.object(registry, 'get_provider', return_value=mock_provider):
            response = await handler.handle_web_search_request(
                claude_request=sample_claude_request,
                provider_config=provider_config,
                web_search_config=web_search_config
            )

            assert response is not None
            assert response["role"] == "assistant"
            assert len(response["content"]) == 4

    @pytest.mark.asyncio
    async def test_handle_web_search_request_no_provider(self, handler, sample_claude_request):
        """Test web search request with unknown provider"""
        provider_config = {"api_key": "test-key"}
        web_search_config = "unknown.provider"

        with patch.object(registry, 'get_provider', return_value=None):
            with pytest.raises(Exception):  # Should raise HTTPException
                await handler.handle_web_search_request(
                    claude_request=sample_claude_request,
                    provider_config=provider_config,
                    web_search_config=web_search_config
                )

    def test_format_empty_response(self, handler):
        """Test empty response formatting"""
        response = handler._format_empty_response("test query")

        assert response["role"] == "assistant"
        assert len(response["content"]) == 4
        assert "didn't find any relevant results" in response["content"][0]["text"]


class TestWebSearchRegistry:
    """Test web search registry"""

    def test_registry_initialization(self):
        """Test registry initialization"""
        assert hasattr(registry, '_providers')
        assert hasattr(registry, '_instances')

    def test_provider_registration(self):
        """Test provider registration"""
        # Bocha provider should be auto-registered
        assert registry.has_provider("bocha.websearch")

    def test_list_providers(self):
        """Test listing available providers"""
        providers = registry.list_providers()
        assert "bocha.websearch" in providers

    def test_get_provider_missing_config(self):
        """Test getting provider with missing config"""
        # This should raise ValueError due to missing api_key
        with pytest.raises(ValueError):
            registry.get_provider("bocha.websearch", {})


if __name__ == "__main__":
    pytest.main([__file__])