# Feature 004 Step 005: Split Research from Planning

## Context

Step 4 introduced tool-based planning: the planning LLM uses `add_fact`, `add_decision`, `update_stat` tools to build a `PlanningContext` instead of outputting JSON. This step splits the combined planning stage into separate **research** and **planning** stages, each with its own LLM call, tool set, system prompt, and admin-editable prompt.

**Why split?** A research stage focused purely on gathering facts (cheap, fast model) produces better context than asking one LLM call to simultaneously gather info AND make creative decisions. The planning stage can then focus on decisions with all facts already collected.

**Depends on**: Feature 004 Step 004 (tool-based PlanningContext) must be implemented first.

## Design

### New Stage Types

| step_type | Tools | Purpose | Model |
|-----------|-------|---------|-------|
| `"research"` | 8 read tools + `add_fact` | Gather context, record facts | `tool_model_id` |
| `"planning"` | `add_decision` + `update_stat` + read tools | Make decisions, update stats | `tool_model_id` |
| `"writing"` | 5 read-only tools | Write prose | `text_model_id` |

**Shared state**: All pre-writing stages share a single `PlanningContext` instance. Research fills `facts`, planning fills `decisions` and `stat_updates`.

### Pipeline Configs (examples)

**2-stage (backward compatible — same as step 4):**
```json
{
  "stages": [
    {"step_type": "planning", "prompt": "...", "max_agent_steps": 10},
    {"step_type": "writing", "prompt": "..."}
  ]
}
```
Planning stage still gets ALL planning tools (add_fact + add_decision + update_stat).

**3-stage (new):**
```json
{
  "stages": [
    {"step_type": "research", "prompt": "...", "max_agent_steps": 10},
    {"step_type": "planning", "prompt": "...", "max_agent_steps": 5},
    {"step_type": "writing", "prompt": "..."}
  ]
}
```

### Per-Stage Model Selection (new field)

Add optional `model_id` to `PipelineStage`:
```python
class PipelineStage(BaseModel):
    step_type: str          # "research" | "planning" | "writing"
    prompt: str = ""
    max_agent_steps: int | None = None
    model_id: str | None = None   # NEW — override session model for this stage
```

Resolution order: `stage.model_id` → session's `tool_model_id`/`text_model_id` → error.

This allows a cheap fast model for research, a smart model for planning, a creative model for writing — all configured per-world.

---

## Changes

### 1. `backend/app/models/schemas/pipeline.py` — Add model_id to PipelineStage

```python
class PipelineStage(BaseModel):
    step_type: str  # "research" | "planning" | "writing"
    prompt: str = ""
    max_agent_steps: int | None = None
    model_id: str | None = None  # optional per-stage model override
```

No migration needed — new field has default `None`, existing JSON configs are backward compatible.

### 2. `frontend/src/types/world.d.ts` — Add model_id to PipelineStage interface

```typescript
export interface PipelineStage {
  step_type: string;
  prompt: string;
  max_agent_steps: number | null;
  model_id: string | null;  // NEW
}
```

### 3. `backend/app/services/chat_tools.py` — Research tool factory

Add new factory:
```python
def get_research_tools(
    world_id: int,
    session_id: int,
    planning_context: PlanningContext,
) -> tuple[list[dict], dict[str, Callable]]:
```

Returns 8 read tools + `add_fact` only. No `add_decision`, no `update_stat`.

**Existing factories after step 4+5:**

| Factory | Tools | Used by |
|---------|-------|---------|
| `get_chat_tools()` | 8 standard tools | Simple mode |
| `get_research_tools()` | 8 standard + `add_fact` | Research stage |
| `get_planning_tools()` | 8 standard + `add_fact` + `add_decision` + `update_stat` | Planning stage (combined or split) |
| `get_writer_tools()` | 5 read-only tools | Writing stage |

Note: `get_planning_tools()` from step 4 still includes `add_fact` — so the combined "planning" stage (without separate research) still works.

### 4. `backend/app/services/prompts/` — Research system prompt

**New file: `research_system_prompt.py`**

`build_research_system_prompt()` — same inputs as planning prompt, but:
- Role: "You are a research agent. Your job is to gather all context the planning agent needs."
- Instructions: Use read tools to find relevant info, call `add_fact(content)` for each finding
- No decisions, no stat updates — those are for the planning stage
- Same world/location/NPC/rules/stats context sections as planning prompt
- Admin prompt from `stage.prompt`

