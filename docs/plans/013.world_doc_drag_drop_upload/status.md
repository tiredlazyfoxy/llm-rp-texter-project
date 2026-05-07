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

## Bug Fixes

### 2026-05-07 — Empty-state placeholder is now a visible drop target (Step 002)

- **Bug**: On a typed tab (`location` / `npc` / `lore_fact`) with zero documents, the empty-state `<Text c="dimmed">No documents yet.</Text>` was a tiny target inside a 2px-transparent-bordered wrapper. The wrapper technically still received drop events, but visually the drop zone was invisible — users perceived "no drop area when there are no documents". Per `frontend/src/admin/CLAUDE.md`, "Empty tables remain drop targets", so this was an affordance regression.
- **Fix**: `frontend/src/admin/pages/WorldViewPage.tsx` — in `DocsTab`, when `state.docs.length === 0` and `docTypeFilter` is truthy, render a `<Stack>` placeholder (`align="center"`, `justify="center"`, `minHeight: 160`) with two lines: "No documents yet." plus dimmed sub-line "Drop .md or .txt files here to upload." The existing wrapper at lines ~466–500 inherits drag handlers + dashed-blue active border + overlay automatically. The `all`-tab branch (`!docTypeFilter`) keeps the original single-line `<Text>` since that tab is intentionally not a drop target. No state, props, or behavior changes — purely empty-state styling.
- **Verification**: `npx tsc --noEmit` clean; `npx vite build` clean.

### 2026-05-07 — Drop zone hover affordance + always-visible idle border (Step 002)

- **Bug** (user words): "doesn't work for the test (i'm trying lore) — make :hover style with highlighting drop area". Tested on the empty `lore_fact` tab. The drop zone's idle border was `2px dashed transparent`, so the user could not see the drop area at all before dragging — "doesn't work" was an affordance failure, not a wiring failure. The drop handlers, the empty-state placeholder, and the backend `lore_fact` upload branch (Step 001) are all wired correctly; the user simply could not tell the wrapper existed because it was invisible until a drag started. Confirmed by reading `frontend/src/admin/pages/WorldViewPage.tsx` (`DocsTab` handlers / wrapper), `frontend/src/admin/pages/worldViewPageState.ts` (`uploadDocuments`), `frontend/src/api/worlds.ts` (`uploadDocuments` POSTs `?doc_type=<type>` multipart, no per-type branching), and `backend/app/services/world_editor.py` (`upload_documents` lore_fact branch creates a row per file via `create_document`). No code path silently fails for `lore_fact`.
- **Fix**:
  - `frontend/src/admin/pages/worldViewPageState.ts` — added `dropHover: boolean` observable + `setDropHover(value)` action on `WorldViewPageState`. Lives on page state to satisfy the step's "no `useState`" rule (Step 002 DoD).
  - `frontend/src/admin/pages/WorldViewPage.tsx` — wrapper now has three visible border states: idle (`gray-3`), hover (`gray-5` + faint `default-hover` background), and drag (`blue-5` solid dashed + translucent blue overlay, unchanged). `dropActive` continues to trump `dropHover`. Wired `onMouseEnter` / `onMouseLeave` on the wrapper to toggle `dropHover`. Existing drag handlers untouched. The `all` tab path stays unchanged (`if (!docTypeFilter) return tableContent`); `ACCEPTED_UPLOAD_EXTENSIONS` and the parity comment are intact. No new components.
- **Verification**: `npm run build` clean (tsc + vite).
- **Note on the "doesn't work" symptom**: nothing in the wiring is broken for `lore_fact`. Backend, API client, page-state mutation, and drop handlers are all type-uniform across the three doc types. The fix above makes the drop zone discoverable — the user should now see a faint dashed gray border around the table area on every typed tab, a stronger gray border on mouse hover, and a solid blue dashed border + overlay during an active drag. Live retest on `lore_fact` is recommended to confirm.

### 2026-05-07 — Hide idle border on populated documents table (Step 002)

- **Bug** (user words): "remove border on 'non-empty' table". The idle dashed gray border + hover affordance (gray-5 border + faint background) made sense as a discoverability cue around the empty-state placeholder, but on a populated table the same styling read as visual noise around an already-self-evident table.
- **Fix**: `frontend/src/admin/pages/WorldViewPage.tsx` — gated the idle/hover visual application on `state.docs.length === 0`. Introduced a local `isEmpty = state.docs.length === 0` / `showIdleAffordance = isEmpty` flag inside the wrapper render. When the table is populated: idle border is `transparent` and hover styling (border + background) is suppressed. When the table is empty: previous three-state behaviour (idle gray-3 dashed, hover gray-5 dashed + faint default-hover bg) is preserved. Drag-active branch is unchanged — `dropActive` still trumps everything and renders the solid dashed blue border + translucent overlay regardless of row count, so empty tables remain visible drop targets per the originating step DoD ("Empty table is still a drop target"). Drop handlers, `incrementDropDepth` / `decrementDropDepth` / `resetDropDepth` wiring, `dropHover` / `setDropHover` wiring (`onMouseEnter` / `onMouseLeave`), `ACCEPTED_UPLOAD_EXTENSIONS` parity, and the `all`-tab early-return (`if (!docTypeFilter) return tableContent`) are all untouched. No state, props, or new components added.
- **Verification**: `npm run build` clean (tsc + vite).
