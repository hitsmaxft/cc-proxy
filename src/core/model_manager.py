from src.core.config import Config, config

class ModelManager:
    def __init__(self, config: Config):
        self.config = config
        self.request_counters = {}

    def enable_websearch(self):
        return self.config.web_search
    
    def map_claude_model_to_openai(self, claude_model: str) -> str:
        """Map Claude model names to OpenAI model names based on BIG/SMALL pattern"""
        # If it's already an OpenAI model, return as-is
        if claude_model.startswith("gpt-") or claude_model.startswith("o1-"):
            key = f"self.{claude_model.replace('-', '_')}"
            self.request_counters[key] = self.request_counters.get(key, 0) + 1
            return claude_model

        # If it's other supported models (ARK/Doubao/DeepSeek), return as-is
        if (claude_model.startswith("ep-") or claude_model.startswith("doubao-") or 
            claude_model.startswith("deepseek-")):
            key = f"self.{claude_model.replace('-', '_')}"
            self.request_counters[key] = self.request_counters.get(key, 0) + 1
            return claude_model
        
        # Map based on model naming patterns
        model_lower = claude_model.lower()
        if 'haiku' in model_lower:
            model = self.config.small_model
            self.request_counters['self.small_model'] = self.request_counters.get('self.small_model', 0) + 1
        elif 'sonnet' in model_lower:
            model = self.config.middle_model
            self.request_counters['self.middle_model'] = self.request_counters.get('self.middle_model', 0) + 1
        elif 'opus' in model_lower:
            model = self.config.big_model
            self.request_counters['self.big_model'] = self.request_counters.get('self.big_model', 0) + 1
        else:
            # Default to big model for unknown models
            model = self.config.big_model
            self.request_counters['self.big_model'] = self.request_counters.get('self.big_model', 0) + 1
        
        return model
    
    def get_model_counters(self) -> dict:
        """Return model request counters for /api/config/get"""
        return self.request_counters

model_manager = ModelManager(config)