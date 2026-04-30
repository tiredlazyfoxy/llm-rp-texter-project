# Rules

- **No Co-Authored-By lines in commits** — do not add Claude co-author attribution (legal/copyright concerns)
- Use all git calls, except commit withot confirmation on commit scenario
- use any non-chaning commans: read, search, grep,, etc commands inside the project folder without confirmation

# Backend

FastAPI application — Python 3.13, SQLite, SQLModel ORM.

## Directory Structure

```
backend/
  app/                   — FastAPI application (see app/CLAUDE.md)
    main.py              — FastAPI app, CORS, router mounting
    models/              — SQLModel DB models + Pydantic API schemas
    routes/              — API route handlers (HTTP layer only)
    db/                  — Data access layer (DB-agnostic interface)
    services/            — Business logic (no direct DB queries, no session creation)
  pyproject.toml         — Dependencies
  data/                  — SQLite DB location (dev)
```

See per-folder `CLAUDE.md` files for contents of each subfolder.

## Sub-APIs

- **Auth** (`/api/auth`) — Login, setup, JWT
- **Chats** (`/api/chats`) — User chat sessions, SSE streaming
- **LLM** (`/api/llm`) — Enabled models list (for editor/player)
- **Admin** (`/api/admin`) — LLM servers CRUD, world management, DB management

## Generation Modes

`World.generation_mode` controls which generation flow is used for chat:

- **`"simple"`** — Single LLM call with admin-selected tools, prompt template with `{PLACEHOLDER}` syntax, stat validation. Admin prompt: `World.system_prompt`. Tools: `World.simple_tools`. Service: `simple_generation_service.py`
- **`"chain"`** — Pipeline stages from `World.pipeline` JSON (PipelineConfig). Each stage has step_type (`"tool"` or `"writer"`), admin-configurable prompt template, and per-stage tool selection. Default: tool stage → writer stage. Service: `chain_generation_service.py`
- **`"agentic"`** (future) — Sub-agent orchestration, config in `World.agent_config`. Not yet implemented.

Dispatch in `chat_agent_service.py` routes to the appropriate service. Shared infrastructure: `chat_tools.py`, `chat_context.py`, `stat_validation.py`, rich system prompt.

## Setup

- Local `.venv` virtual environment
- Dependencies managed via `pyproject.toml`
- Dev server: `uvicorn app.main:app --port 8085 --reload`
- SQLite DB in `backend/data/` (dev), Docker volume `./data/` (prod)
- Production Docker: `backend/Dockerfile` (python:3.13, port 8085, build context is repo root)

## Layer Separation

- **`routes/`** — HTTP layer only: parse requests, call services, format responses. No business logic, no direct DB queries.
- **`services/`** — Business logic: authentication, validation, orchestration. No `session`, `AsyncSession`, `select()`, `session.exec()`, or `session.add()`.
- **`db/`** — DB-agnostic data access interface. Exposes **business-level functions only** — no sessions, connections, or ORM types leak out. All SQL/ORM internals are hidden. The entire `db/` layer could be replaced with Mongo/Redis/file without changing services or routes. Config is injectable via `DbConfig` for tests and environments.
- **`models/`** — SQLModel table definitions + Pydantic schemas. No logic.

**Rules:**
- Routes depend on services and db
- Services depend on db (never import from routes)
- DB layer depends only on models (never import from services or routes)
- **No `session`, `AsyncSession`, or connection objects outside `db/`**
- **No `select()`, `session.exec()`, `session.add()` outside `db/`**
- Import/export serialization (`db_import_export.py`) stays in `services/` — it's format logic, not DB logic

## Data Modeling — Strict Typing

- **Pydantic `BaseModel`**: API request/response, tool parameter schemas
- **SQLModel**: All database models (SQLAlchemy + Pydantic)
- **`TypedDict`**: Internal data passing between functions
- **No free dictionaries, no untyped data**

## DB Models

See [`architecture/db-models.md`](../architecture/db-models.md). Implementation lives in [`backend/app/models/`](app/models/).

## DB Import/Export

- **Every model must have JSONL import/export** — gzipped `.jsonl.gz` in a zip
- Extend `db_import_export.py` whenever a model is added/changed
- Vector index (LanceDB) is rebuilt from source documents on import, not exported
- **Streaming**: export uses callback per row; import reads JSONL line-by-line, sends batched upserts
- **No in-memory bulk load** — never decode entire file to array
- **UPSERT semantics** — import is idempotent (can re-import without clearing)
- `init_db()` creates/reshapes tables before import

## LLM Client

- Library: PythonLLMClient (`git+https://github.com/Iezious/PythonLLMClient.git`)
- Tool schemas via `pydantic_to_openai_tool()` — no manual JSON
- Backends: Ollama, OpenAI, llama-swap

## IDs

- Snowflake: 41-bit timestamp + 19-bit sequence + 3-bit machine
- Stored as INTEGER in SQLite, serialized as **string** in all API responses

## Logging

- Python `logging` module, default to console
- `INFO`: all API requests
- `DEBUG`: full agent flow with internal results

## See Also

- `architecture/backend.md` — Full backend architecture details
- `architecture/quick-reference.md` — Condensed API endpoints, tools, SSE protocol
