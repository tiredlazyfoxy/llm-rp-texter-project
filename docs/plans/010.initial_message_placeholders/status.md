# Feature 010 — initial_message_placeholders

| Step | File                                                | Status  | Verifier | Date |
|------|-----------------------------------------------------|---------|----------|------|
| 001  | `001.backend_uppercase_and_migration.md`            | done    | PASS     | 2026-05-05 |
| 002  | `002.move_placeholder_components.md`                | done    | PASS     | 2026-05-05 |
| 003  | `003.wire_into_world_field_edit.md`                 | done    | PASS     | 2026-05-05 |
| 004  | `004.backend_runtime_substitution_helper.md`        | done    | PASS     | 2026-05-05 |
| 005  | `005.backend_chat_tools_substitution.md`            | done    | PASS     | 2026-05-05 |
| 006  | `006.backend_editor_prompt_placeholders.md`         | done    | PASS     | 2026-05-05 |
| 007  | `007.frontend_wire_document_editor.md`              | done    | PASS     | 2026-05-05 |

## Files Changed

### Step 001 — Backend: uppercase placeholders + migration
- `backend/app/services/chat_service.py` — runtime substitution uses uppercase `{CHARACTER_NAME}` / `{LOCATION_NAME}` / `{LOCATION_SUMMARY}` only (lines 425-432).
- `backend/app/services/prompts/world_field_editor_system_prompt.py` — initial_message role docstring lists the three uppercase placeholders.
- `backend/app/db/worlds.py` — adds `INITIAL_MESSAGE_TOKEN_REWRITES`, pure `rewrite_initial_message_tokens()` helper, and idempotent `normalize_initial_message_placeholders()` migration.
- `backend/app/main.py` — lifespan calls `worlds_db.normalize_initial_message_placeholders()` once after engine init when DB is ready.
- `backend/app/services/db_import_export.py` — `_dict_to_world` runs imported `initial_message` through `rewrite_initial_message_tokens` before constructing the row.
- `backend/tests/db/__init__.py` — package marker for the new test folder.
- `backend/tests/db/test_initial_message_migration.py` — covers lowercase/uppercase/mixed rewrite, idempotency, and the pure helper.
- `backend/tests/services/test_chat_service.py` — asserts uppercase substitution at chat start and that lowercase tokens are not recognized at runtime.

### Step 002 — Frontend: move placeholder components to shared folder
- `frontend/src/admin/components/placeholders/PlaceholderTextarea.tsx` — moved (git mv) from `components/pipelines/`; contents identical.
- `frontend/src/admin/components/placeholders/PlaceholderPanel.tsx` — moved (git mv) from `components/pipelines/`; contents identical.
- `frontend/src/admin/components/placeholders/PlaceholderSuggestions.tsx` — moved (git mv) from `components/pipelines/`; contents identical.
- `frontend/src/admin/components/placeholders/placeholderAutocompleteState.ts` — moved (git mv) from `components/pipelines/`; contents identical.
- `frontend/src/admin/pages/PipelineStageEditPage.tsx` — `PlaceholderPanel` and `PlaceholderTextarea` imports rewritten to `../components/placeholders/`.
- `frontend/src/admin/CLAUDE.md` — `components/pipelines/` entry replaced with `components/placeholders/`, noting it is shared between pipeline-stage and world-field editors.

### Step 003 — Frontend: wire placeholder UI into WorldFieldEditPage
- `frontend/src/admin/components/placeholders/initialMessagePlaceholders.ts` — new constants module exporting `INITIAL_MESSAGE_PLACEHOLDERS` (CHARACTER_NAME / LOCATION_NAME / LOCATION_SUMMARY, unbraced).
- `frontend/src/admin/pages/WorldFieldEditPage.tsx` — adds `controllerRef`, branches on `state.fieldName === "initial_message"` to render `<PlaceholderTextarea>` + `<PlaceholderPanel>`; `description` keeps the plain `<Textarea>`. Page remains wrapped in `observer`.

