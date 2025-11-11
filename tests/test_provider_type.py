"""Tests for provider type configuration and functionality."""
import pytest
from typing import Dict, Any
from src.core.config import ModelProvider, Config
from src.core.model_manager import ModelManager, EnhancedModelConfig
from src.core.client_factory import ClientFactory
from src.core.client import OpenAIClient
from src.core.anthropic_client import AnthropicClient


class TestProviderTypeConfiguration:
    """Test provider type configuration validation and loading."""

    def test_provider_type_defaults_to_openai(self):
        """Test that provider_type defaults to 'openai' when not specified."""
        config = Config()
        config.provider = [{
            "name": "TestProvider",
            "base_url": "https://api.test.com",
            "api_key": "test-key",
            "big_models": ["model1"],
            "middle_models": ["model2"],
            "small_models": ["model3"]
        }]
        config.load_providers(config.provider)

        assert config.provider[0]["provider_type"] == "openai"

    def test_provider_type_anthropic_validation(self):
        """Test that 'anthropic' is accepted as a valid provider_type."""
        config = Config()
        provider_config = {
            "name": "Anthropic-Direct",
            "base_url": "https://api.anthropic.com",
            "api_key": "test-key",
            "provider_type": "anthropic",
            "big_models": ["claude-3-opus"],
            "middle_models": ["claude-3-sonnet"],
            "small_models": ["claude-3-haiku"]
        }

        assert config.validate_provider_config(provider_config) == True

    def test_provider_type_invalid_validation(self):
        """Test that invalid provider_type values are rejected."""
        config = Config()
        provider_config = {
            "name": "TestProvider",
            "base_url": "https://api.test.com",
            "api_key": "test-key",
            "provider_type": "invalid",
            "big_models": ["model1"],
            "middle_models": ["model2"],
            "small_models": ["model3"]
        }

        assert config.validate_provider_config(provider_config) == False

    def test_mixed_provider_types(self):
        """Test configuration with both OpenAI and Anthropic providers."""
        config = Config()
        config.provider = [
            {
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
                "api_key": "openai-key",
                "provider_type": "openai",
                "big_models": ["gpt-4"],
                "middle_models": ["gpt-4"],
                "small_models": ["gpt-3.5-turbo"]
            },
            {
                "name": "Anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "anthropic-key",
                "provider_type": "anthropic",
                "big_models": ["claude-3-opus"],
                "middle_models": ["claude-3-sonnet"],
                "small_models": ["claude-3-haiku"]
            }
        ]
        config.load_providers(config.provider)

        assert len(config.provider) == 2
        assert config.provider[0]["provider_type"] == "openai"
        assert config.provider[1]["provider_type"] == "anthropic"


class TestModelManagement:
    """Test model management with provider types."""

    def test_enhanced_model_config_includes_provider_type(self):
        """Test that EnhancedModelConfig includes provider_type."""
        providers = [{
            "name": "TestProvider",
            "base_url": "https://api.test.com",
            "api_key": "test-key",
            "provider_type": "anthropic",
            "big_models": ["test-model"]
        }]

        config = EnhancedModelConfig.from_model_id("TestProvider:test-model", providers)

        assert config.provider_type == "anthropic"
        assert config.model == "test-model"
        assert config.provider == "TestProvider"

    def test_model_config_includes_provider_type(self):
        """Test that ModelConfig includes provider_type."""
        config = Config()
        config.provider = [{
            "name": "Anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key": "test-key",
            "provider_type": "anthropic",
            "big_models": ["claude-3-opus"],
            "middle_models": [],
            "small_models": []
        }]

        manager = ModelManager(config)
        model_config = manager.get_model_config("claude-3-opus", "big_model")

        assert model_config["provider_type"] == "anthropic"
        assert model_config["model"] == "claude-3-opus"

    def test_anthropic_model_mapping_bypass(self):
        """Test that Anthropic models bypass mapping when found in Anthropic provider."""
        config = Config()
        config.provider = [
            {
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
                "api_key": "openai-key",
                "provider_type": "openai",
                "big_models": ["gpt-4"]
            },
            {
                "name": "Anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "anthropic-key",
                "provider_type": "anthropic",
                "big_models": ["claude-3-5-sonnet-20241022"]
            }
        ]
        config.big_model = "OpenAI:gpt-4"  # Default to OpenAI

        manager = ModelManager(config)
        enhanced_config = manager.map_claude_model_to_openai_enhanced("claude-3-5-sonnet-20241022")

        assert enhanced_config.provider_type == "anthropic"
        assert enhanced_config.model == "claude-3-5-sonnet-20241022"
        assert enhanced_config.provider == "Anthropic"

    def test_model_catalog_includes_provider_type(self):
        """Test that model catalog includes provider type information."""
        config = Config()
        config.provider = [{
            "name": "Anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key": "test-key",
            "provider_type": "anthropic",
            "big_models": ["claude-3-opus"]
        }]
        config.big_model = "Anthropic:claude-3-opus"
        config.middle_model = "Anthropic:claude-3-opus"
        config.small_model = "Anthropic:claude-3-opus"

        manager = ModelManager(config)
        catalog = manager.get_model_catalog()

        assert "Anthropic" in catalog["providers"]
        assert catalog["providers"]["Anthropic"]["provider_type"] == "anthropic"


