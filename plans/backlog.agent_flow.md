# Stage 5 — Agent-Subagent Generation Mode (Design)

## Overview

An alternative to the chain pipeline where a **main agent** delegates subtasks to specialized **sub-agents** (data collection, planning, writing). Each sub-agent has its own system prompt, tools, and context window.

## How It Works

1. Main agent receives the user message and session context
2. Main agent decides which sub-agents to invoke and in what order
3. Sub-agents run independently, returning results to the main agent
4. Main agent synthesizes sub-agent outputs into a final response

## Comparison with Chain Mode

| Aspect | Chain | Agentic |
|--------|-------|---------|
| Flow | Fixed stage order | Dynamic, agent-decided |
| Parallelism | Sequential | Sub-agents can run in parallel |
| Complexity | Simple, predictable | More flexible, harder to debug |
| Cost | 2 LLM calls | 3+ LLM calls |
| Control | Admin defines stages | Agent decides routing |

## Why Chain Was Chosen First

- Simpler to implement and debug
- Predictable execution flow (always planning → writing)
- Easier for world creators to understand and tune
- Lower token cost (2 calls vs N calls)
- Sufficient for most RPG scenarios

## When Agentic Might Be Better

- Complex quests with branching logic
- Parallel NPC interactions (multiple NPCs acting simultaneously)
- Scenarios requiring dynamic tool selection per subtask
- Multi-step reasoning where the planning itself needs sub-planning

## Implementation Notes

- Config stored in `World.agent_config` JSON field (separate from `pipeline`)
- Activated via `World.generation_mode = "agentic"`
- Service: `agent_generation_service.py` (dispatched by `chat_agent_service.py`)
- Currently disabled in admin UI with "coming soon" label
