from fastapi import APIRouter, HTTPException, Request, Header, Depends
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

# Import aiohttp for making the request
import requests
from datetime import datetime
import uuid
from typing import Optional
from pydantic import BaseModel

from src.core.config import config
from src.core.logging import logger
from src.core.client import OpenAIClient
from src.models.claude import ClaudeMessagesRequest, ClaudeTokenCountRequest
from src.conversion.request_converter import convert_claude_to_openai
from src.conversion.response_converter import (
    convert_openai_to_claude_response,
    convert_openai_streaming_to_claude_with_cancellation,
)
from src.core.model_manager import model_manager
from src.services.history_manager import history_manager
from src.storage.database import MessageHistoryDatabase

router = APIRouter()

# Initialize database
config_db = MessageHistoryDatabase()

# Setup Jinja2 templates
templates = Jinja2Templates(directory="src/assets")

openai_client = OpenAIClient(
    config.openai_api_key,
    config.openai_base_url,
    config.request_timeout,
    api_version=config.azure_api_version,
)


async def validate_api_key(
    x_api_key: Optional[str] = Header(None), authorization: Optional[str] = Header(None)
):
    """Validate the client's API key from either x-api-key header or Authorization header."""
    client_api_key = None

    # Extract API key from headers
    if x_api_key:
        client_api_key = x_api_key
    elif authorization and authorization.startswith("Bearer "):
        client_api_key = authorization.replace("Bearer ", "")

    # Skip validation if ANTHROPIC_API_KEY is not set in the environment
    if not config.anthropic_api_key:
        return

    # Validate the client API key
    if not client_api_key or not config.validate_client_api_key(client_api_key):
        logger.warning(f"Invalid API key provided by client")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key. Please provide a valid Anthropic API key.",
        )


@router.post("/v1/messages")
async def create_message(
    request: ClaudeMessagesRequest,
    http_request: Request,
    _: None = Depends(validate_api_key),
):
    try:
        logger.debug(
            f"Processing Claude request: model={request.model}, stream={request.stream}"
        )

        # Generate unique request ID for cancellation tracking
        request_id = str(uuid.uuid4())

        user_agent = "claude-cli/1.0.43 (external, proxy)"

        # openrouter headers
        extra_headers = {
            "user_agent": user_agent,
            "HTTP-Referer": "https:://claudecode.com",
            "X-Title": "ClaudeCode",
        }

        if "user_agent" in http_request.headers:
            user_agent = http_request.headers.get("user_agent")

        for key in http_request.headers:
            if "anthropic" in key or "claude" in key:
                extra_headers[key] = http_request.headers[key]

        # Convert Claude request to OpenAI format
        openai_request = convert_claude_to_openai(request, model_manager)

        # pass extra_headers for openrouter
        openai_request["extra_headers"] = extra_headers

        # Log the request to message history
        await history_manager.log_request(
            request_id=request_id,
            model_name=request.model,
            actual_model=openai_request["model"],
            request_data={
                "_openai_model": openai_request["model"],
                **request.dict(exclude_none=True),
            },
            user_agent=user_agent,
            is_streaming=request.stream,
        )

        # Check if client disconnected before processing
        if await http_request.is_disconnected():
            raise HTTPException(status_code=499, detail="Client disconnected")

        if request.stream:
            # Streaming response - wrap in error handling
            try:
                openai_stream = openai_client.create_chat_completion_stream(
                    openai_request, request_id
                )
                return StreamingResponse(
                    convert_openai_streaming_to_claude_with_cancellation(
                        openai_stream,
                        request,
                        logger,
                        http_request,
                        openai_client,
                        request_id,
                    ),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "*",
                    },
                )
            except HTTPException as e:
                # Convert to proper error response for streaming
                logger.error(f"Streaming error: {e.detail}")
                import traceback

                logger.error(traceback.format_exc())
                error_message = openai_client.classify_openai_error(e.detail)
                error_response = {
                    "type": "error",
                    "error": {"type": "api_error", "message": error_message},
                }
                return JSONResponse(status_code=e.status_code, content=error_response)
        else:
            # Non-streaming response
            openai_response = await openai_client.create_chat_completion(
                openai_request, request_id
            )
            claude_response = await convert_openai_to_claude_response(
                openai_response, request, request_id
            )

            return claude_response
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(f"Unexpected error processing request: {e}")
        logger.error(traceback.format_exc())
        error_message = openai_client.classify_openai_error(str(e))
        raise HTTPException(status_code=500, detail=error_message)


