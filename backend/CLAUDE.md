# Backend

FastAPI application — Python 3.13, SQLite, SQLModel ORM.

## Sub-APIs
- **Agent API** (`/api/agent`) — LLM orchestration via PythonLLMClient, tool calling (internal async functions)
- **Users/Chats API** (`/api/users`, `/api/chats`) — User accounts, game states, chat histories
- **Admin API** (`/api/admin`) — User and world database management

## Setup
- Local `.venv` virtual environment
- Dependencies managed via `pyproject.toml`
- Dev server: `uvicorn app.main:app --port 8085 --reload`
- SQLite DB in `backend/data/` (dev), Docker volume `./data/` (prod)

## Data Modeling — Strict Typing
- **Pydantic `BaseModel`**: API request/response, tool parameter schemas
- **SQLModel**: All database models (SQLAlchemy + Pydantic)
- **`TypedDict`**: Internal data passing between functions
- **No free dictionaries, no untyped data**

## LLM Client
- Library: PythonLLMClient (`git+https://github.com/Iezious/PythonLLMClient.git`)
- Tool schemas via `pydantic_to_openai_tool()` — no manual JSON
- Backends: Ollama, OpenAI, llama-swap

## Logging
- Python `logging` module, default to console, file optional
- `INFO`: all API requests
- `DEBUG`: full agent flow with internal results

## Key Constraints
- Tool implementations are 100% internal async functions (no bash, no external HTTP)
- LLM calls go to remote backends via PythonLLMClient HTTP client
- CORS enabled in dev for localhost:8094; not needed in prod (nginx proxy)

## See Also
- `architecture/backend.md` — Full backend architecture details
