# Outcome — Feature 012 Stat Placeholders

## Intended documentation changes (for the architect)

### `docs/architecture/quick-reference.md`

- **Stat System section** — add a sub-bullet noting that
  `WorldStatDefinition.name` values are usable inside chat-runtime
  prose as `{USER:NAME}` and `{WORLD:NAME}`. Cross-link to the new
  Runtime Placeholders section.
- **Runtime Placeholders section (new)** — document
  `apply_runtime_placeholders` as the single chat-runtime
  substitution helper, list the supported tokens (existing
  Feature 010 set plus the new `{USER:*}` / `{WORLD:*}` namespaced
  pair), and state the render rules:
  - `int` → `str(value)`
  - `enum` → value as-is
  - `set` → comma-space joined
  - missing/unknown name → empty string + DEBUG log
  - hidden stats DO substitute; the `hidden` flag only gates the
    player-facing stats panel
  - editor flows never substitute stat tokens (editor-bound
    contexts carry no stats).
- **API quick-reference table** — add row for
  `PUT /api/chats/{chat_id}/stats` (admin-only). Note that it
  reuses the LLM tool's validation path and emits the same
  `stat_update` SSE event.
- **SSE events table** — note that `stat_update` may also be
  emitted by the admin endpoint, not only the agent's `set_stat`
  tool. (Same payload shape; consumers don't need to distinguish.)

### `docs/architecture/backend.md`

- **Routes / Services / DB layering example** — if a stats-related
  layering example is worth adding, point to
  `routes/chats.py:update_chat_stats` →
  `services/stat_service.validate_and_apply_stat_updates` →
  existing db helper. Otherwise leave untouched.

### `docs/architecture/frontend.md` (or admin SPA / user SPA notes)

- **Admin SPA — DocumentEditPage / WorldFieldEditPage** — note that
  the placeholder badge panel, inline `{PARTIAL` autocomplete, and
  LLM helper system prompt now include the world's
  `WorldStatDefinition` rows as `{USER:NAME}` / `{WORLD:NAME}`
  badges in addition to the runtime placeholders introduced in
  Feature 010.
- **User SPA — ChatViewPage** — document the new admin-only stat
  editor drawer: trigger gated on `auth.role === "admin"`,
  PUT to `/api/chats/{chat_id}/stats`, refreshes via existing
  `stat_update` SSE event handler.

### `docs/architecture/db-models.md`

- No schema changes. No edits required. (Mention only if the
  architect wants to cross-link the new endpoint from the
  `ChatStat` row in the model index.)

## Observations

- Step 002: the `(StatScope -> owner-token)` mapping is centralized in `runtime_placeholders.build_stat_values_map(stat_defs, character_stats, world_stats)` (pure builder, no DB). Every chat-runtime entrypoint (`chat_context.build_chat_context`, `chat_service.create_chat`, `simple_generation_service`, both `chain_generation_service` sites) calls it. Possible impact: add to the new Runtime Placeholders section in `quick-reference.md` so future contributors know not to re-derive owner tokens at new call sites.
- Step 002: `ChatContext` now surfaces `character_stats_raw: dict[str, int|str|list[str]]` and `world_stats_raw: dict[str, int|str|list[str]]` (raw parsed JSON dicts) so downstream chat-runtime sites consume one source instead of re-parsing `ChatSession.character_stats` / `.world_stats`. Possible impact: brief note in `backend.md` under chat context structure (or quick-reference Stat System section).
- Step 002: `chat_agent_service.py` does not actually build a `ToolContext` or `RuntimePlaceholderContext` — it is purely a dispatcher. The step-002 plan and `002.context.md` both list it as a chat-runtime entrypoint requiring the wiring; the planner may want to drop it from that list when finalizing or clarify that the dispatcher itself owns no chat-runtime context.
- Step 003: editor-prompt stat rendering chosen as a bulleted markdown block grouped by owner (matches Feature 010's `{CHARACTER_NAME}` bullets in the same files), with the zero-stats branch **omitting** the section entirely (mirrors how empty `world_description` / `world_lore` are skipped in the same builders). Shared via a new `prompts/stat_placeholders_section.py` helper consumed by both builders. Possible impact: when the architect adds the Runtime Placeholders section to `quick-reference.md`, also note that editor system prompts surface the world's `WorldStatDefinition` names as a literal vocabulary list (and that `prompts/stat_placeholders_section.py` is the single render site).
- Step 003: `routes/llm_chat.py` now loads `stat_defs_db.list_by_world(world_id)` per editor request (one extra small SELECT alongside the existing world / lore-facts loads). All world-scoped editor traffic flows through this single route, so caching is unnecessary; flagged here only so the architect knows to mention it if `backend.md` documents the editor-route load shape.
- Step 004: the admin endpoint **does not emit SSE** (user resolution, option 1 — see `status.md` "Step 004 — Resolution"). The planner-authored sections of this file still mention emitting the same `stat_update` event; the `quick-reference.md` API row and SSE-events note should drop that claim and replace it with: response echoes `applied: list[StatUpdateItem]`, the admin drawer (step 006) refreshes from that response. Possible impact: rewrite the `quick-reference.md` API/SSE rows for `PUT /api/chats/{chat_id}/stats` accordingly when finalizing.
- Step 004: chose to put `apply_admin_stat_updates` in the existing `services/stat_validation.py` (the step file said `services/stat_service.py`, which doesn't exist in this codebase). Co-located with `validate_and_apply_stat_updates` / `validate_single_value` — same module, no new file. Possible impact: minor — the planner-authored `outcome.md` references "stat_service.validate_and_apply_stat_updates" in `backend.md`'s layering example; the architect should rename that to `stat_validation` when finalizing.
- Step 004: the admin endpoint is **all-or-nothing** on validation errors (raises `HTTPException(422)` on the first bad item; the chat row is untouched). The LLM tool path silently skips invalid entries instead. Both paths share `validate_single_value` for per-value checks, but their failure semantics differ on purpose: the LLM tool can't crash a streaming generation, while the admin path should surface errors so the operator can fix and retry. Error body shape (`{status, reason, all_stats}`) is identical so any frontend renderer works for both. Possible impact: worth a sentence in `quick-reference.md`'s new Runtime Placeholders / Stat System section (or wherever the admin endpoint lands) so future contributors don't try to "unify" the failure semantics.
