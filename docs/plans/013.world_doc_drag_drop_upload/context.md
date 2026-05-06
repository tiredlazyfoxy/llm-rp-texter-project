# Feature 013 — World Document Drag-and-Drop Upload

## Goal

On the admin WorldViewPage, make the **documents table** a drop
target for files so an editor can upload `.md` / `.txt` documents
by dragging them onto the table area. Restrict the drop affordance
to **typed** document tabs (`location`, `npc`, `lore_fact`) — the
`all` tab is intentionally **not** a drop target so the uploaded
`doc_type` is never ambiguous. Drop works on an empty table too.

To make `lore_fact` a legal upload target, extend the backend
upload service (which currently rejects `lore_fact` with HTTP 400)
to bulk-create new lore facts, one per uploaded file. Filenames are
discarded for lore facts (no `name` field on `WorldLoreFact`).

## Scope and decisions (locked)

1. **Drop target = the documents table area** inside `DocsTab`,
   wrapped only when `state.docTypeFilter` is truthy
   (`"location" | "npc" | "lore_fact"`). The filter row, header,
   and action buttons are not part of the drop zone.
2. **Empty table is still a drop target** — the wrapper sits around
   the table area regardless of row count.
3. **`all` tab is NOT a drop target.** Without a chosen `doc_type`
   the upload would be ambiguous; the user explicitly opted out.
4. **Backend `upload_documents` learns `lore_fact`.** The service
   currently raises HTTPException 400 for `doc_type == "lore_fact"`.
   Replace that branch: every file becomes a brand-new
   `WorldLoreFact` row (no upsert by name; lore facts have no name
   field). The existing `_validate_doc_type` already accepts
   `lore_fact`; only the service rejection goes away.
5. **Existing "Upload" menu + hidden file input is kept**
   alongside the new drop zone. Both flows reuse
   `uploadDocuments(state, files, docType, signal)`.
6. **Mixed file types reject the whole drop.** If any dropped file
   has an extension other than `.md` / `.txt`, the entire drop is
   rejected — no partial upload. Surface a clear error via the
   existing `state.docsError` ("Only `.md` / `.txt` files are
   accepted; drop rejected because it contained other types"). If
   all files are accepted, upload them all.
7. **`doc_type` for the upload call is `state.docTypeFilter`.**
   The drop handler short-circuits when `docTypeFilter` is
   `undefined` (defense-in-depth — the wrapper isn't rendered then,
   but the handler still guards).
8. **No new backend Pydantic schemas, no DB migration, no JSONL
   importer change.** `WorldLoreFact` already exists; we just stop
   rejecting it on the upload path.

## Files involved (across multiple steps)

Backend:

- `backend/app/services/world_editor.py` — step 001 removes the
  `lore_fact` rejection and adds a per-file `WorldLoreFact` create
  branch; the existing `location` / `npc` upsert branches are
  untouched.
- `backend/app/models/world.py` — referenced for the `WorldLoreFact`
  shape (no edit; planner-side reference).
- `backend/tests/` — step 001 adds `lore_fact` upload coverage
  alongside the existing upload-route tests (locate the existing
  test file via the harvester search; create a new file if none
  exists).

Frontend:

- `frontend/src/admin/pages/WorldViewPage.tsx` — step 002 wraps the
  documents table area inside `DocsTab` with HTML5 drag-and-drop
  handlers, gated on `state.docTypeFilter` truthiness.
- `frontend/src/admin/pages/worldViewPageState.ts` — step 002 may
  add a `dropActive: boolean` observable for visual feedback (the
  existing `uploadDocuments` mutation is reused as-is for the
  network call; `state.docsError` covers the "all-filtered-out"
  error message).

## External references

- `docs/plans/008.*` and `docs/plans/009.document_draft_create/` —
  most recent admin/worlds frontend features; consult their step
  files for the page-aware MobX-component shape this feature
  follows.
- `docs/architecture/quick-reference.md` — Admin API endpoints
  table; `POST /api/admin/worlds/{world_id}/documents/upload` row
  needs a follow-up note that `lore_fact` is now accepted (covered
  in `outcome.md`).
- `docs/architecture/frontend.md` — admin SPA component conventions
  (observer-wrapped, MobX page state, no `useState`, no custom
  hooks, no `useCallback` / `useMemo`).
- `frontend/src/admin/CLAUDE.md` — admin-SPA layout; page-aware
  components colocated under `components/<domain>/` and reactive
  state on `<page>State.ts`.
- `frontend/src/api/CLAUDE.md` — multipart uploads use raw `fetch`
  + `authHeaders()` + `throwApiError`; the existing
  `uploadDocuments` API client already complies.

## Vocabulary

- **Typed tab** — one of `location`, `npc`, `lore_fact`. The page
  exposes the typed `doc_type` via the computed
  `state.docTypeFilter`. The `all` tab returns `undefined`.
- **Drop zone** — the wrapper around the documents table area
  inside `DocsTab`. Adds drag-over visual feedback; on drop, filters
  files by extension and calls `uploadDocuments`.
- **Accepted extensions** — `.md`, `.txt` (matches the existing
  hidden `<input type="file" accept=".md,.txt" multiple>` already
  in `DocsTab`).
- **Filename → doc name (location/npc only)** — `_b_filename_stem`
  in the existing service derives the name. Lore facts have no name
  field, so the filename is discarded after upload.

## Cross-cutting constraints

- **Layer separation (backend):** the upload route already lives at
  `routes/admin/worlds.py` and delegates to
  `services/world_editor.upload_documents`. Step 001 stays inside
  the service layer; no DB queries leak into the route.
- **Strict typing (frontend):** no `any`; new state fields use
  precise types; native HTML5 DnD uses `React.DragEvent<HTMLElement>`
  (or the more specific element type) — never `any` event.
- **No new Pydantic schemas / no `.d.ts` change.** The upload
  endpoint's request shape (`multipart/form-data` + `doc_type`
  query param) and response (`list[DocumentSaveResponse]`) are
  unchanged.
