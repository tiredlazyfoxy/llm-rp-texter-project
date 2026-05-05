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

---

## Additional doc changes for the scope expansion (steps 004–007)

## `docs/architecture/quick-reference.md`

- Section: "Placeholders" (the entry added by the original feature
  010 changes above) — extend.
- Change: rename / expand the existing entry to "Runtime
  placeholders". Document that the same three uppercase tokens
  (`{CHARACTER_NAME}`, `{LOCATION_NAME}`, `{LOCATION_SUMMARY}`)
  apply not just to `World.initial_message` but also to the
  `content` field of `WorldLocation`, `WorldNPC`, and
  `WorldLoreFact`. Note that they substitute in:
  - `chat_service.py` at chat creation (initial_message)
  - `chat_context.py` (location.content, lore_fact.content, NPC
    briefs)
  - `chat_tools.py` chat-side document-returning tools
    (`get_location_info`, `get_npc_info`, `move_to_location`,
    `get_memory`, plus `_b_search` / `_b_get_lore` bindings).
  Note the **current-location** semantics for non-initial-message
  uses. Reference the central helper module.
- Reason: world authors and admins now have a wider syntax
  surface; the quick-reference is the canonical contract pointer.

## `docs/architecture/backend.md` (or `backend/app/services/CLAUDE.md`)

- Section: services module listing.
- Change: add `runtime_placeholders.py` to the list of service
  modules with a one-line description: "pure helper —
  `apply_runtime_placeholders(text, ctx)` — single substitution
  implementation for chat-runtime placeholder tokens; consumed by
  `chat_service`, `chat_context`, and chat-side wrappers in
  `chat_tools`."
- Reason: a new module in the services layer should be
  discoverable from the architecture doc; the editor-vs-chat
  substitution distinction is non-obvious and worth one sentence.

## `backend/app/services/CLAUDE.md`

- Section: tool-context layering / chat vs admin tools.
- Change: note that `ToolContext` carries an optional
  `runtime_placeholders` context. Chat-bound construction sites
  populate it; editor-bound sites leave it `None`. This is the
  mechanism that keeps `admin_tools.py` raw while making
  `chat_tools.py` substitute. Cross-reference
  `runtime_placeholders.py`.
- Reason: the layering decision (admin_tools raw, chat_tools
  substituted) is the kind of thing a future contributor will
  trip over without an explicit note.

## `frontend/src/admin/CLAUDE.md`

- Section: `components/placeholders/` entry (added by step 002).
- Change: rename the constants-file mention from
  `initialMessagePlaceholders.ts` (`INITIAL_MESSAGE_PLACEHOLDERS`)
  to `runtimePlaceholders.ts` (`RUNTIME_PLACEHOLDERS`). Note that
  the same constant is consumed by both `WorldFieldEditPage`
  (`initial_message` field) and `DocumentEditPage` (`Content`
  field).
- Reason: the per-folder CLAUDE doc is the first stop for the
  next contributor; the rename and the second consumer both need
  to be reflected.

## `docs/architecture/quick-reference.md` — editor-prompt note

- Section: "Prompts" / LLM-assisted editor entries (if such a
  list exists; otherwise a one-liner near the document/world
  editor mention).
- Change: note that both editor system prompts
  (`document_editor_system_prompt.py`,
  `world_field_editor_system_prompt.py` for `initial_message`)
  now teach the AI about the three runtime placeholders and that
  `world_field_editor_system_prompt.py` uses doubled-brace
  escaping because the role string is rendered through `.format`.
- Reason: a future contributor adding a new placeholder or a new
  editor field needs the escaping gotcha documented somewhere
  durable.

## End-to-end behavior note (composition across steps)

- The chat-runtime use of placeholders in document content
  requires steps 004 + 005 to be landed together; step 004 alone
  substitutes in `chat_context` but not in tool-returned content,
  step 005 alone has the tool wiring but no helper. The
  document-editor frontend (step 007) is independently
  build-clean but its user-visible benefit (write
  `{CHARACTER_NAME}` in a document, see substitution in chat)
  requires 004 + 005 to ship as well. The editor-prompt step
  (006) is independently shippable but its training signal only
  pays off once 004 + 005 are live.
- Possible impact: mention the composition in the release /
  changelog note alongside the original 001 + 003 composition.
