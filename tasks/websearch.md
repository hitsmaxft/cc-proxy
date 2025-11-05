# Web Search Plugin Implementation Plan

## Overview

Design and implement an extensible web search plugin system that allows CC-Proxy to support multiple web search providers, starting with Bocha. The system should support configurable web search providers per LLM provider and handle search requests that bypass LLM providers when configured.

## Requirements Analysis

### Current State
- Existing `web_search_20250305` tool type in Claude models
- Basic web search detection in request converter
- OpenRouter integration adds `:online` suffix for web search
- Bocha API documented in `docs/search_api.md`

### New Requirements
1. **Configurable web search providers**: `web_search="bocha.websearch"` per provider
2. **Extensible plugin architecture**: Support for multiple search providers
3. **Bocha integration**: Direct API calls to Bocha for web search
4. **LLM bypass**: Option to handle search requests without LLM provider
5. **Claude-compatible response format**: Return search results in expected format
6. **Per-provider configuration**: Different search providers per LLM provider

## Architecture Design

### 1. Web Search Plugin System

```
src/websearch/
├── __init__.py
├── base.py              # Abstract base classes
├── registry.py           # Plugin registry
├── providers/
│   ├── __init__.py
│   ├── bocha.py         # Bocha implementation
│   └── openrouter.py    # OpenRouter implementation (existing)
└── response_formatter.py # Claude response formatting
```

### 2. Configuration Schema

#### providers.toml
```toml
[[provider]]
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
api_key = "your-key"
web_search = "openrouter.online"  # or "bocha.websearch"
big_models = ["anthropic/claude-3-opus-20240229"]
middle_models = ["anthropic/claude-3-sonnet-20240229"]
small_models = ["anthropic/claude-3-haiku-20240307"]

[web_search_providers.bocha]
api_key = "bocha-api-key"  # or env_key
base_url = "https://api.bochaai.com/v1"

[web_search_providers.openrouter]
api_key = "openrouter-key"  # optional override
```

### 3. Request Flow

#### When web_search is configured:
1. **Request Detection**: Check if request contains `web_search_20250305` tool
2. **Provider Selection**: Use configured web search provider for current LLM provider
3. **Search Execution**: Call web search API directly
4. **Response Fomation**: Format search results in Claude-compatible format
5. **LLM Bypass**: Skip LLM provider call if configured for direct search

## Implementation Plan

### Task 1: Create Base Plugin Architecture

#### Files:
- `src/websearch/base.py` - Abstract base classes
- `src/websearch/registry.py` - Plugin registry system

#### Implementation:
```python
# src/websearch/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class SearchResult:
    url: str
    title: str
    content: str
    page_age: Optional[str] = None
    snippet: Optional[str] = None

@dataclass
class SearchQuery:
    query: str
    max_results: int = 5
    allowed_domains: List[str] = None
    blocked_domains: List[str] = None
    user_location: Dict[str, str] = None

class WebSearchProvider(ABC):
    """Abstract base class for web search providers"""

    name: str
    description: str

    @abstractmethod
    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute search and return results"""
        pass

    @abstractmethod
    def get_required_config(self) -> List[str]:
        """Return list of required configuration keys"""
        pass

class ResponseFormatter(ABC):
    """Abstract base for formatting search responses"""

    @abstractmethod
    def format_search_response(
        self,
        original_query: str,
        search_results: List[SearchResult],
        tool_use_id: str
    ) -> Dict[str, Any]:
        """Format search results for Claude response"""
        pass
```

### Task 2: Implement Bocha Provider

#### Files:
- `src/websearch/providers/bocha.py`
- Add Bocha-specific configuration handling

#### Implementation:
```python
# src/websearch/providers/bocha.py
import httpx
from typing import List, Dict, Any
from datetime import datetime
from ..base import WebSearchProvider, SearchQuery, SearchResult

class BochaProvider(WebSearchProvider):
    name = "bocha.websearch"
    description = "Bocha AI web search provider"

    def __init__(self, api_key: str, base_url: str = "https://api.bochaai.com/v1"):
        self.api_key = api_key
        self.base_url = base_url

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
            "freshness": "noLimit"
        }

        if query.allowed_domains:
            payload["domains"] = query.allowed_domains

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/web-search",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()

            api_response = response.json()
            results = []

            # Parse Bocha's actual response format
            if api_response.get("code") == 200:
                web_pages = api_response.get("data", {}).get("webPages", {})

                for item in web_pages.get("value", []):
                    # Extract date information
                    publish_date = item.get("datePublished")
                    crawl_date = item.get("dateLastCrawled")

                    # Format date for Claude response
                    page_age = None
                    if publish_date:
                        try:
                            dt = datetime.fromisoformat(publish_date.replace('Z', '+00:00'))
                            page_age = dt.strftime("%B %d, %Y")
                        except:
                            page_age = publish_date

                    result = SearchResult(
                        url=item.get("url", ""),
                        title=item.get("name", ""),
                        content=item.get("summary", item.get("snippet", "")),
                        snippet=item.get("snippet", ""),
                        page_age=page_age
                    )
                    results.append(result)

            return results

    def get_required_config(self) -> List[str]:
        return ["api_key"]
```

