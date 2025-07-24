# DeepSeek Model Support

This document explains the DeepSeek model support in CC-Proxy, including the special transformer implementation that enhances tool usage.

## Problem Statement

DeepSeek models have an issue where they become less proactive in using tools over time in long conversations. Initially, models will actively call tools, but after several rounds of dialogue, they tend to only return text responses and ignore available tools.

## Solution: DeepSeek Transformer

The transformer system implements the following enhancements for DeepSeek models:

1. Forces tool usage by setting `tool_choice="required"` when tools are available
2. Adds an `ExitTool` to allow graceful exit from tool mode
3. Injects a system prompt to encourage appropriate tool usage
4. Handles DeepSeek-specific parameters like `max_output`

## Configuration

DeepSeek transformer can be configured in the `providers.toml` file:

```toml
[transformers.deepseek]
enabled = true
providers = ["deepseek"]
models = ["deepseek-*"]
max_output = 8000
```

Configuration options:
- `enabled`: Whether the transformer is enabled (default: true)
- `providers`: List of providers the transformer should apply to
- `models`: List of models the transformer should apply to
- `max_output`: Maximum output tokens for DeepSeek models (default: 8192)

## How It Works

### Tool Mode Enforcement

When tools are available in a request to a DeepSeek model, the transformer:

1. Sets `tool_choice="required"` to force the model to use at least one tool
2. Adds a system message explaining that tool usage is expected
3. Adds an `ExitTool` that can be called when no other tool is appropriate

### ExitTool

The `ExitTool` allows the model to exit tool mode gracefully by providing a text response:

```json
{
  "name": "ExitTool",
  "description": "Use this tool when you are in tool mode and have completed the task.",
  "parameters": {
    "type": "object",
    "properties": {
      "response": {
        "type": "string",
        "description": "Your response will be forwarded to the user exactly as returned."
      }
    },
    "required": ["response"]
  }
}
```

When the model calls `ExitTool`, the transformer converts the tool call into a regular text response, making it seamless for the client application.


### Response JSON Repairing 

DeepSeek models may return JSON content wrapped in markdown code blocks instead of pure JSON. The transformer automatically repairs these responses by extracting the JSON content from the code blocks.

For example, the transformer converts responses from:

```
{ "content": "```json\n{\n \"isNewTopic\": true,\n \"title\": \"Code Structure Improvement\"\n}\n```", "tool_calls": {}, "stop_reason": "end_turn" }
```

to:

```
{ "content": "{\n \"isNewTopic\": true,\n \"title\": \"Code Structure Improvement\"\n}\n", "tool_calls": {}, "stop_reason": "end_turn" }
```

This ensures that clients receive properly formatted JSON content without markdown code block wrappers. The repairing functionality handles both regular and streaming responses, and only modifies content when valid JSON is detected within code blocks.



## Usage

No special client-side configuration is required. The transformer is automatically applied to requests for DeepSeek models.

## Limitations

- The `tool_choice="required"` parameter may cause unnecessary tool calls for simple queries
- This approach may consume more tokens due to additional system messages and potentially unnecessary tool calls

## Example

When using tools with DeepSeek models, the transformer ensures consistent tool usage by forcing the model to either use a relevant tool or explicitly call `ExitTool` when a direct text response is more appropriate.