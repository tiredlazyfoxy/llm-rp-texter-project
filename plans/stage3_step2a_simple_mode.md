# Stage 3 Step 2a — Simple Mode Backend (Tools + Rich Prompt)

## Context

Simple mode (`generation_mode == "simple"`) is the enhanced version of the current single-step LLM call. Currently: no tools available in chat, minimal system prompt, stub stat handling. This step adds tool access, a rich system prompt with full world context, and real stat validation.

The existing `World.system_prompt` field serves as the admin-editable prompt for simple mode — no new fields needed.

### Dependencies

- Stage 3 Step 1 (generation_mode, pipeline schema, hidden stats, prompt skeletons)
- Shared infrastructure (chat_tools, chat_context, stat_validation, rich system prompt)

### Prompt Convention

All **pre-coded** (hardcoded) prompt parts — system prompts, structural instructions, JSON schema descriptions, tool usage instructions — must be placed in `backend/app/services/prompts/` as separate documented files following the stage-4 docstring convention (PURPOSE, USAGE, VARIABLES, DESIGN RATIONALE, CHANGELOG). Admin-editable parts are injected into these prompts as variables. No hardcoded prompt text in service files.

---

## 1. Shared Infrastructure (Built as Part of This Step)

These components are shared by all modes. Built here, reused by chain mode.

### 1a. Chat Tools — `backend/app/services/chat_tools.py` (Create)

Seven player-facing tools, following `admin_tools.py` pattern exactly (Pydantic BaseModel params → `pydantic_to_openai_tool()` → factory).

| Tool | Params | Implementation |
| ---- | ---- | ---- |
| `get_location_info` | `query: str` | Vector search scoped to locations. Return full doc + exits + linked NPCs. |
| `get_npc_info` | `query: str` | Vector search scoped to NPCs. Return full doc + location links. |
| `search` | `query: str`, `source_type?: str` | Delegate to `admin_tools.search_impl()` |
| `get_lore` | `query: str` | Delegate to `admin_tools.get_lore_impl()` |
| `web_search` | `query: str` | Delegate to `admin_tools.web_search_impl()` |
| `get_memory` | (none) | Return all session memories concatenated |
| `add_memory` | `content: str` | Create ChatMemory record |

**Factory**:
```python
def get_chat_tools(world_id: int, session_id: int) -> tuple[list[dict], dict[str, Callable]]:
    """Returns (CHAT_TOOL_DEFINITIONS, {name: async_callable}) bound to world and session."""
```

**DB layer additions** in `backend/app/db/chats.py`:
- `list_memories(session_id: int) -> list[ChatMemory]`
- `create_memory(memory: ChatMemory) -> ChatMemory`

### 1b. Context Builder — `backend/app/services/chat_context.py` (Create)

```python
class ChatContext(TypedDict):
    world: World
    location_name: str
    location_description: str
    location_exits: str
    present_npcs: str
    rules: str
    stat_definitions: str
    current_stats: str
    injected_lore: str
    memories: str

async def build_chat_context(session: ChatSession) -> ChatContext:
    """Loads all context needed for system prompt. Formats into strings."""
```

Loads:
- World via `worlds_db.get_by_id(session.world_id)`
- Current location via `locations_db.get_by_id(session.current_location_id)`
- NPCs at location via `npc_links_db.list_by_location()` + `npcs_db.get_by_id()`
- Rules via `rules_db.list_by_world()`
- Stat definitions via `stat_defs_db.list_by_world()`
- Current stats from `session.character_stats` / `session.world_stats` (parsed)
- Injected lore via `lore_facts_db` (filter `is_injected=True`)
- Memories via `chats_db.list_memories(session.id)`

Formats each into human-readable strings suitable for prompt injection.

### 1c. Rich System Prompt — `backend/app/services/prompts/chat_system_prompt.py` (Rewrite)

Replace current stub with:

```python
def build_rich_chat_system_prompt(
    world_name: str,
    world_description: str,
    admin_system_prompt: str,       # World.system_prompt (for simple mode)
    location_name: str,
    location_description: str,
    location_exits: str,
    present_npcs: str,
    rules: str,
    stat_definitions: str,
    current_stats: str,
    character_name: str,
    character_description: str,
    injected_lore: str,
    user_instructions: str,
    memories: str,
) -> str:
```

Prompt sections (in order):
1. **World** — name + description
2. **Current Location** — name, description, exits
3. **NPCs Present** — name + brief for each NPC at location
4. **World Rules** — numbered list
5. **Stats** — definitions (name, type, constraints) + current values
6. **World Context** — injected lore facts
7. **Your Character** — name + description
8. **Game Master Instructions** — `admin_system_prompt` (World.system_prompt)
9. **Player Instructions** — user_instructions (session-level)
10. **Memories** — session memories

Keep old `build_chat_system_prompt()` as deprecated wrapper that calls new function with empty values.

### 1d. Stat Validation — `backend/app/services/stat_validation.py` (Create)

```python
def validate_and_apply_stat_updates(
    updates: list[StatUpdateEntry],
    stat_defs: list[WorldStatDefinition],
    char_stats: dict[str, Any],
    world_stats: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
```

For each update:
- Find matching stat definition by name
- **int**: parse value as int, check min/max range
- **enum**: check value is in `enum_values` list
- **set**: parse as list, check each element is in `enum_values`
- Unknown stat name or invalid value: log warning, skip
- Returns new copies of char_stats and world_stats

### 1e. Shared Helpers — Extract from `chat_agent_service.py`