### 5. `backend/app/services/prompts/planning_system_prompt.py` — Update for split mode

When research stage exists (facts already gathered), the planning prompt should:
- Include the collected facts as context: "The research agent has gathered these facts: ..."
- Instruct: "Based on the facts above, make decisions about what happens this turn"
- Tools: `add_decision` + `update_stat` (+ read tools for any follow-up lookups)
- No `add_fact` instructions (research already done)

When no research stage (combined mode), planning prompt stays as in step 4 — full instructions for research + decisions + stats.

**Implementation**: Add a `facts_already_collected: list[str] | None = None` parameter to `build_planning_system_prompt()`. When provided, inject facts and adjust instructions.

### 6. `backend/app/services/chain_generation_service.py` — Sequential stage execution

**Major refactor**: Replace the current `if planning_stage: ... if writing_stage: ...` pattern with a **stage loop**:

```python
planning_context = PlanningContext()

for stage in pipeline.stages:
    if stage.step_type == "research":
        await _run_research_stage(stage, ...)
    elif stage.step_type == "planning":
        await _run_planning_stage(stage, planning_context, ...)
    elif stage.step_type == "writing":
        await _run_writing_stage(stage, planning_context, ...)
```

Each `_run_*_stage()` is an extracted function handling:
- Model resolution: `stage.model_id` or session fallback
- Tool selection: factory based on stage type
- System prompt: builder based on stage type
- LLM call: `chat_with_tools` with stage-specific options
- SSE events: `phase` event with stage type name

**Model resolution per stage:**
```python
def _resolve_model(stage: PipelineStage, chat: ChatSession) -> str:
    if stage.model_id:
        return stage.model_id
    if stage.step_type in ("research", "planning"):
        return chat.tool_model_id or chat.text_model_id
    return chat.text_model_id  # writing
```

**PlanningContext sharing**: Created once before the loop, passed to all pre-writing stages. Research fills `facts`, planning fills `decisions`/`stat_updates`. Writing reads from the converted `GenerationPlanOutput`.

### 7. `frontend/src/admin/pages/WorldEditPage.tsx` — Add "Research" to stage dropdown

Update the stage type Select options (line 528-529):
```typescript
{ value: "research", label: "Research" },
{ value: "planning", label: "Planning" },
{ value: "writing", label: "Writing" },
```

Update `max_agent_steps` default — show for both research and planning (line 555):
```typescript
{(stage.step_type === "planning" || stage.step_type === "research") && (
```

Add model_id selector per stage — a Select dropdown with available models (from LLM servers API). Show for all stage types. Optional (null = use session default).

### 8. `frontend/src/admin/pages/PipelineStageEditPage.tsx` — No structural changes

The stage prompt editor works the same for all stage types — it edits `stage.prompt` via LLM chat. No changes needed.

---

## Documentation Changes

### 9. `docs/architecture/quick-reference.md`

**Generation Modes section (lines 211-217):**
- Update chain mode: describe 2-stage (planning+writing) and 3-stage (research+planning+writing) configurations
- Show both example configs with JSON

**Pipeline Config section (lines 221-229):**
- Add `model_id: str | null` field to PipelineStage schema
- Update `step_type` values: `"research" | "planning" | "writing"`
- Add 3-stage example config alongside existing 2-stage

**Chat Tools section (lines 168-185):**
- Add `get_research_tools()` factory to the tools table: "8 standard + add_fact"
- Update `get_planning_tools()` description to show it includes all 3 planning tools
- Show which tools are available at each stage type

**SSE Streaming Protocol (lines 111-135):**
- Update chain mode event order to show 3-stage: `phase("research")` → `phase("planning")` → `phase("writing")`

### 10. `docs/architecture/backend.md`

**Generation Modes section (lines 220-237):**
- Update chain mode: "configurable multi-stage pipeline: research → planning → writing (or combined planning → writing)"
- Note PlanningContext shared across pre-writing stages
- Document per-stage model override via `stage.model_id`

**Prompt Architecture section (lines 239-255):**
- Add `research_system_prompt.py` — "Research stage prompt: gather context via tools, call add_fact"
- Note planning prompt adapts when facts already collected by research stage

