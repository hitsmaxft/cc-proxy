import json
import logging
from typing import Any, Dict
import uuid
from fastapi import HTTPException, Request, logger
from src.core.constants import Constants
from src.models.claude import ClaudeMessagesRequest
from src.services.history_manager import history_manager
from src.utils.token_counter import (
    extract_token_usage,
    estimate_input_tokens_from_request,
)

logger = logging.getLogger(__name__)


def fix_qwen3_coder_json(
    args_buffer: str, model_name: str, tool_call: Dict[str, Any] = None
) -> str:
    """
    Fixes JSON formatting issues specific to qwen3_coder model responses.
    This function handles special JSON formatting requirements for qwen3_coder model responses,
    where certain dictionary values need to be converted to JSON strings.
    Args:
        args_buffer (str): The input JSON string to be processed
        model_name (str): The name of the model being used
    Returns:
        str: The processed JSON string. If the model name contains 'qwen3_coder',
             dictionary values are converted to JSON strings. If JSON parsing fails,
             returns the original args_buffer unchanged. For other models, returns
             the original args_buffer.
    Example:
        >>> input_json = '{"content": {"code": "print('hello')"}, "type": "code"}'
        >>> fix_qwen3_coder_json(input_json, "qwen3_coder")
        '{"content": "\\"{\\\\"code\\\\": \\\\"print('hello')\\\\"}\\"", "type": "code"}'
    """

    if "qwen3_coder" in model_name.lower().replace("-", "_"):
        try:
            args_buffer_loads = json.loads(args_buffer)
            if isinstance(args_buffer_loads, dict):
                for key, value in args_buffer_loads.items():
                    if isinstance(value, dict) or isinstance(value, list):
                        args_buffer_loads[key] = json.dumps(value)
                    elif tool_call and tool_call.get("name") == "Write":
                        args_buffer_loads[key] = json.dumps(value, ensure_ascii=False)
            return json.dumps(args_buffer_loads, ensure_ascii=False)
        except json.JSONDecodeError:
            return args_buffer
    return args_buffer


