# Web Search Plugin System

An extensible web search plugin system for CC-Proxy that enables Claude Code to perform web searches using various providers, starting with Bocha AI.

## ✅ Features

- **Extensible Architecture**: Easy to add new search providers
- **Bocha AI Integration**: Full API integration with real-time web search
- **LLM Bypass**: Direct web search responses without LLM processing
- **Claude Compatible**: Native Claude API response format
- **Per-Provider Configuration**: Different search providers per LLM provider
- **Secure**: Environment variable support for API keys

## 🚀 Quick Start

### 1. Set Environment Variable
```bash
export BOCHA_API_TOKEN="your-bocha-api-token"
```

### 2. Configure Provider
Add to your `providers.toml`:

```toml
[[provider]]
name = "Bocha-Direct"
web_search = "bocha.websearch"

[web_search_providers.bocha.websearch]
env_key = "BOCHA_API_TOKEN"
base_url = "https://api.bochaai.com/v1"
```

### 3. Start Proxy
```bash
python start_proxy.py --conf your-config.toml
```

### 4. Use with Claude Code
```bash
export ANTHROPIC_BASE_URL=http://localhost:8082
claude
```

## 📖 Configuration Options

### Direct Web Search (LLM Bypass)
```toml
[[provider]]
name = "Bocha-Direct"
web_search = "bocha.websearch"
```

### Hybrid Mode (Search + LLM)
```toml
[[provider]]
name = "Bocha-Plus-OpenAI"
base_url = "https://api.openai.com/v1"
api_key = "your-openai-key"
web_search = "bocha.websearch"
big_models = ["gpt-4o"]
```

### OpenRouter Integration
```toml
[[provider]]
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
api_key = "your-openrouter-key"
web_search = "openrouter.online"
big_models = ["anthropic/claude-3-opus-20240229"]
```

## 🔧 Web Search Providers

### Bocha AI
```toml
[web_search_providers.bocha.websearch]
env_key = "BOCHA_API_TOKEN"  # Recommended
base_url = "https://api.bochaai.com/v1"  # Optional
```

## 📝 Usage Examples

### Direct Search Request
When Claude Code sends a request with web search tools:

```json
{
  "model": "Bocha-Direct:any-model",
  "max_tokens": 1024,
  "messages": [{"role": "user", "content": "What's the latest news about AI?"}],
  "tools": [{
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5
  }]
}
```

The proxy will:
1. Detect the web search tool
2. Call Bocha API directly
3. Return Claude-compatible response with search results

### Response Format
```json
{
  "role": "assistant",
  "content": [
    {"type": "text", "text": "I'll search for latest news about AI."},
    {"type": "server_tool_use", "id": "srvtoolu_abc123", "name": "web_search", "input": {"query": "latest AI news"}},
    {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_abc123", "content": [
      {"type": "web_search_result", "url": "https://example.com", "title": "AI News", "encrypted_content": "Summary..."}
    ]},
    {"type": "text", "text": "Based on the search results, I found relevant sources."}
  ],
  "usage": {"server_tool_use": {"web_search_requests": 1}},
  "stop_reason": "end_turn"
}
```

## 🧪 Testing

### Run Tests
```bash
python -m pytest tests/test_websearch.py -v
```

### Test with API Key
```bash
export BOCHA_API_TOKEN="your-token"
python examples/websearch-usage.py
```

## 🏗️ Architecture

```
src/websearch/
├── __init__.py              # Package exports
├── base.py                  # Abstract base classes
├── registry.py              # Provider registry
├── response_formatter.py    # Claude response formatting
└── providers/
    ├── __init__.py
    └── bocha.py             # Bocha AI provider
```

## 🔧 Adding New Providers

1. Create provider class in `src/websearch/providers/`
2. Inherit from `WebSearchProvider`
3. Implement required methods:
   - `async search(query: SearchQuery) -> List[SearchResult]`
   - `get_required_config() -> List[str]`
4. Register in `src/websearch/registry.py`

Example:
```python
class NewProvider(WebSearchProvider):
    name = "new.provider"

    async def search(self, query: SearchQuery) -> List[SearchResult]:
        # Implement search logic
        pass

    @classmethod
    def get_required_config(cls) -> List[str]:
        return ["api_key"]
```

## 🐛 Troubleshooting

### Import Errors
Ensure all dependencies are installed:
```bash
pip install httpx
```

### API Key Issues
Check environment variables:
```bash
echo $BOCHA_API_KEY
```

### Configuration Issues
Validate your TOML configuration:
```bash
python -c "
import toml
config = toml.load('your-config.toml')
print('Providers:', config.get('provider', []))
print('Web Search Providers:', config.get('web_search_providers', {}))
"
```

## 📚 Documentation

- **Implementation Plan**: `tasks/websearch.md`
- **Configuration Examples**: `examples/websearch-config.toml`
- **Usage Examples**: `examples/websearch-usage.py`
- **Test Suite**: `tests/test_websearch.py`

## 🤝 Contributing

To add a new search provider:

1. Implement the `WebSearchProvider` interface
2. Add comprehensive tests
3. Update documentation
4. Register in the registry

## 📄 License

This web search plugin system is part of the CC-Proxy project.