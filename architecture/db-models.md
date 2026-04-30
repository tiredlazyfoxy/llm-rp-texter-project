# DB Models

SQLModel table definitions live in [`backend/app/models/`](../backend/app/models/).

| Table | Key Fields |
|---|---|
| `users` | username, role (admin/editor/player), pwdhash, jwt_signing_key |
| `worlds` | name, system_prompt, simple_tools, character_template, generation_mode, pipeline, agent_config, status |
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