### Step 004 — Backend: runtime placeholder helper + chat_context substitution
- `backend/app/services/runtime_placeholders.py` — new pure helper: `RuntimePlaceholderContext` TypedDict + `apply_runtime_placeholders(text, ctx)`; nullable ctx returns text unchanged (editor-mode contract); uppercase-only token contract.
- `backend/app/services/chat_service.py` — `create_chat` now imports the helper, builds a local `RuntimePlaceholderContext` from the freshly-resolved character + starting location, and replaces the inline `.replace()` chain with a single `apply_runtime_placeholders(...)` call (behavior preserved).
- `backend/app/services/chat_context.py` — `build_chat_context` builds one `RuntimePlaceholderContext` from `session.character_name` + the **current** location, applies it to `location.content`, joined `injected_lore`, and each NPC brief; `_format_npcs_at_location` gains a trailing `runtime_placeholders: RuntimePlaceholderContext | None` parameter and substitutes the brief before formatting.
- `backend/tests/services/test_runtime_placeholders.py` — new pure-helper tests: all-three-tokens, ctx=None pass-through, idempotency, lowercase non-substitution, no-token pass-through, empty string.
- `backend/tests/services/test_chat_context.py` — new integration tests: current-location semantics for `location.content`, injected lore, and NPC brief substitution.

### Step 006 — Backend: editor system prompts learn the placeholders
- `backend/app/services/prompts/document_editor_system_prompt.py` — `build_document_editor_system(...)` always emits a "## Runtime Placeholders" section listing `{CHARACTER_NAME}` / `{LOCATION_NAME}` / `{LOCATION_SUMMARY}` with one-line semantics each plus a chat-time substitution explanation; included unconditionally for every `doc_type`.
- `backend/app/services/prompts/world_field_editor_system_prompt.py` — `_FIELD_ROLES["initial_message"]` one-liner replaced with a multi-line block mirroring the document-editor one (heading, three tokens, chat-time-substitution explanation), using doubled `{{...}}` brace escaping so the surrounding `.format(world_name=...)` at line 146 leaves literal `{CHARACTER_NAME}` / `{LOCATION_NAME}` / `{LOCATION_SUMMARY}` in the rendered prompt; `_FIELD_ROLES["description"]` and `_FIELD_ROLES["system_prompt"]` untouched.
- `backend/tests/services/prompts/__init__.py` — package marker for the new test folder.
- `backend/tests/services/prompts/test_document_editor_system_prompt.py` — new file: parametrized snippet checks across `doc_type` in {`location`, `npc`, `lore_fact`} that the section is present, all three literal tokens appear, the chat-time-substitution explanation appears, and the section survives both empty-world-context and `enable_tools=True` builds.
- `backend/tests/services/prompts/test_world_field_editor_system_prompt.py` — new file: snippet check on the `initial_message` branch (block + three literal-brace tokens + chat-time phrase), an escaping regression that confirms tokens render as single-braced literals (no `{{...}}` leak, no bare-name leak), and regression asserts that `description` and `system_prompt` branches do **not** contain the placeholders block.

### Step 007 — Frontend: wire placeholder UI into DocumentEditPage
- `frontend/src/admin/components/placeholders/runtimePlaceholders.ts` — renamed (git mv) from `initialMessagePlaceholders.ts`; exported constant renamed `INITIAL_MESSAGE_PLACEHOLDERS` → `RUNTIME_PLACEHOLDERS`; descriptions reworded to reflect current-location semantics shared with documents; doc comment updated to list all three runtime substitution sites.
- `frontend/src/admin/pages/WorldFieldEditPage.tsx` — import path updated to `../components/placeholders/runtimePlaceholders` and identifier updated to `RUNTIME_PLACEHOLDERS` at both usage sites; behavior unchanged.
- `frontend/src/admin/pages/DocumentEditPage.tsx` — Content `<Textarea>` block replaced with `<PlaceholderTextarea>` + `<PlaceholderPanel>` driven by `RUNTIME_PLACEHOLDERS`; adds `useRef<PlaceholderTextareaController | null>(null)` and `handleInsertPlaceholder`; `Textarea` import dropped (no other usage); `Name`, metadata fields, and `<LlmChatPanel>` untouched; page stays wrapped in `observer`.

