# Project Rules

## DEV Environment

- **OS**: Windows 11
- **Preferred shell**: PowerShell (use PowerShell over bash when possible)
- **Path separators**: Use backslashes (`\`) for Windows paths in PowerShell; forward slashes are acceptable in git commands

## Prod Environment

- Docker compose
- Static nginx for fronend

## Rules

### File System Access

- Freely run `ls`, `dir`, `Get-ChildItem`, search, and other read-only commands on the project folder and subfolders
- No restrictions on reading files within the project

### Git Policy

- **Read-only commands** (run freely, no permission needed): `git status`, `git log`, `git diff`, `git branch`, `git remote`, `git show`, `git stash list`, and any other non-modifying commands
- **`git add` and `git commit`** (require explicit user permission before running)
- **Other write commands** (run freely): `git push`, `git merge`, `git rebase`, `git checkout`, `git stash`, etc.

## Project Overview

LLM-driven RPG chat application. World, NPCs, rules, and interactions are defined — actions and dialogue are generated dynamically by an LLM agent using MCP tools.

See `architecture/` for full documentation.

## Tech Stack

- **Backend**: FastAPI, Python 3.13, SQLite, pyproject.toml
- **Frontend**: TypeScript, React, MobX, Vite
- **Auth**: JWT tokens
- **Prod**: Docker (nginx + FastAPI), no CORS
- **Dev**: API on :8085, Frontend on :8094, CORS enabled

## Project Structure

- `architecture/` — Architecture documents and design decisions
- `plans/` — Project plans and task breakdowns (tracked in git)
- `backend/` — FastAPI backend (agent, users/chats API, admin API)
- `frontend/` — Vite multi-page app (User SPA + Admin SPA)
- `docker-compose.dev.yml` — Dev Docker setup with build
- `docker-compose.prod.yml` — Production Docker setup (pre-built images)
- `build.ps1` — Build images, compress with 7z, export to NAS
- `fetch.sh` — Import images from NAS on deployment server
- `.dockerignore` — Docker build exclusions
- Each subfolder has its own `CLAUDE.md` for context

## Conventions

- Planning docs go to `plans/` folder (tracked in git) — **not** `~/.claude/plans/`
- **Backlog ideas**: `backlog.<idea_name>.md` — ideas not yet scheduled for execution
- **Scheduled work**: `stageN_stepM_somename.md` — when a backlog item is promoted to execution
- **Completed work**: `stageN_stepM_somename.done.md` — for retrospective
- Final architecture docs go to `architecture/`
- Every project subfolder must have a `CLAUDE.md`

## API Typing — Full Stack

- **All API contracts are strictly typed on both sides** — no `any`, no untyped data
- **Backend**: Pydantic `BaseModel` for all request/response schemas
- **Frontend**: TypeScript `.d.ts` interfaces matching backend schemas exactly
- **No free dictionaries** on backend, **no `any`** on frontend

## DB Import/Export

- **All DB-persistent models must have JSONL import/export support**
- Format: gzipped JSONL files (`.jsonl.gz`)
- **Every time a DB model is added or changed, update the import/export logic as part of the same change**
- This is not optional — treat it as part of the model definition process

## Backend Conventions

- **Pydantic `BaseModel`**: All API models, tool parameter schemas
- **SQLModel**: All database models
- **`TypedDict`**: Internal data passing
- **No free dictionaries, no untyped data**
- **LLM client**: PythonLLMClient — tool schemas via `pydantic_to_openai_tool()`
- **Logging**: Python `logging`, INFO for requests, DEBUG for full flow

## Backend Layer Separation

- **`routes/`** — HTTP only (parse request, call service, return response)
- **`services/`** — Business logic (no direct DB queries, no session creation)
- **`db/`** — DB-agnostic data access (session-free public API — all sessions managed internally)
- **No `session`, `AsyncSession`, or connection objects outside `db/`**
- **Import style**: namespace modules — `from app.db import users, worlds` then `await users.get_by_id(id)`
- Services import as: `from app.services import auth as auth_service` then `auth_service.create_token(user)`
