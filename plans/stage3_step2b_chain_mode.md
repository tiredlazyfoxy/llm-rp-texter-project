# Stage 3 Step 2b — Chain Mode Backend (Planning → Writing Pipeline)

## Context

Chain mode (`generation_mode == "chain"`) executes pipeline stages sequentially as defined in `World.pipeline` (PipelineConfig). The default setup is two stages: a planning stage (LLM with tools → structured JSON) followed by a writing stage (LLM → prose). The structure supports additional stages in the future.

Each stage has a `prompt` field — admin-editable free text that is combined with hardcoded structural instructions. The planning stage produces a `GenerationPlanOutput` (collected_data, decisions, stat_updates); the writing stage consumes it to generate narrative prose.

### Dependencies

- Stage 3 Step 1 (PipelineConfig, PipelineStage schemas, generation_mode, prompt skeletons)
- Stage 3 Step 2a (shared infrastructure: chat_tools, chat_context, stat_validation, rich prompt, dispatcher)

### Prompt Convention

All **pre-coded** (hardcoded) prompt parts — system prompts, structural instructions, JSON schema descriptions, tool usage instructions — must be placed in `backend/app/services/prompts/` as separate documented files following the stage-4 docstring convention (PURPOSE, USAGE, VARIABLES, DESIGN RATIONALE, CHANGELOG). Admin-editable parts (`PipelineStage.prompt`) are injected into these prompts as variables. No hardcoded prompt text in service files.

---

## 1. Chain Generation Service

### 1a. New File: `backend/app/services/chain_generation_service.py`

```python
async def generate_chain_response(
    session_id: int,
    user_id: int,
    user_message: str,
    caller_role: str,
) -> AsyncGenerator[str, None]:

async def regenerate_chain_response(
    session_id: int,
    user_id: int,
    caller_role: str,
) -> AsyncGenerator[str, None]:
```

### 1b. Flow — `generate_chain_response()`

**Setup:**
1. Load session, verify active + ownership
2. Load world, parse `PipelineConfig.model_validate_json(world.pipeline)`
3. Validate pipeline has at least one stage
4. Save user message to DB
5. Build context via `build_chat_context(session)`

**Stage Loop — iterate through `pipeline.stages`:**

**For `step_type == "planning"` stages:**

6. Yield `phase("planning")`, `status("Gathering context...")`
7. Build system prompt via `build_planning_system_prompt()`:
   - Full world context from ChatContext (location, NPCs, rules, stat defs, current stats, injected lore)
   - `stage.prompt` as admin-editable instructions
   - Character name/description
   - `session.user_instructions` — player's recommendations/feedback about RP flow (always included)
   - JSON output schema: instruct LLM to produce `GenerationPlanOutput` format
   - Tool usage instructions
   - "Do NOT write narrative prose. Only produce the JSON plan."
8. Build LLM message history via `_build_llm_messages(session_id)`
9. Get tools from `get_chat_tools(world_id, session_id)`
10. Wrap tools with SSE emission, **filtered by caller_role**:
    - Editor+: emit `tool_call_start`, `tool_call_result`, `thinking` events
    - Player: emit only `status` events (e.g. `status("Searching world knowledge...")`)
11. Get LLM client via `get_llm_client_for_model(session.tool_model_id)`
12. Call `client.chat_with_tools(messages, tool_defs, wrapped_tools, system, options, max_loops=stage.max_agent_steps or 10, stream=True, on_delta=callback)`
13. Parse final response as JSON → `GenerationPlanOutput`:
    - Primary: `json.loads(response_text)`
    - Fallback: regex `\{[\s\S]*\}` extraction, then `json.loads`
    - Failure: yield `error` SSE event, abort generation
14. Validate stat updates via `validate_and_apply_stat_updates(plan.stat_updates, stat_defs, char_stats, world_stats)`
15. Store plan for use by writing stage
16. Yield `stat_update` event (always — marks phase boundary)

**For `step_type == "writing"` stages:**

17. Yield `phase("writing")`, `status("Writing...")`
18. Build system prompt via `build_writing_system_prompt()`:
    - World name/description, character name/description
    - Injected lore
    - `stage.prompt` as admin-editable instructions
    - `session.user_instructions` — player's recommendations/feedback about RP flow (always included)
    - "Follow the generation plan faithfully. Do not add/remove/change plot points."
    - "Write immersive narrative prose. Include all NPC dialogue."
    - "Output ONLY narrative prose. No stats, JSON, tags, or meta-information."
19. Build writer message history:
    - Summaries (if any)
    - Clean messages (user + assistant only — no tool_calls content)
    - Plan message via `build_writing_plan_message(plan.collected_data, plan.decisions)`:
      ```
      ## Generation Plan

      ### Context
      {collected_data}

      ### What Happens This Turn
      - {decision 1}
      - {decision 2}
      - ...
      ```
20. Get LLM client via `get_llm_client_for_model(session.text_model_id)`
21. Stream via `client.chat(messages, system, options, stream=True, on_delta=callback)`
22. Callback emits `token` events (with thinking tag detection)

**Finalize:**

23. Save assistant message to DB:
    - `content` = prose output from writing stage
    - `generation_plan` = JSON string of `GenerationPlanOutput`
    - `tool_calls` = JSON array of tool call records from planning stage
24. Update session: increment turn, update stats (from validation step 14), update modified_at
25. Save snapshot with stats at this turn
26. Yield `done` with `ChatMessageResponse`

### 1c. Flow — `regenerate_chain_response()`

1. Mark current active assistant message as inactive (`is_active_variant=False`)
2. Reload user message for current turn
3. Restore stats from snapshot at turn-1
4. Re-run full pipeline (all stages from step 6 onwards)
5. Don't increment turn, update/create snapshot for current turn

