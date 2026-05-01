# Backend Architecture

## Overview

FastAPI application (Python 3.13) with three sub-APIs, SQLite storage, and LLM integration via PythonLLMClient.

## Data Modeling Conventions

### Strict Typing Policy

**No free dictionaries. No untyped data. Everything is typed.**

| Layer | Model Type | Usage |
|-------|-----------|-------|
| API request/response | Pydantic `BaseModel` | All endpoint I/O |
| Database models | SQLModel | ORM models (SQLAlchemy + Pydantic) |
| Tool definitions | Pydantic `BaseModel` | Parameter schemas for LLM function calling |
| Internal data | `TypedDict` | In-process data passing between internal functions |

### Examples

```python
# API models — Pydantic
from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: str
    content: str

# DB models — SQLModel
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    role: str = Field(default="user")

# Tool parameter schemas — Pydantic
class GetNPCParams(BaseModel):
    npc_id: str
    include_inventory: bool = False

# Internal data — TypedDict
from typing import TypedDict

class AgentContext(TypedDict):
    location_id: str
    active_npcs: list[str]
```

## DB Layer — DB-Agnostic Interface

The `db/` layer is a **fully abstracted data access interface**. No sessions, connections, or ORM-specific types leak to callers. Services and routes make pure business calls.

### Design Principles

- **Session-free public API**: All `db/` functions manage sessions internally. Callers never see `AsyncSession`, `select()`, or `session.exec()`.
- **Injectable config**: `init_engine(config=DbConfig(...))` accepts DB path, connection params. Tests inject a temporary DB path; production uses defaults.
- **Swappable backend**: The entire `db/` layer could be replaced with Mongo, Redis, or file-based storage without changing services or routes.
- **Namespace modules**: One file per entity (`users.py`, `worlds.py`, `locations.py`, etc.) with short function names (`get_by_id`, `create`, `update`, `delete`, `list_by_world`). Import as `from app.db import users, worlds`. Services follow the same pattern: `from app.services import auth as auth_service`.
- **Business-level signatures**: Functions accept/return model objects or plain types — e.g., `users.get_by_id(user_id: int) -> User | None`.

### Import/Export Pattern

**Export** — callback-based streaming:

1. Service opens zip file, creates gzip stream inside
2. Calls `db.export_table(ModelClass, callback)` — db iterates all rows, calls `callback(row)` per row
3. Callback serializes row to JSONL and writes to gzip stream
4. No bulk `SELECT *` into memory array

**Import** — chunked upsert streaming:

1. Service calls `db.init_db()` to create/reshape tables
2. Service opens zip, reads gzip JSONL line-by-line
3. Accumulates a batch of model instances (e.g., 100)
4. Calls `db.upsert_batch(items)` — db merges batch into table
5. Repeats until EOF
6. **UPSERT** (not INSERT) — idempotent, can re-import safely

### Config

```python
@dataclass
class DbConfig:
    db_path: Path       # SQLite file path (injectable for tests)
    echo: bool = False  # SQLAlchemy echo for debugging
```

## ORM — SQLModel

- SQLModel combines SQLAlchemy and Pydantic into a single model
- All database tables defined as `SQLModel` classes with `table=True`
- Async session via `sqlalchemy.ext.asyncio`
- Migrations: TBD (alembic or manual)

## LLM Client — PythonLLMClient

**Source**: `git+https://github.com/Iezious/PythonLLMClient.git`

### Supported Backends

| Backend | Default URL | Use Case |
|---------|------------|----------|
| Ollama | `http://localhost:11434` | Local models |
| OpenAI | `https://api.openai.com/v1` | Cloud API |
| llama-swap | `http://localhost:8080/v1` | Local alternative |

### Client Initialization

```python
from llm import get_llm_client

client = get_llm_client(
    server_type="ollama",      # or "openai", "llama_swap"
    base_url="http://localhost:11434",
    model="llama3",
    timeout=30,
    bearer_token=None
)
```

### Tool Definition — No Manual JSON

Tools are defined using Pydantic models and `pydantic_to_openai_tool()`:

```python
from llm.tools import pydantic_to_openai_tool
from pydantic import BaseModel

class GetLocationParams(BaseModel):
    location_id: str

tools = [
    pydantic_to_openai_tool(
        "get_location",
        "Get details about a location in the game world",
        GetLocationParams
    )
]
```

### Function Calling Flow

```python
# Define tool implementations as async functions
async def get_location(location_id: str) -> str:
    # Internal async function — no bash, no external HTTP
    location = await db.get_location(location_id)
    return location.model_dump_json()

# Call LLM with tools
response = await client.chat_with_tools(
    model="llama3",
    messages=conversation_history,
    tools_definitions=tools,
    tools_callables={"get_location": get_location},
    max_loops=5
)
```

### Key Constraints

