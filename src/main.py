from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
import starlette
from starlette.requests import Request
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn
import sys
import argparse
import os
import logging
from src.core.config import config, Config


logger = logging.getLogger(__name__)


def main():
    # Disable various logging sources
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.disabled = False

    # Disable HTTP client logging that shows the POST requests
    http_loggers = [
        "openai._base_client",
        "httpx",
        "httpcore",
        "httpcore.connection",
        "httpcore.http11",
        "httpcore.http2",
        "httpx._client",
        "urllib3.connectionpool",
        "requests.packages.urllib3.connectionpool",
    ]

    for logger_name in http_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
        logging.getLogger(logger_name).disabled = True

    parser = argparse.ArgumentParser(description="Claude-to-OpenAI API Proxy v1.0.0")
    parser.add_argument("--conf", help="Path to config toml file", required=True, type=str)
    parser.add_argument("--host", help="override host in config", required=False, type=str)
    parser.add_argument("--port", help="override port in config", required=False, type=int)
    parser.add_argument("--log", help="enable access_log", default=False)
    args = parser.parse_args()

    from src.core.config import init_config

    global config
    print(f"✅ Loading TOML config from: {args.conf}")
    config = init_config(config_file=args.conf)

    # Load model configuration from database
    import asyncio

    try:
        # Run async database loading function
        asyncio.run(
            config.load_model_config_from_db()
        )
    except Exception as e:
        print(f"⚠️  Warning: Could not load model configuration from database: {e}")

    # Help logic
    if "--help" in sys.argv:
        print("Claude-to-OpenAI API Proxy v1.0.0")
        print("")
        print("Usage: python src/main.py --conf CONFIG_FILE")
        print("")
        print("Required arguments:")
        print("  --conf PATH - Path to TOML configuration file")
        print("")
        print("Configuration file format (TOML):")
        print("  [config]")
        print("  port = 8082")
        print("  host = \"0.0.0.0\"")
        print("  log_level = \"INFO\"")
        print("  big_model = \"gpt-4o\"")
        print("  middle_model = \"gpt-4o\"") 
        print("  small_model = \"gpt-4o-mini\"")
        print("")
        print("  [[provider]]")
        print("  name = \"OpenAI\"")
        print("  base_url = \"https://api.openai.com/v1\"")
        print("  api_key = \"your-api-key\"")
        print("  big_models = [\"gpt-4o\"]")
        print("  middle_models = [\"gpt-4o\"]")
        print("  small_models = [\"gpt-4o-mini\"]")
        print("")
        print("Model mapping:")
        print(f"  Claude haiku models -> {config.small_model}")
        print(f"  Claude sonnet models -> {config.middle_model}")  
        print(f"  Claude opus models -> {config.big_model}")
        sys.exit(0)

    # Configuration summary
    print("🚀 Claude-to-OpenAI API Proxy v1.0.0")
    print(f"✅ Configuration loaded successfully")
    print(f"   Big Model (opus): {config.big_model}")
    print(f"   Middle Model (sonnet): {config.middle_model}")
    print(f"   Small Model (haiku): {config.small_model}")
    print(f"   Max Tokens Limit: {config.max_tokens_limit}")
    print(f"   Request Timeout: {config.request_timeout}s")
    print(f"   Server: {config.host}:{config.port}")
    print(
        f"   Client API Key Validation: {'Enabled' if config.anthropic_api_key else 'Disabled'}"
    )
    print("")

    # Parse log level - extract just the first word to handle comments
    log_level = config.log_level.split()[0].lower()

    # Validate and set default if invalid
    valid_levels = ["debug", "info", "warning", "error", "critical"]
    if log_level not in valid_levels:
        log_level = "info"

    from src.api.endpoints import router as api_router
    from src.api.websocket_manager import router as websocket_router

    app = FastAPI(title="Claude-to-OpenAI API Proxy", version="1.0.0")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for development
        allow_credentials=True,
        allow_methods=["*"],  # Allow all HTTP methods
        allow_headers=["*"],  # Allow all headers
    )

    app.include_router(api_router)
    app.include_router(websocket_router)

    # other http exception
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc):
        print(
            f"====error on request {type(exc)}====\nurl={request.url}?{request.query_params}\nbody:\n{await request.body()}\nERROR{exc}"
        )
        return PlainTextResponse(str(exc.detail), status_code=exc.status_code)

    # request format error
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc):
        # logger.error("error", exc , exc_info=True)
        print(
            f"====error on request {type(exc)}====\nurl={request.url}?{request.query_params}\nbody:\n{await request.body()}\nERROR{exc}"
        )
        return PlainTextResponse(str(exc), status_code=400)

    # Start server
    uvicorn.run(
        app,
        host=args.host or config.host,
        port=args.port or config.port,
        log_level=log_level,
        reload=False,
        access_log=args.log,
    )


if __name__ == "__main__":
    main()
