# Quick Reference

Condensed technical reference for the LLM RPG project. Sourced from plan documents — read those for full details.

## IDs — Snowflake Format

- 41 bits timestamp (epoch 2025-01-01) + 19 bits sequence + 3 bits machine
- Stored as INTEGER (int64) in SQLite
- Serialized as **string** in all JSON API responses (JS can't handle int64)

## Roles

`admin` > `editor` > `player` (inherited top-down)

## Database Tables

### Stage 1 — World System

**users**: id, username, pwdhash, salt, role (admin/editor/player), jwt_signing_key, last_login, last_key_update

**worlds**: id, name, description, lore, system_prompt, character_template (with `{PLACEHOLDER}` tokens), initial_message (template for first chat message, supports `{character_name}`, `{location_name}`, `{location_summary}`), pipeline (JSON), status (draft/public/private/archived), owner_id (FK users.id, nullable — private worlds visible only to owner), created_at, modified_at

**world_locations**: id, world_id, name, content (markdown), exits (JSON array of location IDs or None), created_at, modified_at

**world_npcs**: id, world_id, name, content (markdown), created_at, modified_at

**world_lore_facts**: id, world_id, content (markdown), created_at, modified_at

**npc_location_links**: id, npc_id, location_id, link_type (present/excluded). No links = roaming NPC.

**world_stat_definitions**: id, world_id, name, description, scope (character/world), stat_type (int/enum/set), default_value (JSON), min_value, max_value, enum_values (JSON array)

**world_rules**: id, world_id, rule_text (natural language), order

**llm_servers**: id, name, backend_type (llama-swap/openai), base_url, api_key (supports `$ENV_VAR`), enabled_models (JSON array), is_active, is_embedding (bool, at most one server), embedding_model (model ID or null), created_at, modified_at

### Stage 2 — Chat System

**chat_sessions**: id, user_id, world_id, current_location_id, character_name, character_description, character_stats (JSON), world_stats (JSON), current_turn, status (active/archived), llm_server_id, llm_model_id, temperature, user_instructions, created_at, modified_at

**chat_messages**: id, session_id, role (user/assistant/system), content, turn_number, tool_calls (JSON array), summary_id (FK to summaries, null if not summarized), is_active_variant, created_at

**chat_state_snapshots**: id, session_id, turn_number, location_id, character_stats (JSON), world_stats (JSON), created_at

**chat_summaries**: id, session_id, start_message_id, end_message_id, start_turn, end_turn, content, created_at

### Vector Storage (LanceDB, external)

Chunks: id, world_id, source_type (location/npc/lore_fact), source_id, chunk_index, text, vector. Rebuilt from source documents on import.

## API Endpoints

### Auth (`/api/auth`) — stage1_step1

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/api/auth/status` | Returns `{ needs_setup: bool }` |
| POST | `/api/auth/login` | Login, returns JWT |
| POST | `/api/auth/setup/create` | Create DB + admin user |
| POST | `/api/auth/setup/import` | Import DB from zip upload |

### Admin — LLM Servers (`/api/admin/llm-servers`) — stage1_step3

| Method | Path | Purpose | Role |
| ------ | ---- | ------- | ---- |
| GET | `/api/admin/llm-servers` | List all servers | admin |
| POST | `/api/admin/llm-servers` | Create server | admin |
| PUT | `/api/admin/llm-servers/:id` | Update server | admin |
| DELETE | `/api/admin/llm-servers/:id` | Delete server | admin |
| GET | `/api/admin/llm-servers/:id/available-models` | Probe server | admin |
| PUT | `/api/admin/llm-servers/:id/enabled-models` | Set enabled models | admin |
| GET | `/api/admin/llm-servers/embedding` | Get embedding config | admin |
| PUT | `/api/admin/llm-servers/:id/embedding` | Set as embedding server | admin |
| DELETE | `/api/admin/llm-servers/embedding` | Clear embedding designation | admin |
| GET | `/api/llm/models` | List all enabled models | editor |

### Admin — DB Management (`/api/admin/db`) — stage1_step6

| Method | Path | Purpose | Role |
| ------ | ---- | ------- | ---- |
| GET | `/api/admin/db` | Get status of all tables | admin |
| POST | `/api/admin/db/tables/:table_name/create` | Create missing table | admin |
| GET | `/api/admin/db/export` | Export all data (zip) | admin |
| POST | `/api/admin/db/import` | Import data from zip | admin |
| POST | `/api/admin/db/reindex-vectors` | Rebuild vector index from all docs | admin |

### Admin — Worlds (`/api/admin/worlds`) — stage1_step4

CRUD for worlds, locations, NPCs, lore facts, stat definitions, rules. All require editor+ role. Includes `POST /api/admin/worlds/:id/reindex` for per-world vector reindex. (See stage1_step4 plan for full endpoint list.)

### Chats (`/api/chats`) — stage2_step3

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/api/chats/worlds` | List public worlds for selection |
| POST | `/api/chats` | Create new chat session |
| GET | `/api/chats` | List user's chat sessions |
| GET | `/api/chats/:id` | Get chat detail (messages, snapshots, variants) |
| POST | `/api/chats/:id/message` | Send message, SSE stream response |
| POST | `/api/chats/:id/regenerate` | Regenerate last assistant message (SSE) |
| POST | `/api/chats/:id/continue` | Pick variant, delete others |
| POST | `/api/chats/:id/rewind` | Rewind to target turn |
| PUT | `/api/chats/:id/model` | Change LLM model |
| PUT | `/api/chats/:id/settings` | Update temperature, user_instructions |
| PUT | `/api/chats/:id/archive` | Archive chat (read-only) |
| DELETE | `/api/chats/:id` | Delete chat and all related data |

## SSE Streaming Protocol

Used for chat message generation and regeneration.

| Event | Data | When |
| ----- | ---- | ---- |
| `thinking` | `{"content": "...delta..."}` | Reasoning token delta |
| `thinking_done` | `{}` | End of thinking |
| `tool_call_start` | `{"tool_name": "...", "arguments": {...}}` | Tool invocation begins |
| `tool_call_result` | `{"tool_name": "...", "result": "..."}` | Tool returned |
| `token` | `{"content": "...delta..."}` | Content token delta |
| `stat_update` | `{"stats": {"name": value, ...}}` | Stats changed |
| `done` | `{"message": ChatMessageResponse}` | Final message |
| `error` | `{"detail": "..."}` | Error |

Typical order: `thinking*` -> `thinking_done` -> `tool_call_start` -> `tool_call_result` -> `token*` -> `stat_update?` -> `done`

## Agent Tools (stage2_step2)

All tools are internal async functions (DB queries only, no external HTTP).

- **get_location_info**(location_id) — Full location details + linked NPCs
- **get_npc_info**(npc_id) — Full NPC details + location links
- **search**(query, source_type?) — LanceDB vector search across world knowledge
- **google_search**(query) — Stub, returns "not implemented" message

Tool schemas generated via `pydantic_to_openai_tool()` from Pydantic `BaseModel` params.

## Stat System

- **Defined per world** via `world_stat_definitions` (schema/template)
- **Valued per chat session** in `character_stats` / `world_stats` JSON fields
- **Types**: int (min/max range), enum (single from list), set (multiple from list)
- **Updates**: LLM outputs `[STAT_UPDATE]...[/STAT_UPDATE]` block, parsed and validated server-side
- **Snapshots**: `chat_state_snapshots` records stats at each turn for rewind

## Regeneration & Variants

- `is_active_variant` field on `chat_messages`
- Regenerate: create new assistant message, mark old as inactive
- Variants only exist for the **latest** turn
- Continue: pick one variant, delete others

## Summarization (stage2_step4)

- LLM compresses older message ranges into `chat_summaries`
- Summarized messages get `summary_id` set (not deleted)
- Context build order: system prompt -> summaries (by start_turn ASC) -> raw non-summarized active messages
- Lazy-loaded, triggered when context exceeds threshold

## Key Patterns

- **Prompts**: All in `backend/app/services/prompts/` — one documented file per prompt, re-exported via `__init__.py`
- **LLM client**: PythonLLMClient, `pydantic_to_openai_tool()` for tool schemas
- **Auth**: Per-user HS256 JWT signing key (no global secret), key rotation on login (30-day interval)
- **Password**: App-level salt + bcrypt (direct `bcrypt` library, not passlib)
- **API key security**: `$ENV_VAR` syntax in `llm_servers.api_key`, never expose raw key in responses
- **Import/export**: ZIP of `.jsonl.gz` files, one per table. Streaming callback export, batched upsert import. Must be updated with every model change.
- **DB layer**: Session-free, namespace modules — `from app.db import users, worlds` then `await users.get_by_id(id)`
- **Services layer**: Namespace imports — `from app.services import auth as auth_service`

## Implementation Progress

- Stage 1 Step 1: Login, User Model, DB Bootstrap — done
- Stage 1 Step 2: World models, vector storage, import/export — done
- Stage 1 Step 3: LLM Servers CRUD + embedding server designation — done
- Stage 1 Step 6: DB Management admin page — done
- DB layer refactored to DB-agnostic interface (session-free, injectable config, streaming import/export)
