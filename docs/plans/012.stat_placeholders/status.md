# Feature 012 — Stat Placeholders

| Step | File                          | Status  | Verifier | Date |
|------|-------------------------------|---------|----------|------|
| 001  | `001.runtime_helper.md`       | done    | PASS     | 2026-05-06 |
| 002  | `002.context_threading.md`    | pending | —        | —    |
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

## Notes & Issues

### Step 001
- **Snapshot shape choice (open trade-off).** The step file used a placeholder type `dict[tuple[str, str], ChatStat]`, but the codebase has no `ChatStat` model — chat stat values live as JSON dicts on `ChatStateSnapshot.character_stats` / `.world_stats`, and `stat_validation.validate_single_value` already pre-types them as `int | str | list[str]`. Picked the precomputed-map shape (`stat_values: dict[tuple[str, str], int | str | list[str]]`) keyed by `(owner, name)` and kept `stat_definitions: list[WorldStatDefinition]` for kind/declared-order lookup. This matches Feature 010's pattern of carrying small typed values directly on the TypedDict. Architect may want to record this on `quick-reference.md` when finalizing.
- **Set iteration order.** Picked `WorldStatDefinition.enum_values` declared order when parseable (falls back to stored iteration order). Documented in the helper docstring.
- **`TypedDict` switched to `total=False`.** All existing callers still populate the three Feature 010 keys, so runtime is unchanged; the relaxation only allows editor-mode dummies / step-002 wiring to add the new optional fields. The helper now uses `.get(..., "")` for the legacy keys so a missing key resolves to empty string instead of `KeyError` — strictly safer.
