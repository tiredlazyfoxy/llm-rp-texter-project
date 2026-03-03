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
