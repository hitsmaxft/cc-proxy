# Model Transformers

The Model Transformer system allows for modifying requests and responses to better support different model providers and improve compatibility between them. This document explains how the transformer system works and how to create your own transformers.

## Architecture

The transformer system consists of several key components:

1. **AbstractTransformer**: Base class for all transformers
2. **TransformerRegistry**: Registry for discovering and loading transformers
3. **TransformerPipeline**: Pipeline for applying transformers to requests and responses
4. **TransformerConfig**: Configuration system for transformers

### Request/Response Flow

When a request is sent to a model provider, the following transformations occur:

```
Request -> transformRequestIn -> transformRequestOut -> Provider API -> transformResponseIn -> transformResponseOut -> Response
```

For streaming responses, the transformations are applied to each chunk:

```
StreamChunk -> transformStreamingResponseIn -> transformStreamingResponseOut -> Streamed Response
```

## Creating a Transformer

To create a new transformer, follow these steps:

1. Create a new file in `src/conversion/transformer/transformers/` (e.g., `my_transformer.py`)
2. Create a class that inherits from `AbstractTransformer`
3. Register your transformer in the `__init__.py` file

### Example Transformer

Here's a simple example of a transformer that adds a system message to every request:

```python
from src.conversion.transformer.base import AbstractTransformer

class SystemMessageTransformer(AbstractTransformer):
    name = "system_message"
    
    def should_apply_to(self, provider: str, model: str) -> bool:
        # Apply this transformer only to specific providers or models
        return provider.lower() == "openai"
    
    def transformRequestIn(self, request: Dict[str, Any]) -> Dict[str, Any]:
        # Add a system message if there are messages but no system message yet
        if "messages" in request:
            has_system = any(msg.get("role") == "system" for msg in request["messages"])
            if not has_system:
                request["messages"].insert(0, {
                    "role": "system",
                    "content": "You are a helpful assistant."
                })
        return request
```

### Available Transformation Methods

Each transformer can implement the following methods:

- `transformRequestIn`: Transform a request before sending it to the provider
- `transformRequestOut`: Final transformation of a request before sending
- `transformResponseIn`: Transform a response received from the provider
- `transformResponseOut`: Final transformation of a response before returning to the client
- `transformStreamingResponseIn`: Transform a streaming response chunk from the provider
- `transformStreamingResponseOut`: Final transformation of a streaming response chunk

## Built-in Transformers

### ToolUseTransformer

The `ToolUseTransformer` enhances tool usage for models like DeepSeek by:

1. Injecting a system reminder to encourage tool use
2. Setting `tool_choice` to "required" to force tool calling
3. Adding an `ExitTool` that allows graceful exit from tool mode
4. Handling `ExitTool` responses by converting them back to regular text responses

By default, this transformer applies to DeepSeek models but can be configured to work with other providers.

## Configuration

Transformers can be configured in the application configuration. For example:

```python
# Example configuration
config.transformers = {
    "tooluse": {
        "enabled": True,
        "providers": ["deepseek"],
        "models": ["*"]
    },
    "system_message": {
        "enabled": True,
        "providers": ["openai"],
        "models": ["gpt-3.5-turbo", "gpt-4"]
    }
}
```

Configuration options:
- `enabled`: Whether the transformer is enabled (default: True)
- `providers`: List of providers the transformer should apply to
- `models`: List of models the transformer should apply to (use "*" for all models)

## Testing Transformers

To test your transformer, you can add test cases to `tests/test_transformer.py`. Here's an example:

```python
def test_my_transformer(self):
    transformer = MyTransformer()
    request = {"messages": [{"role": "user", "content": "Hello"}]}
    transformed = transformer.transformRequestIn(request)
    # Assert your expected transformations
    self.assertEqual(transformed["messages"][0]["role"], "system")
```

Run the tests with:

```
python -m unittest tests/test_transformer.py
```

## Adding a New Transformer to the Registry

After creating your transformer, add it to the registry by updating `src/conversion/transformer/transformers/__init__.py`:

```python
from src.conversion.transformer.transformers.tooluse import ToolUseTransformer
from src.conversion.transformer.transformers.my_transformer import MyTransformer

__all__ = [
    'ToolUseTransformer',
    'MyTransformer',
]
```

The transformer will be automatically discovered and registered when the application starts.