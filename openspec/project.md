# Project Context

## Purpose
**CC-Proxy** is a sophisticated proxy server that enables Claude Code CLI to work with OpenAI-compatible API providers. The project's main goals are:

- **API Translation**: Seamlessly convert between Claude API format and OpenAI API format
- **Provider Flexibility**: Support multiple OpenAI-compatible providers (OpenAI, Azure OpenAI, Ollama, custom endpoints)
- **Enhanced Features**: Provide web UI management, cost tracking, message history storage, and usage analytics
- **Claude Code Integration**: Enable Claude Code CLI to work with any OpenAI-compatible API provider
- **Security & Management**: Secure API key handling via environment variables and dynamic configuration management

## Tech Stack

### Backend Framework
- **Python 3.9+**: Core language with modern async/await support
- **FastAPI**: High-performance async web framework for API endpoints
- **Uvicorn**: ASGI server with WebSocket support
- **Pydantic**: Data validation and serialization

### HTTP & API
- **HTTPX**: Async HTTP client with SOCKS proxy support
- **OpenAI SDK**: Official OpenAI Python client for provider communication
- **Requests**: Fallback HTTP library for synchronous operations

### Data & Storage
- **SQLite**: Local database for message history and configuration
- **aiosqlite**: Async SQLite interface for non-blocking database operations
- **TOML**: Configuration file format for provider settings

### Development Tools
- **UV**: Fast Python package manager and dependency resolver
- **Black**: Code formatter (line length 100)
- **isort**: Import sorting (Black-compatible profile)
- **MyPy**: Static type checking with strict settings
- **pytest**: Testing framework with async support

### UI & Templates
- **Jinja2**: Template engine for web UI rendering
- **WebSocket**: Real-time communication for UI updates

## Project Conventions

### Code Style
- **Line Length**: 100 characters (Black + isort configured)
- **Type Hints**: Required for all function definitions (`disallow_untyped_defs = true`)
- **Import Style**: Black-compatible isort profile with line length 100
- **Python Version**: Target Python 3.8+ syntax, runtime requires 3.9+
- **Async/Await**: Prefer async patterns for I/O operations
- **Error Handling**: Comprehensive exception handling with proper logging

### Architecture Patterns

#### Layered Architecture
- **API Layer** (`src/api/`): FastAPI endpoints, WebSocket management, request validation
- **Core Layer** (`src/core/`): Configuration, model management, client abstractions, logging
- **Conversion Layer** (`src/conversion/`): Bidirectional API format translation (Claude ↔ OpenAI)
- **Services Layer** (`src/services/`): Business logic, history management
- **Storage Layer** (`src/storage/`): Database abstractions and operations
- **Models Layer** (`src/models/`): Pydantic models for Claude, OpenAI, and history data

#### Transformer Pipeline Pattern
- **Pluggable Architecture**: Provider-specific customizations via transformers
- **Registry Pattern**: Dynamic transformer registration and selection
- **Base Classes**: Abstract transformer interfaces for consistent implementation
- **Provider Adapters**: Specific transformers for DeepSeek, OpenRouter, tool use, etc.

#### Configuration Management
- **Environment Priority**: Environment variables override TOML configuration
- **Secure Defaults**: `env_key` for API keys instead of direct storage
- **Dynamic Updates**: Runtime configuration changes via API endpoints
- **Validation**: Pydantic-based configuration validation

### Testing Strategy
- **Unit Testing**: pytest with async support (`pytest-asyncio`)
- **Integration Testing**: Full server testing against running instances
- **Test Structure**: Separate test files for different components
  - `test_main.py`: Core functionality and integration tests
  - `test_transformer.py`: Transformer pipeline testing
  - `test_config.py`: Configuration management testing
- **HTTP Testing**: Using `httpx` for async API testing
- **Coverage**: Target comprehensive coverage for critical conversion logic

### Git Workflow
- **Main Branch**: `main` (default branch for PRs)
- **Development**: Feature branches with descriptive names
- **Commit Style**: Conventional commits preferred
- **Dependencies**: UV lock file (`uv.lock`) committed for reproducible builds

## Domain Context

### API Translation Domain
- **Claude API Format**: Anthropic's native API structure with specific message formats, tool definitions
- **OpenAI API Format**: Standard format used by many providers (OpenAI, Azure, Ollama, etc.)
- **Model Mapping**: Strategic mapping of Claude model tiers (Haiku→small, Sonnet→middle, Opus→big)
- **Token Counting**: Accurate token usage tracking and cost calculation
- **Streaming**: Support for both streaming and non-streaming responses

### Proxy Server Patterns
- **Request/Response Cycle**: Intercept → Convert → Forward → Convert → Return
- **Provider Abstraction**: Unified interface for multiple OpenAI-compatible providers
- **Health Monitoring**: Connection testing and provider availability checks
- **Rate Limiting**: Configurable timeouts and retry logic

### Claude Code CLI Integration
- **Base URL Override**: `ANTHROPIC_BASE_URL=http://localhost:8086`
- **API Compatibility**: Full Claude API surface area support
- **Authentication**: Optional Anthropic API key validation for client requests

## Important Constraints

### Technical Constraints
- **Python 3.9+ Required**: Modern async/await and type hinting features
- **Single Database**: SQLite for simplicity, not designed for high concurrency
- **Memory Usage**: In-memory message history caching for performance
- **Port Configuration**: Default port 8082, configurable but must avoid conflicts

### Security Constraints
- **API Key Handling**: Never log or expose API keys in responses
- **Environment Variables**: Prefer `env_key` over direct `api_key` in configuration
- **CORS**: Web UI requires proper CORS configuration for browser access
- **Validation**: All API inputs must be validated via Pydantic models

### Compatibility Constraints
- **OpenAI API Compatibility**: Must maintain compatibility with OpenAI SDK expectations
- **Claude API Compatibility**: Must fully support Claude Code CLI requirements
- **Provider Variations**: Handle differences in OpenAI-compatible provider implementations

## External Dependencies

### Required Services
- **OpenAI API** (or compatible): Primary provider for model inference
- **Claude Code CLI**: The client application this proxy serves
- **SQLite**: Local database (no external database required)

### Optional Integrations
- **Azure OpenAI**: Enterprise OpenAI access with different authentication
- **Ollama**: Local model serving for offline/private deployments
- **OpenRouter**: Multi-provider API aggregation service
- **DeepSeek**: Alternative AI provider with specific API variations

### Development Dependencies
- **UV Package Manager**: Fast dependency resolution and virtual environment management
- **Docker**: Containerized deployment via `docker.yml`
- **Just**: Command runner for development workflows (`justfile`)

### Monitoring & Observability
- **Web UI**: Built-in dashboard at `http://localhost:8086/`
- **Health Endpoints**: `/health`, `/test-connection` for monitoring
- **Usage Analytics**: Token counting, cost tracking, request history
- **Logging**: Configurable log levels (DEBUG/INFO/WARNING/ERROR)
