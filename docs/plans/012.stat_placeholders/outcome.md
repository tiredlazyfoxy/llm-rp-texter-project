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
- Step 005: the admin SPA placeholder modules live under `frontend/src/admin/components/placeholders/` (moved by Feature 010 step 002), not the `state/placeholders/` path that step 005's "Files to create or modify" listed. Possible impact: when the architect updates `frontend/CLAUDE.md` or `quick-reference.md`'s Admin SPA section to mention the new stat badges + autocomplete, anchor on `components/placeholders/` so future plans don't re-introduce the path drift.
- Step 005: the project has **no frontend test framework** — no vitest, no jsdom, no `*.test.*` files anywhere under `frontend/src` (Feature 010 also shipped no frontend tests). Step 005 requested unit tests "next to existing Feature 010 tests"; none exist to sit next to, and standing one up was outside the step's file scope. Possible impact: either schedule a follow-up step to bootstrap a frontend test runner, or update `frontend/CLAUDE.md` with an explicit "no frontend tests; verify via `npm run build`" line so future plans stop assuming a runner exists.
- Step 005: the badge panel renders namespaced stats under a "Stats" subgroup separate from the flat Feature 010 row (used the existing `Badge` + `Tooltip` filled-vs-outline visual treatment, just stacked under a small "Stats" `Text c="dimmed"` heading). Possible impact: when documenting the admin authoring surfaces, note the two-row layout (top: runtime placeholders flat, bottom: stats subgroup) so the visual contract is preserved if the panel is reused elsewhere.
- Step 006: drawer refresh strategy is **re-fetch + merge**, not "trust the response." The step-004 endpoint's `UpdateChatStatsResponse.applied` echoes the *requested* values rather than the post-clamp persisted ones (e.g. an int submitted past `max_value` is clamped on persist but echoed verbatim). The drawer therefore calls `getChatDetail` after a successful PUT and merges through the existing `mergeChatDetail` helper so the snapshot reflects the actual stored state. Possible impact: when finalizing `quick-reference.md`'s row for `PUT /api/chats/{chat_id}/stats`, document the response-vs-persisted divergence and recommend the re-fetch pattern for any future admin-write client.
- Step 006: frontend trigger gating is `role === "admin" || role === "editor"` — matches the backend's `require_role(UserRole.editor)` minimum-role gate (admin still passes). Step 006's step file said admin-only; the gate widening was decided during step 004 follow-up. Possible impact: the planner-authored `outcome.md` section above ("trigger gated on `auth.role === 'admin'`") is now stale — when finalizing `frontend.md` / user-SPA notes, write "admin or editor" so future readers don't reintroduce the narrower gate.
- Step 006: drawer mounted under `frontend/src/user/components/chats/` (alongside `ChatSettingsPanel.tsx` / `StatsPanel.tsx`), not at `components/` root. The step file's path used the bare `components/` folder, but only `UserSidebar.tsx` lives there as a layout-shell exception per `frontend/src/user/CLAUDE.md`. Possible impact: when updating `frontend/CLAUDE.md` or the user-SPA architecture notes, list `StatEditorDrawer.tsx` under `components/chats/` so the convention sticks.
