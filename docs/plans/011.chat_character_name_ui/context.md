# Feature 011 — Chat Character Name UI

## Goal

Make `chat_session.character_name` a first-class, user-editable
field — both at chat creation and in the in-chat settings panel —
so it can be set explicitly and changed after the chat exists. The
field is the single source of truth for the `{CHARACTER_NAME}`
runtime placeholder added in feature 010, which is now substituted
across initial messages, location/NPC content, and tool returns.

## Resolved decisions (from orchestrator briefing)

1. **Creation form** — replace the heuristic
   (`state.variables["NAME"] || state.variables[placeholders[0]] || "Hero"`)
   with a dedicated "Character Name" `TextInput`. It is the sole
   source of truth for `chat.character_name`. The world template's
   `{NAME}` variable (when present) remains a separate concept — no
   auto-sync, no two-way binding.
2. **Update validation** — `character_name` must be non-empty after
   trimming whitespace. Backend rejects empty / whitespace-only with
   HTTP 400 on **both** create and update. The trimmed value is the
   one persisted.
3. **Effect on active chat when name changes** — persist only. The
   next turn's `apply_runtime_placeholders` reads from the live
   `chat_session.character_name`, so substitution updates
   automatically. Stored history is **not** rewritten. No banner,
   no special UI signal.

## Files involved across multiple steps

### Backend
- `backend/app/models/schemas/chat.py` — `CreateChatRequest`
  (line 17), `UpdateChatSettingsRequest` (lines 38-40),
  `ChatSessionResponse` (line 47), `ChatSessionListItem` (line 65).
  Touched for both validation and the new optional field on update.
- `backend/app/services/chat_service.py` — already builds the runtime
  placeholder context from `chat.character_name`. Hosts the existing
  update-settings service function (currently handling
  `tool_model` / `text_model`); `character_name` is added to that
  same path.
- `backend/app/db/chats.py` — DB-layer access for chat sessions.
  The settings-update DB helper (whatever the service currently
  calls for `tool_model` / `text_model`) is extended to persist
  `character_name`.
- `backend/app/routes/chat.py` — `POST /api/chats` (lines 87-100)
  forwards to `chat_service.create_chat(...)`. The existing
  `PATCH`/update-settings route on the same router consumes
  `UpdateChatSettingsRequest`; coder locates the handler by
  following `UpdateChatSettingsRequest` usage.

### Frontend
- `frontend/src/types/chat.d.ts` — `CreateChatRequest`,
  `UpdateChatSettingsRequest`, `ChatSessionResponse`,
  `ChatSessionListItem` interfaces. `character_name` is added to
  `UpdateChatSettingsRequest` (optional).
- `frontend/src/user/pages/CharacterSetupPage.tsx` — chat-creation
  form. Gains an explicit "Character Name" input.
- `frontend/src/user/state/characterSetupPageState.ts` —
  `submitCharacter` (lines 121-154) currently derives
  `character_name` heuristically. Replace with explicit
  `state.characterName` field + non-empty trim validation.
- `frontend/src/user/components/chats/ChatSettingsPanel.tsx` —
  in-chat settings panel. Currently edits `tool_model` /
  `text_model`; gains a "Character Name" input wired through the
  same `UpdateChatSettingsRequest` flow.

### Files NOT changed (do not touch)
- `backend/app/models/chat_session.py` — `character_name: str`
  already exists on the SQLModel; no model migration.
- `backend/app/services/runtime_placeholders.py`,
  `backend/app/services/chat_context.py`,
  `backend/app/services/chat_tools.py` — runtime substitution
  already consumes `chat_session.character_name`. No changes.
- World JSONL import/export — model schema is unchanged, so the
  import/export shape is unchanged.

## Cross-cutting constraints

- **Layer separation** (see `backend/CLAUDE.md`,
  `docs/architecture/backend.md`): the new validation lives at the
  Pydantic schema layer; the persistence change goes through the
  `db/` layer. No `session` / `AsyncSession` / `select()` leaks
  into services or routes.
- **Strict typing** — Pydantic `BaseModel` on the backend, no
  `any` on the frontend. The `.d.ts` interface mirrors the schema
  exactly, including the optional `character_name?: string` on
  update.
- **No model change → no JSONL change.** This feature only adds a
  schema field on update and tightens validation; the
  `chat_sessions` SQLModel is untouched, so JSONL import/export is
  not affected. (Project policy still applies if a future change
  touches the model.)
- **`observer` everywhere** — every modified MobX-driven component
  stays wrapped in `observer`.
- **Error contract** — non-empty validation rejects with HTTP 400
  and a clear message; the frontend disables the submit/save
  button when the input is empty after trim, matching the backend
  contract so legitimate users never hit a 400.

## Vocabulary

- **Character name** — the value of
  `chat_session.character_name`. Used at chat creation and at
  every chat-runtime substitution of `{CHARACTER_NAME}`.
- **Template variable `{NAME}`** — a per-world template variable
  the world author may declare in `World.template_variables`.
  Distinct from `character_name`; never auto-synced.
- **Settings update** — the existing `PATCH` flow that today
  edits `tool_model` / `text_model` on a chat session; this
  feature adds `character_name` to that same flow.

## References

- `docs/plans/CLAUDE.md` — plan layout and lifecycle.
- `docs/architecture/quick-reference.md` — runtime placeholders;
  chat / world model summary; API endpoint table.
- `docs/architecture/backend.md` — layer separation rules.
- `docs/architecture/db-models.md` — `chat_sessions` row shape
  (read-only here; model unchanged).
- `docs/architecture/frontend-pages.md`,
  `docs/architecture/frontend-forms.md`,
  `docs/architecture/frontend-state.md` — patterns for the
  creation page and the settings panel.
- `docs/plans/010.initial_message_placeholders/` — the feature
  that put `{CHARACTER_NAME}` into runtime substitution and made
  `chat_session.character_name` load-bearing.

## End-to-end behavior (composition across steps)

- Step 001 (backend) is independently shippable but user-invisible
  on its own.
- Step 002 (frontend) requires step 001 for the settings-panel
  half (the API field must exist) but the creation-form half
  works standalone (the field has always been on
  `CreateChatRequest`).
- Plan to ship 001 first, then 002, in a single release window.
