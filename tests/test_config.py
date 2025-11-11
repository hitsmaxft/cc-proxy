"""Unit tests for configuration functionality."""

import os
import tempfile
import unittest
from unittest.mock import patch
import toml
import sys

# Add src to path for importing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.config import Config, init_config


class TestConfigEnvironmentKeys(unittest.TestCase):
    """Test environment key functionality in configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_config_data = {
            "config": {
                "port": 8082,
                "log_level": "INFO",
                "big_model": "gpt-4o",
                "middle_model": "gpt-4o",
                "small_model": "gpt-4o-mini"
            },
            "provider": []
        }

    def test_env_key_resolution_success(self):
        """Test successful environment variable resolution."""
        # Create test config with env_key
        self.test_config_data["provider"] = [{
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "env_key": "TEST_OPENAI_API_KEY",
            "big_models": ["gpt-4o"],
            "middle_models": ["gpt-4o"],
            "small_models": ["gpt-4o-mini"]
        }]

        # Set up environment variable
        test_api_key = "sk-test1234567890abcdef"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(self.test_config_data, f)
            config_file = f.name

        try:
            with patch.dict(os.environ, {'TEST_OPENAI_API_KEY': test_api_key}):
                config = init_config(config_file)

                # Verify the API key was loaded from environment
                self.assertEqual(len(config.provider), 1)
                self.assertEqual(config.provider[0]["api_key"], test_api_key)
                self.assertEqual(config.provider[0]["name"], "OpenAI")
        finally:
            os.unlink(config_file)

    def test_env_key_resolution_missing_var(self):
        """Test behavior when environment variable is missing."""
        # Create test config with env_key
        self.test_config_data["provider"] = [{
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "env_key": "MISSING_API_KEY",
            "big_models": ["gpt-4o"],
            "middle_models": ["gpt-4o"],
            "small_models": ["gpt-4o-mini"]
        }]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(self.test_config_data, f)
            config_file = f.name

        try:
            # Ensure the env var doesn't exist
            with patch.dict(os.environ, {}, clear=False):
                if 'MISSING_API_KEY' in os.environ:
                    del os.environ['MISSING_API_KEY']

                config = init_config(config_file)

                # Provider should be skipped due to missing env var
                self.assertEqual(len(config.provider), 0)
        finally:
            os.unlink(config_file)

    def test_direct_api_key_still_works(self):
        """Test that direct API key in config still works (backward compatibility)."""
        test_api_key = "sk-direct1234567890abcdef"

        # Create test config with direct api_key
        self.test_config_data["provider"] = [{
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "api_key": test_api_key,
            "big_models": ["gpt-4o"],
            "middle_models": ["gpt-4o"],
            "small_models": ["gpt-4o-mini"]
        }]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(self.test_config_data, f)
            config_file = f.name

        try:
            config = init_config(config_file)

            # Verify the direct API key is used
            self.assertEqual(len(config.provider), 1)
            self.assertEqual(config.provider[0]["api_key"], test_api_key)
            self.assertEqual(config.provider[0]["name"], "OpenAI")
        finally:
            os.unlink(config_file)

    def test_env_key_takes_priority_over_api_key(self):
        """Test that env_key takes priority when both env_key and api_key are specified."""
        direct_api_key = "sk-direct1234567890abcdef"
        env_api_key = "sk-env1234567890abcdef"

        # Create test config with both api_key and env_key
        self.test_config_data["provider"] = [{
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "api_key": direct_api_key,
            "env_key": "PRIORITY_TEST_API_KEY",
            "big_models": ["gpt-4o"],
            "middle_models": ["gpt-4o"],
            "small_models": ["gpt-4o-mini"]
        }]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(self.test_config_data, f)
            config_file = f.name

        try:
            with patch.dict(os.environ, {'PRIORITY_TEST_API_KEY': env_api_key}):
                config = init_config(config_file)

                # Verify the env API key is used (takes priority)
                self.assertEqual(len(config.provider), 1)
                self.assertEqual(config.provider[0]["api_key"], env_api_key)
                self.assertNotEqual(config.provider[0]["api_key"], direct_api_key)
        finally:
            os.unlink(config_file)

    def test_multiple_providers_mixed_config(self):
        """Test multiple providers with mixed env_key and direct api_key configuration."""
        direct_api_key = "sk-direct1234567890abcdef"
        env_api_key = "sk-env1234567890abcdef"

        # Create test config with multiple providers
        self.test_config_data["provider"] = [
            {
                "name": "OpenAI-Direct",
                "base_url": "https://api.openai.com/v1",
                "api_key": direct_api_key,
                "big_models": ["gpt-4o"],
                "middle_models": ["gpt-4o"],
                "small_models": ["gpt-4o-mini"]
            },
            {
                "name": "OpenAI-Env",
                "base_url": "https://api.openai.com/v1",
                "env_key": "MULTI_TEST_API_KEY",
                "big_models": ["gpt-4o"],
                "middle_models": ["gpt-4o"],
                "small_models": ["gpt-4o-mini"]
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(self.test_config_data, f)
            config_file = f.name

        try:
            with patch.dict(os.environ, {'MULTI_TEST_API_KEY': env_api_key}):
                config = init_config(config_file)

                # Verify both providers were loaded correctly
                self.assertEqual(len(config.provider), 2)

                # Check direct API key provider
                direct_provider = next(p for p in config.provider if p["name"] == "OpenAI-Direct")
                self.assertEqual(direct_provider["api_key"], direct_api_key)

                # Check env API key provider
                env_provider = next(p for p in config.provider if p["name"] == "OpenAI-Env")
                self.assertEqual(env_provider["api_key"], env_api_key)
        finally:
            os.unlink(config_file)

    def test_provider_validation_no_keys(self):
        """Test provider validation when neither api_key nor env_key is specified."""
        # Create test config without api_key or env_key
        self.test_config_data["provider"] = [{
            "name": "Invalid",
            "base_url": "https://api.example.com/v1",
            "big_models": ["gpt-4o"],
            "middle_models": ["gpt-4o"],
            "small_models": ["gpt-4o-mini"]
        }]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(self.test_config_data, f)
            config_file = f.name

        try:
            config = init_config(config_file)

            # Provider should be skipped due to missing keys
            self.assertEqual(len(config.provider), 0)
        finally:
            os.unlink(config_file)


if __name__ == '__main__':
    unittest.main()