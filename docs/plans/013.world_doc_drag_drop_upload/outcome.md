# Outcome — Feature 013 World Document Drag-and-Drop Upload

## Intended documentation changes (for the architect)

### `docs/architecture/quick-reference.md`

- **Admin API endpoints table** — update the row for
  `POST /api/admin/worlds/{world_id}/documents/upload` to note
  that `doc_type=lore_fact` is now accepted (previously rejected
  with HTTP 400). Behavior: each uploaded file becomes a brand-new
  `WorldLoreFact` row (no upsert by name; filename is discarded).
  `doc_type=location` and `doc_type=npc` continue to upsert by
  lowercased filename stem.
- **Admin SPA — WorldViewPage section (or add one if missing)** —
  note that the documents table on typed tabs (`location`, `npc`,
  `lore_fact`) is now a drag-and-drop target for `.md` / `.txt`
  files. The `all` tab is intentionally NOT a drop target so the
  uploaded `doc_type` is unambiguous. Empty tables remain drop
  targets. The existing "Upload Locations / Upload NPCs" menu is
  kept alongside the drop zone.

### `docs/architecture/frontend.md`

- **Admin SPA component conventions** — if this is the first
  drag-and-drop UI in the codebase, sanction the **native HTML5
  DnD** pattern as the project's standard for file-drop affordances
  (no `@mantine/dropzone` or `react-dropzone` dependency). Note
  the gotchas:
  - `e.preventDefault()` on `dragover` AND `drop` is required.
  - `dragleave` fires on every descendant boundary; use a depth
    counter (or equivalent) for stable visual state.
  - Drag-over visual state lives on the page's MobX state (no
    `useState`).

### `docs/architecture/backend.md`

- **Document upload service** — note that
  `services/world_editor.upload_documents` now accepts all three
  document types: `location` (upsert by name), `npc` (upsert by
  name), and `lore_fact` (always create — no name field on
  `WorldLoreFact`).

### `docs/architecture/db-models.md`

- No schema changes. No edits required. (Mention only if the
  architect wants to cross-link the upload endpoint from the
  `WorldLoreFact` model in the index.)

## Observations

