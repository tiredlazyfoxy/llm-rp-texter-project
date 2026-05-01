# models/

SQLModel DB models + Pydantic API schemas. No logic.

See [`docs/architecture/db-models.md`](../../../docs/architecture/db-models.md) for the table reference.

```
models/
  schemas/           — Pydantic request/response schemas (auth.py, chat.py, db_management.py, pipeline.py)
  user.py, world.py, pipeline.py, llm_server.py, chat_session.py, chat_message.py, ...
```