@router.post("/v1/messages/count_tokens")
async def count_tokens(
    request: ClaudeTokenCountRequest, _: None = Depends(validate_api_key)
):
    try:
        # For token counting, we'll use a simple estimation
        # In a real implementation, you might want to use tiktoken or similar

        total_chars = 0

        # Count system message characters
        if request.system:
            if isinstance(request.system, str):
                total_chars += len(request.system)
            elif isinstance(request.system, list):
                for block in request.system:
                    if hasattr(block, "text"):
                        total_chars += len(block.text)

        # Count message characters
        for msg in request.messages:
            if msg.content is None:
                continue
            elif isinstance(msg.content, str):
                total_chars += len(msg.content)
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if hasattr(block, "text") and block.text is not None:
                        total_chars += len(block.text)

        # Rough estimation: 4 characters per token
        estimated_tokens = max(1, total_chars // 4)

        return {"input_tokens": estimated_tokens}

    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "openai_api_configured": True,
        "api_key_valid": True,
        "client_api_key_validation": True,
    }


@router.get("/test-connection")
async def test_connection():
    """Test API connectivity to OpenAI"""
    try:
        # Simple test request to verify API connectivity
        test_response = await openai_client.create_chat_completion(
            {
                "model": config.small_model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5,
            }
        )

        return {
            "status": "success",
            "message": "Successfully connected to OpenAI API",
            "model_used": config.small_model,
            "timestamp": datetime.now().isoformat(),
            "response_id": test_response.get("id", "unknown"),
        }

    except Exception as e:
        logger.error(f"API connectivity test failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "failed",
                "error_type": "API Error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
                "suggestions": [
                    "Check your OPENAI_API_KEY is valid",
                    "Verify your API key has the necessary permissions",
                    "Check if you have reached rate limits",
                ],
            },
        )


