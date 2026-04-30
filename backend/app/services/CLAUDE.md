# services/

Business logic — no direct DB queries, no session creation. No `session`, `AsyncSession`, `select()`, `session.exec()`, or `session.add()`.

```
services/
  snowflake.py       — Snowflake ID generator (int64)
  database.py        — DB setup orchestration (create/import)
  auth.py            — JWT create/verify, password hashing
  db_import_export.py — gzipped JSONL per table
  db_management.py    — DB introspection service (status, schema drift, create tables)
  prompts/           — LLM prompt package (see prompts/CLAUDE.md)
  chat_tools.py         — Universal tool registry (TOOL_REGISTRY, 12 tools) + ToolContext + build_tools(names, ctx). No per-stage factories — every caller selects tools by name and passes the state it has; missing required state → ValueError.
  chat_context.py       — Context builder for rich system prompts
  stat_validation.py    — Stat update validation against definitions
  chat_service.py       — Chat CRUD (sessions, messages, memories, rewind, edit/delete messages)
  chat_agent_service.py — Generation dispatcher (routes to mode-specific services)
  simple_generation_service.py  — Simple mode: single LLM call with tools
  chain_generation_service.py   — Chain mode: planning (tools → PlanningContext → GenerationPlanOutput) → writing pipeline
```

**Rules:**
- Services depend on db (never import from routes)
- Import/export serialization (`db_import_export.py`) stays here — it's format logic, not DB logic
