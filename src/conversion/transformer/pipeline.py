import logging
from typing import List, Dict, Any, Optional, AsyncGenerator

from src.conversion.transformer.base import AbstractTransformer

logger = logging.getLogger(__name__)


class TransformerPipeline:
    """
    Pipeline for transforming requests and responses.

    The pipeline applies a sequence of transformers to requests before they are sent to the provider
    and to responses before they are returned to the client.
    """

    def __init__(self, transformers: Optional[List[AbstractTransformer]] = None):
        """
        Initialize the pipeline with a list of transformers.

        Args:
            transformers: List of transformers to apply. Order matters for request transformations.
                          For responses, transformers are applied in reverse order.
        """
        self.transformers = transformers or []

    def transform_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a request through the pipeline.

        The pipeline applies each transformer's transformRequestIn method in order,
        then applies each transformer's transformRequestOut method in reverse order.

        Args:
            request: The request to transform

        Returns:
            The transformed request
        """
        transformed_request = request

        # Apply transformRequestIn in forward order
        for transformer in self.transformers:
            try:
                transformed_request = transformer.transformRequestIn(
                    transformed_request
                )
                logger.debug(
                    f"Applying transformer '{transformer.name}' request in {transformed_request}"
                )
            except Exception as e:
                logger.error(
                    f"Error in transformer '{transformer.name}.transformRequestIn': {e}"
                )

        # Apply transformRequestOut in reverse order
        for transformer in reversed(self.transformers):
            try:
                logger.debug(f"Applying transformer '{transformer.name}' request out")
                transformed_request = transformer.transformRequestOut(
                    transformed_request
                )
            except Exception as e:
                logger.error(
                    f"Error in transformer '{transformer.name}.transformRequestOut': {e}"
                )

        return transformed_request

    def transform_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a response through the pipeline.

        The pipeline applies each transformer's transformResponseIn method in order,
        then applies each transformer's transformResponseOut method in reverse order.

        Args:
            response: The response to transform

        Returns:
            The transformed response
        """
        transformed_response = response

        # Apply transformResponseIn in forward order
        for transformer in self.transformers:
            try:
                logger.debug(f"Applying transformer '{transformer.name}' response in")
                transformed_response = transformer.transformResponseIn(
                    transformed_response
                )
            except Exception as e:
                logger.error(
                    f"Error in transformer '{transformer.name}.transformResponseIn': {e}"
                )

        # Apply transformResponseOut in reverse order
        for transformer in reversed(self.transformers):
            try:
                logger.debug(f"Applying transformer '{transformer.name}' response out")
                transformed_response = transformer.transformResponseOut(
                    transformed_response
                )
            except Exception as e:
                logger.error(
                    f"Error in transformer '{transformer.name}.transformResponseOut': {e}"
                )

        return transformed_response

    async def transform_streaming_response(
        self, response_stream: AsyncGenerator[Dict[str, Any], None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Transform a streaming response through the pipeline.

        For each chunk in the stream, the pipeline applies each transformer's
        transformStreamingResponseIn method in order, then applies each transformer's
        transformStreamingResponseOut method in reverse order.

        Args:
            response_stream: The streaming response to transform

        Yields:
            Transformed response chunks
        """
        async for chunk in response_stream:
            transformed_chunk = chunk

            # Apply transformStreamingResponseIn in forward order
            for transformer in self.transformers:
                try:
                    logger.debug(
                        f"Applying transformer '{transformer.name}' streaming response in"
                    )
                    transformed_chunk = await transformer.transformStreamingResponseIn(
                        transformed_chunk
                    )
                except Exception as e:
                    logger.error(
                        f"Error in transformer '{transformer.name}.transformStreamingResponseIn': {e}"
                    )

            # Apply transformStreamingResponseOut in reverse order
            for transformer in reversed(self.transformers):
                try:
                    logger.debug(
                        f"Applying transformer '{transformer.name}' streaming response out"
                    )
                    transformed_chunk = await transformer.transformStreamingResponseOut(
                        transformed_chunk
                    )
                except Exception as e:
                    logger.error(
                        f"Error in transformer '{transformer.name}.transformStreamingResponseOut': {e}"
                    )

            yield transformed_chunk