### Task 3: Create Claude Response Formatter

#### Files:
- `src/websearch/response_formatter.py`
- Implement Claude-compatible response format

#### Implementation:
```python
# src/websearch/response_formatter.py
import uuid
from typing import List, Dict, Any
from .base import SearchResult, ResponseFormatter

class ClaudeResponseFormatter(ResponseFormatter):
    """Format search results for Claude API response"""

    def format_search_response(
        self,
        original_query: str,
        search_results: List[SearchResult],
        tool_use_id: str
    ) -> Dict[str, Any]:
        """Format response in Claude-compatible format"""

        # Generate unique tool use ID if not provided
        if not tool_use_id:
            tool_use_id = f"srvtoolu_{uuid.uuid4().hex[:16]}"

        # Build search tool results
        search_content = []
        for result in search_results:
            search_content.append({
                "type": "web_search_result",
                "url": result.url,
                "title": result.title,
                "encrypted_content": result.content,  # Real content, not encrypted
                "page_age": result.page_age or ""
            })

        # Build complete response
        response = {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": f"I'll search for {original_query}."
                },
                {
                    "type": "server_tool_use",
                    "id": tool_use_id,
                    "name": "web_search",
                    "input": {
                        "query": original_query
                    }
                },
                {
                    "type": "web_search_tool_result",
                    "tool_use_id": tool_use_id,
                    "content": search_content
                },
                {
                    "type": "text",
                    "text": f"Based on the search results, I found {len(search_results)} relevant sources."
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

        return response
```

### Task 4: Create Web Search Registry

#### Files:
- `src/websearch/registry.py`
- Manage provider registration and selection

#### Implementation:
```python
# src/websearch/registry.py
from typing import Dict, Optional
from .base import WebSearchProvider
from .providers.bocha import BochaProvider

class WebSearchRegistry:
    """Registry for web search providers"""

    def __init__(self):
        self._providers: Dict[str, type] = {}
        self._instances: Dict[str, WebSearchProvider] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default providers"""
        self.register("bocha.websearch", BochaProvider)

    def register(self, name: str, provider_class: type):
        """Register a web search provider"""
        self._providers[name] = provider_class

    def get_provider(self, name: str, config: dict) -> Optional[WebSearchProvider]:
        """Get provider instance by name"""
        if name not in self._providers:
            return None

        # Create instance with config
        provider_class = self._providers[name]
        return provider_class(**config)

    def list_providers(self) -> list:
        """List available provider names"""
        return list(self._providers.keys())

# Global registry instance
registry = WebSearchRegistry()
```

### Task 5: Create Web Search API Handler

#### Files:
- `src/api/web_search.py`
- Handle web search requests

#### Implementation:
```python
# src/api/web_search.py
from typing import Dict, Any, Optional
from fastapi import HTTPException
from src.models.claude import ClaudeMessagesRequest
from src.websearch.registry import registry
from src.websearch.base import SearchQuery
from src.websearch.response_formatter import ClaudeResponseFormatter

class WebSearchHandler:
    """Handle web search requests"""

    def __init__(self):
        self.formatter = ClaudeResponseFormatter()

    async def handle_web_search_request(
        self,
        claude_request: ClaudeMessagesRequest,
        provider_config: dict,
        web_search_config: str
    ) -> Optional[Dict[str, Any]]:
        """Handle web search request and return formatted response"""

        # Extract search query from tools
        search_tool = None
        for tool in claude_request.tools:
            if tool.type == "web_search_20250305":
                search_tool = tool
                break

        if not search_tool:
            return None

        # Get provider from registry
        provider_name = web_search_config
        provider = registry.get_provider(provider_name, provider_config)

        if not provider:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown web search provider: {provider_name}"
            )

        # Build search query
        query_input = search_tool.input_schema or {}
        search_query = SearchQuery(
            query=query_input.get("query", ""),
            max_results=query_input.get("max_uses", 5),
            allowed_domains=query_input.get("allowed_domains", []),
            user_location=query_input.get("user_location")
        )

        # Execute search
        results = await provider.search(search_query)

        # Format response
        response = self.formatter.format_search_response(
            original_query=search_query.query,
            search_results=results,
            tool_use_id=None
        )

        return response
```

