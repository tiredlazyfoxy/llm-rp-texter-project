# Rules

- **No Co-Authored-By lines in commits** — do not add Claude co-author attribution (legal/copyright concerns)
- Use all git calls, except commit withot confirmation on commit scenario
- use any non-chaning commans: read, search, grep,, etc commands inside the project folder without confirmation

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
        placeholder_registry.py     — Static registry of prompt placeholders ({WORLD_NAME}, {RULES}, {DECISION}, …)
        tool_catalog.py             — Static registry of tools with name, description, category (research/action/planning/director)
        default_templates.py        — Default prompt templates (simple, tool, writer, director) using {PLACEHOLDER} syntax
        world_field_editor_system_prompt.py — System prompt for LLM-assisted field editing
        planning_system_prompt.py   — Planning stage system prompt (chain mode, legacy fallback)
        writing_system_prompt.py    — Writing stage system prompt (chain mode, legacy fallback)
        writing_plan_message.py     — Plan injection template for writer
      chat_tools.py         — Universal tool registry (TOOL_REGISTRY, 12 tools) + ToolContext + build_tools(names, ctx). No per-stage factories — every caller selects tools by name and passes the state it has; missing required state → ValueError.
      chat_context.py       — Context builder for rich system prompts
      stat_validation.py    — Stat update validation against definitions
      chat_service.py       — Chat CRUD (sessions, messages, memories, rewind, edit/delete messages)
      chat_agent_service.py — Generation dispatcher (routes to mode-specific services)
      simple_generation_service.py  — Simple mode: single LLM call with tools
      chain_generation_service.py   — Chain mode: planning (tools → PlanningContext → GenerationPlanOutput) → writing pipeline
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

| Table | Key Fields |
|---|---|
| `users` | username, role (admin/editor/player), pwdhash, jwt_signing_key |
| `worlds` | name, system_prompt, simple_tools, character_template, generation_mode, pipeline, agent_config, status |
| `world_locations` | world_id, name, content, exits |
| `world_npcs` | world_id, name, content |
| `world_lore_facts` | world_id, content, is_injected (bool), weight (int) |
| `npc_location_links` | npc_id, location_id, link_type (present/excluded) |
| `world_stat_definitions` | world_id, name, scope, stat_type, constraints, hidden |
| `world_rules` | world_id, rule_text, order |
| `llm_servers` | name, backend_type, base_url, enabled_models, is_embedding, embedding_model |
| `chat_sessions` | user_id, world_id, current_location_id, tool_model_id, text_model_id, character_stats, world_stats, current_turn, generation_variants (JSON) |
| `chat_messages` | session_id, role, content, turn_number, tool_calls, generation_plan, thinking_content, is_active_variant |
| `chat_state_snapshots` | session_id, turn_number, location_id, character_stats, world_stats |
| `chat_summaries` | session_id, start/end turn, content |
| `chat_memories` | session_id, content |

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
