# System Architecture Overview

## High-Level Diagram

```
┌─────────────────────────────────────────────────┐
│                    nginx                         │
│  / ──► User SPA (static)                        │
│  /admin ──► Admin SPA (static)                  │
│  /api ──► FastAPI backend (proxy)               │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│              FastAPI Backend                      │
│                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │  Agent API   │  │ Users/Chats  │  │ Admin   │ │
│  │  /api/agent  │  │ /api/users   │  │ /api/   │ │
│  │              │  │ /api/chats   │  │  admin  │ │
│  └──────┬───── ┘  └──────┬───────┘  └────┬────┘ │
│         │                │                │      │
│         ▼                ▼                ▼      │
│  ┌─────────────┐  ┌──────────────────────────┐  │
│  │ MCP Tools   │  │        SQLite            │  │
│  │ (internal   │  │  - users                 │  │
│  │  async fns) │  │  - game states           │  │
│  └──────┬──────┘  │  - chat histories        │  │
│         │         │  - world data            │  │
│         ▼         └──────────────────────────┘  │
│  ┌─────────────┐                                 │
│  │ LLM Backend │                                 │
│  │ (HTTP API)  │                                 │
│  │ - llama.cpp │                                 │
│  │ - OpenAI    │                                 │
│  └─────────────┘                                 │
└─────────────────────────────────────────────────┘
```

## Backend Sub-APIs

### 1. Agent API (`/api/agent`)

The core game engine. Orchestrates LLM calls and exposes MCP tools.

- Calls remote LLM via HTTP (llama.cpp or OpenAI-compatible API)
- Provides MCP tools as **internal async functions** (no bash, no external HTTP)
- MCP tools give the LLM access to: world data, locations, NPCs, items, rules
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

## Data Storage

- **SQLite** for all persistent data
- Single database or multiple databases (TBD based on scaling needs)
