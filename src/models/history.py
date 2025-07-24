from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime


class MessageHistoryItem(BaseModel):
    """Pydantic model for a single message history item"""

    id: int
    request_id: str
    timestamp: str
    model_name: str
    actual_model: str
    request_data: Dict[str, Any]
    response_data: Dict[str, Any]
    user_agent: Optional[str] = None
    is_streaming: bool = False
    request_length: int = 0
    response_length: int = 0
    status: str = "pending"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class MessageHistoryResponse(BaseModel):
    """Pydantic model for the message history API response"""

    messages: List[MessageHistoryItem]
    total_count: int
    timestamp: str


class MessageHistorySummary(BaseModel):
    """Pydantic model for a summarized message history item (for list display)"""

    id: int
    request_id: str
    timestamp: str
    model_name: str
    actual_model: str
    request_length: int
    response_length: int
    status: str
    is_streaming: bool
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    @property
    def formatted_timestamp(self) -> str:
        """Return formatted timestamp for display"""
        try:
            dt = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return self.timestamp
