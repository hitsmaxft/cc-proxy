import json


def test_response_convert():
    request = json.loads("""
                        {
    "model": "qwen/qwen3-coder",
    "messages": [
        {
            "role": "user",
            "content": ""
        }
    ],
    "tools": [
        {
            "name": "Write",
            "description": "",
            "input_schema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The absolute path to the file to write (must be absolute, not relative)"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file, should be string"
                    }
                },
                "required": [
                    "file_path",
                    "content"
                ],
                "additionalProperties": false
            }
        }
    ],
    "max_tokens": 4200
} 
""")
    tool_call =  {
        "name": "Write",
        "arguments": json.dumps({
            "content": {
                "pattern": "package",
                "path": "/Users/qixiang/Projects/solutions/testmcp/src/main/java/com/tpp/solution/CallTpp/TppClientExample.java"
            },
            "file_path": "a.json"
        }) 
    }

    response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [tool_call]
                }
            }
        ]
    }

    from src.conversion.transformer.transformers.qwen3 import QwenTransformer
    
    transformer = QwenTransformer()
    transformer.transformRequestIn(request)
    transformed_response = transformer.transformResponseIn(response)
    print(transformed_response)
    print(json.dumps({
        "value": json.dumps({"a": "b"}, indent=2)}))
    pass
    
if __name__ == "__main__":
    test_response_convert()