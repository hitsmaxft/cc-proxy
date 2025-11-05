from typing import Dict, List, TypedDict, Tuple, Optional
from dataclasses import dataclass
from src.core.config import Config, config


class ModelConfig(TypedDict):
    model: str
    base_url: str
    api_key: str
    provider: str


@dataclass
class EnhancedModelConfig:
    """Enhanced ModelConfig with provider:model format support"""
    model: str           # Original model name without provider
    provider: str        # Provider name
    base_url: str       # Provider base URL
    api_key: str        # Provider API key
    model_id: str       # Full provider:model format

    @classmethod
    def from_model_id(cls, model_id: str, providers: List[Dict]) -> 'EnhancedModelConfig':
        """Create EnhancedModelConfig from provider:model format"""
        if ':' in model_id:
            provider_name, model_name = model_id.split(':', 1)
        else:
            # Backward compatibility - find first provider with model
            provider_name, model_name = cls._resolve_legacy_model(model_id, providers)

        # Find the provider configuration
        provider_config = None
        for p in providers:
            if p["name"] == provider_name:
                provider_config = p
                break

        if not provider_config:
            raise ValueError(f"Provider '{provider_name}' not found")

        return cls(
            model=model_name,
            provider=provider_name,
            base_url=provider_config["base_url"],
            api_key=provider_config["api_key"],
            model_id=f"{provider_name}:{model_name}"
        )

    @classmethod
    def _resolve_legacy_model(cls, model_name: str, providers: List[Dict]) -> Tuple[str, str]:
        """Handle legacy model names without provider prefix"""
        for provider in providers:
            all_models = (
                provider.get("big_models", []) +
                provider.get("middle_models", []) +
                provider.get("small_models", [])
            )
            if model_name in all_models:
                return provider["name"], model_name

        raise ValueError(f"Model '{model_name}' not found in any provider")

    def to_legacy_model_config(self) -> ModelConfig:
        """Convert to legacy ModelConfig format for backward compatibility"""
        return ModelConfig(
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            provider=self.provider
        )


