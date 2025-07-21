import json
import os
import sys
from typing import Any, Dict, List, Optional, TypedDict
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
    openai_base_url:str =None
    openai_api_key: str = None
    openai_base_url: str =None
    azure_api_version:str=None
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
    max_tokens_limit:int
    max_retries:int
    port:int
    db_file:str

    big_models : List[str] = []
    middle_models : List[str] = []
    small_models : List[str] = []

    def init_toml(self):
        for (k, v) in self.config.items():
            print(f"set config.{k}={v}")
            if k in ["port", "request_timeout", "min_tokens_limit", "max_tokens_limit"]:
                setattr(self, k, int(v))
            else:
                setattr(self, k, v)
        self.load_providers(self.provider)

    def load_providers(self, provider: List[Dict[str, Any]]):
        self.provider_names = [ x["name"] for x in provider]
        self.provider = provider

        for provider in provider:
            print(f"add provider {provider["name"]}")
            for m in ["big_models", "middle_models", "small_models"]:
                if m in provider:
                    getattr(self, m).extend(provider[m])
        print("big_models:", self.big_models)
        print("middle_models:", self.middle_models)
        print("small_models:", self.small_models)


    def load_env(self):
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        # Add Anthropic API key for client validation
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.anthropic_api_key:
            print("Warning: ANTHROPIC_API_KEY not set. Client API key validation will be disabled.")

        self.openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.azure_api_version = os.environ.get("AZURE_API_VERSION")  # For Azure OpenAI
        self.host = os.environ.get("HOST", "0.0.0.0")
        self.port = int(os.environ.get("PORT", "8082"))
        self.log_level = os.environ.get("LOG_LEVEL", "INFO")
        self.max_tokens_limit = int(os.environ.get("MAX_TOKENS_LIMIT", "4096"))
        self.min_tokens_limit = int(os.environ.get("MIN_TOKENS_LIMIT", "100"))
        self.db_file = os.environ.get("DB_FILE", "cc.db")

        # Connection settings
        self.request_timeout = int(os.environ.get("REQUEST_TIMEOUT", "90"))
        self.max_retries = int(os.environ.get("MAX_RETRIES", "2"))

        # Model settings - BIG and SMALL models
        # Available model lists for CLI
        self.big_models = [m.strip() for m in os.environ.get("BIG_MODELS", os.environ.get("BIG_MODEL", "gpt-4o")).split(",")]
        self.middle_models = [m.strip() for m in os.environ.get("MIDDLE_MODELS",os.environ.get("MIDDLE_MODEL", self.big_models)).split(",")]
        self.small_models = [m.strip() for m in os.environ.get("SMALL_MODELS",os.environ.get("SMALL_MODEL", "gpt-4o-mini")).split(",")]


        self.big_model = self.big_models[0]
        self.middle_model = self.middle_models[0]
        self.small_model = self.small_models[0]
        self.model_provders = {}

        self.web_search = os.environ.get("WEB_SEARCH")  # For Azure OpenAI

        self.load_providers(
            [ModelProvider(
            name="default",
            base_url=self.openai_base_url,
            api_key=self.openai_api_key,
            big_models=self.big_models,
            middle_models=self.middle_models,
            small_models= self.small_models,
        )]

        )

    def validate_api_key(self):
        """Basic API key validation"""
        if not self.openai_api_key:
            return False
        # Basic format check for OpenAI API keys
        if not self.openai_api_key.startswith('sk-'):
            return False
        return True

    def validate_client_api_key(self, client_api_key):
        """Validate client's Anthropic API key"""
        # If no ANTHROPIC_API_KEY is set in the environment, skip validation
        if not self.anthropic_api_key:
            return True

        # Check if the client's API key matches the expected value
        return client_api_key == self.anthropic_api_key

# Global config instance - will be initialized from main.py
config = None

def init_config(config_file:Optional[str] = None):
    """Initialize global config instance"""

    global config
    if config_file:
        print(f"load toml config from {config_file}")
        with open(config_file, 'r') as f:
            data = toml.load(f)
            config = Config()
            for key, value in data.items():
                setattr(config, key, value)
            for (k, v) in data.get("config", {}).items():
                os.environ[k] = "v"
            config.init_toml()
            print(f" Configuration loaded: providers={config.provider_names}")
                
    else:
        try:
            config = Config()
            config.load_env()
            print(f" Configuration loaded: API_KEY={'*' * 20}..., BASE_URL='{config.openai_base_url}'")
            return config
        except Exception as e:
            print(f"=4 Configuration Error: {e}")
            sys.exit(1)
    return config
