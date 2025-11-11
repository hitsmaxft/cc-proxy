import asyncio
import json
import logging
from fastapi import HTTPException
from typing import Optional, AsyncGenerator, Dict, Any

from anthropic import AsyncAnthropic, APIError, RateLimitError, AuthenticationError, BadRequestError

from src.core.model_manager import ModelConfig
from src.services.history_manager import history_manager

logger = logging.getLogger(__name__)


class AnthropicClient:
    """Async Anthropic client with cancellation support matching OpenAI client interface."""

    clients: Dict[str, AsyncAnthropic] = {}
    timeout: int

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

        # Create Anthropic client
        self.client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url if base_url != "https://api.anthropic.com" else None,
            timeout=timeout,
            max_retries=2
        )
        self.active_requests: Dict[str, asyncio.Event] = {}

    def get_client(self, api_key: str, base_url: str) -> AsyncAnthropic:
        if not api_key:
            return self.client

        if api_key in self.clients:
            return self.clients[api_key]

        client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url if base_url != "https://api.anthropic.com" else None,
            timeout=self.timeout,
            max_retries=2
        )

        self.clients[api_key] = client
        return client

    async def create_chat_completion(
        self, request: Dict[str, Any], request_id: str, model_config: ModelConfig
    ) -> Dict[str, Any]:
        """Send chat completion to Anthropic API with cancellation support."""

        # Create cancellation token if request_id provided
        if request_id:
            cancel_event = asyncio.Event()
            self.active_requests[request_id] = cancel_event

        try:
            # Get client
            client = self.get_client(model_config["api_key"], model_config["base_url"])

            # Log the request for history
            await history_manager.update_openai_request(
                request_id=request_id, openai_request=request
            )

            # Create task that can be cancelled
            completion_task = asyncio.create_task(
                client.messages.create(**request)
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

            # Convert to dict format
            response = completion.model_dump()

            return response

        except AuthenticationError as e:
            raise HTTPException(
                status_code=401, detail=self.classify_anthropic_error(str(e))
            )
        except RateLimitError as e:
            raise HTTPException(
                status_code=429, detail=self.classify_anthropic_error(str(e))
            )
        except BadRequestError as e:
            raise HTTPException(
                status_code=400, detail=self.classify_anthropic_error(str(e))
            )
        except APIError as e:
            status_code = getattr(e, "status_code", 500)
            raise HTTPException(
                status_code=status_code, detail=self.classify_anthropic_error(str(e))
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
        """Send streaming chat completion to Anthropic API with cancellation support."""

        # Create cancellation token if request_id provided
        if request_id:
            cancel_event = asyncio.Event()
            self.active_requests[request_id] = cancel_event

        try:
            # Get client
            client = self.get_client(model_config["api_key"], model_config["base_url"])

            # Ensure stream is enabled
            request["stream"] = True

            logger.debug(f"Anthropic streaming request: {request}")

            await history_manager.update_openai_request(
                request_id=request_id, openai_request=request
            )

            # Create the streaming completion
            streaming_completion = await client.messages.create(**request)

            async for chunk in streaming_completion:
                # Check for cancellation before yielding each chunk
                if request_id and request_id in self.active_requests:
                    if self.active_requests[request_id].is_set():
                        raise HTTPException(
                            status_code=499, detail="Request cancelled by client"
                        )

                # Convert chunk to dict and then to SSE format
                chunk_dict = chunk.model_dump()
                chunk_json = json.dumps(chunk_dict, ensure_ascii=False)
                yield f"data: {chunk_json}"

            # Signal end of stream
            yield "data: [DONE]"

        except AuthenticationError as e:
            raise HTTPException(
                status_code=401, detail=self.classify_anthropic_error(str(e))
            )
        except RateLimitError as e:
            raise HTTPException(
                status_code=429, detail=self.classify_anthropic_error(str(e))
            )
        except BadRequestError as e:
            raise HTTPException(
                status_code=400, detail=self.classify_anthropic_error(str(e))
            )
        except APIError as e:
            status_code = getattr(e, "status_code", 500)
            raise HTTPException(
                status_code=status_code, detail=self.classify_anthropic_error(str(e))
            )
        except Exception as e:
            logger.error("common error", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

        finally:
            # Clean up active request tracking
            if request_id and request_id in self.active_requests:
                del self.active_requests[request_id]

    def classify_anthropic_error(self, error_detail: Any) -> str:
        """Provide specific error guidance for common Anthropic API issues."""
        error_str = str(error_detail).lower()

        # API key issues
        if "invalid" in error_str and "api" in error_str and "key" in error_str:
            return "Invalid API key. Please check your ANTHROPIC_API_KEY configuration."

        # Rate limiting
        if "rate" in error_str and "limit" in error_str:
            return "Rate limit exceeded. Please wait and try again, or upgrade your API plan."

        # Model not found
        if "model" in error_str and ("not found" in error_str or "does not exist" in error_str):
            return "Model not found. Please check your model configuration."

        # Billing issues
        if "billing" in error_str or "payment" in error_str or "credit" in error_str:
            return "Billing issue. Please check your Anthropic account billing status."

        # Default: return original message
        return str(error_detail)

    def cancel_request(self, request_id: str) -> bool:
        """Cancel an active request by request_id."""
        if request_id in self.active_requests:
            self.active_requests[request_id].set()
            return True
        return False