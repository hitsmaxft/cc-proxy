"""
Client factory to select appropriate client based on provider type.
"""
import logging
from typing import Union, Optional

from src.core.client import OpenAIClient
from src.core.anthropic_client import AnthropicClient
from src.core.model_manager import ModelConfig
from src.core.config import config

logger = logging.getLogger(__name__)


class ClientFactory:
    """Factory class to create appropriate client based on provider type."""

    _openai_client: Optional[OpenAIClient] = None
    _anthropic_client: Optional[AnthropicClient] = None

    @classmethod
    def get_client(cls, model_config: ModelConfig) -> Union[OpenAIClient, AnthropicClient]:
        """
        Get appropriate client based on provider type.

        Args:
            model_config: Model configuration containing provider type

        Returns:
            Either OpenAIClient or AnthropicClient based on provider type
        """
        provider_type = model_config.get("provider_type", "openai")

        if provider_type == "anthropic":
            logger.debug(f"Using Anthropic client for provider: {model_config['provider']}")
            return cls._get_anthropic_client()
        else:
            logger.debug(f"Using OpenAI client for provider: {model_config['provider']}")
            return cls._get_openai_client()

    @classmethod
    def _get_openai_client(cls) -> OpenAIClient:
        """Get or create OpenAI client singleton."""
        if cls._openai_client is None:
            cls._openai_client = OpenAIClient(
                api_key=config.openai_api_key,
                base_url=config.openai_base_url,
                timeout=config.request_timeout,
                api_version=config.azure_api_version,
            )
        return cls._openai_client

    @classmethod
    def _get_anthropic_client(cls) -> AnthropicClient:
        """Get or create Anthropic client singleton."""
        if cls._anthropic_client is None:
            # For Anthropic client, we'll use a dummy API key since the actual
            # key comes from model_config
            cls._anthropic_client = AnthropicClient(
                api_key="dummy",
                base_url="https://api.anthropic.com",
                timeout=config.request_timeout,
            )
        return cls._anthropic_client

    @classmethod
    def cancel_request(cls, request_id: str) -> bool:
        """
        Cancel a request across all client types.

        Args:
            request_id: The request ID to cancel

        Returns:
            True if request was cancelled, False otherwise
        """
        cancelled = False

        # Try to cancel in both clients
        if cls._openai_client:
            cancelled |= cls._openai_client.cancel_request(request_id)

        if cls._anthropic_client:
            cancelled |= cls._anthropic_client.cancel_request(request_id)

        return cancelled