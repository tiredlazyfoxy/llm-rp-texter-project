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

