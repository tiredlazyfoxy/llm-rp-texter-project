# Feature 013 — World Document Drag-and-Drop Upload

| Step | File                              | Status  | Verifier | Date |
|------|-----------------------------------|---------|----------|------|
| 001  | `001.backend_lore_fact_upload.md` | done    | PASS     | 2026-05-06 |
| 002  | `002.frontend_drop_zone.md`       | pending | —        | —    |

## Files Changed

### Step 001 — Backend: extend `upload_documents` to accept `lore_fact`
- `backend/app/services/world_editor.py` — replace the `lore_fact` rejection with a per-file `WorldLoreFact` create branch that delegates to `create_document` (mirrors the helpers used by the `location` / `npc` branches: `generate_id`, `_now`, `_index_document`).
- `backend/tests/services/test_world_editor_upload_documents.py` — new test module covering `lore_fact` happy path (multi-file, persistence, distinct ids, no-raise regression, no-upsert), zero-file case, and `location` / `npc` regression (create + upsert-by-name).

## Notes & Issues

- Step 001: the `lore_fact` branch delegates to `create_document` rather than inlining the row construction. `create_document` already mirrors the exact "snowflake id + `_now()` + `lore_facts.create` + `_index_document` + `DocumentSaveResult`" sequence the step file describes, so delegation is the cleanest mirror of the `location` / `npc` branches (which also delegate via `create_document` / `update_document`). Filename is discarded as specified.