**Directory Structure (lines 34-44):**
- Add line: `research_system_prompt.py   — Research stage system prompt (chain mode)`
- Update `chain_generation_service.py` description: "Chain mode: sequential stage execution (research → planning → writing)"

### 11. `backend/CLAUDE.md`

**Generation Modes section (lines 56-64):**
- Update chain description: "Configurable stages from `World.pipeline` JSON. Default: planning → writing. Optional: research → planning → writing. Each stage can override model via `stage.model_id`."
- Service: `chain_generation_service.py`

**Directory Structure - services/prompts (lines 34-37):**
- Add line: `research_system_prompt.py    — Research stage system prompt (chain mode)`

**Directory Structure - services (line 44):**
- Update `chat_tools.py` to: "Chat tool implementations (8 tools) + planning tools (3) + factories (chat/research/planning/writer)"

### 12. `frontend/CLAUDE.md`

**Debug Mode section (lines 77-85):**
- Update: "Generation plan visible (chain mode: collected facts from research, decisions from planning, stat_updates)"

**Admin SPA Routes (line 53):**
- No route changes, but note that PipelineStageEditPage now handles research/planning/writing stage types

### Documentation NOT changed

- `docs/architecture/system-overview.md` — high-level, no pipeline details
- `docs/architecture/auth.md`, `docs/architecture/deployment.md`, `docs/architecture/dev-environment.md` — unrelated

---

## Files Summary

| File | Change |
|------|--------|
| `backend/app/models/schemas/pipeline.py` | Add `model_id` to PipelineStage |
| `frontend/src/types/world.d.ts` | Add `model_id` to PipelineStage interface |
| `backend/app/services/chat_tools.py` | Add `get_research_tools()` factory |
| `backend/app/services/prompts/research_system_prompt.py` | **New file** — research stage system prompt |
| `backend/app/services/prompts/planning_system_prompt.py` | Add `facts_already_collected` parameter for split mode |
| `backend/app/services/chain_generation_service.py` | Refactor to sequential stage loop with extracted stage runners |
| `frontend/src/admin/pages/WorldEditPage.tsx` | Add "Research" to stage dropdown, model_id selector per stage |
| `docs/architecture/quick-reference.md` | Update generation modes (2/3-stage), pipeline config (model_id, step_types), tools (research factory), SSE events |
| `docs/architecture/backend.md` | Update generation modes, prompt architecture (research prompt), directory structure |
| `backend/CLAUDE.md` | Update generation modes (configurable stages), directory structure (research prompt, tool factories) |
| `frontend/CLAUDE.md` | Update debug mode description |

## Implementation Order

1. `pipeline.py` — add `model_id` to PipelineStage
2. `world.d.ts` — add `model_id` to frontend type
3. `chat_tools.py` — add `get_research_tools()` factory
4. `research_system_prompt.py` — new file
5. `planning_system_prompt.py` — add `facts_already_collected` parameter
6. `chain_generation_service.py` — refactor to stage loop
7. `WorldEditPage.tsx` — add Research option + model_id selector
8. Documentation — update all 4 doc files

## Verification

1. **2-stage config (backward compat)**: Existing planning+writing config works unchanged
2. **3-stage config**: Create world with research → planning → writing, verify:
   - Research stage: server logs show read tools + `add_fact` calls, no `add_decision`
   - Planning stage: receives facts, logs show `add_decision` + `update_stat` calls
   - Writing stage: receives full plan, produces prose
3. **Per-stage model**: Set different `model_id` on research vs planning, verify logs show correct model used
4. **SSE phases**: Frontend shows phase transitions: "research" → "planning" → "writing"
5. **Admin UI**: "Research" appears in stage dropdown, model_id selector works, existing worlds unaffected

## Risks

- **Prompt quality for split stages**: Research needs clear instructions on what to gather vs skip. Planning needs to work with pre-gathered facts without re-researching. Both need testing with actual LLMs.
- **Stage ordering validation**: No enforcement that research comes before planning or writing is last. Could add validation but may not be worth the complexity — admin misconfiguration is self-correcting (bad results, not errors).
- **Model availability**: Per-stage model_id might reference a model that's offline. Existing error handling (`get_llm_client_for_model` raises 404) covers this.
