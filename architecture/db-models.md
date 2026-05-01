# DB Models

SQLModel table definitions live in [`backend/app/models/`](../backend/app/models/).

| Table | Key Fields |
|---|---|
| `users` | username, role (admin/editor/player), pwdhash, jwt_signing_key |
| `worlds` | name, description, character_template, initial_message, pipeline_id (FK pipelines.id, nullable), status, owner_id |
| `pipelines` | name, description, kind (simple/chain/agentic), system_prompt, simple_tools, pipeline_config, agent_config |
| `world_locations` | world_id, name, content, exits |
| `world_npcs` | world_id, name, content |
| `world_lore_facts` | world_id, content, is_injected (bool), weight (int) |
| `npc_location_links` | npc_id, location_id, link_type (present/excluded) |
| `world_stat_definitions` | world_id, name, scope, stat_type, constraints, hidden |
| `world_rules` | world_id, rule_text, order |
| `llm_servers` | name, backend_type, base_url, enabled_models, is_embedding, embedding_model |
| `chat_sessions` | user_id, world_id, current_location_id, tool_model_id, text_model_id, character_stats, world_stats, current_turn, generation_variants (JSON) |
| `chat_messages` | session_id, role, content, turn_number, tool_calls, generation_plan, thinking_content, is_active_variant |
| `chat_state_snapshots` | session_id, turn_number, location_id, character_stats, world_stats |
| `chat_summaries` | session_id, start/end turn, content |
| `chat_memories` | session_id, content |

## Notes

- **Feature 007 — pipelines extracted from worlds.** Generation flows (simple / chain / agentic) live on the `pipelines` table; worlds reference one via `world.pipeline_id`. The legacy world columns `system_prompt`, `simple_tools`, `pipeline`, `generation_mode`, `agent_config` remain on the schema but are write-dead — kept for old-export backward compat and one-shot rollback. Cleanup of those columns is a planned follow-up.
- **`world.lore`** continues to be deprecated (unchanged by Feature 007).
