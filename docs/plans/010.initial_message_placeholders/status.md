# Feature 010 — initial_message_placeholders

| Step | File                                          | Status  | Verifier | Date |
|------|-----------------------------------------------|---------|----------|------|
| 001  | `001.backend_uppercase_and_migration.md`      | done    | PASS     | 2026-05-05 |
| 002  | `002.move_placeholder_components.md`          | done    | PASS     | 2026-05-05 |
| 003  | `003.wire_into_world_field_edit.md`           | done    | PASS     | 2026-05-05 |

## Files Changed

### Step 001 — Backend: uppercase placeholders + migration
- `backend/app/services/chat_service.py` — runtime substitution uses uppercase `{CHARACTER_NAME}` / `{LOCATION_NAME}` / `{LOCATION_SUMMARY}` only (lines 425-432).
- `backend/app/services/prompts/world_field_editor_system_prompt.py` — initial_message role docstring lists the three uppercase placeholders.
- `backend/app/db/worlds.py` — adds `INITIAL_MESSAGE_TOKEN_REWRITES`, pure `rewrite_initial_message_tokens()` helper, and idempotent `normalize_initial_message_placeholders()` migration.
- `backend/app/main.py` — lifespan calls `worlds_db.normalize_initial_message_placeholders()` once after engine init when DB is ready.
- `backend/app/services/db_import_export.py` — `_dict_to_world` runs imported `initial_message` through `rewrite_initial_message_tokens` before constructing the row.
- `backend/tests/db/__init__.py` — package marker for the new test folder.
- `backend/tests/db/test_initial_message_migration.py` — covers lowercase/uppercase/mixed rewrite, idempotency, and the pure helper.
- `backend/tests/services/test_chat_service.py` — asserts uppercase substitution at chat start and that lowercase tokens are not recognized at runtime.

### Step 002 — Frontend: move placeholder components to shared folder
- `frontend/src/admin/components/placeholders/PlaceholderTextarea.tsx` — moved (git mv) from `components/pipelines/`; contents identical.
- `frontend/src/admin/components/placeholders/PlaceholderPanel.tsx` — moved (git mv) from `components/pipelines/`; contents identical.
- `frontend/src/admin/components/placeholders/PlaceholderSuggestions.tsx` — moved (git mv) from `components/pipelines/`; contents identical.
- `frontend/src/admin/components/placeholders/placeholderAutocompleteState.ts` — moved (git mv) from `components/pipelines/`; contents identical.
- `frontend/src/admin/pages/PipelineStageEditPage.tsx` — `PlaceholderPanel` and `PlaceholderTextarea` imports rewritten to `../components/placeholders/`.
- `frontend/src/admin/CLAUDE.md` — `components/pipelines/` entry replaced with `components/placeholders/`, noting it is shared between pipeline-stage and world-field editors.

### Step 003 — Frontend: wire placeholder UI into WorldFieldEditPage
- `frontend/src/admin/components/placeholders/initialMessagePlaceholders.ts` — new constants module exporting `INITIAL_MESSAGE_PLACEHOLDERS` (CHARACTER_NAME / LOCATION_NAME / LOCATION_SUMMARY, unbraced).
- `frontend/src/admin/pages/WorldFieldEditPage.tsx` — adds `controllerRef`, branches on `state.fieldName === "initial_message"` to render `<PlaceholderTextarea>` + `<PlaceholderPanel>`; `description` keeps the plain `<Textarea>`. Page remains wrapped in `observer`.

## Notes & Issues
- Step 002: `frontend/src/admin/components/pipelines/` is now an empty directory — git tracks no files there but the folder remains on disk. Step does not require its removal; left untouched to stay in scope.

_populated by the coder when worth saying_
