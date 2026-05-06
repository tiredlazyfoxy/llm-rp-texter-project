# Feature 012 — Stat Placeholders

| Step | File                          | Status  | Verifier | Date |
|------|-------------------------------|---------|----------|------|
| 001  | `001.runtime_helper.md`       | done    | PASS     | 2026-05-06 |
| 002  | `002.context_threading.md`    | done    | PASS     | 2026-05-06 |
| 003  | `003.editor_prompts.md`       | pending | —        | —    |
| 004  | `004.admin_stats_endpoint.md` | pending | —        | —    |
| 005  | `005.frontend_authoring.md`   | pending | —        | —    |
| 006  | `006.admin_drawer.md`         | pending | —        | —    |

## Files Changed

### Step 001 — runtime helper learns `{USER:NAME}` / `{WORLD:NAME}`
- `backend/app/services/runtime_placeholders.py` — widened `RuntimePlaceholderContext` (now `total=False`) with `stat_definitions` + `stat_values` fields; added namespaced-stat regex pass with int/enum/set render rules and debug-log fallback for missing entries.
- `backend/app/services/prompts/prompt_injection.py` — added defensive comment near `\{([A-Z_]+)\}` regex warning future maintainers not to widen it to match `:` (would collide with namespaced runtime tokens).
- `backend/tests/services/test_runtime_placeholders.py` — added stat-placeholder cases (int/enum/set/hidden/unknown name/unknown owner/lowercase/missing snapshots/None snapshots/coexistence with feature 010 tokens/owner-vs-scope routing).
- `backend/tests/services/prompts/test_prompt_injection.py` — new regression test asserting `resolve_prompt_template` does not consume `{USER:HEALTH}` / `{WORLD:WEATHER}`.

### Step 002 — thread stat snapshots through chat-runtime contexts
- `backend/app/services/runtime_placeholders.py` — added pure builder `build_stat_values_map(stat_defs, character_stats, world_stats)` centralizing the `(StatScope -> owner-token)` mapping shared by every chat-runtime entrypoint.
- `backend/app/services/chat_context.py` — extended `ChatContext` with `character_stats_raw` / `world_stats_raw` (raw parsed dicts) so downstream sites consume one source; `build_chat_context` now loads stat defs / parses stat dicts up-front and attaches `stat_definitions` + `stat_values` to its `runtime_ctx` for NPC-brief / lore-fact / location-content substitution.
- `backend/app/services/chat_service.py` — initial-message branch now attaches the seeded chat's stat snapshot to its `RuntimePlaceholderContext` so `{USER:NAME}` / `{WORLD:NAME}` resolve in `world.initial_message`.
- `backend/app/services/simple_generation_service.py` — `ToolContext` builder now reads `context["stat_defs_list"]` + the new raw dicts and threads them through `runtime_placeholders`.
- `backend/app/services/chain_generation_service.py` — both tool-stage and writer-stage `ToolContext` builders now thread the stat snapshot via `runtime_placeholders` (using the locally-scoped `char_stats` / `world_stats` parameters for live values).
- `backend/tests/services/test_runtime_placeholders.py` — added four cases for the new `build_stat_values_map` builder (scope routing, missing-def drop, scope-mismatch drop, int/enum/set/hidden coverage).
- `backend/tests/services/test_chat_context.py` — added end-to-end cases asserting `ChatContext` exposes the raw stat dicts, that `{USER:HEALTH}` / `{WORLD:WEATHER}` substitute inside location content via the chat-runtime builder, and that the editor analogue (None ctx) leaves namespaced tokens literal.
- `backend/tests/services/test_chat_service.py` — added end-to-end case asserting `create_chat` substitutes `{USER:HEALTH}` / `{WORLD:WEATHER}` in the seeded initial system message using the stats seeded from `WorldStatDefinition.default_value`.

## Notes & Issues

### Step 001
- **Snapshot shape choice (open trade-off).** The step file used a placeholder type `dict[tuple[str, str], ChatStat]`, but the codebase has no `ChatStat` model — chat stat values live as JSON dicts on `ChatStateSnapshot.character_stats` / `.world_stats`, and `stat_validation.validate_single_value` already pre-types them as `int | str | list[str]`. Picked the precomputed-map shape (`stat_values: dict[tuple[str, str], int | str | list[str]]`) keyed by `(owner, name)` and kept `stat_definitions: list[WorldStatDefinition]` for kind/declared-order lookup. This matches Feature 010's pattern of carrying small typed values directly on the TypedDict. Architect may want to record this on `quick-reference.md` when finalizing.
- **Set iteration order.** Picked `WorldStatDefinition.enum_values` declared order when parseable (falls back to stored iteration order). Documented in the helper docstring.
- **`TypedDict` switched to `total=False`.** All existing callers still populate the three Feature 010 keys, so runtime is unchanged; the relaxation only allows editor-mode dummies / step-002 wiring to add the new optional fields. The helper now uses `.get(..., "")` for the legacy keys so a missing key resolves to empty string instead of `KeyError` — strictly safer.

### Step 002
- **Helper shape choice (open trade-off).** The step file suggested `services/stat_service.py::load_chat_stat_snapshot(chat_id) -> tuple[list[WorldStatDefinition], dict[(owner,name), value]]`, but `chat_context.build_chat_context` and the four generation services already load `stat_defs` + raw stat dicts in scope (the chain-generation tool stage even pre-parses them as locals). A chat-id-only signature would force a re-load at every site. Chose a pure builder `runtime_placeholders.build_stat_values_map(stat_defs, character_stats, world_stats)` instead — same centralization benefit, no DB hit, every call site stays one composition step. Architect may want to record this on `quick-reference.md`.
- **`ChatContext` widened with raw dicts.** Surfaced `character_stats_raw` / `world_stats_raw` on `ChatContext` so `simple_generation_service` and `chain_generation_service` (writer stage) consume one source instead of re-parsing JSON off `ChatSession`. The chain-tool stage and `chat_service.create_chat` already had the raw dicts in local scope, so they pass them directly without going through `ChatContext`.
- **`chat_agent_service.py` does NOT build a runtime ctx or `ToolContext`.** The step file lists it (and the harvested context flagged "locate its `ToolContext` builder"), but inspection shows the file is purely a dispatcher (`generate_response`, `regenerate_response`, `_resolve_pipeline`) that hands work to `simple_generation_service` / `chain_generation_service` — no chat-runtime context construction lives there. Treated as no-op for this step (not the escape valve, since the listed surface is missing rather than extra). Architect may want to drop it from `context.md`'s chat-runtime list.
- **`admin_tools.py` and `summarization_service.py` confirmed unchanged via `git diff` — no stat data leaks into editor/summarization flows.**
