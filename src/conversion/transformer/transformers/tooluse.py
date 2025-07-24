import json
import logging
from typing import Dict, Any, Optional

from src.conversion.transformer.base import AbstractTransformer

logger = logging.getLogger(__name__)


class ToolUseTransformer(AbstractTransformer):
    """
    Transformer to enhance tool usage for models like DeepSeek.

    This transformer:
    1. Injects a system reminder to encourage tool use
    2. Sets tool_choice to "required" to force tool calling
    3. Adds an ExitTool that allows graceful exit from tool mode
    4. Handles ExitTool responses by converting them back to regular text responses
    """

    name = "tooluse"

    def should_apply_to(self, provider: str, model: str) -> bool:
        """
        Apply this transformer to DeepSeek models by default.
        Can be overridden with configuration.

        Args:
            provider: The provider name
            model: The model name

        Returns:
            True if transformer should be applied
        """
        provider_match = self.config.get("providers", ["deepseek"])
        model_match = self.config.get("models", ["*"])

        if provider.lower() in [p.lower() for p in provider_match]:
            if "*" in model_match:
                return True
            return any(m.lower() in model.lower() for m in model_match)

        return False

    def transformRequestIn(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a request to enhance tool usage.

        Args:
            request: The unified chat request object

        Returns:
            Modified request with tool mode enhancements
        """
        # Only apply transformation if tools are provided
        if not request.get("tools"):
            return request

        # Add system reminder to encourage tool use
        if "messages" in request:
            request["messages"].append(
                {
                    "role": "system",
                    "content": (
                        "<system-reminder>Tool mode is active. The user expects you to proactively "
                        "execute the most suitable tool to help complete the task. \n"
                        "Before invoking a tool, you must carefully evaluate whether it matches the current task. "
                        "If no available tool is appropriate for the task, you MUST call the `ExitTool` to exit "
                        "tool mode — this is the only valid way to terminate tool mode.\n"
                        "Always prioritize completing the user's task effectively and efficiently by "
                        "using tools whenever appropriate.</system-reminder>"
                    ),
                }
            )

        # Force tool calling by setting tool_choice to required
        request["tool_choice"] = "required"

        # Add ExitTool to allow graceful exit from tool mode
        request["tools"].insert(
            0,
            {
                "type": "function",
                "function": {
                    "name": "ExitTool",
                    "description": (
                        "Use this tool when you are in tool mode and have completed the task. "
                        "This is the only valid way to exit tool mode.\n"
                        "IMPORTANT: Before using this tool, ensure that none of the available tools are "
                        "applicable to the current task. You must evaluate all available options — only "
                        "if no suitable tool can help you complete the task should you use ExitTool to "
                        "terminate tool mode.\n"
                        "Examples:\n"
                        '1. Task: "Use a tool to summarize this document" — Do not use ExitTool if a '
                        "summarization tool is available.\n"
                        '2. Task: "What\'s the weather today?" — If no tool is available to answer, use '
                        "ExitTool after reasoning that none can fulfill the task."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "response": {
                                "type": "string",
                                "description": (
                                    "Your response will be forwarded to the user exactly as returned — "
                                    "the tool will not modify or post-process it in any way."
                                ),
                            }
                        },
                        "required": ["response"],
                    },
                },
            },
        )

        return request

    def transformResponseIn(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a response to handle ExitTool calls.

        Args:
            response: The unified chat response object

        Returns:
            Modified response with ExitTool output converted to regular text
        """
        # Check if the response contains choices with messages
        if "choices" not in response or not response["choices"]:
            return response

        # Get the first choice's message
        choice = response["choices"][0]
        if "message" not in choice:
            return response

        message = choice["message"]

        # Check if the message contains tool calls
        if not message.get("tool_calls"):
            return response

        # Look for ExitTool usage
        for tool_call in message.get("tool_calls", []):
            if tool_call.get("function", {}).get("name") == "ExitTool":
                try:
                    # Parse the arguments
                    arguments = json.loads(tool_call["function"].get("arguments", "{}"))
                    # Replace the tool call with the response content
                    message["content"] = arguments.get("response", "")
                    # Remove all tool calls
                    del message["tool_calls"]
                    break
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Error processing ExitTool response: {e}")

        return response

    async def transformStreamingResponseIn(
        self, response_chunk: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform a streaming response chunk to handle ExitTool calls.

        Args:
            response_chunk: A chunk of the streaming response

        Returns:
            Modified response chunk
        """
        # This is a simplified version that checks if a complete ExitTool call exists
        # A more complex implementation would need to track state across chunks

        if "choices" not in response_chunk or not response_chunk["choices"]:
            return response_chunk

        choice = response_chunk["choices"][0]
        delta = choice.get("delta", {})

        # If this chunk contains a complete tool call
        if "tool_calls" in delta:
            for tool_call in delta["tool_calls"]:
                function = tool_call.get("function", {})
                if function.get("name") == "ExitTool" and "arguments" in function:
                    try:
                        arguments = json.loads(function["arguments"])
                        if "response" in arguments:
                            # Convert the ExitTool call to content
                            delta["content"] = arguments["response"]
                            del delta["tool_calls"]
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(
                            f"Error processing streaming ExitTool response: {e}"
                        )

        return response_chunk
