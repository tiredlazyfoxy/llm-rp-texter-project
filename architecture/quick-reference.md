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

**worlds**: id, name, description, system_prompt (full prompt template with `{PLACEHOLDER}` syntax), simple_tools (JSON list of enabled tool names for simple mode), character_template (with `{PLACEHOLDER}` tokens), initial_message (template for first chat message, supports `{character_name}`, `{location_name}`, `{location_summary}`), generation_mode (str: "simple"/"chain"/"agentic", default "simple"), pipeline (JSON — PipelineConfig for chain mode), agent_config (JSON — future agentic mode config), status (draft/public/private/archived), owner_id (FK users.id, nullable — private worlds visible only to owner), created_at, modified_at. (`lore` field exists in DB but is deprecated — hidden from UI, not used in prompts.)

**world_locations**: id, world_id, name, content (markdown), exits (JSON array of location IDs or None), created_at, modified_at

**world_npcs**: id, world_id, name, content (markdown), created_at, modified_at

**world_lore_facts**: id, world_id, content (markdown), is_injected (bool), weight (int), created_at, modified_at. Injected facts (sorted by weight) are always included in system prompts; non-injected are available only via search tools.

**npc_location_links**: id, npc_id, location_id, link_type (present/excluded). No links = roaming NPC.

**world_stat_definitions**: id, world_id, name, description, scope (character/world), stat_type (int/enum/set), default_value (JSON), min_value, max_value, enum_values (JSON array), hidden (bool, default false — hidden stats not shown to players but included in LLM prompts)

**world_rules**: id, world_id, rule_text (natural language), order

**llm_servers**: id, name, backend_type (llama-swap/openai), base_url, api_key (supports `$ENV_VAR`), enabled_models (JSON array), is_active, is_embedding (bool, at most one server), embedding_model (model ID or null), created_at, modified_at

### Stage 2 — Chat System

**chat_sessions**: id, user_id, world_id, current_location_id, character_name, character_description, character_stats (JSON), world_stats (JSON), current_turn, status (active/archived), tool_model_id, tool_temperature, tool_repeat_penalty, tool_top_p, text_model_id, text_temperature, text_repeat_penalty, text_top_p, user_instructions (deprecated — now per-message), generation_variants (JSON), created_at, modified_at

**chat_messages**: id, session_id, role (user/assistant/system), content, turn_number, tool_calls (JSON array), generation_plan (JSON, nullable — GenerationPlanOutput from chain mode), thinking_content (text, nullable — stored reasoning for debug), user_instructions (text, nullable — per-turn OOC instructions extracted from `(( ))` notation), summary_id (FK to summaries, null if not summarized), is_active_variant, created_at

**chat_state_snapshots**: id, session_id, turn_number, location_id, character_stats (JSON), world_stats (JSON), created_at

**chat_summaries**: id, session_id, start_message_id, end_message_id, start_turn, end_turn, content, created_at

**chat_memories**: id (snowflake, natural order), session_id, content (free text), created_at. Managed via MCP tools.

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

CRUD for worlds, locations, NPCs, lore facts, stat definitions, rules. All require editor+ role. Includes `POST /api/admin/worlds/:id/reindex` for per-world vector reindex. `GET /api/admin/worlds/pipeline-config` returns static config data (placeholders, tools, default templates) for the admin prompt editor UI. (See stage1_step4 plan for full endpoint list.)

