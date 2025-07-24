import json
import logging
import re
from typing import Dict, Any, List

from src.conversion.transformer.base import AbstractTransformer

logger = logging.getLogger(__name__)


class DeepSeekTransformer(AbstractTransformer):
    """
    Transformer for DeepSeek models that implements tool mode enhancement.

    This transformer addresses the issue where DeepSeek models tend to become
    less proactive in tool usage over time in long conversations. It implements:

    1. Forcing tool usage with tool_choice="required" when tools are available
    2. Adding an ExitTool to allow graceful exit from tool mode
    3. Adding system prompts to encourage appropriate tool usage
    4. Handling max_output parameter specific to DeepSeek
    """

    name = "deepseek"

    def _repair_json_content(self, content: str) -> str:
        """
        Repair JSON content by extracting pure JSON from markdown code blocks.

        Args:
            content: The content string that may contain JSON in markdown code blocks

        Returns:
            The content with JSON extracted from markdown code blocks, or the original content
        """
        if not content:
            return content

        # Pattern to match JSON in markdown code blocks
        # Matches ```json\n{...}\n``` or ```json\r\n{...}\r\n```
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, content)

        if match:
            json_content = match.group(1).strip()
            # Try to validate that it's actually JSON
            try:
                # Attempt to parse as JSON to validate it
                parsed = json.loads(json_content)
                # If successful, return the clean JSON content
                return json_content
            except json.JSONDecodeError:
                # If it's not valid JSON, return the original content
                logger.debug(
                    f"Extracted content is not valid JSON: {json_content[:100]}..."
                )
                return content

        # Return original content if no JSON code block found
        return content

    def should_apply_to(self, provider: str, model: str) -> bool:
        """
        Apply this transformer to DeepSeek models.

        Args:
            provider: The provider name
            model: The model name

        Returns:
            True if transformer should be applied
        """
        model_match = "deepseek" in model.lower()

        return model_match

    def transformRequestIn(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a request for DeepSeek models.

        Args:
            request: The unified chat request object

        Returns:
            Modified request with DeepSeek-specific optimizations
        """
        # Make a copy to avoid modifying the original request
        transformed = request.copy()

        # Handle max_output parameter (DeepSeek has 8192 default)
        if "max_tokens" in transformed and transformed["max_tokens"] > 8192:
            # If explicitly configured, use that value instead
            max_output = self.config.get("max_output", 4096)
            logger.debug(
                f"Limiting max_tokens for DeepSeek from {transformed['max_tokens']} to {max_output}"
            )
            transformed["max_tokens"] = max_output

        # Enable tool mode if tools are available
        if "tools" in transformed and transformed["tools"]:
            # Add tool mode system message
            if "messages" in transformed:
                # Add system message to encourage tool usage
                transformed["messages"].append(
                    {
                        "role": "system",
                        "content": "<system-reminder>Tool mode is active. The user expects you to proactively "
                        "execute the most suitable tool to help complete the task. \n"
                        "Before invoking a tool, you must carefully evaluate whether it matches the current task. "
                        "If no available tool is appropriate for the task, you MUST call the `ExitTool` to exit "
                        "tool mode — this is the only valid way to terminate tool mode.\n"
                        "Always prioritize completing the user's task effectively and efficiently by "
                        "using tools whenever appropriate.</system-reminder>",
                    }
                )

            # Set tool_choice to required to force tool usage
            transformed["tool_choice"] = "required"

            # Add ExitTool if it doesn't already exist
            exit_tool_exists = False
            for tool in transformed["tools"]:
                if (
                    tool.get("type") == "function"
                    and tool.get("function", {}).get("name") == "ExitTool"
                ):
                    exit_tool_exists = True
                    break

            if not exit_tool_exists:
                transformed["tools"].insert(
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

        return transformed

    def transformResponseIn(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a response from DeepSeek models.

        Args:
            response: The unified chat response object

        Returns:
            Modified response with ExitTool handling and JSON repairing
        """
        # Handle ExitTool responses
        if "choices" in response and response["choices"]:
            choice = response["choices"][0]
            if "message" in choice:
                # Repair JSON content in regular messages
                if "content" in choice["message"] and choice["message"]["content"]:
                    choice["message"]["content"] = self._repair_json_content(
                        choice["message"]["content"]
                    )

                # Handle ExitTool responses
                if "tool_calls" in choice["message"]:
                    tool_calls = choice["message"]["tool_calls"]

                    # Check if the first tool call is ExitTool
                    if (
                        tool_calls
                        and tool_calls[0].get("function", {}).get("name") == "ExitTool"
                    ):
                        try:
                            # Extract the response from ExitTool arguments
                            arguments = json.loads(
                                tool_calls[0]["function"].get("arguments", "{}")
                            )
                            response_content = arguments.get("response", "")

                            # Replace tool call with text response
                            choice["message"]["content"] = response_content
                            del choice["message"]["tool_calls"]

                            # Update finish reason
                            if "finish_reason" in choice:
                                choice["finish_reason"] = "stop"
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.error(f"Error processing ExitTool response: {e}")

        return response

    async def _transformStreamingResponseIn(
        self, response_chunk: Dict[str, Any]
    ) -> Dict[str, Any]:
        # support streaming responses yet
        return response_chunk

    async def _transformStreamingResponseIn(
        self, response_chunk: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform streaming response chunks from DeepSeek models.

        disabled since responsing stream should use with state, need to be fixed later
        after pipeline refactoring into AsyncGenerator

        Args:
            response_chunk: A chunk of the streaming response

        Returns:
            Modified response chunk with ExitTool handling and JSON repairing
        """
        # Process ExitTool responses in streaming mode
        if "choices" in response_chunk and response_chunk["choices"]:
            choice = response_chunk["choices"][0]
            if "delta" in choice:
                # Repair JSON content in streaming messages (disabled for now, since it' parsing with state)
                if "content" in choice["delta"] and choice["delta"]["content"]:
                    choice["delta"]["content"] = self._repair_json_content(
                        choice["delta"]["content"]
                    )

                # Process ExitTool responses
                if "tool_calls" in choice["delta"]:
                    tool_calls = choice["delta"]["tool_calls"]

                    # Check if tool_calls is not None and is iterable
                    if tool_calls:
                        for tool_call in tool_calls:
                            function = tool_call.get("function", {})
                            if (
                                function.get("name") == "ExitTool"
                                and "arguments" in function
                            ):
                                try:
                                    # Try to parse the arguments
                                    arguments = json.loads(function["arguments"])
                                    if "response" in arguments:
                                        # Convert the tool call to a text response
                                        choice["delta"]["content"] = arguments[
                                            "response"
                                        ]
                                        del choice["delta"]["tool_calls"]
                                        if "finish_reason" in choice:
                                            choice["finish_reason"] = "stop"
                                except (json.JSONDecodeError, KeyError) as e:
                                    logger.error(
                                        f"Error processing streaming ExitTool response: {tool_calls} , {e}"
                                    )

        return response_chunk
