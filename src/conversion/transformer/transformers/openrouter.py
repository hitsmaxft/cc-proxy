import fnmatch
import logging
from typing import Any, Dict, List, Optional

from src.conversion.transformer.base import AbstractTransformer
from src.conversion.transformer.pipeline import TransformerPipeline

logger = logging.getLogger(__name__)


class OpenRouterTransformer(AbstractTransformer):
    """
    Transformer for OpenRouter API requests and responses with caching optimization.

    LifeCycle: Per Request

    This transformer implements OpenRouter-specific features to optimize API usage:
    - Adds cache_control parameters for ephemeral caching of large content blocks
    - Enables usage tracking for cost monitoring
    - Supports model-specific caching configurations

    The cache_control mechanism significantly reduces API costs by caching large
    system prompts and context, particularly beneficial for applications with
    repetitive large context usage.

    Example usage with ephemeral caching:
    ```json
    {
        "messages": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "System prompt..."
                    },
                    {
                        "type": "text",
                        "text": "Large context document...",
                        "cache_control": {
                            "type": "ephemeral"
                        }
                    }
                ]
            }
        ]
    }
    ```

    Attributes:
        name: Transformer identifier for registry
        enable_caching: Global toggle for caching features
        caching_models: Pattern matching for models supporting caching
    """

    name: str = "openrouter"
    enable_caching: bool = False

    # Model patterns that support prompt caching
    caching_models: List[str] = [
        "openai/*",
        "deepseek/*",
        "anthropic/*",
    ]

    def should_apply_to(self, provider: str, model: str) -> bool:
        """
        Determine if this transformer should be applied to the given provider.

        Checks whether the provider configuration matches OpenRouter. This method
        enables selective transformation only when the API provider is confirmed
        to be OpenRouter, preventing unwanted modifications to other providers.

        Args:
            provider: The provider identifier (e.g., 'openrouter', 'anthropic')
            model: The model name (unused in this check but provided for interface consistency)

        Returns:
            bool: True if the provider matches OpenRouter configuration, False otherwise
        """
        configured_providers: List[str] = self.config.get("providers", ["openrouter"])

        return provider.lower() in [p.lower() for p in configured_providers]

    def transformRequestIn(
        self, request: Dict[str, Any], pipeline: Optional[TransformerPipeline] = None
    ) -> Dict[str, Any]:
        """
        Transform incoming request for OpenRouter API with caching optimization.

        Implements OpenRouter-specific request modifications:
        1. Enables usage tracking for cost monitoring via extra_query parameters
        2. Adds ephemeral cache_control to large system prompt blocks for models that support it
        3. Skips caching for DeepSeek models due to compatibility issues

        The caching threshold is set to 1000 characters, which provides a reasonable
        balance between caching benefits and overhead for system prompts.

        Args:
            request: The unified chat request dictionary containing model, messages, and other parameters

        Returns:
            Dict[str, Any]: Transformed request with OpenRouter optimizations applied
        """
        # Create a shallow copy to avoid mutating the original request
        transformed: Dict[str, Any] = request.copy()

        # Ensure extra_query structure exists for usage tracking
        if "extra_query" not in transformed:
            transformed["extra_query"] = {}

        # Enable usage tracking for cost monitoring
        if "usage" not in transformed["extra_query"]:
            transformed["extra_query"]["usage"] = {"include": True}

        model: str = request.get("model", "")

        # Skip caching for models that don't support it or have known issues
        if not any(
            fnmatch.fnmatch(model.lower(), pattern.lower())
            for pattern in self.caching_models
        ):
            return transformed

        # DeepSeek models have compatibility issues with caching - skip them
        if "deepseek" in model.lower():
            return transformed

        # Apply caching to large system prompt blocks
        # self._apply_ephemeral_caching(transformed)

        logger.debug("Applied OpenRouter request transformations")
        return transformed

    def _apply_ephemeral_caching(
        self, request: Dict[str, Any], pipeline: Optional[TransformerPipeline] = None
    ) -> None:
        """Apply ephemeral caching to large text blocks in system messages."""
        messages: List[Dict[str, Any]] = request.get("messages", [])

        for message in messages:
            if message.get("role") != "system":
                continue

            content = message.get("content")
            if not isinstance(content, list):
                continue

            # Add cache_control to large text blocks in system messages
            for i, content_block in enumerate(content):
                if not isinstance(content_block, dict):
                    continue

                is_text_block = content_block.get("type") == "text"
                text_length = len(content_block.get("text", ""))
                has_cache_control = "cache_control" in content_block

                # Apply caching to large text blocks (>1000 chars) without existing cache_control
                if is_text_block and text_length > 1000 and not has_cache_control:
                    content_block["cache_control"] = {"type": "ephemeral"}

    def transformResponseIn(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform incoming response from OpenRouter API.

        Currently implements no transformations as OpenRouter responses are
        already in the expected unified format. This method serves as a
        placeholder for future OpenRouter-specific response handling.

        Args:
            response: The unified chat response dictionary from OpenRouter

        Returns:
            Dict[str, Any]: The response unchanged, ready for downstream processing
        """
        if not isinstance(response, dict):
            return response

        print("OpenRouter response received:", response)
        return response

    def transformStreamingResponseIn(self, response_chunk):
        return super().transformStreamingResponseIn(response_chunk)
