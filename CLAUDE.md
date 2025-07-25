# CC-proxy

## Project Structure

```
src/
├── main.py                 # Application entry point
├── api/
│   └── endpoints.py        # API route definitions
├── core/
│   ├── client.py           # Core client functionality
│   ├── config.py           # Configuration management
│   ├── constants.py        # Application constants
│   ├── logging.py          # Logging configuration
│   └── model_manager.py    # Model management
├── services/
│   └── history_manager.py  # Chat history management
├── models/
│   ├── claude.py           # Claude model integration
│   ├── openai.py           # OpenAI model integration
│   └── history.py          # History model definitions
├── storage/
│   └── database.py         # Database operations
├── conversion/
│   └── request_converter.py # Request format conversion
├── tools/
│   └── websearch.py        # Web search functionality
└── utils/
    └── token_counter.py    # Token counting utilities
```

## notice

* you MUST use openai client for model requets 
* you MUST use requests non model request