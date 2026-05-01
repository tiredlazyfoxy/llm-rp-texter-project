# Feature 002 — User Chat

Global planner context for the user-facing chat experience: chat DB models, agent tools/prompts, chat API + UI, summarization.

## Files / References

- `docs/architecture/quick-reference.md` — condensed DB models, SSE protocol, tools
- `backend/CLAUDE.md` — backend structure
- `frontend/CLAUDE.md` — frontend routes/components
- Depends on Feature 001 (admin setup, world/LLM models)

## Facts

- LLM-driven RPG; actions/dialogue generated dynamically by an LLM agent using MCP-style tools.
- SSE streaming for chat responses.
- Chat sessions persisted with summarization for long-context handling.
