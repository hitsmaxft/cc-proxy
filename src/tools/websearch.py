# Define the tool schema
web_search_tool = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Perform a web search with configurable parameters",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query to execute"},
                "max_uses": {
                    "type": "integer",
                    "description": "Max number of search results to return (1-10)",
                    "minimum": 1,
                    "maximum": 10,
                },
                "allowed_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Only include results from these domains",
                },
                "user_location": {
                    "type": "object",
                    "description": "Localize search results",
                    "properties": {
                        "city": {"type": "string"},
                        "country": {"type": "string", "pattern": "^[A-Z]{2}$"},
                    },
                },
            },
            "required": ["query"],
        },
    },
}


async def claude_web_search(messages, tools):
    """
        this a claude web search converter, when user send messages with tools
        like
        ```
        {
            "model": "anthropic/claude-sonnet-4",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": "How do I update a web app to TypeScript 5.5?"
                }
            ],
            "tools": [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5
            }]
        }

        ```
        step 1  replace tools with tools definition like
        ```
        {
      "type": "web_search_20250305",
      "name": "web_search",

      // Optional: Limit the number of searches per request
      "max_uses": 5,

      // Optional: Only include results from these domains
      "allowed_domains": ["example.com", "trusteddomain.org"],

      // Optional: Never include results from these domains
      "blocked_domains": ["untrustedsource.com"],

      // Optional: Localize search results
      "user_location": {
        "type": "approximate",
        "city": "San Francisco",
        "region": "California",
        "country": "US",
        "timezone": "America/Los_Angeles"
      }
    }
        ```

        send reques to background and wait for a tool call

        ```response message content
        {
          "type": "web_search_tool_result",
          "tool_use_id": "srvtoolu_01WYG3ziw53XMcoyKL4XcZmE",
          "content": [
            {
              "type": "web_search_result",
              "url": "https://en.wikipedia.org/wiki/Claude_Shannon",
              "title": "Claude Shannon - Wikipedia",
              "encrypted_content": "EqgfCioIARgBIiQ3YTAwMjY1Mi1mZjM5LTQ1NGUtODgxNC1kNjNjNTk1ZWI3Y...",
              "page_age": "April 30, 2025"
            }
          ]
        }
        ```
    """
    return {}
