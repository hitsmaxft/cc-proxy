import abc
from typing import Dict, Any, Optional, Union, List
import logging

logger = logging.getLogger(__name__)

# Define unified request/response types for transformers to work with
UnifiedChatRequest = Dict[str, Any]
UnifiedChatResponse = Dict[str, Any]


class AbstractTransformer(abc.ABC):
    """
    Base transformer interface for request/response modification.

    Transformers can modify requests before they are sent to the model provider
    and responses before they are returned to the client.

    Each transformer should have a unique name and can be activated based on
    provider and model matching.
    """

    name: str = "abstract_transformer"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the transformer with optional configuration.

        Args:
            config: Configuration options for the transformer
        """
        self.config = config or {}

    def transformRequestIn(self, request: UnifiedChatRequest) -> UnifiedChatRequest:
        """
        Transform a request before it's sent to the provider.

        Args:
            request: The unified chat request object

        Returns:
            Modified request object
        """
        # Default implementation: no changes
        return request

    def transformRequestOut(self, request: UnifiedChatRequest) -> UnifiedChatRequest:
        """
        Final transformation of a request before it leaves the transformer pipeline.

        Args:
            request: The unified chat request object

        Returns:
            Final modified request object
        """
        # Default implementation: no changes
        return request

    def transformResponseIn(self, response: UnifiedChatResponse) -> UnifiedChatResponse:
        """
        Transform a response when it's received from the provider.

        Args:
            response: The unified chat response object

        Returns:
            Modified response object
        """
        # Default implementation: no changes
        return response

    def transformResponseOut(
        self, response: UnifiedChatResponse
    ) -> UnifiedChatResponse:
        """
        Final transformation of a response before it leaves the transformer pipeline.

        Args:
            response: The unified chat response object

        Returns:
            Final modified response object
        """
        # Default implementation: no changes
        return response

    async def transformStreamingResponseIn(
        self, response_chunk: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform a streaming response chunk when it's received from the provider.

        Args:
            response_chunk: A chunk of the streaming response

        Returns:
            Modified response chunk
        """
        # Default implementation: no changes
        return response_chunk

    async def transformStreamingResponseOut(
        self, response_chunk: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Final transformation of a streaming response chunk before it leaves the transformer pipeline.

        Args:
            response_chunk: A chunk of the streaming response

        Returns:
            Final modified response chunk
        """
        # Default implementation: no changes
        return response_chunk

    def should_apply_to(self, provider: str, model: str) -> bool:
        """
        Determine if this transformer should be applied to the given provider and model.

        Args:
            provider: The provider name
            model: The model name

        Returns:
            True if the transformer should be applied, False otherwise
        """
        # Default implementation: apply to everything (should be overridden by subclasses)
        return False