async def convert_openai_to_claude_response(
    openai_response: dict, original_request: ClaudeMessagesRequest, request_id: str
) -> dict:
    """Convert OpenAI response to Claude format."""

    # Extract response data
    choices = openai_response.get("choices", [])
    if not choices:
        raise HTTPException(status_code=500, detail="No choices in OpenAI response")

    choice = choices[0]
    message = choice.get("message", {})

    # Build Claude content blocks
    content_blocks = []

    # Add text content
    text_content = message.get("content")
    if text_content is not None:
        content_blocks.append({"type": Constants.CONTENT_TEXT, "text": text_content})

    # Add tool calls
    tool_calls = message.get("tool_calls", []) or []
    for tool_call in tool_calls:
        if tool_call.get("type") == Constants.TOOL_FUNCTION:
            function_data = tool_call.get(Constants.TOOL_FUNCTION, {})
            try:
                arguments = json.loads(function_data.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {"raw_arguments": function_data.get("arguments", "")}

            content_blocks.append(
                {
                    "type": Constants.CONTENT_TOOL_USE,
                    "id": tool_call.get("id", f"tool_{uuid.uuid4()}"),
                    "name": function_data.get("name", ""),
                    "input": arguments,
                }
            )

    # Ensure at least one content block
    if not content_blocks:
        content_blocks.append({"type": Constants.CONTENT_TEXT, "text": ""})

    # Map finish reason
    finish_reason = choice.get("finish_reason", "stop")
    stop_reason = {
        "stop": Constants.STOP_END_TURN,
        "length": Constants.STOP_MAX_TOKENS,
        "tool_calls": Constants.STOP_TOOL_USE,
        "function_call": Constants.STOP_TOOL_USE,
    }.get(finish_reason, Constants.STOP_END_TURN)

    # Extract token usage from response
    input_tokens, output_tokens, total_tokens = extract_token_usage(openai_response)

    # Build Claude response
    claude_response = {
        "id": request_id,
        "type": "message",
        "role": Constants.ROLE_ASSISTANT,
        "model": original_request.model,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }

    # Log the response to message history
    try:
        await history_manager.log_response(
            request_id=request_id,
            response_data={
                **claude_response,
                "_usage": openai_response.get("usage", {}),
            },
            status="completed",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    except Exception as e:
        logger.error(f"Failed to log response for request {request_id}: {e}")

    # Format the response with message type and stop reason indicators
    return claude_response
    # return format_response_output(claude_response)


# deprecated
async def convert_openai_streaming_to_claude(
    openai_stream, original_request: ClaudeMessagesRequest, logger
):
    """Convert OpenAI streaming response to Claude streaming format."""

    message_id = f"msg_{uuid.uuid4().hex[:24]}"

    # Send initial SSE events
    yield f"event: {Constants.EVENT_MESSAGE_START}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_START, 'message': {'id': message_id, 'type': 'message', 'role': Constants.ROLE_ASSISTANT, 'model': original_request.model, 'content': [], 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}}, ensure_ascii=False)}\n\n"

    yield f"event: {Constants.EVENT_CONTENT_BLOCK_START}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_START, 'index': 0, 'content_block': {'type': Constants.CONTENT_TEXT, 'text': ''}}, ensure_ascii=False)}\n\n"

    yield f"event: {Constants.EVENT_PING}\ndata: {json.dumps({'type': Constants.EVENT_PING}, ensure_ascii=False)}\n\n"

    # Process streaming chunks
    text_block_index = 0
    tool_block_counter = 0
    current_tool_calls = {}
    final_stop_reason = Constants.STOP_END_TURN

    try:
        async for line in openai_stream:
            if line.strip():
                if line.startswith("data: "):
                    chunk_data = line[6:]
                    if chunk_data.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(chunk_data)
                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Failed to parse chunk: {chunk_data}, error: {e}"
                        )
                        continue

                    choice = choices[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    # Handle text delta
                    if delta and "content" in delta and delta["content"] is not None:
                        yield f"event: {Constants.EVENT_CONTENT_BLOCK_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_DELTA, 'index': text_block_index, 'delta': {'type': Constants.DELTA_TEXT, 'text': delta['content']}}, ensure_ascii=False)}\n\n"

                    # Handle tool call deltas with improved incremental processing
                    if "tool_calls" in delta:
                        for tc_delta in delta["tool_calls"]:
                            tc_index = tc_delta.get("index", 0)

                            # Initialize tool call tracking by index if not exists
                            if tc_index not in current_tool_calls:
                                current_tool_calls[tc_index] = {
                                    "id": None,
                                    "name": None,
                                    "args_buffer": "",
                                    "json_sent": False,
                                    "claude_index": None,
                                    "started": False,
                                }

                            tool_call = current_tool_calls[tc_index]

                            # Update tool call ID if provided
                            if tc_delta.get("id"):
                                tool_call["id"] = tc_delta["id"]

                            # Update function name and start content block if we have both id and name
                            function_data = tc_delta.get(Constants.TOOL_FUNCTION, {})
                            if function_data.get("name"):
                                tool_call["name"] = function_data["name"]

                            # Start content block when we have complete initial data
                            if (
                                tool_call["id"]
                                and tool_call["name"]
                                and not tool_call["started"]
                            ):
                                tool_block_counter += 1
                                claude_index = text_block_index + tool_block_counter
                                tool_call["claude_index"] = claude_index
                                tool_call["started"] = True

                                yield f"event: {Constants.EVENT_CONTENT_BLOCK_START}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_START, 'index': claude_index, 'content_block': {'type': Constants.CONTENT_TOOL_USE, 'id': tool_call['id'], 'name': tool_call['name'], 'input': {}}}, ensure_ascii=False)}\n\n"

                            # Handle function arguments
                            if (
                                "arguments" in function_data
                                and tool_call["started"]
                                and function_data["arguments"] is not None
                            ):
                                tool_call["args_buffer"] += function_data["arguments"]

                                # Try to parse complete JSON and send delta when we have valid JSON
                                try:
                                    json.loads(tool_call["args_buffer"])
                                    # If parsing succeeds and we haven't sent this JSON yet
                                    if not tool_call["json_sent"]:
                                        yield f"event: {Constants.EVENT_CONTENT_BLOCK_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_DELTA, 'index': tool_call['claude_index'], 'delta': {'type': Constants.DELTA_INPUT_JSON, 'partial_json': tool_call['args_buffer']}}, ensure_ascii=False)}\n\n"
                                        tool_call["json_sent"] = True
                                except json.JSONDecodeError:
                                    # JSON is incomplete, continue accumulating
                                    pass

                    # Handle finish reason
                    if finish_reason:
                        if finish_reason == "length":
                            final_stop_reason = Constants.STOP_MAX_TOKENS
                        elif finish_reason in ["tool_calls", "function_call"]:
                            final_stop_reason = Constants.STOP_TOOL_USE
                        elif finish_reason == "stop":
                            final_stop_reason = Constants.STOP_END_TURN
                        else:
                            final_stop_reason = Constants.STOP_END_TURN
                        break

    except Exception as e:
        # Handle any streaming errors gracefully
        logger.error(f"Streaming error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        error_event = {
            "type": "error",
            "error": {"type": "api_error", "message": f"Streaming error: {str(e)}"},
        }
        yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        return

    # Send final SSE events
    yield f"event: {Constants.EVENT_CONTENT_BLOCK_STOP}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_STOP, 'index': text_block_index}, ensure_ascii=False)}\n\n"

    for tool_data in current_tool_calls.values():
        if tool_data.get("started") and tool_data.get("claude_index") is not None:
            yield f"event: {Constants.EVENT_CONTENT_BLOCK_STOP}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_STOP, 'index': tool_data['claude_index']}, ensure_ascii=False)}\n\n"

    usage_data = {"input_tokens": 0, "output_tokens": 0}
    yield f"event: {Constants.EVENT_MESSAGE_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_DELTA, 'delta': {'stop_reason': final_stop_reason, 'stop_sequence': None}, 'usage': usage_data}, ensure_ascii=False)}\n\n"
    yield f"event: {Constants.EVENT_MESSAGE_STOP}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_STOP}, ensure_ascii=False)}\n\n"


async def convert_openai_streaming_to_claude_with_cancellation(
    openai_request: Dict[str, Any],
    openai_stream,
    original_request: ClaudeMessagesRequest,
    logger,
    http_request: Request,
    openai_client,
    request_id: str,
):
    """Convert OpenAI streaming response to Claude streaming format with cancellation support."""

    message_id = f"msg_{uuid.uuid4().hex[:24]}"

    # Send initial SSE events
    yield f"event: {Constants.EVENT_MESSAGE_START}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_START, 'message': {'id': message_id, 'type': 'message', 'role': Constants.ROLE_ASSISTANT, 'model': original_request.model, 'content': [], 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}}, ensure_ascii=False)}\n\n"

    yield f"event: {Constants.EVENT_CONTENT_BLOCK_START}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_START, 'index': 0, 'content_block': {'type': Constants.CONTENT_TEXT, 'text': ''}}, ensure_ascii=False)}\n\n"

    yield f"event: {Constants.EVENT_PING}\ndata: {json.dumps({'type': Constants.EVENT_PING}, ensure_ascii=False)}\n\n"

    # Process streaming chunks
    text_block_index = 0
    tool_block_counter = 0
    current_tool_calls = {}
    final_stop_reason = Constants.STOP_END_TURN
    usage_data = {"input_tokens": 0, "output_tokens": 0}

    content = ""
    stream_ended_normally = False
    usage_data_received = False

    try:
        async for line in openai_stream:
            # Check if client disconnected
            if await http_request.is_disconnected():
                logger.info(f"Client disconnected, cancelling request {request_id}")
                openai_client.cancel_request(request_id)
                break

            if line.strip():
                if line.startswith("data: "):
                    chunk_data = line[6:]
                    if chunk_data.strip() == "[DONE]":
                        stream_ended_normally = True
                        break

                    try:
                        chunk = json.loads(chunk_data)
                        # logger.info(f"OpenAI chunk: {chunk}")
                        usage = chunk.get("usage", None)
                        if usage:
                            cache_read_input_tokens = 0
                            prompt_tokens_details = usage.get(
                                "prompt_tokens_details", {}
                            )
                            if prompt_tokens_details:
                                cache_read_input_tokens = prompt_tokens_details.get(
                                    "cached_tokens", 0
                                )
                            usage_data = {
                                "input_tokens": usage.get("prompt_tokens", 0),
                                "output_tokens": usage.get("completion_tokens", 0),
                                "cache_read_input_tokens": cache_read_input_tokens,
                                **usage,
                            }
                            usage_data_received = True

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Failed to parse chunk: {chunk_data}, error: {e}"
                        )
                        continue

                    choice = choices[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    # Handle text delta
                    if delta and "content" in delta and delta["content"] is not None:
                        content += delta["content"]
                        yield f"event: {Constants.EVENT_CONTENT_BLOCK_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_DELTA, 'index': text_block_index, 'delta': {'type': Constants.DELTA_TEXT, 'text': delta['content']}}, ensure_ascii=False)}\n\n"

                    # Handle tool call deltas with improved incremental processing
                    if delta and "tool_calls" in delta and delta["tool_calls"]:
                        for tc_delta in delta["tool_calls"]:
                            tc_index = tc_delta.get("index", 0)

                            # Initialize tool call tracking by index if not exists
                            if tc_index not in current_tool_calls:
                                current_tool_calls[tc_index] = {
                                    "id": None,
                                    "name": None,
                                    "args_buffer": "",
                                    "json_sent": False,
                                    "claude_index": None,
                                    "started": False,
                                }

                            tool_call = current_tool_calls[tc_index]

                            # Update tool call ID if provided
                            if tc_delta.get("id"):
                                tool_call["id"] = tc_delta["id"]

                            # Update function name and start content block if we have both id and name
                            function_data = tc_delta.get(Constants.TOOL_FUNCTION, {})
                            if function_data.get("name"):
                                tool_call["name"] = function_data["name"]

                            # Start content block when we have complete initial data
                            if (
                                tool_call["id"]
                                and tool_call["name"]
                                and not tool_call["started"]
                            ):
                                tool_block_counter += 1
                                claude_index = text_block_index + tool_block_counter
                                tool_call["claude_index"] = claude_index
                                tool_call["started"] = True

                                yield f"event: {Constants.EVENT_CONTENT_BLOCK_START}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_START, 'index': claude_index, 'content_block': {'type': Constants.CONTENT_TOOL_USE, 'id': tool_call['id'], 'name': tool_call['name'], 'input': {}}}, ensure_ascii=False)}\n\n"

                            # Handle function arguments
                            if (
                                "arguments" in function_data
                                and tool_call["started"]
                                and function_data["arguments"] is not None
                            ):
                                tool_call["args_buffer"] += function_data["arguments"]

                                # Try to parse complete JSON and send delta when we have valid JSON
                                try:
                                    args_buffer_loads = json.loads(
                                        tool_call["args_buffer"]
                                    )

                                    # FIXME bug fix for qwen3-coder, it will deserialize the JSON value, which should keep the original JSON string
                                    if (
                                        "qwen3_coder"
                                        in openai_request.get("model", "")
                                        .lower()
                                        .replace("-", "_")
                                        and tool_call.get("name") == "Write"
                                    ):
                                        if isinstance(args_buffer_loads, dict):
                                            for key, value in args_buffer_loads.items():
                                                if isinstance(
                                                    value, dict
                                                ) or isinstance(value, list):
                                                    args_buffer_loads[key] = json.dumps(
                                                        value
                                                    )
                                                # elif key == "content" and tool_call.get("name") == "Write" and not value.startswith("\""):
                                                #     args_buffer_loads[key] = json.dumps(value, ensure_ascii=False)
                                        finish_reason = "tool_calls"  # Ensure we handle tool calls correctly

                                    tool_call["args_buffer"] = json.dumps(
                                        args_buffer_loads, ensure_ascii=False
                                    )
                                    # logger.info(f"Tool call args buffer: {tool_call['args_buffer']}")

                                    # If parsing succeeds and we haven't sent this JSON yet
                                    if not tool_call["json_sent"]:
                                        yield f"event: {Constants.EVENT_CONTENT_BLOCK_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_DELTA, 'index': tool_call['claude_index'], 'delta': {'type': Constants.DELTA_INPUT_JSON, 'partial_json': tool_call['args_buffer']}}, ensure_ascii=False)}\n\n"
                                        tool_call["json_sent"] = True
                                except json.JSONDecodeError:
                                    # JSON is incomplete, continue accumulating
                                    pass

                    if tool_block_counter > 0:
                        finish_reason = (
                            "tool_calls"  # Ensure we handle tool calls correctly
                        )

                    # Handle finish reason
                    if finish_reason:
                        if finish_reason == "length":
                            final_stop_reason = Constants.STOP_MAX_TOKENS
                        elif finish_reason in ["tool_calls", "function_call"]:
                            final_stop_reason = Constants.STOP_TOOL_USE
                        elif finish_reason == "stop":
                            final_stop_reason = Constants.STOP_END_TURN
                        else:
                            final_stop_reason = Constants.STOP_END_TURN
                        stream_ended_normally = True

    except HTTPException as e:
        # Handle cancellation
        if e.status_code == 499:
            logger.info(f"Request {request_id} was cancelled")
            error_event = {
                "type": "error",
                "error": {
                    "type": "cancelled",
                    "message": "Request was cancelled by client",
                },
            }
            await history_manager.log_response(
                request_id=request_id,
                response_data={"status_code": e.status_code, "error": error_event},
                status="error",
            )
            yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            return
        else:
            await history_manager.log_response(
                request_id=request_id,
                response_data={"status_code": e.status_code, "error": error_event},
                status="error",
            )
            raise
    except Exception as e:
        # Handle any streaming errors gracefully
        logger.error(f"Streaming error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        error_event = {
            "type": "error",
            "error": {"type": "api_error", "message": f"Streaming error: {str(e)}"},
        }
        yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        # Always log the final response state
        await history_manager.log_response(
            request_id=request_id,
            response_data={"error": error_event},
            status="error",
        )
        return

    # Send final SSE events
    yield f"event: {Constants.EVENT_CONTENT_BLOCK_STOP}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_STOP, 'index': text_block_index}, ensure_ascii=False)}\n\n"

    for tool_data in current_tool_calls.values():
        if tool_data.get("started") and tool_data.get("claude_index") is not None:
            yield f"event: {Constants.EVENT_CONTENT_BLOCK_STOP}\ndata: {json.dumps({'type': Constants.EVENT_CONTENT_BLOCK_STOP, 'index': tool_data['claude_index']}, ensure_ascii=False)}\n\n"

    # Ensure message history is updated with final state
    if not usage_data_received or usage_data.get("input_tokens", 0) == 0:
        # Estimate tokens if no usage data was received
        from src.utils.token_counter import (
            estimate_input_tokens_from_request,
            estimate_output_tokens_from_content,
        )

        estimated_input = estimate_input_tokens_from_request(
            {
                "model": original_request.model,
                "messages": original_request.messages,
                "system": getattr(original_request, "system", None),
            }
        )
        estimated_output = estimate_output_tokens_from_content(content)

        if not usage_data_received:
            usage_data = {
                "input_tokens": estimated_input,
                "output_tokens": estimated_output,
                "cache_read_input_tokens": 0,
            }
        else:
            # Fill in missing data
            if usage_data.get("input_tokens", 0) == 0:
                usage_data["input_tokens"] = estimated_input
            if usage_data.get("output_tokens", 0) == 0:
                usage_data["output_tokens"] = estimated_output

    # Always log the final response state
    await history_manager.log_response(
        request_id=request_id,
        response_data={
            "content": content,
            "tool_calls": current_tool_calls,
            "stop_reason": final_stop_reason,
            "usage": usage_data,
        },
        status="completed" if stream_ended_normally else "partial",
        input_tokens=usage_data.get("input_tokens", 0),
        output_tokens=usage_data.get("output_tokens", 0),
        total_tokens=(usage_data.get("input_tokens") or 0)
        + (usage_data.get("output_tokens") or 0),
    )

    yield f"event: {Constants.EVENT_MESSAGE_DELTA}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_DELTA, 'delta': {'stop_reason': final_stop_reason, 'stop_sequence': None}, 'usage': usage_data}, ensure_ascii=False)}\n\n"
    yield f"event: {Constants.EVENT_MESSAGE_STOP}\ndata: {json.dumps({'type': Constants.EVENT_MESSAGE_STOP}, ensure_ascii=False)}\n\n"