### Chats (`/api/chats`) — stage2_step3

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/api/chats/worlds` | List public worlds for selection |
| POST | `/api/chats` | Create new chat session |
| GET | `/api/chats` | List user's chat sessions |
| GET | `/api/chats/:id` | Get chat detail (messages, snapshots, variants) |
| POST | `/api/chats/:id/message` | Send message, SSE stream response |
| POST | `/api/chats/:id/regenerate` | Regenerate assistant message (SSE). Optional `turn_number` for past turns |
| POST | `/api/chats/:id/continue` | Pick variant, delete others |
| POST | `/api/chats/:id/rewind` | Rewind to target turn |
| PUT | `/api/chats/:id/messages/:msg_id` | Edit user message content, delete assistant at that turn + all after, rewind to turn-1 |
| DELETE | `/api/chats/:id/messages/:msg_id` | Delete message + everything after it (user: whole turn+after; assistant: keep user msg, delete turn+1 onward) |
| PUT | `/api/chats/:id/settings` | Update model config |
| PUT | `/api/chats/:id/archive` | Archive chat (read-only) |
| DELETE | `/api/chats/:id` | Delete chat and all related data |

## SSE Streaming Protocol

Used for chat message generation and regeneration.

| Event | Data | When | Visibility |
| ----- | ---- | ---- | ---------- |
| `phase` | `{"phase": "planning" \| "writing"}` | Stage transition (chain mode) | All |
| `status` | `{"text": "..."}` | Human-readable status | All |
| `thinking` | `{"content": "...delta..."}` | Reasoning token delta | Editor+ only |
| `thinking_done` | `{}` | End of thinking | Editor+ only |
| `tool_call_start` | `{"tool_name": "...", "arguments": {...}}` | Tool invocation begins | Editor+ only |
| `tool_call_result` | `{"tool_name": "...", "result": "..."}` | Tool returned | Editor+ only |
| `user_ack` | `{"id": "...", "turn_number": N, "created_at": "..."}` | User message saved to DB | All |
| `token` | `{"content": "...delta..."}` | Content token delta | All |
| `stat_update` | `{"character_stats": {...}, "world_stats": {...}, "turn_number": N}` | Stats changed | All |
| `variants_update` | `{"variants": GenerationVariant[]}` | Updated variants list (regeneration only) | All |
| `done` | `{"message": ChatMessageResponse}` | Final message | All |
| `error` | `{"detail": "..."}` | Error | All |

Simple mode order: `user_ack` -> `status*` -> `thinking*` -> `tool_call_start` -> `tool_call_result` -> `token*` -> `stat_update?` -> `done`

Chain mode order: `user_ack` -> `phase("planning")` -> `status*` -> `tool_call*` -> `stat_update` -> `phase("writing")` -> `status` -> `token*` -> `done`

Regeneration adds `variants_update` after `done` with the updated variants list.

**Visibility filtering**: Backend filters events by `caller_role`. Players receive only All-visibility events. Editors+ receive everything. Frontend debug toggle controls whether editor-only events are displayed or hidden in the UI.

> **Tools + Streaming**: As of llm-client 0.1.3, `chat_with_tools` supports `stream=True` + `on_delta` callback, so `token` events stream in real-time even in tools mode.

## Admin LLM Tools (stage1_step7)

Available only during admin document editing (`enable_tools: true` in `LlmChatRequest`). Not available to players.

- **search(query, source_type?)** — Semantic search across world docs. Returns full text of top-5 deduplicated documents joined by `---`. `source_type` filters to `"location"`, `"npc"`, or `"lore_fact"`.
- **get_lore(query)** — Semantic search scoped to `lore_fact` only. Returns single best-matching lore document.
- **web_search(query)** — Google Custom Search API. Requires env vars `SEARCH_CSE_KEY` and `SEARCH_CSE_ID`. Returns 5 results (title, URL, snippet).

Implemented in `backend/app/services/admin_tools.py`. Tool schemas via `pydantic_to_openai_tool()`. LLM has up to 15 tool call rounds.

**Lore context with tools enabled:** `is_injected=True` lore facts are always in the system prompt (see Lore Injection below). Non-injected facts are excluded from context — the LLM fetches them via `search`/`get_lore`. Injected fact IDs are filtered out of tool search results to avoid duplication.

## Lore Injection (stage1_step7b)

`WorldLoreFact` has two fields that control context injection:

| Field          | Type | Default | Meaning                                |
| -------------- | ---- | ------- | -------------------------------------- |
| `is_injected`  | bool | false   | Always include in system prompt        |
| `weight`       | int  | 0       | Sort order (ascending); lower = first  |

**Injection rules:**

- `is_injected=True` facts → always appear in `## World Context` section of the system prompt, sorted by weight. This happens **regardless** of `enable_tools`.
- `is_injected=False` facts → only in context when `enable_tools=False` (full lore dump); with tools they must be fetched actively via `search`/`get_lore`.
- Injected fact IDs are excluded from `search` and `get_lore` tool results (already in context, no need to repeat).

`World.lore` (legacy text blob on the world record) is deprecated — hidden from UI, no longer shown in prompts. Field kept in DB for backward compatibility.

**Admin UI:** Lore fact list shows `is_injected=True` facts pinned at top (sorted by weight, pin icon), then regular facts below with a divider. Edit page has "Always inject" toggle and "Injection order" number input.

## Chat Tools (stage3_step2)

Player-facing in-game tools. Implemented in `backend/app/services/chat_tools.py`. Used by all generation modes (simple, chain). Reuses `admin_tools.search_impl()`, `admin_tools.get_lore_impl()`, `admin_tools.web_search_impl()` for search/lore/web tools.

All document-lookup tools use **free text → vector search → full document** (no ID lookup).

