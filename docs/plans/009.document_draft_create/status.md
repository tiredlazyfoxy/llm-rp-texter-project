# Feature 009 — Document Draft Create

| Step | File                                                     | Status  | Verifier | Date |
|------|----------------------------------------------------------|---------|----------|------|
| 001  | `001.backend_snowflake_endpoint_and_create_with_id.md`   | done    | PASS     | 2026-05-05 |
| 002  | `002.frontend_draft_document_create.md`                  | pending | —        | —    |

## Files Changed

### Step 001 — Backend: snowflake endpoint and document create with client-supplied id
- `backend/app/models/schemas/worlds.py` — added optional `id: str | None = None` to `CreateDocumentRequest`.
- `backend/app/db/worlds.py` — added `document_id_exists(doc_id: int) -> bool` helper checking all three document tables (`WorldLocation`, `WorldNPC`, `WorldLoreFact`).
- `backend/app/services/world_editor.py` — `create_document` now parses `req.id` (if present) to int, raises HTTP 400 on non-numeric input and HTTP 409 on collision (delegated to `db.worlds.document_id_exists`); falls back to `generate_id()` when `req.id is None`.
- `backend/app/routes/admin/ids.py` — new thin router exposing `GET /api/admin/snowflake/new` (response model `NewSnowflakeIdResponse { id: str }`); editor-role auth.
- `backend/app/main.py` — included the new `admin_ids_router` (existing project pattern is to register each admin router in `main.py`; no `routes/admin/__init__.py` exists in the codebase).
- `backend/tests/conftest.py` — added `init_db()` call so tables exist for tests; added `admin_user`, `editor_user`, `player_user`, and `http_client` fixtures.
- `backend/tests/routes/__init__.py`, `backend/tests/routes/admin/__init__.py`, `backend/tests/services/__init__.py` — package files for new test layout.
- `backend/tests/routes/admin/test_ids.py` — endpoint tests (200 + numeric id, 401/403 unauth, 403 player, distinct consecutive ids).
- `backend/tests/services/test_world_editor_create_document_with_id.py` — service tests (None regression, unused id success for each doc_type, 409 for each colliding table, non-numeric id → 4xx, `document_id_exists` sanity).

## Notes & Issues

### Step 001 notes

- **No JSONL import/export changes** — model/table shape unchanged (only schema/service behavior, no new columns); per project rule this is verified explicitly.
- **`backend/CLAUDE.md` not updated** — the new file is a sibling route module under an existing folder shape (no new directory), which the step's "only if folder shape changes" gate excludes.
- **Auth dependency choice** — the step says "mirror the auth dependency used by `backend/app/routes/admin/worlds.py`". `worlds.py` uses `_require_editor` (not admin) for `create_document`, so the new id endpoint also uses `_require_editor`, since the endpoint feeds the same flow. Only `delete_world` and a few admin user-management routes use `_require_admin`.
- **Step file's id-assignment line numbers (~612, 677, 762) refer to other create helpers** — the actual `create_document` function lives at line 432 with a single `new_id = generate_id()` site (line 436) used by all three doc_type branches. The implementation correctly honors `req.id` for all three branches via that single assignment site; the planner's intent ("each branch must honor `req.id`") is satisfied.
- **Admin router registration** — step file mentions `backend/app/routes/admin/__init__.py`, but no such file exists in the codebase; existing pattern registers admin routers one-by-one in `app/main.py`. Followed the existing pattern.
