# Stage 4 Step 2 — Agent Mode (Design Document)

## Context

This is a **design document** for the agentic generation mode (`generation_mode == "agentic"`). Not implemented yet — this documents the architecture for future work. The agent mode uses `World.agent_config` JSON field for configuration, separate from the chain pipeline's `World.pipeline`.

### Why This Exists

The chain mode (stage 3 step 2b) uses a fixed stage sequence: planning → writing. This works well for standard RP scenarios but has limitations:
- Fixed control flow — can't dynamically decide to gather more data mid-planning
- Single planning step — can't break complex decisions into sub-tasks
- No inter-agent communication — planning and writing are isolated

The agent mode addresses these by using an orchestrator that dynamically delegates to specialized sub-agents.

---

## 1. Architecture

### 1a. Main Orchestrator Agent

The main agent receives the user message and current context. It decides which sub-agents to invoke and in what order. It has access to sub-agent invocation as "tools" — each sub-agent call is a tool call from the orchestrator's perspective.

### 1b. Sub-Agents

| Sub-Agent | Purpose | Tools Available | Output |
| ---- | ---- | ---- | ---- |
| **Data Collector** | Gather world information relevant to the current situation | get_location_info, get_npc_info, search, get_lore, web_search, get_memory | Formatted context text |
| **Planner** | Analyze situation and decide what happens | None (receives collected data) | Structured plan (decisions, stat updates) |
| **Writer** | Generate narrative prose from the plan | None (receives plan + history) | Prose text |
| **Memory Manager** | Decide what to remember from this turn | add_memory | Memory entries |

### 1c. Orchestrator Flow (Conceptual)

```
User message arrives
  → Orchestrator assesses situation
  → Orchestrator calls Data Collector (possibly multiple times)
  → Orchestrator calls Planner with collected data
  → Orchestrator calls Writer with plan
  → Orchestrator optionally calls Memory Manager
  → Final prose streamed to user
```

The key difference: the orchestrator can call sub-agents in any order, multiple times, or skip them entirely based on the situation.

---

## 2. Comparison with Chain Mode

| Aspect | Chain | Agent |
| ---- | ---- | ---- |
| Control flow | Fixed stage sequence defined in PipelineConfig | Dynamic — orchestrator decides |
| Tool access | Planning stage has all tools | Data Collector sub-agent has world tools |
| Number of LLM calls | Fixed (one per stage) | Variable (orchestrator + N sub-agent calls) |
| Flexibility | Predictable, easy to debug | Adaptive, handles complex scenarios |
| Config field | `World.pipeline` (PipelineConfig) | `World.agent_config` (future schema) |
| Admin prompts | One per pipeline stage | One per sub-agent + orchestrator |
| Cost/latency | Lower (fewer LLM calls) | Higher (more LLM calls) |
| Best for | Standard RP, predictable scenarios | Complex quests, branching narratives, parallel NPC interactions |

---

## 3. Why Chain Was Chosen First

1. **Simpler to implement** — fixed stage sequence, no dynamic orchestration logic
2. **Easier to debug** — predictable event sequence, clear stage boundaries
3. **Admin-controllable** — prompts per stage give world creators direct control
4. **Lower cost** — exactly 2 LLM calls per turn (planning + writing)
5. **Sufficient for most RP** — standard scenarios don't need dynamic sub-agent delegation
6. **Shared infrastructure** — chat_tools, stat_validation, rich prompt all transfer to agent mode

---

## 4. Agent Config Schema (Future)

Will be stored in `World.agent_config` JSON field. Tentative schema:

```python
class SubAgentConfig(BaseModel):
    role: str                    # "data_collector" | "planner" | "writer" | "memory_manager"
    prompt: str = ""             # admin-editable instructions for this sub-agent
    max_steps: int | None = None # for tool-using sub-agents

class AgentConfig(BaseModel):
    orchestrator_prompt: str = ""           # instructions for the main orchestrator
    sub_agents: list[SubAgentConfig] = []   # configured sub-agents
    max_orchestrator_steps: int = 20        # prevent infinite delegation loops
```

### 4a. Admin UI for Agent Config

When `generation_mode == "agentic"`:
- Show orchestrator prompt editor (with LLM chat, like pipeline stage prompts)
- Show list of sub-agents with per-agent prompt editors
- Add/remove/reorder sub-agents
- Max steps configuration

This mirrors the chain pipeline stages UI but with richer configuration per sub-agent.

---

## 5. Implementation Notes (Future)

### 5a. Service File

**New file**: `backend/app/services/agent_generation_service.py`

```python
async def generate_agent_response(
    session_id: int,
    user_id: int,
    user_message: str,
    caller_role: str,
) -> AsyncGenerator[str, None]:
```

### 5b. Sub-Agent Invocation Pattern

Sub-agents are implemented as tool calls from the orchestrator:

```python
# Orchestrator's tool definitions include:
{
    "name": "call_data_collector",
    "description": "Gather world information...",
    "parameters": {"query": "what to look for"}
}
```

When orchestrator calls `call_data_collector`, the system:
1. Builds sub-agent prompt (coded part + admin part from SubAgentConfig)
2. Runs sub-agent LLM call (possibly with tools for data collector)
3. Returns sub-agent output as tool result to orchestrator

### 5c. Shared Infrastructure

Reuses everything from simple/chain modes:
- `chat_tools.py` — same tools, used by Data Collector sub-agent
- `chat_context.py` — same context builder
- `stat_validation.py` — same stat validation
- Rich system prompt — adapted for orchestrator
- SSE streaming — same event types + `phase` events per sub-agent

### 5d. SSE Events

Same as chain mode, with additional sub-agent phases:

```
phase("orchestrating") →
  phase("collecting_data") → [tool events] → phase("orchestrating") →
  phase("planning") → phase("orchestrating") →
  phase("writing") → [token]* →
done
```

---

## 6. Open Questions (To Resolve Before Implementation)

1. **Orchestrator model**: should orchestrator use tool_model or text_model? (Probably tool_model since it's making tool calls)
2. **Sub-agent streaming**: should writer sub-agent stream tokens through the orchestrator, or directly to the client?
3. **Error handling**: if a sub-agent fails, should orchestrator retry with a different approach?
4. **Stat updates**: should only the Planner sub-agent propose stat updates, or can the orchestrator also?
5. **Memory**: should Memory Manager be automatic (always runs) or orchestrator-decided?
6. **Cost controls**: how to limit total LLM calls per turn to prevent runaway costs?
