# Backend

FastAPI application — Python 3.13, SQLite.

## Sub-APIs
- **Agent API** (`/api/agent`) — LLM orchestration, MCP tools (internal async functions)
- **Users/Chats API** (`/api/users`, `/api/chats`) — User accounts, game states, chat histories
- **Admin API** (`/api/admin`) — User and world database management

## Setup
- Local `.venv` virtual environment
- Dependencies managed via `pyproject.toml`
- Dev server: `uvicorn app.main:app --port 8085 --reload`

## Key Constraints
- MCP tools are 100% internal async functions (no bash, no external HTTP)
- LLM calls go to remote llama.cpp or OpenAI-compatible API via HTTP
- CORS enabled in dev for localhost:8094; not needed in prod (nginx proxy)
