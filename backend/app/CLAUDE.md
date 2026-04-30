# app/

FastAPI application root.

- `main.py` — FastAPI app, CORS, router mounting
- `models/` — SQLModel DB models + Pydantic API schemas
- `routes/` — API route handlers (HTTP layer only)
- `db/` — Data access layer (DB-agnostic interface)
- `services/` — Business logic (no direct DB queries, no session creation)

See each subfolder's `CLAUDE.md` for details.
