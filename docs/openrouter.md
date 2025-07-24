# OpenRouter Support

This document explains the OpenRouter support in CC-Proxy, including the specialized transformer implementation that adds cache_control functionality.

## Problem Statement

According to the requirements, OpenRouter needs to use `cache_control` parameters to enable proper caching. Without these parameters, each request may incur unnecessary costs and delay responses.

## Solution: OpenRouterTransformer

The transformer system implements enhancements for OpenRouter to add cache control parameters:

## Configuration

OpenRouter transformer can be configured in the `providers.toml` file:

```toml
[transformers.openrouter]
enabled = true
providers = ["openrouter"]
models = ["*"]
cache_control = { ttl = 3600, refresh = "force" } # 1 hour cache with forced refresh
```

Configuration options:
- `enabled`: Whether the transformer is enabled (default: true)
- `providers`: List of providers the transformer should apply to
- `models`: List of models the transformer should apply to (use "*" for all models)

## How It Works

### Cache Control Implementation

When a request is sent to OpenRouter, the transformer:

1. Adds an `extra_query` object if it doesn't exist
2. Adds a `cache_control` object within `extra_query` with the configured parameters
3. The OpenRouter service will respect these parameters and apply caching accordingly

For example, with the default configuration, responses will be cached for 1 hour, and the cache will be used when available.

## Provider Configuration

To use OpenRouter as a provider, add it to your `providers.toml` file:

```toml
[[provider]]
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
api_key="your-openrouter-api-key"
big_models=["anthropic/claude-3-opus-20240229", "openai/gpt-4o"]
middle_models=["anthropic/claude-3-sonnet-20240229"]
small_models=["anthropic/claude-3-haiku-20240307"]
```

## Limitations

- The cache_control functionality is specific to OpenRouter and is not used by other providers
- Cache behavior depends on OpenRouter's implementation and may change based on their service updates

## Benefits

By using the OpenRouterTransformer:

1. Reduced API costs through effective caching
2. Faster response times for repeated or similar requests
3. More efficient use of OpenRouter's services