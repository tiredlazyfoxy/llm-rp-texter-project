# models/

SQLModel DB models + Pydantic API schemas. No logic.

See [`docs/architecture/db-models.md`](../../../docs/architecture/db-models.md) for the table reference.

```
models/
  schemas/           — Pydantic request/response schemas (auth.py, chat.py, db_management.py, pipeline.py)
  user.py, world.py, pipeline.py, llm_server.py, chat_session.py, chat_message.py, ...
```

## Schema notes

- **`schemas/chat.py`**:
  - `UpdateChatSettingsRequest` accepts three optional fields: `tool_model`, `text_model`, `character_name` (Feature 011). `character_name` uses a trim-and-reject validator shared with `CreateChatRequest` — HTTP 400 on empty / whitespace-only.
  - `StatUpdateItem` / `UpdateChatStatsRequest` / `UpdateChatStatsResponse` (Feature 012) back `PUT /api/chats/:id/stats`. `chat_id` serializes as a string (Snowflake convention). Response `applied` echoes the **requested** (pre-clamp) values; clients should re-fetch for a faithful refresh.
