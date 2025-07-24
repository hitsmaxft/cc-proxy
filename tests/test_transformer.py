import json
import unittest
from unittest.mock import patch, MagicMock

from src.conversion.transformer.base import AbstractTransformer
from src.conversion.transformer.registry import TransformerRegistry
from src.conversion.transformer.pipeline import TransformerPipeline
from src.conversion.transformer.transformers.tooluse import ToolUseTransformer


class TestTransformer(unittest.TestCase):
    def test_abstract_transformer_base_methods(self):
        """Test that the AbstractTransformer base methods return the input unchanged."""
        transformer = AbstractTransformer()

        request = {"messages": [], "model": "test-model"}
        self.assertEqual(transformer.transformRequestIn(request), request)
        self.assertEqual(transformer.transformRequestOut(request), request)

        response = {"choices": [{"message": {"content": "Test"}}]}
        self.assertEqual(transformer.transformResponseIn(response), response)
        self.assertEqual(transformer.transformResponseOut(response), response)

    def test_transformer_registry_registration(self):
        """Test registration of transformers in the registry."""
        registry = TransformerRegistry()

        # Create a test transformer class
        class TestTransformer(AbstractTransformer):
            name = "test_transformer"

        registry.register(TestTransformer)

        # Verify the transformer was registered
        self.assertIn("test_transformer", registry._transformers)
        self.assertEqual(registry._transformers["test_transformer"], TestTransformer)

        # Get an instance of the registered transformer
        transformer = registry.get_transformer("test_transformer")
        self.assertIsInstance(transformer, TestTransformer)

    def test_transformer_pipeline_request_flow(self):
        """Test the transformer pipeline request flow."""
        # Create mock transformers
        transformer1 = MagicMock(spec=AbstractTransformer)
        transformer1.name = "transformer1"
        transformer1.transformRequestIn.return_value = {"step": "transformer1_in"}
        transformer1.transformRequestOut.return_value = {"step": "transformer1_out"}

        transformer2 = MagicMock(spec=AbstractTransformer)
        transformer2.name = "transformer2"
        transformer2.transformRequestIn.side_effect = lambda x: {
            "step": "transformer2_in"
        }
        transformer2.transformRequestOut.side_effect = lambda x: {
            "step": "transformer2_out"
        }

        # Create pipeline with the mock transformers
        pipeline = TransformerPipeline([transformer1, transformer2])

        # Transform a request
        request = {"original": "request"}
        result = pipeline.transform_request(request)

        # Verify the transformers were called in the correct order
        transformer1.transformRequestIn.assert_called_once_with({"original": "request"})
        transformer2.transformRequestIn.assert_called_once_with(
            {"step": "transformer1_in"}
        )
        transformer2.transformRequestOut.assert_called_once_with(
            {"step": "transformer2_in"}
        )
        transformer1.transformRequestOut.assert_called_once_with(
            {"step": "transformer2_out"}
        )

        # Verify the final result
        self.assertEqual(result, {"step": "transformer1_out"})

    def test_transformer_pipeline_response_flow(self):
        """Test the transformer pipeline response flow."""
        # Create mock transformers
        transformer1 = MagicMock(spec=AbstractTransformer)
        transformer1.name = "transformer1"
        transformer1.transformResponseIn.return_value = {"step": "transformer1_in"}
        transformer1.transformResponseOut.return_value = {"step": "transformer1_out"}

        transformer2 = MagicMock(spec=AbstractTransformer)
        transformer2.name = "transformer2"
        transformer2.transformResponseIn.side_effect = lambda x: {
            "step": "transformer2_in"
        }
        transformer2.transformResponseOut.side_effect = lambda x: {
            "step": "transformer2_out"
        }

        # Create pipeline with the mock transformers
        pipeline = TransformerPipeline([transformer1, transformer2])

        # Transform a response
        response = {"original": "response"}
        result = pipeline.transform_response(response)

        # Verify the transformers were called in the correct order
        transformer1.transformResponseIn.assert_called_once_with(
            {"original": "response"}
        )
        transformer2.transformResponseIn.assert_called_once_with(
            {"step": "transformer1_in"}
        )
        transformer2.transformResponseOut.assert_called_once_with(
            {"step": "transformer2_in"}
        )
        transformer1.transformResponseOut.assert_called_once_with(
            {"step": "transformer2_out"}
        )

        # Verify the final result
        self.assertEqual(result, {"step": "transformer1_out"})

    def test_tooluse_transformer_request(self):
        """Test that the ToolUseTransformer correctly modifies requests."""
        transformer = ToolUseTransformer({"providers": ["deepseek"], "models": ["*"]})

        # Test that the transformer is applied to DeepSeek models
        self.assertTrue(transformer.should_apply_to("deepseek", "any-model"))
        self.assertFalse(transformer.should_apply_to("openai", "gpt-4"))

        # Test request transformation
        request = {
            "messages": [{"role": "user", "content": "Hello"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather information",
                        "parameters": {},
                    },
                }
            ],
        }

        transformed = transformer.transformRequestIn(request)

        # Verify that tool_choice is set to "required"
        self.assertEqual(transformed["tool_choice"], "required")

        # Verify that ExitTool was added
        self.assertEqual(len(transformed["tools"]), 2)
        self.assertEqual(transformed["tools"][0]["function"]["name"], "ExitTool")

        # Verify that system message was added
        self.assertEqual(len(transformed["messages"]), 2)
        self.assertEqual(transformed["messages"][1]["role"], "system")
        self.assertIn("Tool mode is active", transformed["messages"][1]["content"])

    def test_tooluse_transformer_response(self):
        """Test that the ToolUseTransformer correctly modifies responses."""
        transformer = ToolUseTransformer()

        # Create a response with an ExitTool call
        response = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "ExitTool",
                                    "arguments": json.dumps(
                                        {"response": "This is the final answer"}
                                    ),
                                }
                            }
                        ]
                    }
                }
            ]
        }

        transformed = transformer.transformResponseIn(response)

        # Verify that the tool call was replaced with content
        self.assertEqual(
            transformed["choices"][0]["message"]["content"], "This is the final answer"
        )
        self.assertNotIn("tool_calls", transformed["choices"][0]["message"])

        # Test with a non-ExitTool response
        response = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_weather",
                                    "arguments": json.dumps({"location": "New York"}),
                                }
                            }
                        ]
                    }
                }
            ]
        }

        transformed = transformer.transformResponseIn(response)

        # Verify that the response was not modified
        self.assertEqual(transformed, response)


if __name__ == "__main__":
    unittest.main()
