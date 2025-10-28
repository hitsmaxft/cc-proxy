import os
import sys
from typing import Any, Dict, List,  TypedDict
from pathlib import Path

import toml

class ModelProvider(TypedDict):
    name: str
    base_url: str
    api_key: str
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

    def load_providers(self, provider: List[Dict[str, Any]]):
        self.provider_names = [x["name"] for x in provider]
        self.provider = provider

        for provider in provider:
            print(f"add provider {provider['name']}")
            for m in ["big_models", "middle_models", "small_models"]:
                if m in provider:
                    getattr(self, m).extend(provider[m])
        print("loaded big_models:", self.big_models)
        print("loaded middle_models:", self.middle_models)
        print("loaded small_models:", self.small_models)

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
                if (
                    "BIG_MODEL" in db_config
                    and db_config["BIG_MODEL"] in self.big_models
                ):
                    old_model = self.big_model
                    self.big_model = db_config["BIG_MODEL"]
                    loaded_models.append(f"BIG: {old_model} -> {self.big_model}")
                else:
                    self.big_model = self.big_models[0]

                if (
                    "MIDDLE_MODEL" in db_config
                    and db_config["MIDDLE_MODEL"] in self.middle_models
                ):
                    old_model = self.middle_model
                    self.middle_model = db_config["MIDDLE_MODEL"]
                    loaded_models.append(f"MIDDLE: {old_model} -> {self.middle_model}")
                else:
                    self.middle_model = self.middle_models[0]

                if (
                    "SMALL_MODEL" in db_config
                    and db_config["SMALL_MODEL"] in self.small_models
                ):
                    old_model = self.small_model
                    self.small_model = db_config["SMALL_MODEL"]
                    loaded_models.append(f"SMALL: {old_model} -> {self.small_model}")
                else:
                    self.small_model = self.small_models[0]

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