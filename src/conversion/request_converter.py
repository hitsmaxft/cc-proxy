import json
from typing import Dict, Any, List
from venv import logger
from src.core.constants import Constants
from src.core.model_manager import ModelConfig, ModelManager
from src.models.claude import ClaudeMessagesRequest, ClaudeMessage, WebSearchTool
from src.core.config import config
import logging

logger = logging.getLogger(__name__)


def get_web_search(claude_request: ClaudeMessagesRequest):
    if claude_request.tools:
        for tool in claude_request.tools:
            if tool.type == "web_search_20250305":
                return True
    return False


def get_mode_config(model: str, model_manager: ModelManager) -> ModelConfig:
    # Map model
    openai_model: ModelConfig = model_manager.map_claude_model_to_openai(model)
    return openai_model


def convert_claude_to_openai(
    claude_request: ClaudeMessagesRequest, model_manager: ModelManager
) -> Dict[str, Any]:
    """Convert Claude API request format to OpenAI format."""

    # Map model
    openai_model: ModelConfig = model_manager.map_claude_model_to_openai(
        claude_request.model
    )

    # Convert messages
    openai_messages = []

    extra_query: Dict[str, Any] = []

    if model_manager.enable_websearch() and get_web_search(claude_request):
        # use plugin for search on claude
        openai_model.model = f"{openai_model.model}:online"
        extra_query["plugins"] = [{"id": "web"}]

    # Add system message if present
    if claude_request.system:
        system_text = ""
        if isinstance(claude_request.system, str):
            system_text = claude_request.system
        elif isinstance(claude_request.system, list):
            text_parts = []
            for block in claude_request.system:
                if hasattr(block, "type") and block.type == Constants.CONTENT_TEXT:
                    text_parts.append(block.text)
                elif (
                    isinstance(block, dict)
                    and block.get("type") == Constants.CONTENT_TEXT
                ):
                    text_parts.append(block.get("text", ""))
            system_text = "\n\n".join(text_parts)

        if system_text.strip():
            openai_messages.append(
                {"role": Constants.ROLE_SYSTEM, "content": system_text.strip()}
            )

    # Process Claude messages
    i = 0
    while i < len(claude_request.messages):
        msg = claude_request.messages[i]

        if msg.role == Constants.ROLE_USER:
            # Check if this user message contains mixed content (text + tool_result)
            if isinstance(msg.content, list) and any(
                block.type == Constants.CONTENT_TOOL_RESULT
                for block in msg.content
                if hasattr(block, "type")
            ):
                # Split mixed content message into separate messages
                mixed_messages = convert_claude_mixed_content_message(msg)
                openai_messages.extend(mixed_messages)
            else:
                # Normal user message
                openai_message = convert_claude_user_message(msg)
                openai_messages.append(openai_message)
        elif msg.role == Constants.ROLE_ASSISTANT:
            openai_message = convert_claude_assistant_message(msg)
            openai_messages.append(openai_message)

            # Check if next message contains tool results (legacy handling)
            if i + 1 < len(claude_request.messages):
                next_msg = claude_request.messages[i + 1]
                if (
                    next_msg.role == Constants.ROLE_USER
                    and isinstance(next_msg.content, list)
                    and any(
                        block.type == Constants.CONTENT_TOOL_RESULT
                        for block in next_msg.content
                        if hasattr(block, "type")
                    )
                ):
                    # This will be handled by the user message processing above
                    # No need to skip here, let the normal flow handle it
                    pass

        i += 1

    # Build OpenAI request
    openai_request = {
        "messages": openai_messages,
        "max_tokens": min(
            max(claude_request.max_tokens, config.min_tokens_limit),
            config.max_tokens_limit,
        ),
        "temperature": claude_request.temperature,
        "stream": claude_request.stream,
        "model": openai_model["model"],
    }

    # add custom query for websearch or other custom feature
    if extra_query:
        openai_request["extra_query"] = extra_query

    # Enhanced logging with provider information
    provider_info = f" (Provider: {openai_model['provider']})" if 'provider' in openai_model else ""
    logger.debug(
        f"Converted Claude request to OpenAI format for model {openai_model['model']}{provider_info}: {json.dumps(openai_request, indent=2, ensure_ascii=False)}"
    )
    # Add optional parameters
    if claude_request.stop_sequences:
        openai_request["stop"] = claude_request.stop_sequences
    if claude_request.top_p is not None:
        openai_request["top_p"] = claude_request.top_p

    # Convert tools
    if claude_request.tools:
        openai_tools = []
        for tool in claude_request.tools:
            if tool.type == "web_search_20250305":
                continue

            if tool.name and tool.name.strip():
                openai_tools.append(
                    {
                        "type": Constants.TOOL_FUNCTION,
                        Constants.TOOL_FUNCTION: {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.input_schema,
                        },
                    }
                )
        if openai_tools:
            openai_request["tools"] = openai_tools

    # Convert tool choice
    if claude_request.tool_choice:
        choice_type = claude_request.tool_choice.get("type")
        if choice_type == "auto":
            openai_request["tool_choice"] = "auto"
        elif choice_type == "any":
            openai_request["tool_choice"] = "auto"
        elif choice_type == "tool" and "name" in claude_request.tool_choice:
            openai_request["tool_choice"] = {
                "type": Constants.TOOL_FUNCTION,
                Constants.TOOL_FUNCTION: {"name": claude_request.tool_choice["name"]},
            }
        else:
            openai_request["tool_choice"] = "auto"

    return openai_request


