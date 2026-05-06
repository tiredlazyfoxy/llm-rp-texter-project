# Feature 012 — Stat Placeholders (`{USER:NAME}` / `{WORLD:NAME}`)

## Goal

Allow author-facing prose (chat field templates, initial messages,
prompt templates) to embed live stat values via `{USER:NAME}` and
`{WORLD:NAME}` placeholders, resolved at chat runtime against the
current chat's `ChatStat` rows. Add an admin-only chat stats editor
drawer so admins can correct stat state during play. Authoring
surfaces (DocumentEditPage, WorldFieldEditPage) gain badge +
autocomplete + LLM helper coverage for the world's stat names.

## Scope and decisions (locked)

1. **Token syntax — namespaced only:** `{USER:NAME}` and
   `{WORLD:NAME}`. No `{STAT:...}` alias. `NAME` matches
   `WorldStatDefinition.name` (uppercase, case-sensitive).
2. **Render rules:**
   - `int` → `str(value)`
   - `enum` → value as-is (string)
   - `set` → comma-space joined (`", ".join(sorted_or_iter)`; see step
     001 for exact iteration order)
   - missing/unknown name → empty string + DEBUG log; never raises.
3. **Hidden flag does NOT gate substitution.** `WorldStatDefinition.hidden`
   only hides the player-facing stats panel; placeholders still
   resolve so authors can use hidden stats in prose.
4. **Resolver scope is chat runtime only.** The new regex pass lives
   in `apply_runtime_placeholders` (the helper used by chat-runtime
   prompts and rendered messages). The prompt-template resolver
   `prompt_injection.resolve_prompt_template` keeps its
   `\{([A-Z_]+)\}` regex unchanged — no collision because that regex
   does not match a `:`.
5. **Editor mode preserved.** `admin_tools.py` and editor-bound
   `ToolContext` carry no stats. Document/world-field editor LLMs
   see the literal `{USER:HEALTH}` text so they learn the syntax,
   never a substituted value.
6. **Admin-only chat stats drawer.** Trigger and drawer in
   `ChatViewPage` are gated on `auth.role === "admin"`. Regular
   players never see them.
7. **New admin endpoint** `PUT /api/chats/{chat_id}/stats` reuses
   the existing `validate_and_apply_stat_updates` service helper and
   emits the same `stat_update` SSE event the LLM tool path emits.
8. **No DB schema change. No JSONL importer change. No data
   migration.** All knowledge about stats is already on
   `WorldStatDefinition` + `ChatStat`.

## Editor-vs-chat boundary (extended to stats)

This feature continues the boundary established by Feature 010
(`docs/plans/010.initial_message_placeholders/context.md`):

- **Chat runtime** = code paths reached from `chat_service` /
  `chat_agent_service` / `simple_generation_service` /
  `chain_generation_service` / `chat_context._build_runtime_ctx`. These
  threads have a `Chat` and (for our purposes) the world's stat
  definitions and the chat's current stat values. They MAY substitute
  `{USER:*}` / `{WORLD:*}`.
- **Editor runtime** = `admin_tools.py`, document/world-field editor
  agent flows. They see prose with placeholders unresolved and must
  preserve them verbatim. The editor-bound `ToolContext` does not
  receive stat data; the existing dummy `RuntimePlaceholderContext`
  used by editors gets the new stat fields populated as `None` /
  empty.

## Vocabulary

- **Stat definition** — `WorldStatDefinition` row on the active
  world (`name`, `kind`, `hidden`, allowed values for enums/sets,
  default).
- **Stat value** — `ChatStat` row on the chat, keyed by
  `(chat_id, stat_name)`. Per-chat live state.
- **Owner** — `"user"` or `"world"`; namespace prefix in the token.
- **Runtime placeholder context** — `RuntimePlaceholderContext`
  TypedDict already exists from Feature 010; we widen it.
- **Stat update SSE event** — existing event name `stat_update`
  emitted by the agent's `set_stat` tool path. Admin endpoint must
  reuse the same event so the user SPA's existing handler refreshes
  without changes.

## Files involved (across multiple steps)

Backend:

- `backend/app/services/runtime_placeholders.py` — helper extended
  in step 001, consumed by step 002.
- `backend/app/services/chat_context.py` — `_build_runtime_ctx`
  populates the new fields (step 002).
- `backend/app/services/chat_service.py` — initial-message branch
  builds runtime ctx (step 002).
- `backend/app/services/chat_agent_service.py` — chat-bound
  `ToolContext` builder (step 002).
- `backend/app/services/simple_generation_service.py` and
  `backend/app/services/chain_generation_service.py` — chat-bound
  `ToolContext` builders (step 002).
