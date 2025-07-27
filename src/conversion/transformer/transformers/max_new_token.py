import json
import logging
import re
from typing import Dict, Any, List, Optional

from src.conversion.transformer.base import AbstractTransformer, UnifiedChatRequest

logger = logging.getLogger(__name__)


class MaxNewTokenTransformer(AbstractTransformer):
    name: str = "max_new_tokens"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the transformer with optional configuration.

        Args:
            config: Configuration options for the transformer
        """
        logger.debug("Initializing MaxNewTokenTransformer with config: %s", config)
        self.config = config or {}

    max_new_tokens: int = 5000

    def should_apply_to(self, provider: str, model: str) -> bool:
        return provider in self.config.get("providers", [])

    def transformRequestIn(self, request: UnifiedChatRequest) -> UnifiedChatRequest:
        extra_query = request.get("extra_query", {})
        max_tokens = request.get("max_tokens", 1000)
        extra_query["max_new_tokens"] = max_tokens
        request["max_tokens"] = self.max_new_tokens + max_tokens
        request["extra_query"] = extra_query
        return request
