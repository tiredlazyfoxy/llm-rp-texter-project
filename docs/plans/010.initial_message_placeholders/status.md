# Feature 010 — initial_message_placeholders

| Step | File                                          | Status  | Verifier | Date |
|------|-----------------------------------------------|---------|----------|------|
| 001  | `001.backend_uppercase_and_migration.md`      | done    | PASS     | 2026-05-05 |
| 002  | `002.move_placeholder_components.md`          | pending | —        | —    |
| 003  | `003.wire_into_world_field_edit.md`           | pending | —        | —    |

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

## Notes & Issues

_populated by the coder when worth saying_