class ModelManager:
    mapping: Dict[str, str]  # model name to provider mapping
    config: Config

    def __init__(self, config: Config):
        self.config = config
        self.request_counters = {}

    def enable_websearch(self):
        return self.config.web_search

    def map_claude_model_to_openai(self, claude_model: str) -> ModelConfig:
        """Map Claude model names to OpenAI format - backward compatible version"""
        enhanced_config = self.map_claude_model_to_openai_enhanced(claude_model)
        return enhanced_config.to_legacy_model_config()

    def map_claude_model_to_openai_enhanced(self, claude_model: str) -> EnhancedModelConfig:
        """Map Claude model names to OpenAI format using provider:model IDs"""
        # If it's already an OpenAI model, return as-is with first available provider
        if claude_model.startswith("gpt-") or claude_model.startswith("o1-"):
            key = f"self.{claude_model.replace('-', '_')}"
            self.request_counters[key] = self.request_counters.get(key, 0) + 1
            return self._create_model_config_for_legacy_model(claude_model)

        # If it's other supported models (ARK/Doubao/DeepSeek), return as-is
        if (
            claude_model.startswith("ep-")
            or claude_model.startswith("doubao-")
            or claude_model.startswith("deepseek-")
        ):
            key = f"self.{claude_model.replace('-', '_')}"
            self.request_counters[key] = self.request_counters.get(key, 0) + 1
            return self._create_model_config_for_legacy_model(claude_model)

        # Map based on model naming patterns to provider:model format
        model_lower = claude_model.lower()
        if "haiku" in model_lower or "claude-3-" in model_lower:
            target_model_id = self.config.small_model
            self.request_counters["self.small_model"] = (
                self.request_counters.get("self.small_model", 0) + 1
            )
        elif "sonnet" in model_lower:
            target_model_id = self.config.middle_model
            self.request_counters["self.middle_model"] = (
                self.request_counters.get("self.middle_model", 0) + 1
            )
        elif "opus" in model_lower:
            target_model_id = self.config.big_model
            self.request_counters["self.big_model"] = (
                self.request_counters.get("self.big_model", 0) + 1
            )
        else:
            # Default to big model for unknown models
            target_model_id = self.config.big_model
            self.request_counters["self.big_model"] = (
                self.request_counters.get("self.big_model", 0) + 1
            )

        return EnhancedModelConfig.from_model_id(target_model_id, self.config.provider)

    def _create_model_config_for_legacy_model(self, model_name: str) -> EnhancedModelConfig:
        """Create EnhancedModelConfig for legacy models that are already in OpenAI format"""
        try:
            return EnhancedModelConfig.from_model_id(model_name, self.config.provider)
        except ValueError:
            # If model not found, use first provider as fallback
            if self.config.provider:
                first_provider = self.config.provider[0]
                return EnhancedModelConfig(
                    model=model_name,
                    provider=first_provider["name"],
                    base_url=first_provider["base_url"],
                    api_key=first_provider["api_key"],
                    model_id=f"{first_provider['name']}:{model_name}"
                )
            else:
                raise ValueError("No providers configured")

    def map_claude_model_to_openai_legacy(self, claude_model: str) -> str:
        """Legacy method - maps to string for backward compatibility"""
        enhanced_config = self.map_claude_model_to_openai(claude_model)
        return enhanced_config.model

    def get_model_config(self, model: str, model_type: str):
        """Legacy method - maintained for backward compatibility"""
        # map big_model to big_models
        type_key = model_type + "s"

        for p in self.config.provider:
            if type_key in p and model in p[type_key]:
                return ModelConfig(
                    model=model,
                    base_url=p["base_url"],
                    api_key=p["api_key"],
                    provider=p["name"],
                )
        raise Exception(f"model {model} not found in providers")

    def get_enhanced_model_config(self, model_id: str) -> EnhancedModelConfig:
        """Get enhanced model configuration from provider:model ID"""
        return EnhancedModelConfig.from_model_id(model_id, self.config.provider)

    def get_available_models(self) -> Dict[str, List[str]]:
        """Get all available models in provider:model format"""
        models_by_category = {
            "big_models": [],
            "middle_models": [],
            "small_models": []
        }

        for provider in self.config.provider:
            provider_name = provider["name"]
            for category in ["big_models", "middle_models", "small_models"]:
                provider_models = provider.get(category, [])
                for model in provider_models:
                    model_id = f"{provider_name}:{model}"
                    models_by_category[category].append(model_id)

        return models_by_category

    def get_model_catalog(self) -> Dict[str, any]:
        """Generate comprehensive model catalog with provider:model IDs"""
        catalog = {
            "providers": {},
            "models_by_category": {
                "big_models": [],
                "middle_models": [],
                "small_models": []
            },
            "current_selection": {
                "big_model": self.config.big_model,
                "middle_model": self.config.middle_model,
                "small_model": self.config.small_model
            }
        }

        for provider in self.config.provider:
            provider_name = provider["name"]
            catalog["providers"][provider_name] = {
                "name": provider_name,
                "base_url": provider["base_url"],
                "models": {
                    "big_models": [f"{provider_name}:{m}" for m in provider.get("big_models", [])],
                    "middle_models": [f"{provider_name}:{m}" for m in provider.get("middle_models", [])],
                    "small_models": [f"{provider_name}:{m}" for m in provider.get("small_models", [])]
                }
            }

            # Add to global category lists
            catalog["models_by_category"]["big_models"].extend(
                [f"{provider_name}:{m}" for m in provider.get("big_models", [])]
            )
            catalog["models_by_category"]["middle_models"].extend(
                [f"{provider_name}:{m}" for m in provider.get("middle_models", [])]
            )
            catalog["models_by_category"]["small_models"].extend(
                [f"{provider_name}:{m}" for m in provider.get("small_models", [])]
            )

        return catalog

    def validate_model_id(self, model_id: str) -> bool:
        """Validate if a model_id is valid and available"""
        try:
            self.get_enhanced_model_config(model_id)
            return True
        except ValueError:
            return False

    def get_model_counters(self) -> dict:
        """Return model request counters for /api/config/get"""
        return self.request_counters

    def get_provider_name_from_model(self, model: str) -> Optional[str]:
        """Extract provider name from model string"""
        if ':' in model:
            return model.split(':', 1)[0]
        return None


model_manager = ModelManager(config)
