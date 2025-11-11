"""Integration tests for Anthropic provider functionality."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.core.config import Config
from src.core.model_manager import ModelManager
from src.api.endpoints import create_message
from src.models.claude import ClaudeMessagesRequest, ClaudeMessage


class TestAnthropicIntegration:
    """Integration tests for Anthropic provider flow."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config with Anthropic provider."""
        config = Mock(spec=Config)
        config.provider = [
            {
                "name": "Anthropic-Direct",
                "base_url": "https://api.anthropic.com",
                "api_key": "test-anthropic-key",
                "provider_type": "anthropic",
                "big_models": ["claude-3-5-sonnet-20241022"],
                "middle_models": ["claude-3-5-sonnet-20241022"],
                "small_models": ["claude-3-5-haiku-20241022"]
            },
            {
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
                "api_key": "test-openai-key",
                "provider_type": "openai",
                "big_models": ["gpt-4o"],
                "middle_models": ["gpt-4o"],
                "small_models": ["gpt-4o-mini"]
            }
        ]
        config.big_model = "Anthropic-Direct:claude-3-5-sonnet-20241022"
        config.middle_model = "Anthropic-Direct:claude-3-5-sonnet-20241022"
        config.small_model = "Anthropic-Direct:claude-3-5-haiku-20241022"
        config.anthropic_api_key = None  # No validation
        return config

    @pytest.mark.asyncio
    @patch("src.core.model_manager.config")
    async def test_anthropic_request_no_conversion(self, mock_global_config, mock_config):
        """Test that Anthropic requests skip conversion."""
        mock_global_config.return_value = mock_config

        # Create test request
        request = ClaudeMessagesRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[
                ClaudeMessage(role="user", content="Hello")
            ],
            max_tokens=100
        )

        # Mock the Anthropic client
        with patch("src.core.client_factory.ClientFactory.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.create_chat_completion = AsyncMock(return_value={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello! How can I help?"}],
                "model": "claude-3-5-sonnet-20241022"
            })
            mock_get_client.return_value = mock_client

            # Mock history manager
            with patch("src.api.endpoints.history_manager") as mock_history:
                mock_history.log_request = AsyncMock()
                mock_history.update_response = AsyncMock()

                # Mock HTTP request
                mock_http_request = AsyncMock()
                mock_http_request.is_disconnected = AsyncMock(return_value=False)

                # Process request - this should NOT call convert_claude_to_openai
                with patch("src.api.endpoints.convert_claude_to_openai") as mock_convert:
                    # Import here to get patched version
                    from src.api.endpoints import create_message

                    response = await create_message(
                        request=request,
                        http_request=mock_http_request
                    )

                    # Verify conversion was NOT called for Anthropic provider
                    mock_convert.assert_not_called()

                    # Verify client was called with original request format
                    mock_client.create_chat_completion.assert_called_once()
                    call_args = mock_client.create_chat_completion.call_args[0][0]
                    assert call_args["model"] == "claude-3-5-sonnet-20241022"

    @pytest.mark.asyncio
    @patch("src.core.model_manager.config")
    async def test_openai_request_with_conversion(self, mock_global_config, mock_config):
        """Test that OpenAI requests still use conversion."""
        # Update config to use OpenAI
        mock_config.big_model = "OpenAI:gpt-4o"
        mock_global_config.return_value = mock_config

        request = ClaudeMessagesRequest(
            model="claude-3-opus-20240229",  # Claude model name
            messages=[
                ClaudeMessage(role="user", content="Hello")
            ],
            max_tokens=100
        )

        with patch("src.core.client_factory.ClientFactory.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.create_chat_completion = AsyncMock(return_value={
                "choices": [{
                    "message": {"content": "Hello! How can I help?"},
                    "finish_reason": "stop"
                }],
                "model": "gpt-4o"
            })
            mock_get_client.return_value = mock_client

            with patch("src.api.endpoints.history_manager") as mock_history:
                mock_history.log_request = AsyncMock()

                mock_http_request = AsyncMock()
                mock_http_request.is_disconnected = AsyncMock(return_value=False)

                # This time conversion SHOULD be called
                with patch("src.api.endpoints.convert_claude_to_openai") as mock_convert:
                    mock_convert.return_value = {
                        "model": "gpt-4o",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "max_tokens": 100
                    }

                    with patch("src.api.endpoints.convert_openai_to_claude_response") as mock_convert_response:
                        mock_convert_response.return_value = {
                            "id": "msg_test",
                            "type": "message",
                            "content": [{"type": "text", "text": "Hello! How can I help?"}]
                        }

                        from src.api.endpoints import create_message
                        response = await create_message(
                            request=request,
                            http_request=mock_http_request
                        )

                        # Verify conversion WAS called for OpenAI provider
                        mock_convert.assert_called_once()
                        mock_convert_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_streaming_anthropic_no_conversion(self):
        """Test that streaming Anthropic requests bypass conversion."""
        # Similar structure but for streaming
        pass  # Implement if needed

    def test_model_mapping_with_mixed_providers(self):
        """Test model mapping works correctly with mixed provider types."""
        config = Config()
        config.provider = [
            {
                "name": "Anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "key1",
                "provider_type": "anthropic",
                "big_models": ["claude-3-5-sonnet-20241022"]
            },
            {
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
                "api_key": "key2",
                "provider_type": "openai",
                "big_models": ["gpt-4o"]
            }
        ]
        config.big_model = "OpenAI:gpt-4o"

        manager = ModelManager(config)

        # Test Anthropic model returns Anthropic config
        config1 = manager.map_claude_model_to_openai("claude-3-5-sonnet-20241022")
        assert config1["provider_type"] == "anthropic"
        assert config1["model"] == "claude-3-5-sonnet-20241022"

        # Test other Claude models map to OpenAI
        config2 = manager.map_claude_model_to_openai("claude-3-opus-20240229")
        assert config2["provider_type"] == "openai"
        assert config2["model"] == "gpt-4o"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])