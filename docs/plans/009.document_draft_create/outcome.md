# Outcome — Feature 009 Document Draft Create

## Intended documentation changes (for the architect at finalization)

### `docs/architecture/frontend-pages.md`

- **Section: query-param-driven flags / draft pages** — document the `?new=1`
  convention used by `DocumentEditPage`: when present, the page skips the
  URL-driven load and initializes an empty draft for the supplied
  `?doc_type=...`. Reload on the same URL re-initializes a fresh draft (same
  id, same doc_type). Reason: establishes a reusable convention beyond the
  pipeline `'shadow' | 'edit'` pattern, which was URL-synthetic.

- **Section: route wrappers** — note that route wrappers may surface query
  params as typed props (`isNew: boolean`, `initialDocType?: string`) rather
  than each page reading `useSearchParams` ad hoc.

### `docs/architecture/frontend-forms.md`

- **Section: draft vs server snapshot** — add a new subsection
  "Pre-allocated id drafts" describing the pattern: client fetches a
  server-generated id first, opens the editor on a real URL with `?new=1`,
  queues child-resource operations (e.g. links) in page state, and flushes
  them after the parent is persisted on Save. Reason: this is the right
  pattern when the editor needs an id for child relationships before first
  save (e.g. NPC ↔ Location links) and a modal would be too cramped.

- **Section: queued operations** — document `pendingLinkOps` style queues as
  a sanctioned approach for child-resource intents during draft mode, with
  the rule that replay happens sequentially against existing APIs after the
  parent POST succeeds.

### `docs/architecture/backend.md`

- **Section: ID generation** — note that create endpoints **may** accept a
  client-supplied snowflake id when the workflow requires the id before
  first save (e.g. draft editors with child relationships). The contract:
  optional `id` field on the request, server falls back to `generate_id()`
  when absent, returns HTTP 409 on collision. Reason: codifies the
  exception to the "server assigns ids" default so future endpoints adopting
  the same pattern follow consistent semantics.

- **Section: admin endpoints** — list the new
  `GET /api/admin/snowflake/new` endpoint as the canonical way for the
  admin SPA to pre-allocate an id.

### `docs/architecture/quick-reference.md` (if it lists endpoints)

- Add `GET /api/admin/snowflake/new -> { id: string }` under admin endpoints.
- Note that `POST /api/admin/worlds/{world_id}/documents` accepts an
  optional `id` field.

## Observations

- Step 001: New `db.worlds.document_id_exists(doc_id)` helper exists for
  cross-table snowflake-id collision checks across `WorldLocation`, `WorldNPC`,
  and `WorldLoreFact`. Possible impact: mention in `db-models.md` (or
  `quick-reference.md` "DB layer helpers" section) as the canonical place to
  check shared document-id space; future code that needs the same check
  should reuse it rather than re-implementing per-table lookups.
- Step 001: The new admin id endpoint is editor-role gated (matches the
  document-create flow), not admin-role. Possible impact: clarify in
  `backend.md` "admin endpoints" section that some `/api/admin/*` paths are
  editor-accessible (the prefix is admin-namespace, not strict admin-only).
- Step 001: New admin route module registered in `app/main.py` directly,
  consistent with existing pattern (no `routes/admin/__init__.py` aggregator
  exists). Possible impact: if `backend.md` documents the routing pattern,
  re-affirm "one router per file, registered in `main.py`" (vs. the planner's
  hypothetical `__init__.py` aggregator).
- Step 002: `getNewSnowflakeId` was added to `frontend/src/api/admin.ts`
  rather than a sibling `ids.ts` (the step file allowed either). Possible
  impact: in `frontend/src/api/CLAUDE.md`, `admin.ts` is described as
  "admin resources" (currently users-only); update that line to reflect that
  it now also hosts cross-cutting admin endpoints like the snowflake
  pre-allocator.
- Step 002: `DocumentEditPageState`'s `pendingLinkOps` queue ended up
  populated only at save time (from `draft.{allowed,prohibited}Ids`), not
  incrementally as the user toggled the MultiSelects, because the existing
  link UI already deferred all backend calls to save via
  `draft.{allowed,prohibited}Ids` + `syncLinks`. Possible impact: when
  `frontend-forms.md` documents the "queued operations" pattern (per
  outcome.md above), call out that `pendingLinkOps` is a *snapshot* taken
  at save time, not a live event log — the live event log is the draft
  fields themselves. Future drafts with truly live child-resource APIs
  (i.e. ones that call the backend on each toggle) would need a different
  shape.
- Step 002: `isDirty` returns `true` while `isNew` so the Save button is
  visible during draft mode. Possible impact: when `frontend-forms.md`
  describes the "shadow vs edit" / "isNew vs server-snapshot" duality,
  note that `isDirty` should always be true in draft mode — the
  alternative ("only mark dirty on field edits") leaves the user with no
  way to commit an empty-but-valid draft.
