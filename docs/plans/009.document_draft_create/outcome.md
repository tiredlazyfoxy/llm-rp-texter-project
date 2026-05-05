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