### Task 6: Integrate with Request Converter

#### Files:
- Modify `src/conversion/request_converter.py`
- Add web search bypass logic

#### Changes:
```python
# In convert_claude_to_openai function
async def convert_claude_to_openai(
    claude_request: ClaudeMessagesRequest,
    model_manager: ModelManager
) -> Dict[str, Any]:

    # Check if web search is enabled and requested
    if (model_manager.enable_websearch() and
        get_web_search(claude_request) and
        model_manager.get_web_search_config()):

        # Check if this is a Bocha web search (direct mode)
        web_search_config = model_manager.get_web_search_config()
        if web_search_config.startswith("bocha."):
            # Return special marker for web search bypass
            return {
                "_web_search_bypass": True,
                "provider": web_search_config,
                "original_request": claude_request
            }

    # Continue with normal OpenAI conversion...
```

### Task 7: Update Configuration Schema

#### Files:
- `src/core/config.py`
- `providers.toml.example`

#### Changes:
```python
# src/core/config.py additions
class Config:
    # Existing fields...
    web_search_providers: Dict[str, Dict] = {}
    web_search_enabled: bool = False

    def get_web_search_config(self, provider_name: str) -> Optional[str]:
        """Get web search config for specific provider"""
        for provider in self.provider:
            if provider["name"] == provider_name:
                return provider.get("web_search")
        return None

    def get_web_search_provider_config(self, provider_type: str) -> dict:
        """Get configuration for web search provider"""
        return self.web_search_providers.get(provider_type, {})
```

### Task 8: Create API Endpoint

#### Files:
- `src/api/endpoints.py`
- Add web search handling endpoint

#### Implementation:
```python
# In existing endpoints.py
from src.api.web_search import WebSearchHandler

web_search_handler = WebSearchHandler()

@app.post("/v1/messages")
async def handle_messages(request: ClaudeMessagesRequest):
    # Existing validation...

    # Check for web search bypass
    openai_request = convert_claude_to_openai(request, model_manager)

    if openai_request.get("_web_search_bypass"):
        # Handle web search directly
        provider_name = openai_request["provider"]
        original_request = openai_request["original_request"]

        # Get provider config
        provider_config = config.get_web_search_provider_config(provider_name)

        # Handle web search
        response = await web_search_handler.handle_web_search_request(
            original_request,
            provider_config,
            provider_name
        )

        return response

    # Continue with normal LLM processing...
```

## Testing Plan

### Unit Tests
- `tests/test_websearch.py` - Test web search providers
- `tests/test_bocha_provider.py` - Test Bocha-specific functionality
- `tests/test_response_formatter.py` - Test response formatting

### Integration Tests
- Test full request flow with web search
- Test configuration loading and provider selection
- Test error handling for invalid providers

### Manual Testing
- Test Bocha API integration with real credentials
- Test response format compatibility with Claude Code
- Test per-provider configuration scenarios

## Configuration Examples

### Basic Bocha Configuration
```toml
[config]
port = 8082

[[provider]]
name = "Direct-Bocha"
base_url = "https://api.bochaai.com/v1"
api_key = "bocha-api-key"
web_search = "bocha.websearch"

[web_search_providers.bocha]
api_key = "bocha-api-key"
base_url = "https://api.bochaai.com/v1"
```

### Mixed Provider Configuration
```toml
[[provider]]
name = "OpenRouter-Search"
base_url = "https://openrouter.ai/api/v1"
api_key = "openrouter-key"
web_search = "openrouter.online"
big_models = ["anthropic/claude-3-opus:online"]

[[provider]]
name = "Bocha-Only"
base_url = ""  # No LLM provider needed
web_search = "bocha.websearch"
```

## Implementation Timeline

1. **Phase 1**: Core plugin architecture (2-3 hours)
2. **Phase 2**: Bocha provider implementation (2-3 hours)
3. **Phase 3**: Response formatter and registry (2-3 hours)
4. **Phase 4**: Integration with existing system (3-4 hours)
5. **Phase 5**: Testing and documentation (2-3 hours)

Total estimated time: 11-16 hours