@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the configuration UI with template rendering"""
    # Pass environment variables and config data to template
    template_vars = {
        "request": request,
        "default_port": config.port,
        "page_title": "Claude Code Proxy Configuration",
        "app_title": "Claude Code Proxy",
        "app_description": "Configuration & Monitoring Interface",
        "openai_base_url": config.openai_base_url,
        "big_model": config.big_model,
        "middle_model": config.middle_model,
        "small_model": config.small_model,
        "host": config.host,
        "log_level": config.log_level,
        "max_tokens_limit": config.max_tokens_limit,
        "request_timeout": config.request_timeout,
        "client_api_key_validation": bool(config.anthropic_api_key),
    }

    return templates.TemplateResponse("config.html", template_vars)


class ConfigUpdateRequest(BaseModel):
    BIG_MODEL: Optional[str] = None
    MIDDLE_MODEL: Optional[str] = None
    SMALL_MODEL: Optional[str] = None


@router.get("/api/config/get")
async def get_config():
    """Get current model configuration and available options"""
    # Get today's model usage from database
    from datetime import date

    today = date.today().isoformat()

    try:
        model_usage = await history_manager.get_token_usage_summary(today, today)

        # Create model counters for today's usage
        today_counts = {}
        for usage in model_usage["by_model"]:
            model_key = usage["model"].replace("-", "_")
            today_counts[f"{model_key}"] = usage["request_count"]

        # Add current configured models
        today_counts["big_model"] = today_counts.get(
            f"{config.big_model.replace('-', '_')}", 0
        )
        today_counts["middle_model"] = today_counts.get(
            f"{config.middle_model.replace('-', '_')}", 0
        )
        today_counts["small_model"] = today_counts.get(
            f"{config.small_model.replace('-', '_')}", 0
        )

    except Exception as e:
        logger.error(f"Error getting today's model usage: {e}")
        today_counts = {}

    return {
        "message": "Claude-to-OpenAI API Proxy v1.0.0",
        "status": "running",
        "config": {
            "openai_base_url": config.openai_base_url,
            "max_tokens_limit": config.max_tokens_limit,
            "api_key_configured": bool(config.openai_api_key),
            "client_api_key_validation": bool(config.anthropic_api_key),
            "big_model": config.big_model,
            "small_model": config.small_model,
        },
        "current": {
            "BIG_MODEL": config.big_model,
            "MIDDLE_MODEL": config.middle_model,
            "SMALL_MODEL": config.small_model,
        },
        "available": {
            "BIG_MODELS": config.big_models,
            "MIDDLE_MODELS": config.middle_models,
            "SMALL_MODELS": config.small_models,
        },
        "base_url": config.openai_base_url,
        "model_counts": today_counts,
    }


@router.post("/api/config/update")
async def update_config(request: ConfigUpdateRequest):
    """Update model configuration dynamically"""
    try:
        # Update config in memory
        if request.BIG_MODEL is not None:
            config.big_model = request.BIG_MODEL
        if request.MIDDLE_MODEL is not None:
            config.middle_model = request.MIDDLE_MODEL
        if request.SMALL_MODEL is not None:
            config.small_model = request.SMALL_MODEL

        # Save to database
        await config_db.save_model_config(
            config.big_model, config.middle_model, config.small_model
        )

        # Return updated configuration
        return {
            "status": "success",
            "message": "Configuration updated successfully and saved to database",
            "current": {
                "BIG_MODEL": config.big_model,
                "MIDDLE_MODEL": config.middle_model,
                "SMALL_MODEL": config.small_model,
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/history")
async def get_message_history(
    limit: int = 5, start_date: Optional[str] = None, end_date: Optional[str] = None
):
    """Get recent message history with optional date filtering"""
    try:
        if limit < 1 or limit > 50:
            limit = 5

        history_response = await history_manager.get_recent_messages(
            limit, start_date, end_date
        )

        return {
            "status": "success",
            "data": history_response.dict(),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving message history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/history/{message_id}")
async def get_message_details(message_id: int):
    """Get detailed information for a specific message"""
    try:
        message = await history_manager.get_message_by_id(message_id)

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        return {
            "status": "success",
            "data": message.dict(),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving message {message_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/summary")
async def get_usage_summary(
    start_date: Optional[str] = None, end_date: Optional[str] = None
):
    """Get token usage summary aggregated by actual model with optional date filtering"""
    try:
        summary = await history_manager.get_token_usage_summary(start_date, end_date)

        return {
            "status": "success",
            "data": summary,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving usage summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/credits")
async def get_openrouter_credits():
    """Get OpenRouter credits information"""
    try:
        op = None

        for p in config.provider:
            if "openrouter.ai" in p["base_url"]:
                op = p
                break
        # Check if we're using OpenRouter
        if not op:
            return {
                "status": "not_openrouter",
                "message": "Not using OpenRouter base URL",
                "data": None,
            }

        openai_api_key = op["api_key"]
        openai_base_url = op["base_url"]

        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json",
        }

        response = requests.get("https://openrouter.ai/api/v1/credits", headers=headers)
        if response.status_code == 200:
            data = response.json()

            return {
                "status": "success",
                "provider": "openrouter",
                "data": {
                    "total": data.get("data", {}).get("total_credits", 0),
                    "usage": data.get("data", {}).get("total_usage", 0),
                },
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to fetch credits: {response.status_code}",
                "data": None,
            }
    except Exception as e:
        logger.error(f"Error fetching OpenRouter credits: {e}")
        return {"status": "error", "message": str(e), "data": None}
