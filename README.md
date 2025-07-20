# CC-Proxy

**An enhanced Claude API proxy with advanced features and web UI management**

CC-Proxy is a powerful proxy server that significantly improves upon the upstream Claude Code proxy project. It enables **Claude Code** to work with OpenAI-compatible API providers while providing a comprehensive web interface for model management, cost tracking, and message history.

![CC-Proxy Web UI](images/main.png)
![Message History](images/messages.png)
![Token Cost Summary](images/summary.png)

![CC-Proxy Demo](demo.png)

## Key Features

### Core Proxy Features
- **Full Claude API Compatibility**: Complete `/v1/messages` endpoint support
- **Multiple Provider Support**: OpenAI, Azure OpenAI, local models (Ollama), and any OpenAI-compatible API
- **Smart Model Mapping**: Configure BIG, MIDDLE, and SMALL models via environment variables
- **Function Calling**: Complete tool use support with proper conversion
- **Streaming Responses**: Real-time SSE streaming support
- **Image Support**: Base64 encoded image input
- **Error Handling**: Comprehensive error handling and logging

### Enhanced Web UI Features
- **Web Configuration Interface**: Easy model and provider configuration through web UI
- **Message History Tracking**: Complete conversation history with search and filtering
- **Token Cost Analysis**: Real-time token usage tracking and cost analysis across models
- **Multi-Model Switching**: Dynamic model switching with usage comparison
- **Web Search Integration**: Built-in web search capabilities (currently supports OpenRoute)
- **Usage Analytics**: Detailed statistics and usage patterns

## Quick Start

### 1. Install Dependencies

```bash
# Using UV (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and add your API configuration
```

### 3. Start Server

```bash
# Direct run
python start_proxy.py

# Or with UV
uv run claude-code-proxy
```

### 4. Use with Claude Code

```bash
# If ANTHROPIC_API_KEY is not set in the proxy:
ANTHROPIC_BASE_URL=http://localhost:8082 ANTHROPIC_API_KEY="any-value" claude

# If ANTHROPIC_API_KEY is set in the proxy:
ANTHROPIC_BASE_URL=http://localhost:8082 ANTHROPIC_API_KEY="exact-matching-key" claude
```

## Configuration

### Environment Variables

**Required:**

- `OPENAI_API_KEY` - Your API key for the target provider

**Security:**

- `ANTHROPIC_API_KEY` - Expected Anthropic API key for client validation
  - If set, clients must provide this exact API key to access the proxy
  - If not set, any API key will be accepted

**Model Configuration:**

- `BIG_MODEL` - Model for Claude opus requests (default: `gpt-4o`)
- `MIDDLE_MODEL` - Model for Claude opus requests (default: `gpt-4o`)
- `SMALL_MODEL` - Model for Claude haiku requests (default: `gpt-4o-mini`)

**API Configuration:**

- `OPENAI_BASE_URL` - API base URL (default: `https://api.openai.com/v1`)

**Server Settings:**

- `HOST` - Server host (default: `0.0.0.0`)
- `PORT` - Server port (default: `8082`)
- `LOG_LEVEL` - Logging level (default: `WARNING`)

**Performance:**

- `MAX_TOKENS_LIMIT` - Token limit (default: `4096`)
- `REQUEST_TIMEOUT` - Request timeout in seconds (default: `90`)

### Model Mapping

The proxy maps Claude model requests to your configured models:

| Claude Request                 | Mapped To     | Environment Variable   |
| ------------------------------ | ------------- | ---------------------- |
| Models with "haiku"            | `SMALL_MODEL` | Default: `gpt-4o-mini` |
| Models with "sonnet"           | `MIDDLE_MODEL`| Default: `BIG_MODEL`   |
| Models with "opus"             | `BIG_MODEL`   | Default: `gpt-4o`      |

### Provider Examples

#### OpenAI

```bash
OPENAI_API_KEY="sk-your-openai-key"
OPENAI_BASE_URL="https://api.openai.com/v1"
BIG_MODEL="gpt-4o"
MIDDLE_MODEL="gpt-4o"
SMALL_MODEL="gpt-4o-mini"
```

#### Azure OpenAI

```bash
OPENAI_API_KEY="your-azure-key"
OPENAI_BASE_URL="https://your-resource.openai.azure.com/openai/deployments/your-deployment"
BIG_MODEL="gpt-4"
MIDDLE_MODEL="gpt-4"
SMALL_MODEL="gpt-35-turbo"
```

#### Local Models (Ollama)

```bash
OPENAI_API_KEY="dummy-key"  # Required but can be dummy
OPENAI_BASE_URL="http://localhost:11434/v1"
BIG_MODEL="llama3.1:70b"
MIDDLE_MODEL="llama3.1:70b"
SMALL_MODEL="llama3.1:8b"
```

#### Other Providers

Any OpenAI-compatible API can be used by setting the appropriate `OPENAI_BASE_URL`.

## Usage Examples

### Basic Chat

```python
import httpx

response = httpx.post(
    "http://localhost:8082/v1/messages",
    json={
        "model": "claude-3-5-sonnet-20241022",  # Maps to MIDDLE_MODEL
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "Hello!"}
        ]
    }
)
```

## Why Choose CC-Proxy

CC-Proxy enhances the original Claude Code proxy with powerful new features:

- **Web UI Dashboard**: Monitor usage, costs, and performance in real-time
- **Message History**: Complete conversation tracking with search capabilities  
- **Token Analytics**: Detailed cost analysis across different models
- **Web Search**: Integrated search functionality for enhanced responses
- **Multi-Model Management**: Easy switching and comparison between models

## Integration with Claude Code

CC-Proxy works seamlessly with Claude Code CLI while providing enhanced monitoring:

```bash
# Start CC-Proxy
python start_proxy.py

# Use Claude Code with CC-Proxy
ANTHROPIC_BASE_URL=http://localhost:8082 claude

# Access web interface at http://localhost:8082/
# Or set permanently
export ANTHROPIC_BASE_URL=http://localhost:8082
claude
```

## Testing

Test the proxy functionality:

```bash
# Run comprehensive tests
python src/test_claude_to_openai.py
```

## Development

### Using UV

```bash
# Install dependencies
uv sync

# Run server
uv run claude-code-proxy

# Format code
uv run black src/
uv run isort src/

# Type checking
uv run mypy src/
```

### Project Structure

```
cc-proxy/
├── src/
│   ├── main.py                     # Main proxy server
│   ├── web_ui/                     # Web interface components
│   ├── models/                     # Data models and schemas
│   ├── utils/                      # Utility functions
│   ├── test_claude_to_openai.py    # Comprehensive tests
│   └── [other modules...]
├── static/                         # Web UI static assets
├── templates/                      # Web UI templates
├── start_proxy.py                  # Startup script
├── .env.example                    # Configuration template
└── README.md                       # This documentation
```

## Performance

- **Async/await** for high concurrency
- **Connection pooling** for efficiency
- **Streaming support** for real-time responses
- **Configurable timeouts** and retries
- **Smart error handling** with detailed logging

## License

MIT License
