# Feature 010 — Initial Message Placeholders

## Goal

Bring the same placeholder UX that the pipeline stage editor offers
(panel of clickable badges + inline `{PARTIAL` autocomplete) to the
world's `initial_message` field in `WorldFieldEditPage`. Normalize
the runtime placeholder tokens to UPPERCASE everywhere
(`{CHARACTER_NAME}`, `{LOCATION_NAME}`, `{LOCATION_SUMMARY}`),
including a one-time data migration of existing worlds.

## Resolved decisions (from orchestrator briefing)

1. **Reuse strategy** — move the existing pipeline placeholder
   components to a shared admin folder and reuse them on
   `WorldFieldEditPage`. Identical UX to the pipeline editor.
2. **Source of placeholder list** — hard-coded constants on the
   frontend; no new backend endpoint.
3. **Casing** — uppercase everywhere. Lowercase tokens in existing
   worlds are migrated.
4. **Scope** — `initial_message` only. The `description` field on
   `WorldFieldEditPage` keeps its plain `<Textarea>`.

## Placeholders exposed in the new UI

| Token                  | Replacement (runtime)                              | Category |
|------------------------|----------------------------------------------------|----------|
| `{CHARACTER_NAME}`     | Chat session character name                        | Character |
| `{LOCATION_NAME}`      | Starting location name                             | Location  |
| `{LOCATION_SUMMARY}`   | Starting location content / summary                | Location  |

(Categories mirror the pipeline registry's `category` field on
`PlaceholderInfo`. We reuse `PlaceholderInfo` directly — no
duplicate type.)

## Files involved across multiple steps

### Frontend
- `frontend/src/admin/components/pipelines/PlaceholderTextarea.tsx`
  — to be moved (steps 002, 003).
- `frontend/src/admin/components/pipelines/PlaceholderPanel.tsx`
  — to be moved (steps 002, 003).
- `frontend/src/admin/components/pipelines/PlaceholderSuggestions.tsx`
  — to be moved (step 002).
- `frontend/src/admin/components/pipelines/placeholderAutocompleteState.ts`
  — to be moved (step 002). The `getPartial` regex `/^[A-Z_]*$/`
  (~line 85) already matches the uppercase convention; no logic
  change needed.
- `frontend/src/admin/pages/PipelineStageEditPage.tsx`
  — imports updated after the move (step 002).
- `frontend/src/admin/pages/WorldFieldEditPage.tsx`
  — gains placeholder UI for `initial_message` (step 003).
- `frontend/src/admin/pages/worldFieldEditPageState.ts`
  — referenced (read-only) for `WorldFieldName` (step 003).
- `frontend/src/types/pipeline.d.ts`
  — defines `PlaceholderInfo`, reused as-is.

### Backend
- `backend/app/services/chat_service.py`
  — runtime substitution at lines 425-432 (step 001).
- `backend/app/services/prompts/world_field_editor_system_prompt.py`
  — placeholder list in docstring at lines ~43-47 (step 001).
- World JSONL importer (location to be confirmed by coder when
  reading the harvested codebase — see `001.context.md`)
  — decision on import-path normalization (step 001).
- One-time idempotent migration in the DB init path (step 001).

## Cross-cutting constraints

- **Frontend folder convention** (see
  `docs/architecture/frontend-layout.md` Rule 4 and
  `frontend/src/admin/CLAUDE.md`): page-aware components live under
  `components/<domain>/`. The placeholder components are admin-only
  and shared between two domains (pipelines, worlds), so the right
  home is a new domain folder `frontend/src/admin/components/placeholders/`.
- **Layer separation** (see `backend/CLAUDE.md`): the migration
  must touch DB rows through the `db/` layer. No `session` /
  `select()` outside `db/`.
- **JSONL import/export rule** (see project `CLAUDE.md`): a
  data-content change does not change the export shape, but the
  importer should not re-introduce lowercase tokens from old
  backups (see "Open trade-off" below).
- **Strict typing** — no `any` on the frontend, Pydantic /
  TypedDict on the backend.
- **`observer` everywhere** — every new/modified component stays
  wrapped in `observer`.

## Open trade-off — JSONL import behavior

Two acceptable choices for handling old (lowercase-token) backups
on re-import:

A. Apply the same uppercase substitution at the importer for
   `World.initial_message`. Pro: re-importing a pre-migration
   backup yields a normalized DB. Con: a small amount of import-
   path code that "knows" about a one-time migration.

B. Leave the importer untouched and rely solely on the startup
   migration to normalize after import (since the migration is
   idempotent and runs on every boot, an old backup imported into
   a running system would be normalized on the next start).

