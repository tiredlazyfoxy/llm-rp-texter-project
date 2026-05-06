# Feature 013 — World Document Drag-and-Drop Upload

| Step | File                              | Status  | Verifier | Date |
|------|-----------------------------------|---------|----------|------|
| 001  | `001.backend_lore_fact_upload.md` | done    | PASS     | 2026-05-06 |
| 002  | `002.frontend_drop_zone.md`       | done    | PASS     | 2026-05-06 |

## Files Changed

### Step 001 — Backend: extend `upload_documents` to accept `lore_fact`
- `backend/app/services/world_editor.py` — replace the `lore_fact` rejection with a per-file `WorldLoreFact` create branch that delegates to `create_document` (mirrors the helpers used by the `location` / `npc` branches: `generate_id`, `_now`, `_index_document`).
- `backend/tests/services/test_world_editor_upload_documents.py` — new test module covering `lore_fact` happy path (multi-file, persistence, distinct ids, no-raise regression, no-upsert), zero-file case, and `location` / `npc` regression (create + upsert-by-name).

### Step 002 — Frontend: drag-and-drop drop zone on the documents table
- `frontend/src/admin/pages/worldViewPageState.ts` — adds `dropDepth` observable + `dropActive` computed + `incrementDropDepth` / `decrementDropDepth` / `resetDropDepth` actions on `WorldViewPageState` (depth-counter pattern to suppress dragleave flicker on descendant boundary crossings). `uploadDocuments` mutation reused unchanged.
- `frontend/src/admin/pages/WorldViewPage.tsx` — wraps the documents table render area inside `DocsTab` with an HTML5 drag-and-drop wrapper, gated on `state.docTypeFilter` truthiness; handlers typed as `React.DragEventHandler<HTMLDivElement>`; whole-drop rejection on any non-`.md` / non-`.txt` extension via `runInAction(() => { state.docsError = ... })`; `ACCEPTED_UPLOAD_EXTENSIONS` constant + parity comment beside the hidden `<input accept=".md,.txt">`; visual feedback is a 2px dashed Mantine-blue border plus a translucent overlay reading "Drop files to upload" while `state.dropActive` is true. The existing Upload menu and hidden input remain unchanged.

## Notes & Issues

- Step 001: the `lore_fact` branch delegates to `create_document` rather than inlining the row construction. `create_document` already mirrors the exact "snowflake id + `_now()` + `lore_facts.create` + `_index_document` + `DocumentSaveResult`" sequence the step file describes, so delegation is the cleanest mirror of the `location` / `npc` branches (which also delegate via `create_document` / `update_document`). Filename is discarded as specified.
- Step 002: chose the depth-counter approach (open trade-off in `context.md`) — added `dropDepth: number` observable with a `dropActive` computed instead of a single boolean. Cleaner against HTML5 dragleave-on-every-descendant behavior. Inline JSX (no extracted component) — the wrapper is ~40 lines and reads cleanly inline; extraction would only add a thin observer wrapper around a single div.
