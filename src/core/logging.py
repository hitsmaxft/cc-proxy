import logging
from src.core.config import config

# Parse log level - extract just the first word to handle comments
log_level = config.log_level.split()[0].upper()

# Validate and set default if invalid
valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if log_level not in valid_levels:
    log_level = "INFO"

# Logging Configuration
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configure uvicorn to be quieter
for uvicorn_logger in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
    logging.getLogger(uvicorn_logger).setLevel(logging.WARNING)

# Disable HTTP client logs from OpenAI library and other HTTP clients
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
