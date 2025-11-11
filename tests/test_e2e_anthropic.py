"""End-to-end tests for Anthropic provider - run against live server."""
import os
import sys
import asyncio
import httpx
import json
from typing import Dict, Any, AsyncGenerator

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_anthropic_non_streaming():
    """Test non-streaming Anthropic request."""
    async with httpx.AsyncClient() as client:
        request_data = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "user", "content": "Say 'Hello from Anthropic!' and nothing else."}
            ],
            "max_tokens": 50
        }

        print("\n=== Testing Anthropic Non-Streaming ===")
        print(f"Request: {json.dumps(request_data, indent=2)}")

        try:
            response = await client.post(
                "http://localhost:8082/v1/messages",
                json=request_data,
                headers={
                    "x-api-key": os.getenv("ANTHROPIC_API_KEY", "test-key"),
                    "content-type": "application/json"
                },
                timeout=30.0
            )

            print(f"Status: {response.status_code}")
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")

            # Verify response structure matches Claude format
            assert result.get("type") == "message"
            assert result.get("role") == "assistant"
            assert "content" in result
            assert len(result["content"]) > 0
            assert result["content"][0].get("type") == "text"

            print("✅ Anthropic non-streaming test passed!")
            return True

        except Exception as e:
            print(f"❌ Error: {e}")
            return False


async def test_anthropic_streaming():
    """Test streaming Anthropic request."""
    async with httpx.AsyncClient() as client:
        request_data = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "user", "content": "Count from 1 to 5, one number at a time."}
            ],
            "max_tokens": 100,
            "stream": True
        }

        print("\n=== Testing Anthropic Streaming ===")
        print(f"Request: {json.dumps(request_data, indent=2)}")

        try:
            events_received = []
            async with client.stream(
                "POST",
                "http://localhost:8082/v1/messages",
                json=request_data,
                headers={
                    "x-api-key": os.getenv("ANTHROPIC_API_KEY", "test-key"),
                    "content-type": "application/json"
                },
                timeout=30.0
            ) as response:
                print(f"Status: {response.status_code}")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data == "[DONE]":
                            print("Stream completed.")
                            break

                        try:
                            event = json.loads(data)
                            events_received.append(event)
                            print(f"Event: {event.get('type')} - {event}")
                        except json.JSONDecodeError:
                            print(f"Could not parse: {data}")

            # Verify we received proper events
            event_types = [e.get("type") for e in events_received]
            assert "message_start" in event_types
            assert "message_stop" in event_types
            assert any("content_block" in t for t in event_types if t)

            print(f"✅ Anthropic streaming test passed! Received {len(events_received)} events")
            return True

        except Exception as e:
            print(f"❌ Error: {e}")
            return False


async def test_openai_still_works():
    """Test that OpenAI provider still works with conversion."""
    async with httpx.AsyncClient() as client:
        # Use a Claude model name that should be mapped to OpenAI
        request_data = {
            "model": "claude-3-opus-20240229",
            "messages": [
                {"role": "user", "content": "Say 'Hello from OpenAI!' and nothing else."}
            ],
            "max_tokens": 50
        }

        print("\n=== Testing OpenAI Provider (with conversion) ===")
        print(f"Request: {json.dumps(request_data, indent=2)}")

        try:
            response = await client.post(
                "http://localhost:8082/v1/messages",
                json=request_data,
                headers={
                    "x-api-key": os.getenv("ANTHROPIC_API_KEY", "test-key"),
                    "content-type": "application/json"
                },
                timeout=30.0
            )

            print(f"Status: {response.status_code}")
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")

            # Should still return Claude format after conversion
            assert result.get("type") == "message"
            assert result.get("role") == "assistant"

            print("✅ OpenAI provider test passed!")
            return True

        except Exception as e:
            print(f"❌ Error: {e}")
            return False


async def test_mixed_providers():
    """Test switching between providers."""
    print("\n=== Testing Mixed Provider Usage ===")

    results = []

    # Test 1: Anthropic provider
    results.append(await test_anthropic_non_streaming())

    # Test 2: OpenAI provider (assuming config has both)
    results.append(await test_openai_still_works())

    # Test 3: Streaming with Anthropic
    results.append(await test_anthropic_streaming())

    return all(results)


async def main():
    """Run all end-to-end tests."""
    print("=" * 60)
    print("CC-Proxy Anthropic Provider End-to-End Tests")
    print("=" * 60)
    print("\nMake sure CC-Proxy is running with Anthropic provider configured!")
    print("Set ANTHROPIC_API_KEY environment variable if using authentication.\n")

    # Wait a bit for user to see instructions
    await asyncio.sleep(2)

    try:
        # Test server connectivity first
        async with httpx.AsyncClient() as client:
            health = await client.get("http://localhost:8082/health")
            print(f"Server health check: {health.status_code}")
            if health.status_code != 200:
                print("❌ Server not responding. Please start CC-Proxy first.")
                return

        # Run all tests
        all_passed = await test_mixed_providers()

        print("\n" + "=" * 60)
        if all_passed:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed. Check output above.")
        print("=" * 60)

    except httpx.ConnectError:
        print("❌ Could not connect to CC-Proxy. Is it running on http://localhost:8082?")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())