from typing import List, Dict, Any, Optional
from datetime import datetime

from src.storage.database import MessageHistoryDatabase
from src.models.history import (
    MessageHistoryItem,
    MessageHistoryResponse,
    MessageHistorySummary,
)
from src.core.logging import logger
from src.core.config import config


class HistoryManager:
    """Service class for managing message history operations"""

    def __init__(self):
        # Global database instance
        print(f"load db from {config.db_file}")
        message_db = MessageHistoryDatabase(config.db_file)
        self.database = message_db

    async def log_request(
        self,
        request_id: str,
        model_name: str,
        actual_model: str,
        request_data: Dict[str, Any],
        openai_request: Optional[Dict[str, Any]] = None,
        user_agent: Optional[str] = None,
        is_streaming: bool = False,
    ) -> bool:
        """Log a new request to the history"""
        try:
            # Create a clean copy of request data for storage
            clean_request_data = self._clean_request_data(request_data)

            success = await self.database.store_request(
                request_id=request_id,
                model_name=model_name,
                actual_model=actual_model,
                request_data=clean_request_data,
                user_agent=user_agent,
                is_streaming=is_streaming,
                openai_request=openai_request,
            )

            if success:
                logger.debug(f"Successfully logged request {request_id}")
            else:
                logger.warning(f"Failed to log request {request_id}")

            return success

        except Exception as e:
            logger.error(f"Error logging request {request_id}: {e}")
            return False

    async def log_response(
        self,
        request_id: str,
        response_data: Dict[str, Any],
        status: str = "completed",
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
    ) -> bool:
        """Log the response for an existing request"""
        try:
            # Create a clean copy of response data for storage
            clean_response_data = self._clean_response_data(response_data)

            success = await self.database.update_response(
                request_id=request_id,
                response_data=clean_response_data,
                status=status,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )

            if success:
                logger.debug(f"Successfully logged response for {request_id}")
            else:
                logger.warning(f"Failed to log response for {request_id}")

            return success

        except Exception as e:
            logger.error(f"Error logging response for {request_id}: {e}")
            return False

    async def get_recent_messages(
        self,
        limit: int = 5,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> MessageHistoryResponse:
        """Get recent messages with full details, optionally filtered by date range"""
        try:
            raw_messages = await self.database.get_recent_messages(
                limit, start_date, end_date
            )

            # Convert to Pydantic models
            messages = [MessageHistoryItem(**msg) for msg in raw_messages]

            return MessageHistoryResponse(
                messages=messages,
                total_count=len(messages),
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(f"Error retrieving recent messages: {e}")
            return MessageHistoryResponse(
                messages=[], total_count=0, timestamp=datetime.now().isoformat()
            )

    async def get_message_summaries(
        self, limit: int = 5
    ) -> List[MessageHistorySummary]:
        """Get recent messages as summaries (for list display)"""
        try:
            raw_messages = await self.database.get_recent_messages(limit)

            # Convert to summary models
            summaries = [
                MessageHistorySummary(
                    id=msg["id"],
                    request_id=msg["request_id"],
                    timestamp=msg["timestamp"],
                    model_name=msg["model_name"],
                    actual_model=msg["actual_model"],
                    request_length=msg["request_length"],
                    response_length=msg["response_length"],
                    status=msg["status"],
                    is_streaming=msg["is_streaming"],
                    input_tokens=msg["input_tokens"],
                    output_tokens=msg["output_tokens"],
                    total_tokens=msg["total_tokens"],
                )
                for msg in raw_messages
            ]

            return summaries

        except Exception as e:
            logger.error(f"Error retrieving message summaries: {e}")
            return []

    async def get_message_by_id(self, message_id: int) -> Optional[MessageHistoryItem]:
        """Get a specific message by its database ID"""
        try:
            messages = await self.database.get_recent_messages(
                limit=1000
            )  # Get enough to find by ID

            for msg in messages:
                if msg["id"] == message_id:
                    return MessageHistoryItem(**msg)

            return None

        except Exception as e:
            logger.error(f"Error retrieving message {message_id}: {e}")
            return None

    async def cleanup_old_messages(self, keep_days: int = 30) -> int:
        """Clean up old messages"""
        try:
            deleted_count = await self.database.cleanup_old_messages(keep_days)
            logger.info(f"Cleaned up {deleted_count} old messages")
            return deleted_count

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    def _clean_request_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean request data for storage (remove sensitive information)"""
        cleaned = {}

        for key, value in request_data.items():
            if key == "messages":
                # Convert Pydantic models to dictionaries
                if isinstance(value, list):
                    cleaned[key] = []
                    for item in value:
                        if hasattr(item, "dict"):  # Pydantic model
                            cleaned[key].append(item.dict())
                        elif hasattr(item, "__dict__"):  # Regular object
                            cleaned[key].append(item.__dict__)
                        else:
                            cleaned[key].append(item)
                else:
                    cleaned[key] = value
            elif key == "system":
                # Handle system content
                if isinstance(value, list):
                    cleaned[key] = []
                    for item in value:
                        if hasattr(item, "dict"):  # Pydantic model
                            cleaned[key].append(item.dict())
                        else:
                            cleaned[key].append(item)
                else:
                    cleaned[key] = value
            elif key == "extra_headers":
                # Remove sensitive headers
                headers = value.copy() if isinstance(value, dict) else {}
                for header_key in list(headers.keys()):
                    if (
                        "api" in header_key.lower()
                        or "auth" in header_key.lower()
                        or "key" in header_key.lower()
                    ):
                        headers[header_key] = "[REDACTED]"
                cleaned[key] = headers
            else:
                # For other fields, copy as-is
                cleaned[key] = value

        return cleaned

    def _clean_response_data(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean response data for storage"""
        cleaned = response_data.copy()

        # For now, we store the full response data
        # In the future, we might want to limit the size or redact sensitive content

        return cleaned

    async def get_token_usage_summary(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get aggregated token usage summary with optional date range filtering"""
        try:
            summary_data = await self.database.get_token_usage_summary(
                start_date, end_date
            )

            # Calculate overall totals
            total_requests = sum(item["request_count"] for item in summary_data)
            total_input_tokens = sum(
                item["total_input_tokens"] for item in summary_data
            )
            total_output_tokens = sum(
                item["total_output_tokens"] for item in summary_data
            )
            total_tokens = sum(item["total_tokens"] for item in summary_data)
            total_completed = sum(item["completed_requests"] for item in summary_data)

            return {
                "by_model": summary_data,
                "totals": {
                    "total_requests": total_requests,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_tokens": total_tokens,
                    "total_completed": total_completed,
                    "overall_success_rate": round(
                        total_completed / max(total_requests, 1) * 100, 2
                    )
                    if total_requests > 0
                    else 0,
                },
                "timestamp": datetime.now().isoformat(),
                "date_range": {"start_date": start_date, "end_date": end_date},
            }

        except Exception as e:
            logger.error(f"Error getting token usage summary: {e}")
            return {
                "by_model": [],
                "totals": {
                    "total_requests": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_tokens": 0,
                    "total_completed": 0,
                    "overall_success_rate": 0,
                },
                "timestamp": datetime.now().isoformat(),
                "date_range": {"start_date": start_date, "end_date": end_date},
            }

    async def update_openai_request(
        self,
        request_id: str,
        openai_request: Dict[str, Any],
    ) -> bool:
        """Update the OpenAI request data for an existing request"""
        try:
            success = await self.database.update_openai_request(
                request_id=request_id,
                openai_request=openai_request,
            )

            if success:
                logger.debug(f"Successfully updated OpenAI request {request_id}")
            else:
                logger.warning(f"Failed to update OpenAI request {request_id}")

            return success

        except Exception as e:
            logger.error(f"Error updating OpenAI request {request_id}: {e}")
            return False


# Global history manager instance
history_manager = HistoryManager()