### 1d. Visibility Rules

Based on `caller_role` parameter, filter which SSE events are emitted:

| Event | Player | Editor+ |
| ---- | ---- | ---- |
| `phase` | Yes | Yes |
| `status` | Yes | Yes |
| `tool_call_start` | No | Yes |
| `tool_call_result` | No | Yes |
| `thinking` | No | Yes |
| `thinking_done` | No | Yes |
| `stat_update` | Yes | Yes |
| `token` | Yes | Yes |
| `done` | Yes | Yes |
| `error` | Yes | Yes |

Implementation: check `caller_role` before `queue.put()` for filtered events.

### 1e. SSE Event Sequence

```
phase("planning") →
  status("Gathering context...") →
  [tool_call_start → tool_call_result]* →     (editor+ only)
  [thinking]*  →                               (editor+ only)
  status("Planning response...") →
  stat_update →
phase("writing") →
  status("Writing...") →
  [token]* →
done
```

---

## 2. DB Changes

### 2a. ChatMessage — New Column

**File**: `backend/app/models/chat_message.py`

```python
generation_plan: str | None = Field(default=None)  # JSON string of GenerationPlanOutput
```

Stores the planning stage output so editors can view generation details after the fact.

### 2b. ChatMessageResponse Schema

**File**: `backend/app/models/schemas/chat.py`

Add to `ChatMessageResponse`:
```python
generation_plan: str | None = None
```

### 2c. Chat Service Response Helper

**File**: `backend/app/services/chat_service.py`

Update `_msg_to_response()` to include `generation_plan=msg.generation_plan`.

### 2d. Import/Export

**File**: `backend/app/services/db_import_export.py`

- `_msg_to_dict()`: add `"generation_plan": msg.generation_plan`
- `_dict_to_msg()`: add `generation_plan=d.get("generation_plan")` — backward-compatible (None default)

---

## 3. Prompt Files (Fill In Skeletons)

### 3a. Planning System Prompt

**File**: `backend/app/services/prompts/planning_system_prompt.py`

Fill in `build_planning_system_prompt()` with actual prompt content:

**Coded part** (same for all worlds):
- Role definition: "You are a game planning agent..."
- World context sections (formatted from parameters)
- Tool usage instructions: list of available tools with descriptions
- JSON output schema: `GenerationPlanOutput` with field descriptions and example
- Constraints: "Do NOT write narrative prose. Only produce the JSON plan."
- Stat update instructions: "Only update stats that change. Use stat names exactly as defined."

**Admin part** (per-world):
- `admin_prompt` parameter injected as "World-Specific Instructions" section

**Player part** (per-session):
- `user_instructions` parameter injected as "Player Instructions" section — player's recommendations/feedback about RP flow, always included in all prompts when non-empty

### 3b. Writing System Prompt

**File**: `backend/app/services/prompts/writing_system_prompt.py`

Fill in `build_writing_system_prompt()`:

**Coded part**:
- Role definition: "You are a narrative writer for an RPG..."
- World name/description for tone
- Character context
- Constraints: "Follow the generation plan faithfully", "Output ONLY narrative prose"
- Injected lore for consistency

**Admin part**:
- `admin_prompt` parameter injected as "Writing Style Instructions" section

**Player part** (per-session):
- `user_instructions` — always included when non-empty

### 3c. Writing Plan Message

**File**: `backend/app/services/prompts/writing_plan_message.py`

Fill in `build_writing_plan_message()`:

```python
def build_writing_plan_message(collected_data: str, decisions: list[str]) -> str:
    decision_list = "\n".join(f"- {d}" for d in decisions)
    return f"""## Generation Plan

### Context
{collected_data}

### What Happens This Turn
{decision_list}"""
```

---

## 4. Files Summary

### Create

| File | What |
| ---- | ---- |
| `backend/app/services/chain_generation_service.py` | Chain mode: planning → writing |

### Modify

| File | Change |
| ---- | ---- |
| `backend/app/models/chat_message.py` | Add `generation_plan` column |
| `backend/app/models/schemas/chat.py` | Add `generation_plan` to ChatMessageResponse |
| `backend/app/services/chat_service.py` | Include `generation_plan` in `_msg_to_response()` |
| `backend/app/services/db_import_export.py` | Add `generation_plan` to ChatMessage export/import |
| `backend/app/services/prompts/planning_system_prompt.py` | Fill in actual prompt (from skeleton) |
| `backend/app/services/prompts/writing_system_prompt.py` | Fill in actual prompt (from skeleton) |
| `backend/app/services/prompts/writing_plan_message.py` | Fill in actual template (from skeleton) |

---

## 5. Verification

1. Chain mode activates when `world.generation_mode == "chain"` and pipeline has stages
2. Planning stage: LLM calls tools, gathers context, produces valid `GenerationPlanOutput` JSON
3. JSON parse fallback: regex extraction works when LLM wraps JSON in markdown or extra text
4. JSON parse failure: error SSE event emitted, no partial message saved
5. Stat updates from plan: validated against definitions, invalid ones skipped with log warning
6. Writing stage: receives plan as context, streams narrative prose
7. Prose output does not contain JSON, stat updates, or meta-information
8. `generation_plan` saved on assistant message, returned in ChatMessageResponse
9. Editor+ sees all events (tool calls, thinking); player sees only phase/status/token/done
10. Regeneration: re-runs all stages, stats reverted from previous snapshot
11. Tool errors during planning: error returned to LLM (doesn't crash), LLM continues
12. Import/export handles `generation_plan` column (backward-compatible)
