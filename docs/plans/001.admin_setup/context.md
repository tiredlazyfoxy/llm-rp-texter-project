# Feature 001 — Admin Setup

Global planner context for the admin-side foundation: auth, world models, LLM server management, world editor, LLM-assisted editing, DB management, admin LLM tools, lore injection.

## Files / References

- `docs/architecture/` — full architecture docs
- `docs/architecture/quick-reference.md` — condensed DB models, API, SSE, tools
- `backend/CLAUDE.md` — backend layout
- `frontend/CLAUDE.md` — frontend layout

## Facts

- Tech: FastAPI, Python 3.13, SQLite, React/Vite/MobX, JWT auth.
- Layered backend: `routes/` → `services/` → `db/` (no DB sessions outside `db/`).
- All API contracts strictly typed (Pydantic ↔ TypeScript `.d.ts`).
- All DB-persistent models require gzipped JSONL import/export.