### Step 005 — Backend: chat_tools runtime substitution
- `backend/app/services/chat_tools.py` — imports `RuntimePlaceholderContext` + `apply_runtime_placeholders`; adds `runtime_placeholders: RuntimePlaceholderContext | None = None` to `ToolContext`; the six chat-side bindings (`_b_get_location_info`, `_b_get_npc_info`, `_b_search`, `_b_get_lore`, `_b_get_memory`, `_b_move_to_location`) capture `ctx.runtime_placeholders` and wrap their return value with `apply_runtime_placeholders` before returning. The four `*_impl` functions and `admin_tools` are untouched (signatures preserved; editor mode = ctx None = raw return).
- `backend/app/services/chain_generation_service.py` — imports `RuntimePlaceholderContext`; both chat-bound `ToolContext(...)` sites (tool-stage at line ~318 and writer-stage at line ~458) build the placeholder dict from `chat.character_name` + `context["location_name"]` + `context["location_description"]` and pass it through.
- `backend/app/services/simple_generation_service.py` — same pattern: imports `RuntimePlaceholderContext` and populates `runtime_placeholders` on the simple-mode `ToolContext` from session character + chat-context current location.
- `backend/app/services/summarization_service.py` — comment-only change: documents that the `add_memory`-only `ToolContext` intentionally leaves `runtime_placeholders=None` because the tool returns no document content.
- `backend/tests/services/test_chat_tools.py` — new file: 12 tests covering each chat-side tool (`get_location_info`, `get_npc_info`, `move_to_location`, `get_memory`, `search`, `get_lore`) with both `runtime_placeholders` set (substitution applied) and `None` (raw tokens preserved); uses `monkeypatch` to stub `vector_storage.search` against real DB rows.
- `backend/tests/services/test_chat_service.py` — appends end-to-end `move_to_location` test: creates a chat session via `chat_service.create_chat`, mirrors the chat-runtime `ToolContext` construction, dispatches the bound `move_to_location`, and asserts the destination's `{CHARACTER_NAME}` / `{LOCATION_NAME}` are substituted in the user-visible JSON payload + the session's `current_location_id` advanced.

## Notes & Issues
- Step 002: `frontend/src/admin/components/pipelines/` is now an empty directory — git tracks no files there but the folder remains on disk. Step does not require its removal; left untouched to stay in scope.

_populated by the coder when worth saying_

## Bug Fixes
- Step 003 follow-up (2026-05-05): `WorldFieldEditPage.tsx` `initial_message` branch still showed a visible vertical gap between `<PlaceholderTextarea>` and `<PlaceholderPanel>` after the prior `minRows: 4 -> 12` bump — that mirror was insufficient because Mantine's `autosize: true` sets the input's inline `height` from row count and ignores the parent's `60vh` wrapper, so short content collapsed the textarea well below the wrapper. Superseded the earlier fix: switched `textareaProps` to `autosize: false` and used the Mantine 7 Textarea Styles API (`root` / `wrapper` / `input` keys, all valid per `__InputStylesNames`) to make the input fill its parent via `flex: 1` + `height: 100%` + `resize: 'none'`. Also turned the `60vh` resizable wrapper into a `display: flex; flexDirection: column` container so the inner textarea grows/shrinks with the user-resized wrapper. Page-local change only — `PlaceholderTextarea.tsx` and `PipelineStageEditPage.tsx` untouched.
