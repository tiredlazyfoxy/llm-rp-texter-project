# services/

Business logic — no direct DB queries, no session creation. No `session`, `AsyncSession`, `select()`, `session.exec()`, or `session.add()`.

```
services/
  snowflake.py       — Snowflake ID generator (int64)
  database.py        — DB setup orchestration (create/import)
  auth.py            — JWT create/verify, password hashing
  pipelines.py       — Pipeline validation + CRUD orchestration (kind, simple_tools, pipeline_config)
  db_import_export.py — gzipped JSONL per table
  db_management.py    — DB introspection service (status, schema drift, create tables)
  prompts/           — LLM prompt package (see prompts/CLAUDE.md)
  chat_tools.py         — Universal tool registry (TOOL_REGISTRY, 12 tools) + ToolContext + build_tools(names, ctx). No per-stage factories — every caller selects tools by name and passes the state it has; missing required state → ValueError. ToolContext.runtime_placeholders is populated for chat-bound construction and left None for editor-bound construction (the layering that keeps admin_tools.py raw while making chat_tools.py substitute).
  chat_context.py       — Context builder for rich system prompts. ChatContext exposes character_stats_raw / world_stats_raw (parsed JSON dicts) so downstream chat-runtime sites consume one source.
  stat_validation.py    — Stat update validation against definitions. Hosts validate_and_apply_stat_updates (LLM-tool path, silent-skip), validate_single_value (per-value), and apply_admin_stat_updates (admin-route adapter for PUT /api/chats/:id/stats — all-or-nothing 422 vs the LLM tool's silent-skip).
  runtime_placeholders.py — Pure helper apply_runtime_placeholders(text, ctx) — single substitution implementation for chat-runtime placeholder tokens (Feature 010 + Feature 012 namespaced stats). build_stat_values_map(stat_defs, character_stats, world_stats) is the centralized (StatScope -> owner-token) builder; every chat-runtime entrypoint calls it.
  chat_service.py       — Chat CRUD (sessions, messages, memories, rewind, edit/delete messages). character_name uses a trim-and-reject validator shared with the API schemas.
  chat_agent_service.py — Generation dispatcher (routes to mode-specific services). Owns no chat-runtime context — pure dispatcher.
  world_editor.py       — Document upload accepts location (upsert by lowercased filename stem), npc (upsert by lowercased filename stem), lore_fact (always create — no name field on WorldLoreFact).
  simple_generation_service.py  — Simple mode: single LLM call with tools
  chain_generation_service.py   — Chain mode: planning (tools → PlanningContext → GenerationPlanOutput) → writing pipeline
  prompts/stat_placeholders_section.py — Shared "## Stat Placeholders" markdown section consumed by both editor system prompts; empty stat_defs returns "" so callers omit the section.
```

**Rules:**
- Services depend on db (never import from routes)
- Import/export serialization (`db_import_export.py`) stays here — it's format logic, not DB logic