- **MobX rules (frontend):** no `useState` / `useMemo` /
  `useCallback`. Drag-over state, if observable, lives on the page
  state class. Components stay `observer`-wrapped.
- **Accept-list parity:** the drop filter must accept the same
  extensions as the hidden input (`.md`, `.txt`). If the input's
  accept list ever changes, both must move together — call out in
  comments on both sides.
- **Drag-over default-prevention:** native HTML5 DnD requires
  `e.preventDefault()` on `dragover` (and `drop`) to prevent the
  browser from navigating to the file. Step 002 must include this.
- **JSONL coverage:** no DB schema change in this feature, so the
  importer/exporter is not touched. If any step finds it must
  change a model, stop and hand back to the orchestrator.
- **Auth:** the upload route is already gated on the
  `_require_editor` dependency. Step 001 keeps that gate; the new
  `lore_fact` branch inherits it for free.

## Out of scope

- Drop target on the `all` tab (intentional — no `doc_type`
  inferable).
- Drop target outside the documents table (e.g. anywhere on the
  page or on the tabs strip).
- Non-text file types (images, PDFs, archives). The accept list
  stays `.md` / `.txt`.
- Per-file progress / per-file error reporting. Whole-batch
  try/catch updating `state.docsError` is the existing contract;
  this feature does not introduce per-file status.
- Replacing the existing "Upload Locations / Upload NPCs" menu —
  it stays as a fallback for users who prefer click-to-upload.
- Adding a "Upload Lore Facts" entry to the Upload menu — out of
  scope for this feature; only the drop-zone path is added for
  lore facts. (A separate follow-up may add the menu item if
  desired; flag in `outcome.md`.)
- Introducing a drag-drop library (`@mantine/dropzone`,
  `react-dropzone`). Native HTML5 DnD is sufficient and matches
  the codebase's "no extra deps unless needed" posture.

## Open trade-offs (left for the coder; documented to surface choice)

These were raised during planning and intentionally not pinned;
the coder should pick the path that fits the existing code,
document the choice in step status notes, and the architect can
revise in `outcome.md` if needed.

- **Inline JSX vs extracted component (step 002).** The drop-zone
  wrapper can stay inline inside `DocsTab` or be extracted to a
  new `frontend/src/admin/components/worlds/DocsTableDropZone.tsx`.
  Pick based on size and readability per `frontend-components.md`'s
  "growing components split into observer subcomponents" guidance.
  If extracted, keep it `observer`-wrapped and accept page state
  via prop (matches the rest of the admin SPA).
- **Visual feedback mechanism (step 002).** Either toggle a
  `dropActive` observable on page state (cleanly reactive, but
  needs `runInAction`) or attach a CSS class via a ref-based
  approach. Page-state observable is the more conventional choice
  for this codebase; pick that unless there's a strong reason
  otherwise.
- **`dragleave` debouncing (step 002).** HTML5 DnD fires
  `dragleave` whenever the cursor crosses any descendant boundary,
  which causes flicker if you toggle visual state on every event.
  Either (a) track depth with a counter (increment on `dragenter`,
  decrement on `dragleave`, only clear at zero), or (b) check the
  event's `relatedTarget` against the wrapper's bounds. Counter
  approach is simpler and is the common pattern; pick (a) unless
  it doesn't fit cleanly.