class TestClientFactory:
    """Test client factory with provider types."""

    def test_client_factory_returns_openai_client_for_openai_type(self):
        """Test that ClientFactory returns OpenAIClient for openai provider_type."""
        model_config = {
            "model": "gpt-4",
            "base_url": "https://api.openai.com/v1",
            "api_key": "test-key",
            "provider": "OpenAI",
            "provider_type": "openai"
        }

        client = ClientFactory.get_client(model_config)
        assert isinstance(client, OpenAIClient)

    def test_client_factory_returns_anthropic_client_for_anthropic_type(self):
        """Test that ClientFactory returns AnthropicClient for anthropic provider_type."""
        model_config = {
            "model": "claude-3-opus",
            "base_url": "https://api.anthropic.com",
            "api_key": "test-key",
            "provider": "Anthropic",
            "provider_type": "anthropic"
        }

        client = ClientFactory.get_client(model_config)
        assert isinstance(client, AnthropicClient)

    def test_client_factory_defaults_to_openai_client(self):
        """Test that ClientFactory defaults to OpenAIClient when provider_type is missing."""
        model_config = {
            "model": "gpt-4",
            "base_url": "https://api.openai.com/v1",
            "api_key": "test-key",
            "provider": "OpenAI"
            # provider_type is missing
        }

        client = ClientFactory.get_client(model_config)
        assert isinstance(client, OpenAIClient)


class TestBackwardCompatibility:
    """Test backward compatibility with existing configurations."""

    def test_existing_config_without_provider_type_works(self):
        """Test that existing configurations without provider_type continue to work."""
        config = Config()
        config.provider = [{
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "api_key": "test-key",
            "big_models": ["gpt-4"],
            "middle_models": ["gpt-4"],
            "small_models": ["gpt-3.5-turbo"]
            # No provider_type field
        }]
        config.load_providers(config.provider)

        # Should default to openai
        assert config.provider[0]["provider_type"] == "openai"

        # Model manager should work normally
        config.big_model = "OpenAI:gpt-4"
        manager = ModelManager(config)
        model_config = manager.map_claude_model_to_openai("claude-3-opus")

        assert model_config["provider_type"] == "openai"

    def test_legacy_model_config_conversion(self):
        """Test that EnhancedModelConfig converts to legacy format correctly."""
        enhanced = EnhancedModelConfig(
            model="claude-3-opus",
            provider="Anthropic",
            base_url="https://api.anthropic.com",
            api_key="test-key",
            model_id="Anthropic:claude-3-opus",
            provider_type="anthropic"
        )

        legacy = enhanced.to_legacy_model_config()

        assert legacy["model"] == "claude-3-opus"
        assert legacy["provider"] == "Anthropic"
        assert legacy["provider_type"] == "anthropic"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])