# Feature 009 — Document Draft Create

| Step | File                                                     | Status  | Verifier | Date |
|------|----------------------------------------------------------|---------|----------|------|
| 001  | `001.backend_snowflake_endpoint_and_create_with_id.md`   | done    | PASS     | 2026-05-05 |
| 002  | `002.frontend_draft_document_create.md`                  | done    | PASS     | 2026-05-05 |

## Files Changed

### Step 002 — Frontend: draft document create flow
- `frontend/src/api/admin.ts` — added `getNewSnowflakeId(signal?)` wrapper plus a private `NewSnowflakeIdResponse` interface (kept in `admin.ts` rather than a sibling `ids.ts` for lower friction; `admin.ts` already serves cross-cutting admin endpoints).
- `frontend/src/types/world.d.ts` — added optional `id?: string` to `CreateDocumentRequest`.
- `frontend/src/admin/pages/WorldViewPage.tsx` — `handleCreate` now calls `getNewSnowflakeId()` then navigates to `/worlds/<wid>/documents/<id>/edit?new=1&doc_type=<type>`; no document POST. Dropped `createNewDocument` import.
- `frontend/src/admin/pages/worldViewPageState.ts` — deleted `createNewDocument` and the now-unused `createDocument` import. `createDocStatus` field retained (still used by the new create flow's button spinner).
- `frontend/src/admin/routes.tsx` — `DocumentEditPageRoute` reads `?new=1` and `?doc_type=...` via `useSearchParams` and forwards them as `isNew`/`initialDocType` props.
- `frontend/src/admin/pages/DocumentEditPage.tsx` — accepts `isNew` and `initialDocType` props and passes them to `DocumentEditPageState`'s constructor.
- `frontend/src/admin/pages/documentEditPageState.ts` — added draft mode: optional `{ isNew, initialDocType }` constructor option; observable `isNew`, `initialDocType`, `pendingLinkOps`; new `LinkOp` discriminated union; new `loadDraftDocument` helper that skips `getDocument`, seeds an empty `DocumentItem` of the requested type, fetches link options for npc/location, and sets `loadStatus = "ready"`. `loadDocument` short-circuits to `loadDraftDocument` when `isNew`. `saveDocument` branches on `isNew`: POSTs `createDocument({ id: docId, doc_type, name, content, exits? })`, replays queued link ops sequentially via `createLink` (abort-aware), clears `pendingLinkOps`, flips `isNew = false`, then reloads from server. `isDirty` returns `true` when `isNew` so the Save button is always available in draft mode.

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

### Step 002 notes

- **`getNewSnowflakeId` placement** — added to `frontend/src/api/admin.ts` instead of a new `ids.ts`. The step file allowed either; `admin.ts` is the lower-friction option (already cross-cutting per `frontend/src/api/CLAUDE.md`).
- **`createDocStatus` retained** — the planner asked for `createNewDocument` to be deleted as dead code; the related `createDocStatus` observable is retained because the new `WorldViewPage.handleCreate` still uses it for the create-button loading spinner during the snowflake fetch.
- **Planner's "createLink/deleteLink paths queue into pendingLinkOps" wording** — the existing UI never called the link APIs directly; link mutations were already deferred to save via `draft.{allowed,prohibited}Ids` + `syncLinks`. Implemented the planner's intent literally: the draft Save path captures a `pendingLinkOps: LinkOp[]` snapshot from `draft.{allowed,prohibited}Ids` after the document POST succeeds, then replays those creates sequentially via `createLink` (abort-aware). No prior-link delete replays needed since drafts have no prior links.
- **`isDirty` returns true while isNew** — required so the Save button is visible while the user is filling in a fresh draft; mirrors `PipelineEditPage` shadow-mode UX.
- **Smoke-test checklist for QA** (verbatim from step file):
  1. Click "New Location" — URL becomes
     `/admin/worlds/<wid>/documents/<id>/edit?new=1&doc_type=location` and the
     page shows an empty draft.
  2. Type a name + content, then Save — row is created in the DB with that exact
     id. URL stays the same. `?new=1` becomes irrelevant after save (state's
     `isNew` flips to `false`).
  3. Repeat with NPC and create a link to a location while the NPC is still
     a draft — the link displays in the editor but the network panel shows no
     link API calls. On Save, the document POST happens first, then the link
     POSTs flush.
  4. Click "New Location", reload the page on `?new=1` URL — page shows a fresh
     empty draft with the same id and doc_type. Draft content is gone (expected).
  5. Cancel/close the tab without saving — no orphaned row in the DB.

### Step 001 notes

- **No JSONL import/export changes** — model/table shape unchanged (only schema/service behavior, no new columns); per project rule this is verified explicitly.
- **`backend/CLAUDE.md` not updated** — the new file is a sibling route module under an existing folder shape (no new directory), which the step's "only if folder shape changes" gate excludes.
- **Auth dependency choice** — the step says "mirror the auth dependency used by `backend/app/routes/admin/worlds.py`". `worlds.py` uses `_require_editor` (not admin) for `create_document`, so the new id endpoint also uses `_require_editor`, since the endpoint feeds the same flow. Only `delete_world` and a few admin user-management routes use `_require_admin`.
- **Step file's id-assignment line numbers (~612, 677, 762) refer to other create helpers** — the actual `create_document` function lives at line 432 with a single `new_id = generate_id()` site (line 436) used by all three doc_type branches. The implementation correctly honors `req.id` for all three branches via that single assignment site; the planner's intent ("each branch must honor `req.id`") is satisfied.
- **Admin router registration** — step file mentions `backend/app/routes/admin/__init__.py`, but no such file exists in the codebase; existing pattern registers admin routers one-by-one in `app/main.py`. Followed the existing pattern.
