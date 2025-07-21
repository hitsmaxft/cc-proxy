from typing import Dict, List, TypedDict
from src.core.config import Config, config

    

class ModelConfig(TypedDict):
    model: str
    base_url: str
    api_key: str

class ModelManager:
    mapping: Dict[str, str] # model name to provider mapping
    config:Config

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
            _type = "small_model"
        elif 'sonnet' in model_lower:
            model = self.config.middle_model
            self.request_counters['self.middle_model'] = self.request_counters.get('self.middle_model', 0) + 1
            _type = "middle_model"
        elif 'opus' in model_lower:
            model = self.config.big_model
            self.request_counters['self.big_model'] = self.request_counters.get('self.big_model', 0) + 1
            _type = "big_model"
        else:
            # Default to big model for unknown models
            model = self.config.big_model
            self.request_counters['self.big_model'] = self.request_counters.get('self.big_model', 0) + 1
            _type = "big_model"

        return self.get_model_config(model, _type)

    
    def get_model_config(self, model: str, model_type:str):

        # map big_model to big_models
        type_key = model_type +"s"

        for p in self.config.provider:
            if type_key in p and model in p[type_key]:
                return ModelConfig(
                model=model,
                base_url = p["base_url"],
                api_key = p["api_key"],
            )
        raise Exception(f"model {model} not found in providers")

        
    def get_model_counters(self) -> dict:
        """Return model request counters for /api/config/get"""
        return self.request_counters

model_manager = ModelManager(config)