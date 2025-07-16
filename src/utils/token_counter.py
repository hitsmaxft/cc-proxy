from typing import Dict, Any, Tuple
import re

def extract_token_usage(response_data: Dict[str, Any]) -> Tuple[int, int, int]:
    """
    Extract token usage from OpenAI-style response.
    Returns (input_tokens, output_tokens, total_tokens)
    """
    input_tokens = 0
    output_tokens = 0 
    total_tokens = 0

    try:
        # Check for usage in response (OpenAI format)
        if 'usage' in response_data:
            usage = response_data['usage']
            input_tokens = usage.get('prompt_tokens', 0)
            output_tokens = usage.get('completion_tokens', 0)
            total_tokens = usage.get('total_tokens', 0)
        
        # If total_tokens is not provided, calculate it
        if total_tokens == 0 and (input_tokens > 0 or output_tokens > 0):
            total_tokens = input_tokens + output_tokens
            
    except Exception as e:
        # If extraction fails, return zeros
        pass
    
    return input_tokens, output_tokens, total_tokens

def estimate_token_count_from_text(text: str) -> int:
    """
    Rough estimation of token count from text.
    Uses approximate ratio of 4 characters per token for English text.
    """
    if not text:
        return 0
    
    # Remove extra whitespace and count characters
    cleaned_text = re.sub(r'\s+', ' ', text.strip())
    char_count = len(cleaned_text)
    
    # Rough estimation: 4 characters per token
    estimated_tokens = max(1, char_count // 4)
    
    return estimated_tokens

def estimate_input_tokens_from_request(request_data: Dict[str, Any]) -> int:
    """
    Estimate input tokens from request data.
    """
    total_chars = 0
    
    try:
        # Count system message characters
        if request_data.get('system'):
            system_content = request_data['system']
            if isinstance(system_content, str):
                total_chars += len(system_content)
            elif isinstance(system_content, list):
                for item in system_content:
                    if isinstance(item, dict) and 'text' in item:
                        total_chars += len(item['text'])
        
        # Count message characters
        messages = request_data.get('messages', [])
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get('content', '')
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            total_chars += len(block.get('text', ''))
    
    except Exception:
        # If estimation fails, return 0
        return 0
    
    return estimate_token_count_from_text(' ' * total_chars)

def estimate_output_tokens_from_content(content: str) -> int:
    """
    Estimate output tokens from response content.
    """
    if not content:
        return 0
    
    return estimate_token_count_from_text(content)