- **get_location_info(query)** — Vector search scoped to `location`. Returns full location doc + exits + linked NPCs.
- **get_npc_info(query)** — Vector search scoped to `npc`. Returns full NPC doc + location links.
- **get_lore(query)** — Vector search scoped to `lore_fact`, top 10 candidates, skips injected IDs. Returns single best non-injected lore doc.
- **search(query, source_type?)** — Vector search across all types, returns top 10 chunks with metadata. `source_type` filters to `"location"`, `"npc"`, or `"lore_fact"`.
- **web_search(query)** — Google Custom Search API. Requires `SEARCH_CSE_KEY` and `SEARCH_CSE_ID`. Returns 5 results (title, URL, snippet). (Same env vars and logic as admin `web_search` — separate implementation.)
- **get_memory()** — Returns all `ChatMemory` rows for the session concatenated with `\n---\n`.
- **add_memory(content)** — Appends a new `ChatMemory` row for the session. LLM is instructed to save story-significant facts (promises, relationship changes, plot developments) as 1-2 short factual sentences.
- **move_to_location(location_name)** — Resolves location name via vector search, updates `session.current_location_id`, returns new location info (description, exits, NPCs).

Tool registration: single `TOOL_REGISTRY` (12 tools) + `build_tools(names, ToolContext)` factory. Each registry entry declares `requires` (which `ToolContext` fields must be set). Admin picks tool names per stage (`stage.tools` / `World.simple_tools`); the generation service constructs a `ToolContext` with the state it has (simple mode: `world_id`+`session_id`; chain tool stage: adds `planning_context`, `stat_defs`, `char_stats`, `world_stats`, `decision_state`; chain writer stage: `world_id`+`session_id` only) and calls `build_tools(stage.tools, ctx)`. Unknown names or unmet requirements raise `ValueError`. Planning/director tools:

- **add_fact(content)** — Records a story/context fact into the planning context.
- **add_decision(content)** — Records a narrative decision (what happens next) into the planning context.
- **update_stat(name, value)** — Records a stat change into the planning context.
- **set_decision(content)** — Director-only. Overwrites a turn-level single-decision string (one sentence describing what happens next turn). Attached only to tool stages that request it and receive a `DecisionState`. Surfaced to later stages via the `{DECISION}` placeholder.

`PlanningContext` is built incrementally by tool calls during the planning stage, then converted to `GenerationPlanOutput` for persistence in `chat_messages.generation_plan`. The director's `{DECISION}` is transient (turn-scoped, not persisted).

**Lore injection filter:** `get_lore` skips lore facts already injected into the system prompt (same logic as admin `get_lore` — avoids duplicating context).

## Stat System

- **Defined per world** via `world_stat_definitions` (schema/template)
- **Valued per chat session** in `character_stats` / `world_stats` JSON fields
- **Types**: int (min/max range), enum (single from list), set (multiple from list)
- **Updates (simple mode)**: LLM outputs `[STAT_UPDATE]...[/STAT_UPDATE]` block, parsed and validated server-side via `stat_validation.validate_and_apply_stat_updates()`
- **Updates (chain mode)**: Planning agent calls `update_stat()` tool; results collected in `PlanningContext`, converted to `GenerationPlanOutput`, validated server-side
- **Validation**: int values clamped to `[min, max]` range; enum values checked against allowed list; set elements filtered to valid values; unknown stats logged and skipped
- **Snapshots**: `chat_state_snapshots` records stats at each turn for rewind

## Regeneration & Variants

- Variants stored as JSON array on `chat_sessions.generation_variants` (`GenerationVariant[]`)
- Each variant stores: content, tool_calls, generation_plan, thinking_content, character_stats, world_stats, location_id, location_name
- Regenerate: serialize current assistant message + stats → move to `generation_variants` → delete from DB → restore previous snapshot → generate new
- Only one active assistant message per turn in DB; old ones stored in session JSON
- Inline `< N/M >` switcher in message bubble (variants + current = total)
- Switching variants updates the stats panel to show that variant's stats (`displaySnapshot`)
- Continue (explicit): "Use this" icon on old variant → restore as DB message + stats, clear variants
- Continue (implicit): sending a new message auto-commits viewed variant; server clears variants on send
- `POST /continue` accepts `{ variant_index: int }` (index into variants array)
- SSE: `variants_update` event sent after regeneration with the updated variants list (avoids full chat reload)

## Summarization (stage2_step4)

- LLM compresses older message ranges into `chat_summaries`
- Summarized messages get `summary_id` set (not deleted)
- Context build order: system prompt -> summaries (by start_turn ASC) -> raw non-summarized active messages
- Lazy-loaded, triggered when context exceeds threshold

