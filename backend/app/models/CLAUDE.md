# models/

SQLModel DB models + Pydantic API schemas. No logic.

See [`architecture/db-models.md`](../../../architecture/db-models.md) for the table reference.

```
models/
  schemas/           — Pydantic request/response schemas (auth.py, chat.py, db_management.py, pipeline.py)
  user.py, world.py, llm_server.py, chat_session.py, chat_message.py, ...
```
