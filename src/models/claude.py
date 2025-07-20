from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union, Literal

class ClaudeContentBlockText(BaseModel):
    type: Literal["text"]
    text: str

class ClaudeContentBlockImage(BaseModel):
    type: Literal["image"]
    source: Dict[str, Any]

class ClaudeContentBlockToolUse(BaseModel):
    type: Literal["tool_use"]
    id: str
    name: str
    input: Dict[str, Any]

class ClaudeContentBlockToolResult(BaseModel):
    type: Literal["tool_result"]
    tool_use_id: str
    content: Union[str, List[Dict[str, Any]], Dict[str, Any]]

class ClaudeSystemContent(BaseModel):
    type: Literal["text"]
    text: str

class ClaudeMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Union[str, List[Union[ClaudeContentBlockText, ClaudeContentBlockImage, ClaudeContentBlockToolUse, ClaudeContentBlockToolResult]]]

class ClaudeTool(BaseModel):
    name: str
    description: Optional[str] = None

    type: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None # claude web search may not contains this input

class ClaudeThinkingConfig(BaseModel):
    enabled: bool = True

class ClaudeMessagesRequest(BaseModel):
    model: str
    max_tokens: int
    messages: List[ClaudeMessage]
    system: Optional[Union[str, List[ClaudeSystemContent]]] = None
    stop_sequences: Optional[List[str]] = None
    stream: Optional[bool] = False
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    tools: Optional[List[ClaudeTool]] = None
    tool_choice: Optional[Dict[str, Any]] = None
    thinking: Optional[ClaudeThinkingConfig] = None

class ClaudeTokenCountRequest(BaseModel):
    model: str
    messages: List[ClaudeMessage]
    system: Optional[Union[str, List[ClaudeSystemContent]]] = None
    tools: Optional[List[ClaudeTool]] = None
    thinking: Optional[ClaudeThinkingConfig] = None
    tool_choice: Optional[Dict[str, Any]] = None


# Web Search Tool Implementation
class WebSearchTool(ClaudeTool):
    def __init__(self, max_uses:int = 3):
        super().__init__(
            name="web_search",
            description="Performs web searches with configurable filters",
            type="web_search_20250305",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_uses": {
                        "type": "integer", 
                        "minimum": 1,
                        "maximum": 5,
                        "default": 3
                    },
                    "allowed_domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": []
                    },
                    "user_location": {
                        "type": "object",
                        "properties": {
                            "country": {"type": "string", "pattern": "^[A-Z]{2}$"}
                        }
                    }
                },
                "required": ["query"]
            }
        )