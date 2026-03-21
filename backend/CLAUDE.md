# Backend

FastAPI application — Python 3.13, SQLite, SQLModel ORM.

## Directory Structure

```
backend/
  app/
    main.py              — FastAPI app, CORS, router mounting
    models/              — SQLModel DB models + Pydantic API schemas
      schemas/           — Pydantic request/response schemas (auth.py, chat.py, db_management.py, pipeline.py)
      user.py, world.py, llm_server.py, chat_session.py, chat_message.py, ...
    routes/              — API route handlers (HTTP layer only)
      auth.py, chat.py, llm_servers.py, admin/db_management.py, ...
    db/                  — Data access layer (DB-agnostic interface)
      engine.py          — Async engine, injectable config, DDL, state flags
      users.py           — User CRUD (session-free, import as `from app.db import users`)
      worlds.py          — World CRUD
      locations.py       — WorldLocation CRUD
      npcs.py            — WorldNPC CRUD
      lore_facts.py      — WorldLoreFact CRUD
      npc_links.py       — NPCLocationLink CRUD
      stat_defs.py       — WorldStatDefinition CRUD
      rules.py           — WorldRule CRUD
      import_export_queries.py — export_table(), upsert_batch(), vector rebuild
      db_management.py         — DB introspection (table list, columns, counts, create)
    services/            — Business logic (no direct DB queries, no session creation)
      snowflake.py       — Snowflake ID generator (int64)
      database.py        — DB setup orchestration (create/import)
      auth.py            — JWT create/verify, password hashing
      db_import_export.py — gzipped JSONL per table
      db_management.py    — DB introspection service (status, schema drift, create tables)
      prompts/           — LLM prompt package (one documented file per prompt, stage-4 docstring)
        planning_system_prompt.py   — Planning stage system prompt (chain mode)
        writing_system_prompt.py    — Writing stage system prompt (chain mode)
        writing_plan_message.py     — Plan injection template for writer
      chat_tools.py         — Chat tool implementations (7 tools) + factory
      chat_context.py       — Context builder for rich system prompts
      stat_validation.py    — Stat update validation against definitions
      chat_service.py       — Chat CRUD (sessions, messages, memories, rewind)
      chat_agent_service.py — Generation dispatcher (routes to mode-specific services)
      simple_generation_service.py  — Simple mode: single LLM call with tools
      chain_generation_service.py   — Chain mode: planning → writing pipeline
  pyproject.toml         — Dependencies
  data/                  — SQLite DB location (dev)
```

## Sub-APIs

- **Auth** (`/api/auth`) — Login, setup, JWT
- **Chats** (`/api/chats`) — User chat sessions, SSE streaming
- **LLM** (`/api/llm`) — Enabled models list (for editor/player)
- **Admin** (`/api/admin`) — LLM servers CRUD, world management, DB management

## Generation Modes

`World.generation_mode` controls which generation flow is used for chat:

- **`"simple"`** — Single LLM call with tools, rich system prompt, stat validation. Admin prompt: `World.system_prompt`. Service: `simple_generation_service.py`
- **`"chain"`** — Pipeline stages from `World.pipeline` JSON (PipelineConfig). Default: planning (tools + JSON) → writing (prose). Service: `chain_generation_service.py`
- **`"agentic"`** (future) — Sub-agent orchestration, config in `World.agent_config`. Not yet implemented.

Dispatch in `chat_agent_service.py` routes to the appropriate service. Shared infrastructure: `chat_tools.py`, `chat_context.py`, `stat_validation.py`, rich system prompt.

## Setup

- Local `.venv` virtual environment
- Dependencies managed via `pyproject.toml`
- Dev server: `uvicorn app.main:app --port 8085 --reload`
- SQLite DB in `backend/data/` (dev), Docker volume `./data/` (prod)

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

## DB Models (planned)

| Table | Plan | Key Fields |
|---|---|---|
| `users` | stage1_step1 | username, role (admin/editor/player), pwdhash, jwt_signing_key |
| `worlds` | stage1_step2/stage3_step1 | name, system_prompt, character_template, generation_mode, pipeline, agent_config, status |
| `world_locations` | stage1_step2 | world_id, name, content, exits |
| `world_npcs` | stage1_step2 | world_id, name, content |
| `world_lore_facts` | stage1_step2/step7b | world_id, content, is_injected (bool), weight (int) |
| `npc_location_links` | stage1_step2 | npc_id, location_id, link_type (present/excluded) |
| `world_stat_definitions` | stage1_step2/stage3_step1 | world_id, name, scope, stat_type, constraints, hidden |
| `world_rules` | stage1_step2 | world_id, rule_text, order |
| `llm_servers` | stage1_step3 | name, backend_type, base_url, enabled_models, is_embedding, embedding_model |
| `chat_sessions` | stage2_step1 | user_id, world_id, character_stats, world_stats, current_turn |
| `chat_messages` | stage2_step1/stage3_step2 | session_id, role, content, turn_number, tool_calls, generation_plan, thinking_content, is_active_variant |
| `chat_state_snapshots` | stage2_step1 | session_id, turn_number, character_stats, world_stats |
| `chat_summaries` | stage2_step1 | session_id, start/end turn, content |

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
