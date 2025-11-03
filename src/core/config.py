import os
import sys
from typing import Any, Dict, List, Optional, TypedDict
from pathlib import Path

import toml

class ModelProvider(TypedDict):
    name: str
    base_url: str
    api_key: Optional[str]
    env_key: Optional[str]
    big_models: List[str]
    middle_models: List[str]
    small_models: List[str]


# Configuration
class Config:
    openai_base_url: str = None
    openai_api_key: str = None
    openai_base_url: str = None
    azure_api_version: str = None
    request_timeout: int

    port: int
    host: str
    web_search: bool = False

    config: Dict[str, Any]
    provider: List[ModelProvider]

    provider_names: List[str]
    small_model: str
    big_model: str
    middle_model: str
    max_tokens_limit: int
    max_retries: int
    port: int
    db_file: str

    big_models: List[str] = []
    middle_models: List[str] = []
    small_models: List[str] = []

    def init_toml(self):
        for k, v in self.config.items():
            print(f"set config.{k}={v}")
            if k in ["port", "request_timeout", "min_tokens_limit", "max_tokens_limit"]:
                setattr(self, k, int(v))
            else:
                setattr(self, k, v)
        self.load_providers(self.provider)
        self._normalize_model_references()

    def load_providers(self, provider: List[Dict[str, Any]]):
        self.provider_names = [x["name"] for x in provider]

        # Process each provider and resolve API keys from environment if needed
        processed_providers = []
        for p in provider:
            # Validate provider configuration first
            if not self.validate_provider_config(p):
                continue

            provider_copy = p.copy()

            # Handle API key resolution (env_key takes priority over api_key)
            if "env_key" in p and p["env_key"]:
                # Load API key from environment variable
                env_var_name = p["env_key"]
                api_key = os.getenv(env_var_name)
                if api_key:
                    provider_copy["api_key"] = api_key
                    print(f"add provider {p['name']} (API key loaded from env: {env_var_name})")
                else:
                    print(f"❌ Error: Environment variable '{env_var_name}' not found for provider '{p['name']}'")
                    continue  # Skip this provider if env var is not found
            elif "api_key" in p and p["api_key"]:
                # Use direct API key from config
                print(f"add provider {p['name']} (API key from config)")
            else:
                print(f"❌ Error: No valid API key found for provider '{p['name']}'")
                continue  # Skip this provider

            processed_providers.append(provider_copy)

            # Load model lists
            for m in ["big_models", "middle_models", "small_models"]:
                if m in p:
                    getattr(self, m).extend(p[m])

        self.provider = processed_providers
        print("loaded big_models:", self.big_models)
        print("loaded middle_models:", self.middle_models)
        print("loaded small_models:", self.small_models)

    def validate_provider_config(self, provider: Dict[str, Any]) -> bool:
        """Validate provider configuration for API key setup"""
        has_api_key = "api_key" in provider and provider["api_key"]
        has_env_key = "env_key" in provider and provider["env_key"]

        if has_api_key and has_env_key:
            print(f"⚠️  Warning: Provider '{provider.get('name', 'unknown')}' has both 'api_key' and 'env_key'. Using 'env_key'.")
            return True
        elif has_api_key or has_env_key:
            return True
        else:
            print(f"❌ Error: Provider '{provider.get('name', 'unknown')}' must have either 'api_key' or 'env_key'")
            return False

    def _normalize_model_references(self):
        """Normalize model references to provider:model format"""
        try:
            # Normalize big_model, middle_model, small_model to provider:model format
            self.big_model = self._normalize_model_id(getattr(self, 'big_model', None))
            self.middle_model = self._normalize_model_id(getattr(self, 'middle_model', None))
            self.small_model = self._normalize_model_id(getattr(self, 'small_model', None))

            print(f"📋 Normalized model references:")
            print(f"   Big model: {self.big_model}")
            print(f"   Middle model: {self.middle_model}")
            print(f"   Small model: {self.small_model}")

        except Exception as e:
            print(f"⚠️  Warning: Failed to normalize model references: {e}")
            # Fallback to defaults if normalization fails
            if self.provider:
                first_provider = self.provider[0]["name"]
                self.big_model = f"{first_provider}:gpt-4o"
                self.middle_model = f"{first_provider}:gpt-4o"
                self.small_model = f"{first_provider}:gpt-4o-mini"

    def _normalize_model_id(self, model_ref: str) -> str:
        """Ensure model reference is in provider:model format"""
        if not model_ref:
            # Default to first provider's first big model if available
            if self.provider:
                first_provider = self.provider[0]
                if first_provider.get("big_models"):
                    return f"{first_provider['name']}:{first_provider['big_models'][0]}"
                # Fallback to common model names
                return f"{first_provider['name']}:gpt-4o"
            return "OpenAI:gpt-4o"  # Ultimate fallback

        if ':' in model_ref:
            # Already in provider:model format
            provider_name, model_name = model_ref.split(':', 1)
            # Validate that provider exists
            if any(p['name'] == provider_name for p in self.provider):
                return model_ref
            else:
                print(f"⚠️  Warning: Provider '{provider_name}' not found, trying to find '{model_name}' in available providers")
                # Try to find the model in available providers
                return self._find_model_in_providers(model_name)
        else:
            # Legacy format - need to find provider
            return self._find_model_in_providers(model_ref)

    def _find_model_in_providers(self, model_name: str) -> str:
        """Find a model in available providers and return provider:model format"""
        for provider in self.provider:
            provider_name = provider["name"]
            all_models = (
                provider.get("big_models", []) +
                provider.get("middle_models", []) +
                provider.get("small_models", [])
            )
            if model_name in all_models:
                return f"{provider_name}:{model_name}"

        # If not found in any provider, use first provider as default
        if self.provider:
            first_provider_name = self.provider[0]["name"]
            print(f"⚠️  Model '{model_name}' not found in any provider, defaulting to {first_provider_name}:{model_name}")
            return f"{first_provider_name}:{model_name}"

        # Ultimate fallback
        return f"OpenAI:{model_name}"

    def _get_all_available_models(self) -> List[str]:
        """Get all available models in provider:model format"""
        all_models = []
        for provider in self.provider:
            provider_name = provider["name"]
            for category in ["big_models", "middle_models", "small_models"]:
                models = provider.get(category, [])
                for model in models:
                    model_id = f"{provider_name}:{model}"
                    if model_id not in all_models:
                        all_models.append(model_id)
        return all_models

    def _is_model_available(self, model_id: str) -> bool:
        """Check if a model_id is available in any provider"""
        if ':' not in model_id:
            return False

        provider_name, model_name = model_id.split(':', 1)
        for provider in self.provider:
            if provider["name"] == provider_name:
                all_models = (
                    provider.get("big_models", []) +
                    provider.get("middle_models", []) +
                    provider.get("small_models", [])
                )
                return model_name in all_models
        return False

    def validate_api_key(self):
        """Basic API key validation"""
        if not self.openai_api_key:
            return False
        # Basic format check for OpenAI API keys
        if not self.openai_api_key.startswith("sk-"):
            return False
        return True

    def validate_client_api_key(self, client_api_key):
        """Validate client's Anthropic API key"""
        # If no ANTHROPIC_API_KEY is set in the environment, skip validation
        if not self.anthropic_api_key:
            return True

        # Check if the client's API key matches the expected value
        return client_api_key == self.anthropic_api_key

    async def load_model_config_from_db(self, db_path: str = None):
        """Load model configuration from database if available"""
        if db_path is None:
            db_path = self.db_file

        try:
            # Import here to avoid circular imports
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from src.storage.database import MessageHistoryDatabase

            db = MessageHistoryDatabase(db_path)
            db_config = await db.load_model_config()

            if db_config:
                loaded_models = []

                # Get all available models in provider:model format
                all_available_models = self._get_all_available_models()

                if "BIG_MODEL" in db_config:
                    old_model = self.big_model
                    requested_model = db_config["BIG_MODEL"]
                    # Normalize the requested model to provider:model format
                    normalized_model = self._normalize_model_id(requested_model)
                    if self._is_model_available(normalized_model):
                        self.big_model = normalized_model
                        loaded_models.append(f"BIG: {old_model} -> {self.big_model}")
                    else:
                        print(f"⚠️  Model '{requested_model}' not available for BIG_MODEL, keeping default: {self.big_model}")

                if "MIDDLE_MODEL" in db_config:
                    old_model = self.middle_model
                    requested_model = db_config["MIDDLE_MODEL"]
                    normalized_model = self._normalize_model_id(requested_model)
                    if self._is_model_available(normalized_model):
                        self.middle_model = normalized_model
                        loaded_models.append(f"MIDDLE: {old_model} -> {self.middle_model}")
                    else:
                        print(f"⚠️  Model '{requested_model}' not available for MIDDLE_MODEL, keeping default: {self.middle_model}")

                if "SMALL_MODEL" in db_config:
                    old_model = self.small_model
                    requested_model = db_config["SMALL_MODEL"]
                    normalized_model = self._normalize_model_id(requested_model)
                    if self._is_model_available(normalized_model):
                        self.small_model = normalized_model
                        loaded_models.append(f"SMALL: {old_model} -> {self.small_model}")
                    else:
                        print(f"⚠️  Model '{requested_model}' not available for SMALL_MODEL, keeping default: {self.small_model}")

                if loaded_models:
                    print(
                        f"📥 Loaded model configuration from database: {', '.join(loaded_models)}"
                    )
                return True
            return False

        except Exception as e:
            print(f"⚠️  Warning: Could not load model config from database: {e}")
            return False


# Global config instance - will be initialized from main.py
config = None


def init_config(config_file: str):
    """Initialize global config instance from TOML file"""

    global config
    if not config_file:
        raise ValueError("TOML configuration file is required")
    
    print(f"load toml config from {config_file}")
    with open(config_file, "r") as f:
        data = toml.load(f)
        config = Config()
        for key, value in data.items():
            setattr(config, key, value)
        for k, v in data.get("config", {}).items():
            os.environ[k] = "v"
        config.init_toml()
        print(f" Configuration loaded: providers={config.provider_names}")
    return config
    
## src root
SrcDir= os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
##
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


if __name__ == "__main__":
    print(SrcDir)
    print(ASSETS_DIR)