- All tool implementations are **100% internal async functions**
- No subprocess/bash calls from tools
- No external HTTP calls from tools — only DB and in-memory operations
- LLM HTTP calls are handled exclusively by PythonLLMClient

## Logging

### Strategy

- **Library**: Python standard `logging` module
- **Default output**: Console (stderr)
- **Optional**: File output (configurable)

### Log Levels

| Level | What Gets Logged |
|-------|-----------------|
| `INFO` | All incoming API requests, key lifecycle events |
| `DEBUG` | Full agent flow with internal results, tool calls and responses, LLM request/response details |

### Configuration

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,       # or INFO for production
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),                    # Console (always)
        # logging.FileHandler("app.log"),           # File (optional)
    ]
)
```

## SQLite Storage

| Environment | Path | Notes |
|-------------|------|-------|
| Development | `backend/data/` | Local subfolder, git ignored |
| Production | `./data/` (Docker volume) | Mapped from host via `docker-compose` |

Database file: `data/app.db` (or similar — TBD)

## Sub-API Structure

```
FastAPI app
├── /api/agent   — Agent API (LLM orchestration, tool calling)
├── /api/users   — Users/Chats API (accounts, game states, histories)
├── /api/chats   — Chat history endpoints
└── /api/admin   — Admin API (user & world management)
```

Each sub-API is a separate FastAPI `APIRouter` mounted on the main app.

## Generation Modes

A world picks a pipeline via `world.pipeline_id` (Feature 007); the pipeline's `kind` field selects the generation flow. `world.pipeline_id` is required to start generation — chatting against a world with no pipeline returns 400.

| `pipeline.kind` | Service File | Config Source | Description |
|------|-------------|-------------|-------------|
| `"simple"` | `simple_generation_service.py` | `pipeline.system_prompt`, `pipeline.simple_tools` | Single LLM call with tools, rich prompt, stat validation |
| `"chain"` | `chain_generation_service.py` | `pipeline.pipeline_config` (JSON) | Pipeline stages: planning (planning tools, no JSON output) → writing (prose) |
| `"agentic"` | `agent_generation_service.py` | `pipeline.agent_config` (JSON) | Sub-agent orchestration (future, not yet implemented) |

**Dispatch**: `chat_agent_service.py` loads the world, resolves `world.pipeline_id` to a `Pipeline`, dispatches on `pipeline.kind`, and threads the `Pipeline` into the chosen generation service. Same dispatch for both `generate_response()` and `regenerate_response()`.

**Admin tool surface** (`backend/app/services/admin_tools.py`): admin LLM helpers split by world coupling. `get_admin_tools(world_id)` / `ADMIN_TOOL_DEFINITIONS` are world-scoped (`search`, `get_lore`, `web_search`); `get_world_agnostic_tools()` / `WORLD_AGNOSTIC_TOOL_DEFINITIONS` expose only `web_search`. The pipeline-prompt AI editor (Feature 007) uses the world-agnostic surface so suggestions are identical regardless of which world the editor was opened from.

**Shared infrastructure** (used by all modes):

- `chat_tools.py` — Universal tool registry (`TOOL_REGISTRY`, 12 tools: 8 chat tools, 3 planning tools, 1 director tool). One factory, `build_tools(names, ToolContext)`, binds admin-selected names to whatever state (`world_id`, `session_id`, `planning_context`, `stat_defs`, `char_stats`, `world_stats`, `decision_state`) the caller supplies. Unknown name or unmet `requires` → `ValueError`. No per-stage factories or hardcoded bundles — every stage (simple, chain-tool, chain-writer) honors `stage.tools` verbatim.
- `chat_context.py` — Loads location, NPCs, rules, stats, lore, memories; formats into prompt-ready strings
- `stat_validation.py` — Validates stat updates against definitions (int range clamping, enum membership, set filtering)
- `prompts/chat_system_prompt.py` — Rich system prompt builder with full world context and memory management instructions

## Prompt Architecture

All pre-coded prompt parts live in `backend/app/services/prompts/`. No hardcoded prompt text in service files.

Each prompt file follows the **stage-4 documentation convention**:

- **PURPOSE** — what this prompt does
- **USAGE** — which service/stage calls it
- **VARIABLES** — all template parameters with descriptions
- **DESIGN RATIONALE** — why it's structured this way
- **CHANGELOG** — version history

Prompts combine three layers:

1. **Coded part** — structural instructions, tool usage guidance (hardcoded in the prompt file). Note: planning prompt instructs the LLM to use `add_fact`/`add_decision`/`update_stat` tools for structured output — it does not include JSON output instructions.
2. **Admin part** — pipeline-specific free text (from `Pipeline.system_prompt` for simple kind, or `PipelineStage.prompt` inside `Pipeline.pipeline_config` for chain kind)
3. **Player part** — per-turn OOC instructions from `(( ))` notation in user messages, stored as `message.user_instructions`, injected via `{USER_INSTRUCTIONS}` placeholder (always included when non-empty)