- `backend/app/services/admin_tools.py` — confirmed unchanged.
- `backend/app/services/document_editor_system_prompt.py` and
  `backend/app/services/world_field_editor_system_prompt.py` —
  step 003 adds stat-name listing.
- `backend/app/services/stat_service.py` — already exposes
  `validate_and_apply_stat_updates`; reused by step 004.
- `backend/app/routes/chats.py` — step 004 adds new admin route.
- `backend/app/services/sse_events.py` (or wherever `stat_update`
  is emitted) — reused unchanged by step 004.

Frontend:

- `frontend/src/admin/state/placeholderAutocompleteState.ts` —
  step 005 widens regex.
- `frontend/src/admin/components/PlaceholderBadgePanel.tsx` (and
  `buildStatPlaceholders` helper) — step 005.
- `frontend/src/admin/pages/DocumentEditPage.tsx` and
  `frontend/src/admin/pages/WorldFieldEditPage.tsx` — step 005.
- `frontend/src/user/pages/ChatViewPage.tsx` — step 006 mounts
  admin-only drawer.
- `frontend/src/user/state/chatPageState.ts` — step 006 wires
  drawer state and submit.
- `frontend/src/user/api/chats.ts` (and `chats.d.ts`) — step 006
  adds typed `updateChatStats`.

## External references

- `docs/plans/010.initial_message_placeholders/context.md` — prior
  feature establishing `RuntimePlaceholderContext`,
  `apply_runtime_placeholders`, the editor-vs-chat boundary, and the
  authoring surfaces (badge panel, autocomplete, helper prompt) we
  extend here.
- `docs/architecture/quick-reference.md` — Stat System section
  (existing) and Runtime Placeholders section (to be added per
  `outcome.md`).
- `docs/architecture/backend.md` — Layer separation rules; the new
  endpoint must keep DB queries in `db/`, business logic in
  `services/`, HTTP in `routes/`.

## Cross-cutting constraints

- **Layer separation:** the admin endpoint must call
  `stat_service.validate_and_apply_stat_updates` (or its existing
  caller) — no direct `ChatStat` queries in routes. SSE emit must
  go through the existing helper used by the LLM tool path.
- **Strict typing:** new request/response models are Pydantic
  `BaseModel`s; frontend gets matching `.d.ts`. No free dicts on
  backend, no `any` on frontend.
- **No untyped data passing:** the `RuntimePlaceholderContext`
  widening keeps it a `TypedDict`; new fields are precisely typed.
- **Auth:** new endpoint enforces admin role via existing
  dependency; frontend drawer gating is UI sugar only — backend
  must reject non-admin even if UI is bypassed.
- **JSONL coverage:** no model changes, so importer/exporter is
  not touched. If any step finds it must change a model, stop and
  hand back to the orchestrator.
- **Editor-bound tools must not learn stat values.** Step 002's
  changes are confined to chat-runtime code paths. Editor flows
  continue to receive a stat-less context.

## Open trade-offs (left for the coder; documented to surface choice)

These were raised during planning and intentionally not pinned to a
single answer. The coder should pick the path that fits the
existing code, document the choice in step status notes, and the
architect can revise in `outcome.md` if needed.

- **Stat-def snapshot shape on `RuntimePlaceholderContext`:**
  whether to attach the full `list[WorldStatDefinition]` (richer,
  enables future render rules) or a precomputed
  `dict[tuple[owner, name], WorldStatDefinition]` keyed for O(1)
  lookup. Step 001 specifies the field; the coder picks the shape
  consistent with how Feature 010 attached its snapshots.
- **Editor prompt list rendering (step 003):** whether to render
  the world's stat names inline as a comma-separated list, or as a
  bulleted block grouped by owner. Both keep the literal
  `{USER:NAME}` syntax visible. Pick the form already used for
  document/world-field placeholder lists in Feature 010's helpers.
- **`{USER:NAME}` collision guardrail:** there is no real
  collision (the prompt-template regex doesn't match `:`), but a
  defensive comment in `prompt_injection.py` next to the regex is
  worth adding so future maintainers don't widen it without
  considering namespaced tokens. Step 001 includes this comment.
- **`db/chats.update_stats` reuse vs new function:** step 004 must
  decide whether to call an existing `db/chats.py` helper used by
  the LLM tool path, or add a thin wrapper. The contract is "no DB
  queries in services or routes" — so whatever
  `validate_and_apply_stat_updates` calls today is correct; the
  admin endpoint follows the same path.

## Out of scope

- Player-visible chat stats editor (admin only).
- New stat kinds (only int / enum / set; rendering for any other
  kind logs DEBUG and yields empty string).
- Editing stat *definitions* from the chat drawer — the drawer
  edits `ChatStat` values, not `WorldStatDefinition`.
- Re-rendering historical messages: substitution happens at message
  build time; existing stored messages are not retroactively
  updated.