def convert_claude_user_message(msg: ClaudeMessage) -> Dict[str, Any]:
    """Convert Claude user message to OpenAI format."""
    if msg.content is None:
        return {"role": Constants.ROLE_USER, "content": ""}

    if isinstance(msg.content, str):
        return {"role": Constants.ROLE_USER, "content": msg.content}

    # Handle multimodal content
    openai_content = []
    for block in msg.content:
        if block.type == Constants.CONTENT_TEXT:
            openai_content.append({"type": "text", "text": block.text})
        elif block.type == Constants.CONTENT_IMAGE:
            # Convert Claude image format to OpenAI format
            if (
                isinstance(block.source, dict)
                and block.source.get("type") == "base64"
                and "media_type" in block.source
                and "data" in block.source
            ):
                openai_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{block.source['media_type']};base64,{block.source['data']}"
                        },
                    }
                )

    if len(openai_content) == 1 and openai_content[0]["type"] == "text":
        return {"role": Constants.ROLE_USER, "content": openai_content[0]["text"]}
    else:
        return {"role": Constants.ROLE_USER, "content": openai_content}


def convert_claude_assistant_message(msg: ClaudeMessage) -> Dict[str, Any]:
    """Convert Claude assistant message to OpenAI format."""
    text_parts = []
    tool_calls = []

    if msg.content is None:
        return {"role": Constants.ROLE_ASSISTANT, "content": None}

    if isinstance(msg.content, str):
        return {"role": Constants.ROLE_ASSISTANT, "content": msg.content}

    for block in msg.content:
        if block.type == Constants.CONTENT_TEXT:
            text_parts.append(block.text)
        elif block.type == Constants.CONTENT_TOOL_USE:
            tool_calls.append(
                {
                    "id": block.id,
                    "type": Constants.TOOL_FUNCTION,
                    Constants.TOOL_FUNCTION: {
                        "name": block.name,
                        "arguments": json.dumps(block.input, ensure_ascii=False),
                    },
                }
            )

    openai_message = {"role": Constants.ROLE_ASSISTANT}

    # Set content
    if text_parts:
        openai_message["content"] = "".join(text_parts)
    else:
        openai_message["content"] = None

    # Set tool calls
    if tool_calls:
        openai_message["tool_calls"] = tool_calls

    return openai_message


def convert_claude_tool_results(msg: ClaudeMessage) -> List[Dict[str, Any]]:
    """Convert Claude tool results to OpenAI format."""
    tool_messages = []

    if isinstance(msg.content, list):
        for block in msg.content:
            if block.type == Constants.CONTENT_TOOL_RESULT:
                content = parse_tool_result_content(block.content)
                tool_messages.append(
                    {
                        "role": Constants.ROLE_TOOL,
                        "tool_call_id": block.tool_use_id,
                        "content": content,
                    }
                )

    return tool_messages


def convert_claude_mixed_content_message(msg: ClaudeMessage) -> List[Dict[str, Any]]:
    """
    Convert a Claude message containing mixed content (text + tool_result) into separate OpenAI messages.
    This ensures no content is lost when a user message contains both text and tool results.

    Args:
        msg: ClaudeMessage with mixed content

    Returns:
        List of OpenAI format messages, preserving all content
    """
    messages = []

    if not isinstance(msg.content, list):
        # Fallback to normal processing
        return [convert_claude_user_message(msg)]

    if len(msg.content) == 1  and any(
                block.type == Constants.CONTENT_TOOL_RESULT
                for block in msg.content
                if hasattr(block, "type")
            ):
        return convert_claude_tool_results(msg)

    # Separate content by type
    text_blocks = []
    image_blocks = []

    for block in msg.content:
        if hasattr(block, "type"):
            if block.type == Constants.CONTENT_TEXT:
                text_blocks.append(block)
            elif block.type == Constants.CONTENT_TOOL_RESULT:
                # add at the beginning
                if (len(messages) > 0):
                    raise ValueError("Too many Tool result message in a mixed user message")
                content = parse_tool_result_content(block.content)
                messages.append(
                    {
                        "role": Constants.ROLE_TOOL,
                        "tool_call_id": block.tool_use_id,
                        "content": content,
                    }
                )
            elif block.type == Constants.CONTENT_IMAGE:
                image_blocks.append(block)

    text_blocks.extend(image_blocks)

    # Create user message with text and image content (if any)
    if text_blocks:
        user_content = []

        # Add text content
        for block in text_blocks:
            if block.type == Constants.CONTENT_TEXT:
                user_content.append({"type": "text", "text": block.text})
            else:
                if (
                    isinstance(block.source, dict)
                    and block.source.get("type") == "base64"
                    and "media_type" in block.source
                    and "data" in block.source
                ):
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{block.source['media_type']};base64,{block.source['data']}"
                            },
                        }
                    )
                ## log error fro mailformat image message

        if user_content:
            # If only one text block, use string format for simplicity
            if len(user_content) == 1 and user_content[0]["type"] == "text":
                messages.append({
                    "role": Constants.ROLE_USER,
                    "content": user_content[0]["text"]
                })
            else:
                messages.append({
                    "role": Constants.ROLE_USER,
                    "content": user_content
                })
    return messages


def parse_tool_result_content(content):
    """Parse and normalize tool result content into a string format."""
    if content is None:
        return "No content provided"

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        result_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == Constants.CONTENT_TEXT:
                result_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                result_parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    result_parts.append(item.get("text", ""))
                else:
                    try:
                        result_parts.append(json.dumps(item, ensure_ascii=False))
                    except:
                        result_parts.append(str(item))
        return "\n".join(result_parts).strip()

    if isinstance(content, dict):
        if content.get("type") == Constants.CONTENT_TEXT:
            return content.get("text", "")
        try:
            return json.dumps(content, ensure_ascii=False)
        except:
            return str(content)

    try:
        return str(content)
    except:
        return "Unparseable content"
