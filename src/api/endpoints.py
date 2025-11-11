from fastapi import APIRouter, HTTPException, Request, Header, Depends
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

# Import aiohttp for making the request
from datetime import datetime
import uuid
from typing import Optional
from pydantic import BaseModel

from src.core.config import config, SrcDir,ASSETS_DIR
from src.core.logging import logger
from src.core.client import OpenAIClient
from src.core.client_factory import ClientFactory
from src.models.claude import ClaudeMessagesRequest, ClaudeTokenCountRequest
from src.conversion.request_converter import convert_claude_to_openai
from src.conversion.response_converter import (
    convert_openai_to_claude_response,
    convert_openai_streaming_to_claude_with_cancellation,
)
from src.core.model_manager import model_manager
from src.services.history_manager import history_manager
from src.api.websocket_manager import broadcast_model_update, broadcast_history_update
from src.api.web_search import WebSearchHandler


router = APIRouter()

# Initialize web search handler
web_search_handler = WebSearchHandler()

# Setup Jinja2 templates
templates = Jinja2Templates(directory=f"{SrcDir}/assets")


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

        # for key in http_request.headers:
        #     if "anthropic" in key or "claude" in key:
        #         extra_headers[key] = http_request.headers[key]

        # Check for web search bypass before normal LLM processing
        provider_name = model_manager.get_provider_name_from_model(request.model)
        if provider_name and config.should_use_web_search_bypass(provider_name):
            # Check if this is a web search request
            if web_search_handler.detect_web_search_request(request):
                logger.info(f"Using web search bypass for provider: {provider_name}")

                # Get web search configuration
                web_search_config = config.get_web_search_config(provider_name)
                provider_config = config.get_web_search_provider_config(web_search_config)

                # Handle web search request
                web_search_response = await web_search_handler.handle_web_search_request(
                    claude_request=request,
                    provider_config=provider_config,
                    web_search_config=web_search_config
                )

                if web_search_response:
                    # Log the web search request to history
                    await history_manager.log_request(
                        request_id=request_id,
                        model_name=request.model,
                        actual_model=f"web_search:{web_search_config}",
                        request_data=request.dict(exclude_none=True),
                        user_agent=user_agent,
                        is_streaming=False,
                    )

                    # Log response to history
                    await history_manager.log_response(
                        request_id=request_id,
                        response_data=web_search_response,
                        status_code=200,
                    )

                    return JSONResponse(content=web_search_response)

        # Convert Claude request to OpenAI format
        openai_request = convert_claude_to_openai(request, model_manager)

        # pass extra_headers for openrouter
        openai_request["extra_headers"] = extra_headers

        model_config = model_manager.map_claude_model_to_openai(request.model)

        # Check provider type to decide if conversion is needed
        provider_type = model_config.get("provider_type", "openai")

        if provider_type == "anthropic":
            # For Anthropic providers, use the request directly without conversion
            api_request = request.dict(exclude_none=True)
            # Ensure model is set correctly for Anthropic
            api_request["model"] = model_config["model"]
        else:
            # Convert Claude request to OpenAI format for OpenAI-compatible providers
            api_request = convert_claude_to_openai(request, model_manager)
            # pass extra_headers for openrouter
            api_request["extra_headers"] = extra_headers

        # Get the appropriate client based on provider type
        client = ClientFactory.get_client(model_config)

        # Log the request to message history
        await history_manager.log_request(
            request_id=request_id,
            model_name=request.model,
            actual_model=api_request["model"],
            request_data=request.dict(exclude_none=True),
            user_agent=user_agent,
            is_streaming=request.stream,
        )

        # Check if client disconnected before processing
        if await http_request.is_disconnected():
            raise HTTPException(status_code=499, detail="Client disconnected")

        if request.stream:
            # Streaming response - wrap in error handling
            try:
                if provider_type == "anthropic":
                    # For Anthropic providers, stream directly without conversion
                    api_stream = client.create_chat_completion_stream(
                        api_request, request_id, model_config
                    )
                    return StreamingResponse(
                        api_stream,
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Allow-Headers": "*",
                        },
                    )
                else:
                    # For OpenAI providers, convert the streaming response
                    openai_stream = client.create_chat_completion_stream(
                        api_request, request_id, model_config
                    )
                    return StreamingResponse(
                        convert_openai_streaming_to_claude_with_cancellation(
                            api_request,
                            openai_stream,
                            request,
                            logger,
                            http_request,
                            client,
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
                error_message = client.classify_openai_error(e.detail)
                error_response = {
                    "type": "error",
                    "error": {"type": "api_error", "message": error_message},
                }
                return JSONResponse(status_code=e.status_code, content=error_response)
        else:
            # Non-streaming response
            api_response = await client.create_chat_completion(
                api_request, request_id, model_config
            )

            # Check if we need to convert the response
            if provider_type == "anthropic":
                # For Anthropic providers, the response is already in Claude format
                await history_manager.update_response(
                    request_id=request_id,
                    response_data=api_response,
                    actual_model=api_response.get("model", model_config["model"])
                )
                return api_response
            else:
                # Convert OpenAI response to Claude format
                claude_response = await convert_openai_to_claude_response(
                    api_response, request, request_id
                )
                return claude_response
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(f"Unexpected error processing request: {e}", exc_info=True)
        logger.error(traceback.format_exc())
        if not client:
                error_message = client.classify_openai_error(str(e))
        else:
            error_message = "Internal server error"
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
        # Get model config for small model to test connectivity
        model_config = model_manager.map_claude_model_to_openai(config.small_model)
        client = ClientFactory.get_client(model_config)

        # Simple test request to verify API connectivity
        test_response = await client.create_chat_completion(
            {
                "model": config.small_model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 5,
            },
            request_id=None,
            model_config=model_config
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


@router.get("/styles.css")
async def assets_styles_css():
    """Serve the enhanced JavaScript application file"""
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    import os

    app_styles_path = ASSETS_DIR / "styles.css"
    return FileResponse(app_styles_path, media_type="text/css")


@router.get("/{app}.js")
async def assets_app_js(app: str):
    """Serve the enhanced JavaScript application file"""
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    import os

    app_js_path = ASSETS_DIR / f"{app}.js"
    if not os.path.exists(app_js_path):
        raise HTTPException(status_code=404, detail=f"{app}.js not found")
    return FileResponse(app_js_path, media_type="application/javascript")


class ConfigUpdateRequest(BaseModel):
    BIG_MODEL: Optional[str] = None
    MIDDLE_MODEL: Optional[str] = None
    SMALL_MODEL: Optional[str] = None


@router.get("/api/config/get")
async def get_config():
    """Get current model configuration and available options with provider:model format"""
    # Get today's model usage from database
    from datetime import date

    today = date.today().isoformat()

    try:
        model_usage = await history_manager.get_token_usage_summary(today, today)

        # Create model counters for today's usage with provider context
        today_counts = {}
        for usage in model_usage["by_model"]:  # Correctly access by_model list
            model_id = usage.get("model_id", usage["model"])  # Fallback for legacy data
            model_key = model_id.replace(":", "_").replace("-", "_")
            today_counts[model_key] = usage["request_count"]

        # Add current configured models
        today_counts["big_model"] = today_counts.get(
            config.big_model.replace(":", "_").replace("-", "_"), 0
        )
        today_counts["middle_model"] = today_counts.get(
            config.middle_model.replace(":", "_").replace("-", "_"), 0
        )
        today_counts["small_model"] = today_counts.get(
            config.small_model.replace(":", "_").replace("-", "_"), 0
        )

    except Exception as e:
        logger.error(f"Error getting today's model usage: {e}")
        today_counts = {}

    # Get enhanced model catalog from model manager
    model_catalog = model_manager.get_model_catalog()

    return {
        "message": "Claude-to-OpenAI API Proxy v1.0.0 (Enhanced with Provider:Model Support)",
        "status": "running",
        "config": {
            "openai_base_url": config.openai_base_url,
            "max_tokens_limit": config.max_tokens_limit,
            "api_key_configured": bool(config.openai_api_key),
            "client_api_key_validation": bool(config.anthropic_api_key),
            "big_model": config.big_model,
            "middle_model": config.middle_model,
            "small_model": config.small_model,
        },
        "current": {
            "BIG_MODEL": config.big_model,
            "MIDDLE_MODEL": config.middle_model,
            "SMALL_MODEL": config.small_model,
        },
        "available": {
            "BIG_MODELS": model_catalog["models_by_category"]["big_models"],
            "MIDDLE_MODELS": model_catalog["models_by_category"]["middle_models"],
            "SMALL_MODELS": model_catalog["models_by_category"]["small_models"],
        },
        "providers": model_catalog["providers"],
        "model_catalog": model_catalog,
        "base_url": config.openai_base_url,
        "model_counts": today_counts,
        "format_version": "provider:model",
    }


@router.post("/api/config/update")
async def update_config(request: ConfigUpdateRequest):
    """Update model configuration dynamically with provider:model format validation"""
    try:
        updated_fields = []

        # Update config in memory with validation
        if request.BIG_MODEL is not None:
            # Normalize and validate the model ID
            normalized_model = config._normalize_model_id(request.BIG_MODEL)
            if config._is_model_available(normalized_model):
                old_model = config.big_model
                config.big_model = normalized_model
                updated_fields.append(f"BIG_MODEL: {old_model} -> {normalized_model}")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model '{request.BIG_MODEL}' is not available. Please check provider configuration."
                )

        if request.MIDDLE_MODEL is not None:
            normalized_model = config._normalize_model_id(request.MIDDLE_MODEL)
            if config._is_model_available(normalized_model):
                old_model = config.middle_model
                config.middle_model = normalized_model
                updated_fields.append(f"MIDDLE_MODEL: {old_model} -> {normalized_model}")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model '{request.MIDDLE_MODEL}' is not available. Please check provider configuration."
                )

        if request.SMALL_MODEL is not None:
            normalized_model = config._normalize_model_id(request.SMALL_MODEL)
            if config._is_model_available(normalized_model):
                old_model = config.small_model
                config.small_model = normalized_model
                updated_fields.append(f"SMALL_MODEL: {old_model} -> {normalized_model}")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model '{request.SMALL_MODEL}' is not available. Please check provider configuration."
                )

        # Save to database
        await history_manager.get_db().save_model_config(
            config.big_model, config.middle_model, config.small_model
        )

        # Broadcast update to WebSocket clients
        await broadcast_model_update(
            config.big_model, config.middle_model, config.small_model
        )

        # Log the configuration update
        logger.info(f"Model configuration updated: {', '.join(updated_fields)}")

        # Return updated configuration
        return {
            "status": "success",
            "message": "Configuration updated successfully and saved to database",
            "changes": updated_fields,
            "current": {
                "BIG_MODEL": config.big_model,
                "MIDDLE_MODEL": config.middle_model,
                "SMALL_MODEL": config.small_model,
            },
            "timestamp": datetime.now().isoformat(),
            "format_version": "provider:model",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/history")
async def get_message_history(
    limit: int = 5,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    start_hour: Optional[int] = None,
    end_hour: Optional[int] = None,
    date: Optional[str] = None,
    hour: Optional[int] = None,
):
    """Get recent message history with optional date and hour filtering"""
    try:
        if limit < 1 or limit > 500:
            limit = 5

        # Handle specific date/hour filtering
        if date and hour is not None:
            # Get messages for a specific date and hour
            start_dt = f"{date}T{str(hour).zfill(2)}:00:00"
            end_dt = f"{date}T{str(hour).zfill(2)}:59:59"
            history_response = await history_manager.get_recent_messages(
                limit, start_dt, end_dt
            )
        elif date:
            # Get messages for entire day
            start_dt = f"{date}T00:00:00"
            end_dt = f"{date}T23:59:59"
            history_response = await history_manager.get_recent_messages(
                limit, start_dt, end_dt
            )
        else:
            # Use provided start/end dates with optional hour filtering
            filtered_start_date = start_date
            filtered_end_date = end_date

            if start_date and start_hour is not None:
                filtered_start_date = f"{start_date}T{str(start_hour).zfill(2)}:00:00"
            if end_date and end_hour is not None:
                filtered_end_date = f"{end_date}T{str(end_hour).zfill(2)}:59:59"

            history_response = await history_manager.get_recent_messages(
                limit, filtered_start_date, filtered_end_date
            )

        return {
            "status": "success",
            "data": history_response.dict(),
            "timestamp": datetime.now().isoformat(),
            "filters": {
                "date": date,
                "hour": hour,
                "start_date": start_date,
                "end_date": end_date,
                "start_hour": start_hour,
                "end_hour": end_hour,
                "limit": limit,
            },
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