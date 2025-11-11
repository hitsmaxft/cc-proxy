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
- **Multiple Provider Support**: Native Anthropic API, OpenAI, Azure OpenAI, local models (Ollama), and any OpenAI-compatible API
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

#### TOML Configuration File

Create a configuration file (e.g., `providers.toml`) with your settings:

```toml
# Example providers.toml - Secure Configuration
[config]
port = 8082
anthropic_api_key = ""
log_level = "INFO"
big_model = "gpt-4o"
middle_model = "gpt-4o"
small_model = "gpt-4o-mini"

[[provider]]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
env_key = "OPENAI_API_KEY"  # Secure: Load API key from environment
big_models = ["gpt-4o"]
middle_models = ["gpt-4o"]
small_models = ["gpt-4o-mini"]

# Native Anthropic provider (no conversion, lower latency)
[[provider]]
name = "Anthropic-Direct"
provider_type = "anthropic"  # Skip format conversion
base_url = "https://api.anthropic.com"
env_key = "ANTHROPIC_API_KEY"
big_models = ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"]
middle_models = ["claude-3-5-sonnet-20241022"]
small_models = ["claude-3-5-haiku-20241022"]
```

Set your environment variables before starting:
```bash
export OPENAI_API_KEY="sk-your-actual-openai-key"
export ANTHROPIC_API_KEY="sk-ant-your-actual-anthropic-key"
```

**Configuration File Locations:**
- Default location: `$HOME/.config/claude-code-proxy/providers.toml`
- Custom location: Any path you specify

### 3. Start Server

#### Using Justfile (Recommended)

```bash
# Start with default config file ($HOME/.config/claude-code-proxy/providers.toml)
just load

# Start with custom TOML config file
just load_toml path/to/your/config.toml

# List all available commands
just list
```

#### Direct Commands

```bash
# Direct run with default config
python start_proxy.py

# Or with UV
uv run claude-code-proxy

# With custom TOML config file
uv run claude-code-proxy --conf path/to/config.toml
python start_proxy.py --conf path/to/config.toml
```

### 4. Use with Claude Code

```bash
# If ANTHROPIC_API_KEY is not set in the proxy:
ANTHROPIC_BASE_URL=http://localhost:8082 ANTHROPIC_API_KEY="any-value" claude

# If ANTHROPIC_API_KEY is set in the proxy:
ANTHROPIC_BASE_URL=http://localhost:8082 ANTHROPIC_API_KEY="exact-matching-key" claude
```

## Configuration

CC-Proxy now uses **TOML configuration files only**. All configuration must be specified in a TOML file.

### TOML Configuration Structure

```toml
[config]
port = 8082
anthropic_api_key = ""  # Optional: for client validation
log_level = "INFO"
big_model = "gpt-4o"
middle_model = "gpt-4o"
small_model = "gpt-4o-mini"
max_tokens_limit = 4096
request_timeout = 90

[[provider]]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
env_key = "OPENAI_API_KEY"  # Recommended: Load API key from environment
# api_key = "your-api-key"  # Alternative: Direct API key (not recommended)
big_models = ["gpt-4o"]
middle_models = ["gpt-4o"]
small_models = ["gpt-4o-mini"]
```

### Configuration Options

**Server Settings:**
- `port` - Server port (default: `8082`)
- `log_level` - Logging level (default: `WARNING`)
- `max_tokens_limit` - Token limit (default: `4096`)
- `request_timeout` - Request timeout in seconds (default: `90`)

**Security:**
- `anthropic_api_key` - Expected Anthropic API key for client validation
  - If set, clients must provide this exact API key to access the proxy
  - If not set, any API key will be accepted

**Model Configuration:**
- `big_model` - Model for Claude opus requests (default: `gpt-4o`)
- `middle_model` - Model for Claude sonnet requests (default: `gpt-4o`)
- `small_model` - Model for Claude haiku requests (default: `gpt-4o-mini`)

**Provider Configuration:**
- `name` - Provider identifier
- `base_url` - API base URL
- `api_key` - API key for the provider (not recommended for production)
- `env_key` - Name of environment variable containing the API key (recommended for security)
- `provider_type` - Provider type: `"openai"` (default) or `"anthropic"` (native support, no conversion)
- `big_models`, `middle_models`, `small_models` - Available models for each tier

**Note:** Use `env_key` instead of `api_key` for better security. If both are specified, `env_key` takes priority.

### Model Mapping

The proxy maps Claude model requests to your configured models:

| Claude Request                 | Mapped To     | Default Model      |
| ------------------------------ | ------------- | ------------------ |
| Models with "haiku"            | `small_model` | `gpt-4o-mini`     |
| Models with "sonnet"           | `middle_model`| `gpt-4o`          |
| Models with "opus"             | `big_model`   | `gpt-4o`          |

### Provider Examples

#### OpenAI (Secure Configuration - Recommended)

```toml
[config]
port = 8082
big_model = "gpt-4o"
middle_model = "gpt-4o"
small_model = "gpt-4o-mini"

[[provider]]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
env_key = "OPENAI_API_KEY"  # Load API key from environment variable
big_models = ["gpt-4o"]
middle_models = ["gpt-4o"]
small_models = ["gpt-4o-mini"]
```

Set the environment variable before starting:
```bash
export OPENAI_API_KEY="sk-your-actual-openai-key"
just load_toml /path/to/your/config.toml
```

#### OpenAI (Direct API Key - Development Only)

```toml
[[provider]]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
api_key = "sk-your-openai-key"  # Not recommended for production
big_models = ["gpt-4o"]
middle_models = ["gpt-4o"]
small_models = ["gpt-4o-mini"]
```

#### Azure OpenAI

```toml
[config]
port = 8082
big_model = "gpt-4"
middle_model = "gpt-4"
small_model = "gpt-35-turbo"

[[provider]]
name = "Azure"
base_url = "https://your-resource.openai.azure.com/openai/deployments/your-deployment"
env_key = "AZURE_OPENAI_API_KEY"  # Secure: load from environment
big_models = ["gpt-4"]
middle_models = ["gpt-4"]
small_models = ["gpt-35-turbo"]
```

Set the environment variable:
```bash
export AZURE_OPENAI_API_KEY="your-actual-azure-key"
```

#### Local Models (Ollama)

```toml
[config]
port = 8082
big_model = "llama3.1:70b"
middle_model = "llama3.1:70b"
small_model = "llama3.1:8b"

[[provider]]
name = "Ollama"
base_url = "http://localhost:11434/v1"
api_key = "dummy-key"  # Required but can be dummy
big_models = ["llama3.1:70b"]
middle_models = ["llama3.1:70b"]
small_models = ["llama3.1:8b"]
```

#### Other Providers

Any OpenAI-compatible API can be used by setting the appropriate `base_url` in the provider configuration.

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
