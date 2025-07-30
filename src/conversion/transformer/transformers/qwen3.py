import json
import logging
import re
from typing import Dict, Any, List

from src.conversion.transformer.base import AbstractTransformer

logger = logging.getLogger(__name__)


class QwenTransformer(AbstractTransformer):

    request:Dict[str, Any] = None
    """
    Transformer for DeepSeek models that implements tool mode enhancement.

    This transformer addresses the issue where DeepSeek models tend to become
    less proactive in tool usage over time in long conversations. It implements:

    1. Forcing tool usage with tool_choice="required" when tools are available
    2. Adding an ExitTool to allow graceful exit from tool mode
    3. Adding system prompts to encourage appropriate tool usage
    4. Handling max_output parameter specific to DeepSeek
    """

    name = "qwen3"


    def should_apply_to(self, provider: str, model: str) -> bool:
        """
        Apply this transformer to DeepSeek models.

        Args:
            provider: The provider name
            model: The model name

        Returns:
            True if transformer should be applied
        """
        model_match = "qwen3" in model.lower()
        return model_match

    def transformRequestIn(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        save origin request 

        Args:
            request: The unified chat request object

        Returns:
            Modified request with DeepSeek-specific optimizations
        """
        # Make a copy to avoid modifying the original request
        self.request = request.copy()
        if 'tools' in request:
            self.tools = request['tools']
        else:
            self.tools = []

        return request

    def _repair_json_content(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for tool_call in tool_calls:
            # Ensure tool_call is a dictionary
            if isinstance(tool_call, dict):
                # Check for 'name' and 'arguments' keys
                if 'name' not in tool_call or 'arguments' not in tool_call:
                    logger.error(f"Invalid tool call format: {tool_call}")
                    continue
                else:

                    tool_name = tool_call['name']

                    tool_param_config = None
                    for tool in self.tools:
                        if tool['name'] == tool_name:
                            tool_param_config = tool.get('input_schema', {}).get('properties', {})
                            break   
                    if not tool_param_config:
                        continue

                    # Ensure 'arguments' is a valid JSON string
                    if isinstance(tool_call['arguments'], str):
                        try:
                            tool_arguments = json.loads(tool_call['arguments'])
                            for key, value in tool_arguments.items():
                                # Convert all values to strings
                                if key in tool_param_config:
                                    param_type = tool_param_config[key].get('type', 'string')
                                    if param_type == 'string' and not isinstance(value, str):
                                        logger.warning(
                                            f"Expected string for {key} in tool {tool_name}, got {type(value).__name__}. Converting to string."
                                        )
                                        tool_arguments[key] = json.dumps(value)
                            # tool_call['arguments'] = json.dumps(tool_arguments)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to decode arguments JSON: {tool_call['arguments']}")
                            continue
        return tool_calls

        
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
                    tool_calls = choice["message"].get("tool_calls")

                    # Check if the first tool call is ExitTool
                    if (tool_calls):
                        try:
                            choice["message"]["tool_calls"] = self._repair_json_content(tool_calls)
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.error(f"Error processing tool fix Qwen3 response : {e}")

        return response


    async def transformStreamingResponseIn(
        self, response_chunk: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform streaming response chunks from Qwen3 models.



        Args:
            response_chunk: A chunk of the streaming response

        Returns:
            Modified response chunk with ExitTool handling and JSON repairing
        """
        # Process ExitTool responses in streaming mode
        if "choices" in response_chunk and response_chunk["choices"]:
            choice = response_chunk["choices"][0]
            if "delta" in choice:
                # Process ExitTool responses
                if "tool_calls" in choice["delta"]:
                    tool_calls = choice["delta"]["tool_calls"]

                    # Check if tool_calls is not None and is iterable
                    if tool_calls:
                        try:
                            
                                # Convert the tool call to a text response
                                choice["delta"]["tool_calls"] = self._repair_json_content(tool_calls)
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.error(
                                f"Error processing streaming ExitTool response: {tool_calls} , {e}"
                            )

        return response_chunk