Plan picks **A** — apply the substitution at both the import path
and the startup migration. Reason: the importer is the only path
that can introduce stale tokens after the migration has already
run (e.g. an admin importing an old backup mid-session would
otherwise see lowercase tokens until the next process restart).
The substitution is a 3-line change reused from a shared helper,
so the cost is negligible.

## References

- `docs/plans/CLAUDE.md` — plan layout and lifecycle.
- `docs/architecture/frontend-components.md` — generic vs page-
  aware components, `controllerRef` pattern (see "Imperative API
  escape valve").
- `docs/architecture/frontend-layout.md` — Rule 4 (folder
  convention for components).
- `frontend/src/admin/CLAUDE.md` — current admin component
  layout, including `PlaceholderTextareaController` shape.
- `backend/CLAUDE.md` — layer separation, JSONL import/export
  policy.

## Vocabulary

- **Placeholder token** — the literal `{CHARACTER_NAME}` text
  inside an `initial_message` value.
- **Placeholder info** — the `PlaceholderInfo` DTO
  (`{ name, description, category }`) consumed by
  `PlaceholderPanel` / `PlaceholderTextarea`.
- **Placeholders folder** — the new shared admin folder
  `frontend/src/admin/components/placeholders/` introduced by
  step 002.

---

## Scope expansion (steps 004–007)

Steps 001–003 shipped the placeholder UX for `initial_message` and
the uppercase migration. The expansion takes the same three tokens
and applies them to **document content** (locations, NPCs, lore
facts) — substituted at chat runtime, written by both human admins
and the LLM-assisted document editor.

### New surfaces

**Backend runtime substitution sites** (apply substitution before
the text reaches the player):

- `chat_service.py` lines 426-432 — already substitutes
  `initial_message` at chat creation. Refactor to call the new
  helper instead of inline `.replace()`. (Step 004.)
- `chat_context.py` `build_chat_context(session)`:
  - `location.content` (line 69)
  - injected `WorldLoreFact.content` (line 92)
  - NPC briefs inside `_format_npcs_at_location` (lines 146-160)
  (Step 004.)
- `chat_tools.py` chat-side tool wrappers and bindings:
  `get_location_info_impl` (line 118), `get_npc_info_impl` (line
  171), `move_to_location_impl` (line 236), `get_memory_impl`
  (line 210), and the `_b_search` / `_b_get_lore` bindings
  (lines 351-363) that delegate to `admin_tools.py`. (Step 005.)

**Backend editor-prompt awareness** (teach the AI the syntax):

- `prompts/document_editor_system_prompt.py`
  `build_document_editor_system(...)` line 46 — gains a
  "## Runtime Placeholders" section. (Step 006.)
- `prompts/world_field_editor_system_prompt.py`
  `_FIELD_ROLES["initial_message"]` lines 43-47 — one-liner
  expanded to a coherent multi-line block matching the doc-editor
  one (with doubled-brace escaping for the `.format()` at line
  146). (Step 006.)

**Frontend reuse** (extend the placeholder UX to documents):

- `frontend/src/admin/pages/DocumentEditPage.tsx` Content field
  (lines 214-223) — replace `<Textarea>` with
  `<PlaceholderTextarea>` + `<PlaceholderPanel>`. (Step 007.)
- `frontend/src/admin/components/placeholders/initialMessagePlaceholders.ts`
  → renamed to `runtimePlaceholders.ts` with export
  `RUNTIME_PLACEHOLDERS`; one constants file shared by both pages.
  (Step 007.)
- `frontend/src/admin/pages/WorldFieldEditPage.tsx` — import path
  and name updated; behavior unchanged. (Step 007.)

### New decisions (orchestrator-confirmed)

1. **Same placeholder set for documents and `initial_message`** —
   the trio `{CHARACTER_NAME}` / `{LOCATION_NAME}` /
   `{LOCATION_SUMMARY}`. No per-doc-type variation.
2. **Current-location semantics for documents** — when document
   content references `{LOCATION_NAME}` or `{LOCATION_SUMMARY}`,
   the placeholder resolves to the player's **current** location
   at the time of substitution, not the starting location. For
   `chat_service.py` at chat creation, current == starting, so the
   existing behavior is preserved.
3. **No data migration for documents** — documents never used the
   syntax before this feature; there is nothing to rewrite. The
   importer is also unchanged for `WorldLocation.content`,
   `WorldNPC.content`, `WorldLoreFact.content`. (Contrast with
   step 001's migration of `World.initial_message`.)
4. **Substitution lives only in chat-runtime code paths.**
   Editor-mode tool calls (e.g. inside the document-editor's own
   LLM chat) leave content **raw**, so the AI editor sees literal
   `{CHARACTER_NAME}` and learns the syntax. The substitution
   happens in chat-side wrappers in `chat_tools.py`, never inside
   `admin_tools.py` itself.
5. **Helper centralization** — one new module
   `backend/app/services/runtime_placeholders.py` with
   `RuntimePlaceholderContext` (TypedDict) and pure
   `apply_runtime_placeholders(text, ctx)`. Every substitution
   site calls it; no other module re-implements the `.replace()`
   logic. The existing `chat_service.py` block is refactored to
   use it.
6. **Threading the context** — `chat_context.py` builds the
   `RuntimePlaceholderContext` once at the top of
   `build_chat_context` from session character + current location
   and reuses it for all three substitution sites. `ToolContext`
   in `chat_tools.py` gains an optional
   `runtime_placeholders: RuntimePlaceholderContext | None` field;
   chat-bound `ToolContext` construction sites populate it,
   editor-bound sites leave it as `None`.
7. **Frontend constants reuse** — the constants file is renamed
   to `runtimePlaceholders.ts` and the exported constant to
   `RUNTIME_PLACEHOLDERS`. One source of truth for both pages.

### Editor-vs-chat substitution distinction (central concept)

The substitution distinction is the load-bearing decision of this
expansion:

- **Chat runtime** (chat_service, chat_context, chat_tools): the
  player must never see a literal `{CHARACTER_NAME}`. Substitute
  before the text leaves the backend toward the player.
- **Editor mode** (document-editor LLM chat, world-field-editor
  LLM chat, admin_tools.py): the AI must see the **literal**
  token so it learns to emit them in the content it writes.
  `admin_tools.py` is therefore unchanged; chat-side bindings
  that delegate to `admin_tools` wrap the **return value** with
  the helper.

### Files (expanded scope)

#### Backend (steps 004–006)
- `backend/app/services/runtime_placeholders.py` — new (step 004).
- `backend/app/services/chat_service.py` — refactor lines 426-432
  (step 004).
- `backend/app/services/chat_context.py` — three substitution
  sites + thread context (step 004).
- `backend/app/services/chat_tools.py` — `ToolContext` field +
  substitution in 4 impls + 2 bindings (step 005).
- Whatever services build chat-bound `ToolContext` (likely
  `chat_agent_service.py`, `simple_generation_service.py`,
  `chain_generation_service.py`) — populate the new field
  (step 005).
- `backend/app/services/admin_tools.py` — **unchanged** (step
  005, by design).
- `backend/app/services/prompts/document_editor_system_prompt.py`
  — placeholders section (step 006).
- `backend/app/services/prompts/world_field_editor_system_prompt.py`
  — expanded `initial_message` role with doubled-brace escaping
  (step 006).

#### Frontend (step 007)
- `frontend/src/admin/components/placeholders/runtimePlaceholders.ts`
  — renamed from `initialMessagePlaceholders.ts`, export renamed
  to `RUNTIME_PLACEHOLDERS`.
- `frontend/src/admin/pages/WorldFieldEditPage.tsx` — import
  update only.
- `frontend/src/admin/pages/DocumentEditPage.tsx` — replace
  `<Textarea>` with `<PlaceholderTextarea>` + `<PlaceholderPanel>`
  for the Content field; `<LlmChatPanel>` and `Name` field
  unchanged.

### Trade-off — current vs starting location for documents

Documents could resolve `{LOCATION_NAME}` to either the **current**
or the **starting** location.

- **Starting** matches `chat_service.py`'s existing initial_message
  behavior verbatim and is simpler to thread (the starting
  location is loaded once at chat creation).
- **Current** is semantically correct: a player reading a lore
  fact about "the city of {LOCATION_NAME}" while standing in
  another city should see the city they are in, not the one they
  started in. This is also consistent with how an admin would
  intuitively write document content using the placeholder.

**Decision: current.** The cost is small — `chat_context.py`
already loads the current location for its other purposes, and
`chat_tools.py` ToolContext already has access to the session.
The user-facing semantics are correct. For `chat_service.py` at
chat creation, current == starting, so no behavioral regression.

### Vocabulary additions

- **Runtime placeholder context** — the
  `RuntimePlaceholderContext` TypedDict carrying the three
  substitution values (character_name, location_name,
  location_summary). Built once per chat-runtime entrypoint.
- **`apply_runtime_placeholders`** — the single, pure
  substitution helper in
  `backend/app/services/runtime_placeholders.py`. Accepts a
  nullable context; returns the input unchanged when context is
  `None` (editor mode).
- **Editor mode** vs **chat runtime** — see the distinction
  above. Editor mode = ToolContext.runtime_placeholders is None
  (or admin_tools called directly); chat runtime = ToolContext
  carries a populated context.
- **Runtime placeholders** (frontend) — the renamed constants
  file/constant; the broader name reflects that the trio is
  shared across all places that substitute at chat time.