## Generation Modes (stage3)

`World.generation_mode` controls which generation flow is used:

- **`"simple"`** (default) — Single LLM call with admin-selected tools, prompt template with `{PLACEHOLDER}` syntax, stat validation. Admin prompt: `World.system_prompt`. Tools: `World.simple_tools`. Service: `simple_generation_service.py`
- **`"chain"`** — Pipeline stages defined in `World.pipeline` (PipelineConfig JSON). Each stage has step_type (`"tool"` or `"writer"`), admin-configurable prompt template with `{PLACEHOLDER}` syntax, and per-stage tool selection. Default: tool stage (research + planning tools) → writer stage (prose). Service: `chain_generation_service.py`
- **`"agentic"`** (future) — Sub-agent orchestration, config in `World.agent_config`. Service: `agent_generation_service.py`. Not yet implemented.

Dispatch: `chat_agent_service.py` routes to the appropriate service based on `generation_mode`.

### Pipeline Config (`World.pipeline` JSON)

```
PipelineConfig:
  stages: list[PipelineStage]
    step_type: "tool" | "writer"           (was: "planning" | "writing")
    name: str                              admin-defined stage label (e.g. "Research")
    prompt: str                            full system prompt template with {PLACEHOLDER} syntax
    max_agent_steps: int | null            for tool-calling stages
    tools: list[str]                       enabled tool names from tool catalog

PlanningContext:                         — built incrementally during tool stage
  facts: list[str]                       — added via add_fact() tool calls
  decisions: list[str]                   — added via add_decision() tool calls
  stat_updates: list[StatUpdateEntry]    — added via update_stat() tool calls
  → converted to GenerationPlanOutput for persistence in chat_messages.generation_plan
```

### Debug Mode

Editor+ toggle in user settings. Controls UI visibility of tool call details, thinking content, generation plan, hidden stats. Backend filtering is by `caller_role` (players never receive editor-only SSE events regardless of toggle).

## Key Patterns

- **Prompts**: All pre-coded prompt parts in `backend/app/services/prompts/` — one documented file per prompt (stage-4 docstring: PURPOSE, USAGE, VARIABLES, DESIGN RATIONALE, CHANGELOG), re-exported via `__init__.py`. Admin-editable parts injected as variables. No hardcoded prompt text in service files.
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
- Stage 1 Step 4: World editor (admin CRUD UI for locations, NPCs, lore facts, rules) — done
- Stage 1 Step 5: LLM-assisted world editing (document editor chat panel + field editor for description/system_prompt/initial_message, thinking mode, apply/append) — done
- Stage 1 Step 6: DB Management admin page — done
- Stage 1 Step 7: Admin LLM tools (search, get_lore, web_search), SSE streaming for tools, per-message regenerate — done
- DB layer refactored to DB-agnostic interface (session-free, injectable config, streaming import/export)
- Stage 2 Step 1: Chat DB models (chat_sessions, chat_messages, chat_state_snapshots, chat_summaries, chat_memories) + import/export — done
- Stage 2 Step 2: Chat tools & prompts — done
- Stage 2 Step 3: Chat API, UI, memories, dual model config — done
- Stage 2 Step 4: Summarization API and UI — done
- Stage 3 Step 1: Pipeline config model + admin UI (generation_mode, PipelineConfig, hidden stats, prompt skeletons) — done
- Stage 3 Step 2a: Simple mode backend (chat tools, rich prompt, stat validation, shared infrastructure, move_to_location) — done
- Stage 3 Step 2b: Chain mode backend (planning → writing pipeline, generation_plan, writer tools, memory enforcement) — done
- Stage 3 Step 3: User UI (debug mode, message edit/delete, thinking_content storage, SSE phase/status, hidden stats filtering) — done

- Stage 5 Step 1: Admin-configurable prompt templates — placeholder registry, tool catalog, per-stage tool selection, admin UI (placeholder panel, autocomplete, stage names) — done
- Stage 5 Step 2: Prompt injection engine — `{PLACEHOLDER}` resolution, generation services refactored to dynamic pipeline — done
- Stage 5 Step 3: Director stage — optional tool stage that commits a single `{DECISION}` via `set_decision` for downstream stages (`plans/stage5_step3_director_stage.md`) — done

## Backlog

- Agent flow — sub-agent orchestration design (`plans/backlog.agent_flow.md`)
- Agent mode — agentic generation mode design (`plans/backlog.agent_mode.md`)
- Split research/planning — separate research and planning stages (`plans/backlog.split_research_planning.md`)
- Prompt tuning — infrastructure for prompt iteration (`plans/backlog.prompt_tuning.md`)
