<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CC-Proxy** is a sophisticated proxy server that enables **Claude Code CLI** to work with OpenAI-compatible API providers. It provides complete Claude API compatibility while offering enhanced features like web UI management, cost tracking, and message history storage.

## Key Architectural Patterns

### Core Translation Architecture
- **Request Conversion**: Claude API format → OpenAI API format via `src/conversion/request_converter.py`
- **Response Conversion**: OpenAI API format → Claude API format via `src/conversion/response_converter.py`
- **Transformer Pipeline**: Pluggable architecture in `src/conversion/transformer/` for provider-specific customizations

### Model Mapping Strategy
- **BIG_MODEL**: Maps to Claude Opus requests (configurable, default: gpt-4o)
- **MIDDLE_MODEL**: Maps to Claude Sonnet requests (configurable, default: gpt-4o)
- **SMALL_MODEL**: Maps to Claude Haiku requests (configurable, default: gpt-4o-mini)

### Data Flow
1. **Claude Code** → HTTP Request to `/v1/messages`
2. **API Validation** → `validate_api_key()` in endpoints.py
3. **Format Conversion** → Claude → OpenAI format conversion
4. **Model Selection** → `model_manager.map_claude_model_to_openai()`
5. **Provider Request** → OpenAI/Compatible API call
6. **Response Conversion** → OpenAI → Claude format conversion
7. **History Logging** → Store in SQLite via `MessageHistoryDatabase`

## Essential Commands

### Development Setup
```bash
# Install dependencies (UV recommended)
uv sync

# Install development dependencies
uv run pytest tests/  

# Format code
uv run black src/
uv run isort src/

# Type checking
uv run mypy src/
```

### Run Server
```bash
# With Justfile (recommended)
just load                          # Default config ($HOME/.config/claude-code-proxy/providers.toml)
just load_toml /path/to/config.toml  # Custom TOML config

# Direct commands
python start_proxy.py --conf /path/to/config.toml
uv run claude-code-proxy --conf /path/to/config.toml
```

### Testing
```bash
# Run all tests
python tests/test_main.py

# Run specific test file
uv run pytest tests/test_main.py -v
uv run pytest tests/test_transformer.py -v

# Test against running server (requires server running)
python tests/test_main.py
```

### Configuration Examples

#### Basic Configuration with Direct API Keys
```toml
# TOML config (providers.toml)
[config]
port = 8082
log_level = "INFO"
big_model = "gpt-4o"
middle_model = "gpt-4o"
small_model = "gpt-4o-mini"

[[provider]]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
api_key = "your-api-key"  # Direct API key (not recommended for production)
big_models = ["gpt-4o"]
middle_models = ["gpt-4o"]
small_models = ["gpt-4o-mini"]
```

#### Secure Configuration with Environment Variables (Recommended)
```toml
# TOML config (providers.toml) - Secure approach
[config]
port = 8082
log_level = "INFO"
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

[[provider]]
name = "Azure-OpenAI"
base_url = "https://your-resource.openai.azure.com/openai/deployments/your-deployment"
env_key = "AZURE_OPENAI_API_KEY"  # Each provider can use different env vars
big_models = ["gpt-4"]
middle_models = ["gpt-4"]
small_models = ["gpt-35-turbo"]
```

#### Setting Environment Variables
```bash
# Set environment variables before starting the proxy
export OPENAI_API_KEY="sk-your-actual-openai-key"
export AZURE_OPENAI_API_KEY="your-azure-key"

# Then start the proxy
just load_toml /path/to/your/config.toml
```

#### Mixed Configuration
```toml
# You can mix direct keys and environment variables
# Note: env_key takes priority over api_key if both are specified

[[provider]]
name = "OpenAI-Prod"
base_url = "https://api.openai.com/v1"
env_key = "OPENAI_PROD_KEY"  # Uses environment variable (recommended)
big_models = ["gpt-4o"]
middle_models = ["gpt-4o"]
small_models = ["gpt-4o-mini"]

[[provider]]
name = "OpenAI-Dev"
base_url = "https://api.openai.com/v1"
api_key = "sk-dev-test-key"  # Direct key for development only
big_models = ["gpt-4o-mini"]
middle_models = ["gpt-4o-mini"]
small_models = ["gpt-4o-mini"]
```

## Key Components

### Core System
- **src/main.py**: Application entry point, FastAPI setup
- **src/core/config.py**: Configuration management (ENV + TOML)
- **src/core/client.py**: OpenAI client wrapper with timeout/retry logic
- **src/core/model_manager.py**: Model mapping and management

### API Layer
- **src/api/endpoints.py**: FastAPI routes with validation, history logging
- **/v1/messages**: Primary Claude-compatible endpoint
- **/health**: Health check
- **/api/config/**: Dynamic configuration management
- **/api/history/**: Message history retrieval

### Conversion System
- **src/conversion/request_converter.py**: Claude → OpenAI format conversion
- **src/conversion/response_converter.py**: OpenAI → Claude format conversion  
- **src/conversion/transformer/**: Pluggable transformers for provider adaptations

### Storage & History
- **src/storage/database.py**: SQLite database for message history
- **src/services/history_manager.py**: High-level history operations
- **Database file**: proxy.db (default), configurable via DB_FILE env var

## Advanced Features

### Transformer Architecture
Transformers in `src/conversion/transformer/` provide provider-specific customizations:
- **deepseek.py**: DeepSeek provider adaptations
- **openrouter.py**: OpenRouter-specific handling  
- **tooluse.py**: Tool use responses transformations

### Web UI Management
- Accessible at `http://localhost:8082/`
- Real-time model configuration
- Usage analytics and cost tracking
- Message history with search/filters
- Token usage visualization

### Security & Validation
- **API Key Security**: Support for environment variables via `env_key` to avoid storing sensitive keys in configuration files
- **API Key Validation**: Optional `ANTHROPIC_API_KEY` for client validation
- **Model Selection**: Dynamic model switching via web UI
- **Rate Limiting**: Configurable timeouts and retries

## Monitoring & Debugging

### Available Endpoints
```bash
# Health check
curl http://localhost:8082/health

# Test API connectivity
curl http://localhost:8082/test-connection

# Get current config
curl http://localhost:8082/api/config/get

# Recent message history
curl "http://localhost:8082/api/history?limit=10"

# Usage summary
curl http://localhost:8082/api/summary
```

### Log Levels
- DEBUG: Detailed request/response logging
- INFO: General operation status
- WARNING: Non-critical issues
- ERROR: Critical errors

### Claude Code Integration
```bash
# Set up Claude Code to use proxy
export ANTHROPIC_BASE_URL=http://localhost:8082
claude
```

## Common Patterns

### Adding New Transformers
1. Create in `src/conversion/transformer/transformers/`
2. Inherit from `AbstractTransformer`
3. Register in `src/conversion/transformer/registry.py`
4. Implement required transformation methods

### Model Configuration Updates
1. **Dynamic**: Use web UI at http://localhost:8082/
2. **Via API**: POST to `/api/config/update`
3. **Database Persistence**: Changes saved to SQLite automatically

### Provider Support
Supports any OpenAI-compatible API:
- OpenAI (default)
- Azure OpenAI (with AZURE_API_VERSION)
- Ollama local models
- Anthropic via proxy
- Any custom OpenAI-compatible endpoint