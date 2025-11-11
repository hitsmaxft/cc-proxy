# Native Anthropic Provider Migration Guide

## Overview

CC-Proxy now supports native Anthropic API communication, eliminating the need for format conversion when using Anthropic endpoints. This results in:

- **Lower latency** - No conversion overhead
- **Better compatibility** - Direct pass-through ensures all Anthropic features work
- **Easier debugging** - Requests/responses are not modified
- **Future-proof** - New Anthropic features work without proxy updates

## Migration Steps

### 1. Update Your Configuration

Add a new Anthropic provider to your existing configuration:

```toml
[[provider]]
name = "Anthropic-Direct"
provider_type = "anthropic"  # This is the key setting
base_url = "https://api.anthropic.com"
env_key = "ANTHROPIC_API_KEY"
big_models = ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"]
middle_models = ["claude-3-5-sonnet-20241022"]
small_models = ["claude-3-5-haiku-20241022"]
```

### 2. Update Model References

Change your default model selections to use the Anthropic provider:

```toml
[config]
# Before (using OpenAI provider with conversion)
big_model = "gpt-4o"
middle_model = "gpt-4o"
small_model = "gpt-4o-mini"

# After (using native Anthropic provider)
big_model = "Anthropic-Direct:claude-3-5-sonnet-20241022"
middle_model = "Anthropic-Direct:claude-3-5-sonnet-20241022"
small_model = "Anthropic-Direct:claude-3-5-haiku-20241022"
```

### 3. Set Environment Variables

Ensure your Anthropic API key is available:

```bash
export ANTHROPIC_API_KEY="sk-ant-your-actual-key"
```

### 4. Restart CC-Proxy

```bash
just load_toml /path/to/your/config.toml
```

## Mixed Provider Usage

You can use both OpenAI and Anthropic providers simultaneously:

```toml
[config]
# You can switch between providers via the web UI
big_model = "Anthropic-Direct:claude-3-5-sonnet-20241022"

[[provider]]
name = "Anthropic-Direct"
provider_type = "anthropic"
base_url = "https://api.anthropic.com"
env_key = "ANTHROPIC_API_KEY"
big_models = ["claude-3-5-sonnet-20241022"]

[[provider]]
name = "OpenAI"
provider_type = "openai"  # or omit, as "openai" is default
base_url = "https://api.openai.com/v1"
env_key = "OPENAI_API_KEY"
big_models = ["gpt-4o"]
```

## Verification

1. Start CC-Proxy with your updated configuration
2. Visit the web UI at http://localhost:8082
3. Check the provider list shows both provider types
4. Test with Claude Code CLI:
   ```bash
   export ANTHROPIC_BASE_URL=http://localhost:8082
   claude "Hello, which model are you?"
   ```

## Rollback

If you need to revert to OpenAI-only mode:

1. Remove or comment out Anthropic providers
2. Update model selections back to OpenAI models
3. Restart CC-Proxy

The system is fully backward compatible - existing configurations continue to work unchanged.