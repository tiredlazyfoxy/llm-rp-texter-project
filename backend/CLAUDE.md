# Backend

FastAPI application — Python 3.13, SQLite, SQLModel ORM.

## Directory Structure

```
backend/
  app/
    main.py              — FastAPI app, CORS, router mounting
    models/              — SQLModel DB models + Pydantic API schemas
      schemas/           — Pydantic request/response schemas (auth.py, chat.py)
      user.py, world.py, llm_server.py, chat_session.py, chat_message.py, ...
    routes/              — API route handlers
      auth.py, chat.py, llm_servers.py, admin/...
    services/            — Business logic
      snowflake.py       — Snowflake ID generator (int64)
      database.py        — SQLModel async engine, DB init
      auth.py            — JWT create/verify, password hashing
      db_import_export.py — gzipped JSONL per table
      prompts.py         — All LLM prompt constants (single file)
      chat_tools.py      — Agent tools, NPC logic, stat parsing
      chat_service.py    — Chat generation, regeneration, rewind
  pyproject.toml         — Dependencies
  data/                  — SQLite DB location (dev)
```

## Sub-APIs

- **Auth** (`/api/auth`) — Login, setup, JWT
- **Chats** (`/api/chats`) — User chat sessions, SSE streaming
- **LLM** (`/api/llm`) — Enabled models list (for editor/player)
- **Admin** (`/api/admin`) — LLM servers CRUD, world management

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

## DB Models (planned)

| Table | Plan | Key Fields |
|---|---|---|
| `users` | stage1_step1 | username, role (admin/editor/player), pwdhash, jwt_signing_key |
| `worlds` | stage1_step2 | name, system_prompt, character_template, pipeline, status |
| `world_locations` | stage1_step2 | world_id, name, content, exits |
| `world_npcs` | stage1_step2 | world_id, name, content |
| `world_lore_facts` | stage1_step2 | world_id, content |
| `npc_location_links` | stage1_step2 | npc_id, location_id, link_type (present/excluded) |
| `world_stat_definitions` | stage1_step2 | world_id, name, scope, stat_type, constraints |
| `world_rules` | stage1_step2 | world_id, rule_text, order |
| `llm_servers` | stage1_step3 | name, backend_type, base_url, enabled_models |
| `chat_sessions` | stage2_step1 | user_id, world_id, character_stats, world_stats, current_turn |
| `chat_messages` | stage2_step1 | session_id, role, content, turn_number, tool_calls, is_active_variant |
| `chat_state_snapshots` | stage2_step1 | session_id, turn_number, character_stats, world_stats |
| `chat_summaries` | stage2_step1 | session_id, start/end turn, content |

## DB Import/Export

- **Every model must have JSONL import/export** — gzipped `.jsonl.gz` in a zip
- Extend `db_import_export.py` whenever a model is added/changed
- Vector index (LanceDB) is rebuilt from source documents on import, not exported

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
