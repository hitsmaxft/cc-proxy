#!/usr/bin/env python3
"""
Example usage of the Web Search Plugin System

This script demonstrates how to use the web search functionality
directly without going through the API endpoints.
"""

import asyncio
import os
from src.websearch.registry import registry
from src.websearch.base import SearchQuery
from src.websearch.response_formatter import ClaudeResponseFormatter
from src.models.claude import ClaudeMessagesRequest, ClaudeMessage, ClaudeTool, ClaudeContentBlockText


async def test_bocha_search():
    """Test Bocha web search directly"""

    # Check if Bocha API token is available
    api_key = os.getenv("BOCHA_API_TOKEN")
    if not api_key:
        print("❌ BOCHA_API_TOKEN environment variable not set")
        print("Please set your Bocha API token: export BOCHA_API_TOKEN='your-api-token'")
        return

    print("🔍 Testing Bocha Web Search Provider...")

    try:
        # Get Bocha provider
        provider_config = {
            "api_key": api_key,
            "base_url": "https://api.bochaai.com/v1"
        }

        provider = registry.get_provider("bocha.websearch", provider_config)
        if not provider:
            print("❌ Failed to get Bocha provider")
            return

        print("✅ Bocha provider initialized successfully")

        # Perform search
        query = SearchQuery(
            query="rust hal of ht32f52352",
            max_results=3,
            freshness="noLimit"
        )

        print(f"🔎 Searching for: {query.query}")
        results = await provider.search(query)

        if results:
            print(f"✅ Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result.title}")
                print(f"   URL: {result.url}")
                print(f"   Summary: {result.content[:100]}...")
                print(f"   Date: {result.page_age or 'Unknown'}")
        else:
            print("❌ No results found")

        # Test response formatting
        print("\n📝 Testing Claude response formatting...")
        formatter = ClaudeResponseFormatter()
        response = formatter.format_search_response(
            original_query=query.query,
            search_results=results
        )

        print("✅ Claude-compatible response generated:")
        print(f"   Role: {response['role']}")
        print(f"   Content blocks: {len(response['content'])}")
        print(f"   Tool use ID: {response['content'][1]['id']}")

    except Exception as e:
        print(f"❌ Error during search: {e}")


async def test_web_search_handler():
    """Test the complete web search handler flow"""

    # Check if Bocha API token is available
    api_key = os.getenv("BOCHA_API_TOKEN")
    if not api_key:
        print("❌ BOCHA_API_TOKEN environment variable not set")
        return

    print("\n🔄 Testing Web Search Handler flow...")

    from src.api.web_search import WebSearchHandler

    # Create a sample Claude request
    tool = ClaudeTool(
        name="web_search",
        description="Web search tool",
        type="web_search_20250305",
        input_schema={
            "query": "latest developments in quantum computing",
            "max_uses": 5
        }
    )

    message = ClaudeMessage(
        role="user",
        content=[
            ClaudeContentBlockText(
                type="text",
                text="What are the latest developments in quantum computing?"
            )
        ]
    )

    claude_request = ClaudeMessagesRequest(
        model="Bocha-Direct:any-model",
        max_tokens=1000,
        messages=[message],
        tools=[tool]
    )

    handler = WebSearchHandler()
    provider_config = {"api_key": api_key}
    web_search_config = "bocha.websearch"

    try:
        response = await handler.handle_web_search_request(
            claude_request=claude_request,
            provider_config=provider_config,
            web_search_config=web_search_config
        )

        if response:
            print("✅ Web search handler completed successfully")
            print(f"   Response role: {response['role']}")
            print(f"   Content blocks: {len(response['content'])}")

            # Extract search results from response
            tool_result = response['content'][2]
            if tool_result['type'] == 'web_search_tool_result':
                results = tool_result['content']
                print(f"   Search results found: {len(results)}")
        else:
            print("❌ No response from web search handler")

    except Exception as e:
        print(f"❌ Error in web search handler: {e}")


async def main():
    """Main test function"""
    print("🚀 Web Search Plugin System Test")
    print("=" * 50)

    # Test 1: Direct provider usage
    await test_bocha_search()

    # Test 2: Complete handler flow
    await test_web_search_handler()

    print("\n" + "=" * 50)
    print("✨ Test completed!")


if __name__ == "__main__":
    asyncio.run(main())
