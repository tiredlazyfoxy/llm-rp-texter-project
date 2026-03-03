# System Architecture Overview

## High-Level Diagram

```
┌─────────────────────────────────────────────────┐
│                    nginx                        │
│  / ──► User SPA (static)                        │
│  /admin ──► Admin SPA (static)                  │
│  /api ──► FastAPI backend (proxy)               │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│              FastAPI Backend                    │
│                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │  Agent API  │  │ Users/Chats  │  │ Admin   │ │
│  │  /api/agent │  │ /api/users   │  │ /api/   │ │
│  │             │  │ /api/chats   │  │  admin  │ │
│  └──────┬───── ┘  └──────┬───────┘  └────┬────┘ │
│         │                │               │      │
│         ▼                ▼               ▼      │
│  ┌─────────────┐  ┌──────────────────────────┐  │
│  │ Tool Fns    │  │   SQLite (via SQLModel)  │  │
│  │ (internal   │  │  - users                 │  │
│  │  async fns) │  │  - game states           │  │
│  └──────┬──────┘  │  - chat histories        │  │
│         │         │  - world data            │  │
│         ▼         └──────────────────────────┘  │
│  ┌──────────────────┐                           │
│  │ PythonLLMClient  │                           │
│  │ (HTTP API)       │                           │
│  │ - Ollama         │                           │
│  │ - OpenAI         │                           │
│  │ - llama-swap     │                           │
│  └──────────────────┘                           │
└─────────────────────────────────────────────────┘
```

## Backend Sub-APIs

### 1. Agent API (`/api/agent`)

The core game engine. Orchestrates LLM calls and manages tool-calling flow.

- Calls remote LLM via **PythonLLMClient** (supports Ollama, OpenAI, llama-swap)
- Tools use OpenAI-compatible function calling format
- Tool schemas auto-generated from Pydantic models via `pydantic_to_openai_tool()`
- All tool implementations are **internal async functions** (no bash, no external HTTP)
- Tools give the LLM access to: world data, locations, NPCs, items, rules
- Some context (e.g. current location) may be auto-injected; the core design forces the LLM to actively collect data via tool calls

### 2. Users/Chats API (`/api/users`, `/api/chats`)

Utilitarian data management:

- User accounts and profiles
- Game states and saves
- Chat histories and message storage

### 3. Admin API (`/api/admin`)

Administrative operations:

- User management (CRUD, roles, permissions)
- World database management (locations, NPCs, items, rules)

## Frontend Applications

### User SPA (served at `/`)

- Player-facing chat interface
- TypeScript + React + MobX for state management
- History API for URL routing and back/forward navigation
- Shows admin link for users with admin privileges

### Admin SPA (served at `/admin`)

- World and user management interface
- Same tech stack as User SPA (TypeScript, React, MobX)
- Separate entry point and build from User SPA
- Shares only the login/auth flow with User SPA

## Authentication

- JWT tokens, stateless
- Shared login flow between both SPAs
- Role-based access (user vs admin)

## Data Modeling

- **Pydantic `BaseModel`**: All API request/response models, tool parameter schemas
- **SQLModel**: All database models (SQLAlchemy + Pydantic combined)
- **`TypedDict`**: Internal data passing between functions
- **No free dictionaries, no untyped data** — strict typing throughout

## Data Storage

- **SQLite** via **SQLModel** ORM for all persistent data
- Dev: `backend/data/` subfolder
- Prod: Docker volume mapped to `./data/`
