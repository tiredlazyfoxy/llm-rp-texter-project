# LLM RP Text-Only Project

## Overview

A research-driven RPG chat application where the game world, NPCs, rules, intentions, and interactions are **described and defined** — but actions and dialogues are **not scripted**. Instead, an LLM agent generates them dynamically at runtime.

## Core Idea

Traditional RPGs script NPC dialogue trees and player interactions. This project takes a different approach:

- **Define** the world: locations, NPCs, rules, relationships, intentions
- **Let the LLM generate** actions, dialogue, and narrative in real-time
- **Force the LLM** to actively discover world data via MCP tools rather than having everything pre-loaded (not RAG)

The goal is to research and validate whether this approach produces coherent, engaging RPG experiences.

## System Components

| Component | Tech | Purpose |
|-----------|------|---------|
| Backend (Agent) | FastAPI, Python 3.13, PythonLLMClient | LLM orchestration, tool calling, world data |
| Backend (API) | FastAPI, SQLModel, SQLite | Users, game states, chat histories |
| Backend (Admin API) | FastAPI, SQLModel | User management, world database management |
| User SPA | TypeScript, React, MobX, Vite | Player-facing chat interface |
| Admin SPA | TypeScript, React, MobX, Vite | World & user management interface |

## Key Architectural Decisions

- **Tool calling over RAG**: The LLM collects context via function calls, not vector search
- **Tools are internal**: 100% in-process async functions, no external HTTP or bash
- **LLM client**: PythonLLMClient — supports Ollama, OpenAI, llama-swap backends
- **Strict typing**: Pydantic models for API/tools, SQLModel for DB, TypedDict for internals — no untyped data
- **ORM**: SQLModel (SQLAlchemy + Pydantic)
- **Two SPAs**: User and Admin are separate apps sharing only the login flow
- **JWT authentication**: Stateless tokens shared across both SPAs
- **Frontend architecture**: MobX-only state, observer everywhere, no `useState`/`useCallback`/Context/custom hooks, `useEffect` only at the page level for mount/unmount, page = route owner with remount-on-key, URL query params as the cross-navigation persistence layer, async resource trio (`<name>` / `<name>Status` / `<name>Error`), HTTP isolated in `src/api/` with DTOs in `src/types/`, auth + global settings as module-level state (no `AppState` class), no runtime schema validation. See `frontend.md` and the `frontend-*.md` set for the full rules.
