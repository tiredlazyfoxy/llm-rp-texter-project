# Project Rules

## Environment

- **OS**: Windows 11
- **Preferred shell**: PowerShell (use PowerShell over bash when possible)
- **Path separators**: Use backslashes (`\`) for Windows paths in PowerShell; forward slashes are acceptable in git commands

## File System Access

- Freely run `ls`, `dir`, `Get-ChildItem`, search, and other read-only commands on the project folder and subfolders
- No restrictions on reading files within the project

## Git Policy

- **Read-only commands** (no permission needed): `git status`, `git log`, `git diff`, `git branch`, `git remote`, etc.
- **Write commands** (require explicit user permission): `git add`, `git commit`, `git push`, `git merge`, `git rebase`, `git checkout -b`, and any other commands that modify the repo

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
- `plans/` — Project plans and task breakdowns (git ignored)
- `backend/` — FastAPI backend (agent, users/chats API, admin API)
- `frontend/` — Vite multi-page app (User SPA + Admin SPA)
- `docker-compose.dev.yml` — Dev Docker setup with build
- `docker-compose.prod.yml` — Production Docker setup
- Each subfolder has its own `CLAUDE.md` for context

## Conventions

- Planning docs go to `plans/` folder (git ignored) — **not** `~/.claude/plans/`
- Plan naming: `stageN_stepM_somename.md` (e.g. `stage1_step1_backend_setup.md`)
- When a plan is done: rename to `stageN_stepM_somename.done.md` for retrospective
- Final architecture docs go to `architecture/`
- Every project subfolder must have a `CLAUDE.md`

## API Typing — Full Stack

- **All API contracts are strictly typed on both sides** — no `any`, no untyped data
- **Backend**: Pydantic `BaseModel` for all request/response schemas
- **Frontend**: TypeScript `.d.ts` interfaces matching backend schemas exactly
- **No free dictionaries** on backend, **no `any`** on frontend

## Backend Conventions

- **Pydantic `BaseModel`**: All API models, tool parameter schemas
- **SQLModel**: All database models
- **`TypedDict`**: Internal data passing
- **No free dictionaries, no untyped data**
- **LLM client**: PythonLLMClient — tool schemas via `pydantic_to_openai_tool()`
- **Logging**: Python `logging`, INFO for requests, DEBUG for full flow
