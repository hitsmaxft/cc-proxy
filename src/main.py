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
from dotenv import load_dotenv
from src.core.config import config


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
        "requests.packages.urllib3.connectionpool"
    ]
    
    for logger_name in http_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
        logging.getLogger(logger_name).disabled = True

    parser = argparse.ArgumentParser(description="Claude-to-OpenAI API Proxy v1.0.0")
    parser.add_argument("--env", help="Path to .env file", default=".env")
    parser.add_argument("--log", help="enable access_log", default=False)
    args = parser.parse_args()
    
    # Load environment variables from specified file
    if os.path.exists(args.env):
        load_dotenv(args.env)
        print(f"✅ Loaded environment from: {args.env}")
        if not "DB_FILE" in os.environ:
            os.environ["DB_FILE"] = os.path.splitext(os.path.basename(args.env))[0] + ".db"
    elif args.env != ".env":
        print(f"⚠️ Warning: Specified env file not found: {args.env}")
        os.environ["DB_FILE"] = "proxy.db"
    print(f"✅ Loaded db from: {os.environ["DB_FILE"]}")
    
    # Reinitialize config after loading env
    from src.core.config import init_config
    global config
    config = init_config()
    
    # Keep the old help logic for backward compatibility
    if "--help" in sys.argv:
        print("Claude-to-OpenAI API Proxy v1.0.0")
        print("")
        print("Usage: python src/main.py")
        print("")
        print("Required environment variables:")
        print("  OPENAI_API_KEY - Your OpenAI API key")
        print("")
        print("Optional environment variables:")
        print("  ANTHROPIC_API_KEY - Expected Anthropic API key for client validation")
        print("                      If set, clients must provide this exact API key")
        print(
            f"  OPENAI_BASE_URL - OpenAI API base URL (default: https://api.openai.com/v1)"
        )
        print(f"  BIG_MODEL - Model for opus requests (default: gpt-4o)")
        print(f"  MIDDLE_MODEL - Model for sonnet requests (default: gpt-4o)")
        print(f"  SMALL_MODEL - Model for haiku requests (default: gpt-4o-mini)")
        print(f"  HOST - Server host (default: 0.0.0.0)")
        print(f"  PORT - Server port (default: 8082)")
        print(f"  LOG_LEVEL - Logging level (default: WARNING)")
        print(f"  MAX_TOKENS_LIMIT - Token limit (default: 4096)")
        print(f"  MIN_TOKENS_LIMIT - Minimum token limit (default: 100)")
        print(f"  REQUEST_TIMEOUT - Request timeout in seconds (default: 90)")
        print("")
        print("Command line options:")
        print("  --env PATH - Path to .env file (default: .env)")
        print("")
        print("Model mapping:")
        print(f"  Claude haiku models -> {config.small_model}")
        print(f"  Claude sonnet/opus models -> {config.big_model}")
        sys.exit(0)

    # Configuration summary
    print("🚀 Claude-to-OpenAI API Proxy v1.0.0")
    print(f"✅ Configuration loaded successfully")
    print(f"   OpenAI Base URL: {config.openai_base_url}")
    print(f"   Big Model (opus): {config.big_model}")
    print(f"   Middle Model (sonnet): {config.middle_model}")
    print(f"   Small Model (haiku): {config.small_model}")
    print(f"   Max Tokens Limit: {config.max_tokens_limit}")
    print(f"   Request Timeout: {config.request_timeout}s")
    print(f"   Server: {config.host}:{config.port}")
    print(f"   Client API Key Validation: {'Enabled' if config.anthropic_api_key else 'Disabled'}")
    print("")

    # Parse log level - extract just the first word to handle comments
    log_level = config.log_level.split()[0].lower()
    
    # Validate and set default if invalid
    valid_levels = ['debug', 'info', 'warning', 'error', 'critical']
    if log_level not in valid_levels:
        log_level = 'info'

    from src.api.endpoints import router as api_router
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

    # other http exception
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc):
        print(f"====error on request {type(exc)}====\nurl={request.url}?{request.query_params}\nbody:\n{await request.body()}\nERROR{exc}")
        return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


    # request format error
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc):
        # logger.error("error", exc , exc_info=True)
        print(f"====error on request {type(exc)}====\nurl={request.url}?{request.query_params}\nbody:\n{await request.body()}\nERROR{exc}")
        return PlainTextResponse(str(exc), status_code=400)

    # Start server
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=log_level,
        reload=False,
        access_log=args.log,
    )




if __name__ == "__main__":
    main()