- `_sse(event, data)` — SSE formatting helper (keep in chat_agent_service or new module)
- `_now()` — UTC timestamp helper
- `_build_llm_messages(session_id)` — message history builder (stays, used by all modes)
- `_parse_stat_updates(content)` — extract `[STAT_UPDATE]` blocks (stays, used by simple mode)
- Thinking tag callback — extract to shared factory:
  ```python
  def create_thinking_callback(queue, content_parts) -> Callable:
      """Returns on_delta callback with <think>/<\/think> tag detection."""
  ```

---

## 2. Simple Generation Service

### 2a. New File: `backend/app/services/simple_generation_service.py`

```python
async def generate_simple_response(
    session_id: int,
    user_id: int,
    user_message: str,
) -> AsyncGenerator[str, None]:

async def regenerate_simple_response(
    session_id: int,
    user_id: int,
) -> AsyncGenerator[str, None]:
```

### 2b. Flow — `generate_simple_response()`

1. Load session, verify active + user ownership
2. Resolve `tool_model_id` and `text_model_id` from session config
3. Save user message to DB (same as current)
4. Build context via `build_chat_context(session)`
5. Build rich system prompt via `build_rich_chat_system_prompt()`:
   - `admin_system_prompt` = `context.world.system_prompt`
   - All other fields from ChatContext
6. Build LLM message history via `_build_llm_messages(session_id)`
7. Create async queue + content buffer (same pattern as current)
8. Get tools from `get_chat_tools(world_id, session_id)`
9. Wrap tools with SSE emission:
   ```python
   def _make_tool_wrapper(name, fn, queue):
       async def wrapper(**kwargs):
           await queue.put(_sse("tool_call_start", {"name": name, "arguments": kwargs}))
           result = await fn(**kwargs)
           await queue.put(_sse("tool_call_result", {"name": name, "result": result}))
           return result
       return wrapper
   ```
10. Get LLM client via `get_llm_client_for_model(tool_model_id)`
11. Call `client.chat_with_tools(messages, tool_defs, wrapped_tools, system, options, max_loops=15, stream=True, on_delta=thinking_callback)`
12. On completion:
    - Collect tool call records from wrappers
    - Parse `[STAT_UPDATE]` block from full content
    - Validate + apply stats via `validate_and_apply_stat_updates()`
    - Save assistant message (content + tool_calls JSON)
    - Update session (turn++, stats, modified_at)
    - Save snapshot
    - Strip `[STAT_UPDATE]` from display content
    - Emit `stat_update` + `done` events

### 2c. Flow — `regenerate_simple_response()`

Same pattern as current `regenerate_response()`:
1. Mark current assistant message as inactive
2. Restore stats from snapshot at turn-1
3. Rebuild messages excluding current turn's assistant
4. Run same flow as generate (steps 4-12)
5. Don't increment turn, update snapshot for current turn

### 2d. SSE Events

| Event | Data | When |
| ---- | ---- | ---- |
| `thinking` | `{text}` | Inside `<think>` tags |
| `thinking_done` | `{}` | On `</think>` |
| `tool_call_start` | `{name, arguments}` | Before tool execution |
| `tool_call_result` | `{name, result}` | After tool execution |
| `token` | `{text}` | Normal content tokens |
| `stat_update` | `{character_stats, world_stats}` | After stat validation |
| `done` | `ChatMessageResponse` | Final message |
| `error` | `{detail}` | On exception |

---

## 3. Dispatch Integration

### 3a. Refactor `chat_agent_service.py`

```python
async def generate_response(session_id, user_id, user_message, caller_role="player"):
    session = await chats_db.get_session_by_id(session_id)
    world = await worlds_db.get_by_id(session.world_id)

    if world.generation_mode == "chain":
        return chain_generation_service.generate_chain_response(session_id, user_id, user_message, caller_role)
    elif world.generation_mode == "agentic":
        raise HTTPException(400, "Agentic mode not yet implemented")
    else:
        return simple_generation_service.generate_simple_response(session_id, user_id, user_message)
```

Same dispatch for `regenerate_response()`.

### 3b. Route Changes — `backend/app/routes/chat.py`

Pass `caller.role` to `generate_response()` and `regenerate_response()`:
```python
generator = await chat_agent_service.generate_response(
    int(chat_id), caller.id, req.content, caller_role=caller.role.value
)
```

---

## 4. Files Summary

### Create

| File | What |
| ---- | ---- |
| `backend/app/services/chat_tools.py` | 7 chat tools + factory |
| `backend/app/services/chat_context.py` | Context builder (ChatContext + loader) |
| `backend/app/services/stat_validation.py` | validate_and_apply_stat_updates() |
| `backend/app/services/simple_generation_service.py` | Simple mode generation |

### Modify

| File | Change |
| ---- | ---- |
| `backend/app/services/chat_agent_service.py` | Refactor to dispatcher, extract shared helpers |
| `backend/app/services/prompts/chat_system_prompt.py` | Rewrite with rich context |
| `backend/app/services/prompts/__init__.py` | Re-export `build_rich_chat_system_prompt` |
| `backend/app/routes/chat.py` | Pass caller_role to generation |
| `backend/app/db/chats.py` | Add memory CRUD functions |

---

## 5. Verification

1. Simple mode: tools available — agent calls get_location_info, search, etc. during generation
2. Rich prompt includes: location + exits, NPCs at location, rules, stat definitions + values, injected lore, memories
3. `World.system_prompt` appears in prompt as "Game Master Instructions" section
4. Stat updates: `[STAT_UPDATE]` blocks parsed, validated against definitions (int range, enum membership), applied
5. Invalid stat updates logged and skipped (don't crash generation)
6. Tool call events emitted via SSE (tool_call_start/result)
7. Thinking tags detected and emitted as thinking/thinking_done events
8. Regeneration: stats reverted from previous snapshot, tools re-run, new variant created
9. Existing single-step behavior preserved for worlds without tools (graceful fallback)
10. Memory tools: get_memory returns session memories, add_memory creates new ChatMemory
