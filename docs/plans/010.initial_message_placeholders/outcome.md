# Feature 010 — Outcome

After this feature ships, the architect updates the following
docs:

## `docs/architecture/quick-reference.md`

- Section: "Placeholders" / "Templates" (or wherever runtime
  template tokens are listed; if no such section exists, add a
  short "World initial message placeholders" entry near the
  chat / world model summary).
- Change: document the three uppercase placeholders
  (`{CHARACTER_NAME}`, `{LOCATION_NAME}`, `{LOCATION_SUMMARY}`)
  available in `World.initial_message`, and note that they are
  substituted in `chat_service.py` at chat start.
- Reason: the runtime token surface is a public contract for
  world authors and admins.

## `docs/architecture/frontend-components.md`

- Section: "Reusable stateful UI components (no custom hooks)"
  → "Imperative API escape valve" paragraph.
- Change: extend the worked example to mention that
  `PlaceholderTextarea` is now reused across the pipeline stage
  editor and the world initial-message editor (i.e. it has
  graduated from a one-page utility to a shared admin
  component). One sentence is enough.
- Reason: the doc currently lists the controller-ref pattern
  with `PlaceholderTextarea` as the canonical example; reflecting
  its expanded reuse keeps the example honest.

## `docs/architecture/frontend-layout.md`

- Section: per-SPA structure / admin folder example (the
  `admin/components/` block).
- Change: add `placeholders/` alongside `pipelines/`, `worlds/`,
  `users/`, `llm/` in the example tree.
- Reason: the canonical admin folder list now has a new entry.

## `frontend/src/admin/CLAUDE.md`

- Section: `components/` subtree listing.
- Change: add a new `components/placeholders/` entry describing
  the moved trio + `placeholderAutocompleteState.ts`, and trim
  the `components/pipelines/` entry to remove its now-stale
  placeholder paragraph.
- Reason: per-folder CLAUDE docs are the authoritative pointer
  for component placement; this is the file the planner /
  coder reaches for first.

## `backend/app/services/CLAUDE.md` (if it lists placeholder tokens)

- Change: update any list of `initial_message` placeholders to
  the uppercase form.
- Reason: keep services-doc consistent with `chat_service.py`.

## Observations

- Step 003: end-to-end behaviour (insert `{CHARACTER_NAME}` in the editor, save, start chat, see substitution) only works when both Step 001 (backend uppercase substitution) and Step 003 (frontend UI) are landed; neither is a build-time dependency of the other but they form one user-visible feature. Possible impact: mention this composition in any release/changelog note for feature 010.

