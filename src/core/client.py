import asyncio
import json
import logging
from fastapi import HTTPException
from typing import Optional, AsyncGenerator, Dict, Any

from openai import AsyncOpenAI, AsyncAzureOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai._exceptions import (
    APIError,
    RateLimitError,
    AuthenticationError,
    BadRequestError,
)

from src.conversion.transformer.pipeline import TransformerPipeline
from src.conversion.transformer.config import transformer_config
from src.core.model_manager import ModelConfig
from src.services.history_manager import history_manager

logger = logging.getLogger(__name__)


class OpenAIClient:
    # cached client,  api_key -> client
    clients: Dict[str, AsyncOpenAI] = {}
    api_version: Optional[str] = None
    timeout: int

    """Async OpenAI client with cancellation support."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: int = 90,
        api_version: Optional[str] = None,
    ):
        self.active_requests: Dict[str, asyncio.Event] = {}

        self.timeout = timeout
        if not api_key:
            return

        self.api_key = api_key
        self.base_url = base_url
        # Detect if using Azure and instantiate the appropriate client
        if api_version:
            self.client = AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=base_url,
                api_version=api_version,
                timeout=timeout,
            )
            self.api_version = api_version
        else:
            self.client = AsyncOpenAI(
                api_key=api_key, base_url=base_url, timeout=timeout
            )
        self.active_requests: Dict[str, asyncio.Event] = {}

    def get_client(self, api_key: str, base_url: str) -> AsyncOpenAI:
        if not api_key:
            return self.client

        if api_key in self.clients:
            return self.clients[api_key]

        if self.api_version:
            client = AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=base_url,
                api_version=self.api_version,
                timeout=self.timeout,
            )
        else:
            client = AsyncOpenAI(
                api_key=api_key, base_url=base_url, timeout=self.timeout
            )

        self.clients[api_key] = client
        return client

    async def create_chat_completion(
        self, request: Dict[str, Any], request_id: str, model_config: ModelConfig
    ) -> Dict[str, Any]:
        """Send chat completion to OpenAI API with cancellation support."""

        # Create cancellation token if request_id provided
        if request_id:
            cancel_event = asyncio.Event()
            self.active_requests[request_id] = cancel_event

        try:
            # Extract provider info for transformer selection
            provider = model_config["provider"]
            model = model_config["model"]
            client = self.get_client(model_config["api_key"], model_config["base_url"])

            # Apply transformers to request
            transformed_request = self._apply_request_transformers(
                request, provider, model
            )

            await history_manager.update_openai_request(
                request_id=request_id, openai_request=transformed_request
            )

            # Create task that can be cancelled
            completion_task = asyncio.create_task(
                client.chat.completions.create(**transformed_request)
            )

            if request_id:
                # Wait for either completion or cancellation
                cancel_task = asyncio.create_task(cancel_event.wait())
                done, pending = await asyncio.wait(
                    [completion_task, cancel_task], return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                # Check if request was cancelled
                if cancel_task in done:
                    completion_task.cancel()
                    raise HTTPException(
                        status_code=499, detail="Request cancelled by client"
                    )

                completion = await completion_task
            else:
                completion = await completion_task

            # Convert to dict format that matches the original interface
            response = completion.model_dump()

            # Apply transformers to response
            transformed_response = self._apply_response_transformers(
                response, provider, model
            )

            return transformed_response

        except AuthenticationError as e:
            raise HTTPException(
                status_code=401, detail=self.classify_openai_error(str(e))
            )
        except RateLimitError as e:
            raise HTTPException(
                status_code=429, detail=self.classify_openai_error(str(e))
            )
        except BadRequestError as e:
            raise HTTPException(
                status_code=400, detail=self.classify_openai_error(str(e))
            )
        except APIError as e:
            status_code = getattr(e, "status_code", 500)
            raise HTTPException(
                status_code=status_code, detail=self.classify_openai_error(str(e))
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

        finally:
            # Clean up active request tracking
            if request_id and request_id in self.active_requests:
                del self.active_requests[request_id]

    async def create_chat_completion_stream(
        self, request: Dict[str, Any], request_id: str, model_config: ModelConfig
    ) -> AsyncGenerator[str, None]:
        """Send streaming chat completion to OpenAI API with cancellation support."""

        # Create cancellation token if request_id provided
        if request_id:
            cancel_event = asyncio.Event()
            self.active_requests[request_id] = cancel_event

        try:
            # Extract provider info for transformer selection
            client = self.get_client(model_config["api_key"], model_config["base_url"])

            provider = model_config["provider"]
            model = model_config["model"]

            # Apply transformers to request
            transformed_request = self._apply_request_transformers(
                request, provider, model
            )

            # Ensure stream is enabled
            # transformed_request["stream"] = True
            # if "stream_options" not in transformed_request:
            #     transformed_request["stream_options"] = {}
            # transformed_request["stream_options"]["include_usage"] = True

            logger.debug(f"Transformed request for streaming: {transformed_request}")

            await history_manager.update_openai_request(
                request_id=request_id, openai_request=transformed_request
            )

            # Create the streaming completion
            streaming_completion = await client.chat.completions.create(
                **transformed_request
            )

            # Create transformer pipeline for streaming response if needed
            pipeline = None
            if transformer_config:
                transformers = transformer_config.get_transformers_for_model(
                    provider, model
                )
                if transformers:
                    pipeline = TransformerPipeline(transformers)

            async for chunk in streaming_completion:
                # Check for cancellation before yielding each chunk
                if request_id and request_id in self.active_requests:
                    if self.active_requests[request_id].is_set():
                        raise HTTPException(
                            status_code=499, detail="Request cancelled by client"
                        )

                # Convert chunk to dict
                chunk_dict = chunk.model_dump()

                # Apply transformers if available
                if pipeline:
                    # Apply transformers to streaming response chunk
                    try:
                        chunk_dict = await self._apply_streaming_response_transformers(
                            chunk_dict, pipeline
                        )
                    except Exception as e:
                        logger.error(
                            f"Error applying transformers to streaming response: {e}"
                        )

                # Convert to SSE format
                chunk_json = json.dumps(chunk_dict, ensure_ascii=False)
                yield f"data: {chunk_json}"

            # Signal end of stream
            yield "data: [DONE]"

        except AuthenticationError as e:
            raise HTTPException(
                status_code=401, detail=self.classify_openai_error(str(e))
            )
        except RateLimitError as e:
            raise HTTPException(
                status_code=429, detail=self.classify_openai_error(str(e))
            )
        except BadRequestError as e:
            raise HTTPException(
                status_code=400, detail=self.classify_openai_error(str(e))
            )
        except APIError as e:
            status_code = getattr(e, "status_code", 500)
            raise HTTPException(
                status_code=status_code, detail=self.classify_openai_error(str(e))
            )
        except Exception as e:
            logger.error("common error", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

        finally:
            # Clean up active request tracking
            if request_id and request_id in self.active_requests:
                del self.active_requests[request_id]

    def classify_openai_error(self, error_detail: Any) -> str:
        """Provide specific error guidance for common OpenAI API issues."""
        error_str = str(error_detail).lower()

        # Region/country restrictions
        if (
            "unsupported_country_region_territory" in error_str
            or "country, region, or territory not supported" in error_str
        ):
            return "OpenAI API is not available in your region. Consider using a VPN or Azure OpenAI service."

        # API key issues
        if "invalid_api_key" in error_str or "unauthorized" in error_str:
            return "Invalid API key. Please check your OPENAI_API_KEY configuration."

        # Rate limiting
        if "rate_limit" in error_str or "quota" in error_str:
            return "Rate limit exceeded. Please wait and try again, or upgrade your API plan."

        # Model not found
        if "model" in error_str and (
            "not found" in error_str or "does not exist" in error_str
        ):
            return "Model not found. Please check your BIG_MODEL and SMALL_MODEL configuration."

        # Billing issues
        if "billing" in error_str or "payment" in error_str:
            return "Billing issue. Please check your OpenAI account billing status."

        # Default: return original message
        return str(error_detail)

    def cancel_request(self, request_id: str) -> bool:
        """Cancel an active request by request_id."""
        if request_id in self.active_requests:
            self.active_requests[request_id].set()
            return True
        return False

    def _apply_request_transformers(
        self, request: Dict[str, Any], provider: str, model: str
    ) -> Dict[str, Any]:
        """
        Apply transformers to the request.

        Args:
            request: The original request
            provider: The provider name
            model: The model name

        Returns:
            The transformed request
        """
        if not transformer_config:
            return request.copy()

        transformers = transformer_config.get_transformers_for_model(provider, model)

        if not transformers:
            return request.copy()

        pipeline = TransformerPipeline(transformers)
        return pipeline.transform_request(request.copy())

    def _apply_response_transformers(
        self, response: Dict[str, Any], provider: str, model: str
    ) -> Dict[str, Any]:
        """
        Apply transformers to the response.

        Args:
            response: The original response
            provider: The provider name
            model: The model name

        Returns:
            The transformed response
        """
        if not transformer_config:
            return response

        transformers = transformer_config.get_transformers_for_model(provider, model)
        if not transformers:
            return response

        pipeline = TransformerPipeline(transformers)
        return pipeline.transform_response(response)

    async def _apply_streaming_response_transformers(
        self, chunk: Dict[str, Any], pipeline: TransformerPipeline
    ) -> Dict[str, Any]:
        """
        Apply transformers to a streaming response chunk.

        Args:
            chunk: The response chunk
            pipeline: The transformer pipeline

        Returns:
            The transformed chunk
        """
        # Apply transformStreamingResponseIn
        for transformer in pipeline.transformers:
            try:
                chunk = await transformer.transformStreamingResponseIn(chunk)
            except Exception as e:
                logger.error(
                    f"Error in transformer {transformer.name}.transformStreamingResponseIn: {e}"
                )

        # Apply transformStreamingResponseOut in reverse order
        for transformer in reversed(pipeline.transformers):
            try:
                chunk = await transformer.transformStreamingResponseOut(chunk)
            except Exception as e:
                logger.error(
                    f"Error in transformer {transformer.name}.transformStreamingResponseOut: {e}"
                )

        return chunk
