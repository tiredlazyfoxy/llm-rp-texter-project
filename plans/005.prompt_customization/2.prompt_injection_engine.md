# Stage 5 Step 2: Prompt Injection Engine + Generation Service Refactor

## Goal

Build the backend engine that resolves `{PLACEHOLDER}` patterns in admin-configured prompt templates, and refactor both generation services (simple + chain) to use it. Replace hardcoded prompt builders with dynamic template resolution.

## Prerequisites

Step 1 complete: `PipelineStage.tools`, `PipelineStage.name`, `World.simple_tools`, placeholder registry, tool catalog, default templates (`default_templates.py`), pipeline-config API endpoint (returns placeholders, tools, and default_templates), admin UI (placeholder panel, autocomplete, per-stage tool selection, stage names) all in place.

---

## Changes

### 1. Context Building Updates

**File**: `backend/app/services/chat_context.py`

The `build_chat_context()` return type needs updating. Currently returns separate fields (`location_name`, `location_description`, `location_exits`, `present_npcs`, `stat_definitions`, `current_stats`). Now we need:

- **`location_block: str`** — single formatted block combining name, description, exits, and NPCs present. Code builds this from the session's `current_location_id`:
  ```
  **Location: Tavern of the Red Lantern**

  A dimly lit tavern with creaking floorboards...

  **Exits:** Market Square, Back Alley, Docks

  **NPCs present:**
  - Bartender Mira: A sharp-eyed woman who knows everyone's secrets
  - Guard Captain Voss: Off-duty, drinking alone in the corner
  ```

- **`character_stats: str`** — formatted character-scope stats only (definitions + current values):
  ```
  **Health** (int, 0-100): Physical condition — Current: 85
  **Reputation** (enum: good/neutral/bad): Standing with locals — Current: neutral
  ```

- **`world_stats: str`** — formatted world-scope stats only (definitions + current values):
  ```
  **Day Count** (int, 1-999): Days elapsed — Current: 14
  **Season** (enum: spring/summer/autumn/winter): Current season — Current: autumn
  ```

The existing separate fields can remain for backward compatibility with old prompt builders (fallback). Add the new consolidated fields alongside them.

### 2. Prompt Injection Service

**New file**: `backend/app/services/prompts/prompt_injection.py`

Core engine shared by both generation modes.

#### `resolve_prompt_template()`

```python
def resolve_prompt_template(
    template: str,
    context: ChatContext,
    character_name: str,
    user_instructions: str,
    turn_facts: str = "",
    turn_decisions: str = "",
    tools_description: str = "",
) -> str:
```

- Regex: `re.sub(r"\{([A-Z_]+)\}", replacer, template)`
- Matches only `{UPPER_SNAKE_CASE}` — avoids collisions with markdown, JSON, code blocks
- Unknown placeholders left as-is (admin may have literal curly-brace patterns)
- Empty context values → empty string (admin's template handles formatting)

Value map (11 placeholders):

```python
values = {
    "WORLD_NAME": context["world"].name,
    "RULES": context["rules"],
    "INJECTED_LORE": context["injected_lore"],
    "LOCATION": context["location_block"],
    "CHARACTER_NAME": character_name,
    "CHARACTER_STATS": context["character_stats"],
    "WORLD_STATS": context["world_stats"],
    "USER_INSTRUCTIONS": user_instructions,
    "TURN_FACTS": turn_facts,
    "TURN_DECISIONS": turn_decisions,
    "TOOLS": tools_description,
}
```

#### `build_tools_description()`

```python
def build_tools_description(tool_names: list[str]) -> str:
```

- Looks up each name in `TOOL_CATALOG`
- Returns formatted list: `- \`tool_name\` — description`
- Empty list → `"(no tools available)"`

#### `build_turn_plan_parts()`

```python
def build_turn_plan_parts(
    planning_contexts: list[PlanningContext],
) -> tuple[str, str]:
```

- Accumulates facts and decisions from all prior tool steps
- Returns `(turn_facts, turn_decisions)` as two separate strings
- `turn_facts`: all facts joined with newlines (one per line)
- `turn_decisions`: formatted as bullet list (`- decision 1\n- decision 2`)
- Returns `("", "")` if no planning contexts provided

These map to `{TURN_FACTS}` and `{TURN_DECISIONS}` placeholders. The admin controls WHERE and HOW they appear in the prompt — the code just provides the raw content.

### 3. Tool Selection Factory

**File**: `backend/app/services/chat_tools.py`

New function:

```python
def get_tools_by_names(
    tool_names: list[str],
    world_id: int,
    session_id: int,
    planning_context: PlanningContext | None = None,
    stat_defs: list[WorldStatDefinition] | None = None,
    char_stats: dict[str, Any] | None = None,
    world_stats: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Callable]]:
```

- Builds full tool sets (chat tools + planning tools if needed)
- Filters to only requested names
- Planning tools (`add_fact`, `add_decision`, `update_stat`) only instantiated when:
  - They appear in `tool_names` AND
  - `planning_context` is provided
- Returns `(filtered_defs, filtered_callables)`

Reuses existing `get_chat_tools()` internals. Planning tool closures same pattern as current `get_planning_tools()`.

### 4. Default Prompt Templates

**Existing file** (created in Step 1): `backend/app/services/prompts/default_templates.py`

Three string constants equivalent to the current hardcoded prompts but using `{PLACEHOLDER}` syntax:

#### `DEFAULT_SIMPLE_PROMPT`

Equivalent to `build_rich_chat_system_prompt()` output:

```
You are the narrator and game master for an RPG world called '{WORLD_NAME}'.
You control the world, NPCs, and story. Respond to the player's actions with
immersive narrative prose. Stay in character as the narrator at all times.

## Current Location

{LOCATION}

When the player moves to a different location, you MUST call the
`move_to_location` tool with the exact location name.

## World Rules

{RULES}

## Character Stats

{CHARACTER_STATS}

## World Stats

{WORLD_STATS}

### Updating Stats

When game events change stats, include a stat update block at the end
of your response in this exact format:

[STAT_UPDATE]
{"stat_name": new_value, "another_stat": new_value}
[/STAT_UPDATE]

Only include stats that actually changed.

## World Context

{INJECTED_LORE}

## Your Character

**{CHARACTER_NAME}**

## Available Tools

{TOOLS}

## Player Instructions

{USER_INSTRUCTIONS}

## Memory Management

You MUST use `add_memory` to save facts that matter for the ongoing story.
...memory rules...
```

#### `DEFAULT_TOOL_PROMPT`

Equivalent to `build_planning_system_prompt()` output:

```
You are a game planning agent for an RPG world called '{WORLD_NAME}'.
Your job is to analyze the player's action, aggressively research the
situation using every relevant tool, and use planning tools to build
complete context for a separate writing agent.

You do NOT write story text. Your ONLY output is tool calls.

## Current Location

{LOCATION}

## World Rules

{RULES}

## Character Stats

{CHARACTER_STATS}

## World Stats

{WORLD_STATS}

## World Context

{INJECTED_LORE}

## Player Character

**{CHARACTER_NAME}**

## Available Tools

{TOOLS}

## Mandatory Workflow

### Step 1: RESEARCH (aggressive)
...research instructions...

### Step 2: RECORD FACTS
...fact recording instructions...

### Step 3: DECIDE OUTCOMES
...decision instructions...

### Step 4: UPDATE STATS
...stat evaluation instructions...

### Step 5: SAVE MEMORIES
...memory instructions...

## Player Instructions

{USER_INSTRUCTIONS}
```

#### `DEFAULT_WRITER_PROMPT`

Equivalent to `build_writing_system_prompt()` output:

```
You are a narrative writer for an RPG world called '{WORLD_NAME}'.
Your task is to write immersive, engaging prose based on the turn plan.
Follow the plan faithfully.

## World Context

{INJECTED_LORE}

## Player Character

**{CHARACTER_NAME}**

## Writing Guidelines

- Write in second person, present tense
- Include all NPC dialogue specified in the plan
- Your output is ONLY narrative prose
- Do NOT include stat updates, JSON, tags, or meta-information

## Player Instructions

{USER_INSTRUCTIONS}
```

Note: the writer gets facts + decisions injected as a user message (not in system prompt), matching current behavior. But admin CAN include `{TURN_FACTS}` and `{TURN_DECISIONS}` in the system prompt too via the placeholders.

#### API Endpoint for Default Templates

**Already done in Step 1.** `GET /api/admin/worlds/pipeline-config` already returns `default_templates` with `simple`, `tool`, and `writer` keys.

### 5. Simple Mode Refactor

**File**: `backend/app/services/simple_generation_service.py`

**Current flow** (in `_run_generation`):

```python
system_prompt = build_rich_chat_system_prompt(
    world_name=..., world_description=..., admin_system_prompt=...,
    location_name=..., ...15 params...
)
tool_defs, tool_callables = get_chat_tools(world_id, session_id)
```

**New flow**:

```python
# Build context (unchanged)
context = await build_chat_context(chat)

# Parse tool selection
import json
try:
    simple_tools = json.loads(world.simple_tools) if world.simple_tools else []
except (json.JSONDecodeError, TypeError):
    simple_tools = []

# Build tools description for placeholder
tools_desc = build_tools_description(simple_tools) if simple_tools else build_tools_description(
    [t["name"] for t in TOOL_CATALOG if t["category"] != "planning"]
)

# Resolve prompt template
if world.system_prompt.strip():
    system_prompt = resolve_prompt_template(
        template=world.system_prompt,
        context=context,
        character_name=chat.character_name,
        user_instructions=chat.user_instructions or "",
        turn_facts="",  # not available in simple mode
        turn_decisions="",  # not available in simple mode
        tools_description=tools_desc,
    )
else:
    # FALLBACK: legacy behavior for worlds without template
    system_prompt = build_rich_chat_system_prompt(
        world_name=context["world"].name,
        # ... all 15 params as before
    )

# Get tools by selection (or all chat tools as fallback)
if simple_tools:
    tool_defs, tool_callables = get_tools_by_names(
        simple_tools, chat.world_id, chat.id,
    )
else:
    # Fallback: all 8 chat tools (existing behavior)
    tool_defs, tool_callables = get_chat_tools(chat.world_id, chat.id)
```

Rest of simple generation flow unchanged: wrap tools, stream, validate stats, save message.

### 6. Chain Mode Refactor

**File**: `backend/app/services/chain_generation_service.py`

Replace the hardcoded "find planning + find writing" logic with a dynamic N-step loop.

**Current flow** (in `_run_chain_generation`):

```python
planning_stage = next((s for s in pipeline.stages if s.step_type == "planning"), None)
writing_stage = next((s for s in pipeline.stages if s.step_type == "writing"), None)

if planning_stage:
    # run planning with hardcoded prompt + all 11 tools
if writing_stage:
    # run writing with hardcoded prompt + 5 read-only tools
```

**New flow**:

```python
async def _run_chain_generation(chat, turn, session_id, llm_messages, queue, caller_role, is_regenerate=False):
    # 1. Load world, parse pipeline
    world = await worlds_db.get_by_id(chat.world_id)
    pipeline = PipelineConfig.model_validate_json(world.pipeline)

    # 2. On-read migration of legacy step types
    for stage in pipeline.stages:
        if stage.step_type == "planning":
            stage.step_type = "tool"
            if not stage.tools:
                stage.tools = list(ALL_TOOL_NAMES)  # all 11 tools
        elif stage.step_type == "writing":
            stage.step_type = "writer"
            if not stage.tools:
                stage.tools = ["get_location_info", "get_npc_info", "search", "get_lore", "get_memory"]

    # 3. Build context
    context = await build_chat_context(chat)

    # 4. Shared state across steps
    char_stats = chats_db.parse_stats(chat.character_stats)
    world_stats = chats_db.parse_stats(chat.world_stats)
    planning_contexts: list[PlanningContext] = []
    all_tool_call_records: list[dict] = []
    all_thinking_parts: list[str] = []
    prose_content = ""

    # 5. Iterate steps
    for stage_idx, stage in enumerate(pipeline.stages):

        if stage.step_type == "tool":
            # --- TOOL STEP ---
            planning_ctx = PlanningContext()
            planning_contexts.append(planning_ctx)

            await queue.put(sse("phase", {"phase": "planning"}))  # keep SSE phases unchanged
            await queue.put(sse("status", {"text": f"Step {stage_idx + 1}: Gathering context..."}))

            # Build placeholder values
            tools_desc = build_tools_description(stage.tools)
            if len(planning_contexts) > 1:
                turn_facts, turn_decisions = build_turn_plan_parts(planning_contexts[:-1])
            else:
                turn_facts, turn_decisions = "", ""

            # Resolve or fallback
            if stage.prompt.strip():
                system_prompt = resolve_prompt_template(
                    stage.prompt, context,
                    chat.character_name,
                    chat.user_instructions or "",
                    turn_facts, turn_decisions, tools_desc,
                )
            else:
                system_prompt = build_planning_system_prompt(
                    world_name=world.name, ... # all 14 params, admin_prompt=""
                )

            # Get tools by admin selection
            tool_defs, tool_callables = get_tools_by_names(
                stage.tools, chat.world_id, chat.id,
                planning_context=planning_ctx,
                stat_defs=context["stat_defs_list"],
                char_stats=char_stats, world_stats=world_stats,
            )

            # Wrap, call LLM, collect tool calls
            wrapped = {name: _make_tool_wrapper(name, fn, queue, all_tool_call_records, caller_role)
                       for name, fn in tool_callables.items()}

            tool_parts: list[str] = []
            thinking: list[str] = []
            callback = _create_filtered_thinking_callback(queue, tool_parts, caller_role, thinking)

            options = {"temperature": chat.tool_temperature, "top_p": chat.tool_top_p,
                       "repeat_penalty": chat.tool_repeat_penalty}
            max_loops = stage.max_agent_steps or 10

            client = await get_llm_client_for_model(chat.tool_model_id or chat.text_model_id)
            async with client:
                await client.chat_with_tools(
                    llm_messages, tools_definitions=tool_defs, tools=wrapped,
                    system=system_prompt, options=options, max_loops=max_loops,
                    stream=True, on_delta=callback,
                )

            all_thinking_parts.extend(thinking)

            # Refresh context (move_to_location may have been called)
            chat_refreshed = await chats_db.get_session_by_id(session_id)
            if chat_refreshed:
                context = await build_chat_context(chat_refreshed)
                chat = chat_refreshed  # use refreshed for subsequent steps

        elif stage.step_type == "writer":
            # --- WRITER STEP ---
            await queue.put(sse("phase", {"phase": "writing"}))
            await queue.put(sse("status", {"text": "Writing..."}))

            # Build turn plan from all tool steps
            turn_facts, turn_decisions = build_turn_plan_parts(planning_contexts)
            tools_desc = build_tools_description(stage.tools)

            # Resolve or fallback
            if stage.prompt.strip():
                system_prompt = resolve_prompt_template(
                    stage.prompt, context,
                    chat.character_name,
                    chat.user_instructions or "",
                    turn_facts, turn_decisions, tools_desc,
                )
            else:
                system_prompt = build_writing_system_prompt(
                    world_name=world.name, ... # all 7 params, admin_prompt=""
                )

            # Build writer messages: summaries + clean history + plan
            writer_messages: list[dict[str, str]] = []
            summaries = await chats_db.list_summaries(session_id)
            for s in summaries:
                writer_messages.append({
                    "role": "user",
                    "content": f"[Summary of turns {s.start_turn}–{s.end_turn}]:\n{s.content}",
                })
            all_active = await chats_db.list_active_messages(session_id)
            for m in all_active:
                if m.role in ("user", "assistant"):
                    writer_messages.append({"role": m.role, "content": m.content})
                elif m.role == "system":
                    writer_messages.append({"role": "user", "content": m.content})

            # Inject turn plan as last user message (facts + decisions combined)
            if turn_facts or turn_decisions:
                plan_msg = ""
                if turn_facts:
                    plan_msg += f"## Context\n\n{turn_facts}\n\n"
                if turn_decisions:
                    plan_msg += f"## What Happens This Turn\n\n{turn_decisions}"
                writer_messages.append({"role": "user", "content": plan_msg.strip()})

            # Get writer tools
            tool_defs, tool_callables = get_tools_by_names(
                stage.tools, chat.world_id, chat.id,
            )
            writer_tool_records: list[dict] = []
            wrapped = {name: _make_tool_wrapper(name, fn, queue, writer_tool_records, caller_role)
                       for name, fn in tool_callables.items()}

            # Stream tokens to client
            writing_parts: list[str] = []
            writing_thinking: list[str] = []
            callback = create_thinking_callback(queue, writing_parts, writing_thinking)

            options = {"temperature": chat.text_temperature, "top_p": chat.text_top_p,
                       "repeat_penalty": chat.text_repeat_penalty}

            client = await get_llm_client_for_model(chat.text_model_id)
            async with client:
                await client.chat_with_tools(
                    writer_messages, tools_definitions=tool_defs, tools=wrapped,
                    system=system_prompt, options=options, max_loops=20,
                    stream=True, on_delta=callback,
                )

            prose_content = "".join(writing_parts)
            all_thinking_parts.extend(writing_thinking)
            all_tool_call_records.extend(writer_tool_records)

    # 6. Emit stat_update
    await queue.put(sse("stat_update", {"stats": {**char_stats, **world_stats}}))

    # 7. Finalize — same as current: save message, update session, snapshot, emit done
    # (GenerationPlanOutput from planning_contexts, save to ChatMessage.generation_plan)
    ...
```

### 7. Key Differences Between Tool and Writer Steps

| Aspect | Tool step | Writer step |
| --- | --- | --- |
| Text output | Discarded (only tool calls matter) | Streamed to client as narrative |
| SSE phase | `"planning"` | `"writing"` |
| Position | Any position, multiple allowed | Must be last |
| PlanningContext | Creates one per step, accumulates | Reads all accumulated contexts |
| LLM model | `chat.tool_model_id` (fallback: text) | `chat.text_model_id` |
| LLM options | tool_temperature/top_p/repeat_penalty | text_temperature/top_p/repeat_penalty |
| Message history | Full LLM messages (same as user sees) | Summaries + clean history + plan |
| `{TURN_FACTS}` | Facts from *previous* tool steps | Facts from *all* tool steps |
| `{TURN_DECISIONS}` | Decisions from *previous* tool steps | Decisions from *all* tool steps |

### 8. SSE Protocol — No Changes

The SSE protocol remains unchanged for backward compatibility:

- `step_type == "tool"` emits `phase: "planning"`
- `step_type == "writer"` emits `phase: "writing"`
- All other events unchanged: `token`, `thinking`, `tool_call_start`, `tool_call_result`, `stat_update`, `done`, `error`

Frontend receives the same events — no frontend SSE changes needed.

### 9. Edge Cases

**Empty prompt template** → fallback to old hardcoded builder. This ensures existing worlds continue working without admin intervention. The old prompt builders (`build_planning_system_prompt`, `build_writing_system_prompt`, `build_rich_chat_system_prompt`) are kept as fallbacks, not deleted.

**No tools selected** → `get_tools_by_names([])` returns empty lists. LLM runs without tools. For tool steps this is pointless (LLM has nothing to call), but not an error.

**Multiple tool steps** → each gets its own `PlanningContext`. Facts and decisions from all steps are merged in `build_turn_plan_parts()` for the writer. Stats are shared mutable dicts — changes in step 1 visible in step 2's `{CHARACTER_STATS}` / `{WORLD_STATS}`.

**Admin doesn't use all placeholders** → totally fine. Only used placeholders are resolved. Admin gets exactly the prompt they wrote.

**`{TURN_FACTS}` / `{TURN_DECISIONS}` in simple mode** → both resolve to empty string. No error.

**Planning tools in simple mode** → technically possible if admin adds `add_fact`/`add_decision`/`update_stat` to `simple_tools`. But since there's no `PlanningContext` in simple mode, these tools won't be instantiated. `get_tools_by_names()` requires `planning_context` param to create planning tool closures — if not provided, planning tools are silently skipped even if requested. The admin UI should show a note that planning tools are for chain mode tool steps.

---

## Implementation Order

1. `chat_context.py` — add `location_block`, `character_stats`, `world_stats` fields
2. `prompt_injection.py` — core engine (resolve, build_tools_description, build_turn_plan_parts)
3. ~~`default_templates.py` — done in Step 1~~
4. `chat_tools.py` — add `get_tools_by_names()` factory
5. `simple_generation_service.py` — refactor to use templates + tool selection
6. `chain_generation_service.py` — refactor to dynamic N-step loop
7. ~~Extend pipeline-config API endpoint — done in Step 1~~
8. Integration test: existing chain worlds still work
9. Integration test: custom prompts with placeholders resolve correctly

---

## Files Summary

| File | Action |
| --- | --- |
| `backend/app/services/chat_context.py` | Add `location_block`, `character_stats`, `world_stats` to ChatContext |
| `backend/app/services/prompts/prompt_injection.py` | NEW — resolve_prompt_template, build_tools_description, build_turn_plan_parts |
| `backend/app/services/prompts/default_templates.py` | EXISTS (Step 1) — DEFAULT_SIMPLE_PROMPT, DEFAULT_TOOL_PROMPT, DEFAULT_WRITER_PROMPT |
| `backend/app/services/chat_tools.py` | Add get_tools_by_names() |
| `backend/app/services/simple_generation_service.py` | Replace hardcoded prompt with template resolution |
| `backend/app/services/chain_generation_service.py` | Replace hardcoded 2-stage with dynamic N-step loop |
| `backend/app/routes/admin/worlds.py` | Already done (Step 1) — pipeline-config endpoint has default_templates |
| `backend/app/services/prompts/chat_system_prompt.py` | KEEP as fallback (no changes) |
| `backend/app/services/prompts/planning_system_prompt.py` | KEEP as fallback (no changes) |
| `backend/app/services/prompts/writing_system_prompt.py` | KEEP as fallback (no changes) |
| `backend/app/services/prompts/writing_plan_message.py` | KEEP as fallback (no changes) |
