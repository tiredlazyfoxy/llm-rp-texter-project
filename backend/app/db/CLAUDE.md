# db/

Data access layer — DB-agnostic interface. Exposes business-level functions only — no sessions, connections, or ORM types leak out. The entire `db/` layer could be replaced with Mongo/Redis/file without changing services or routes. Config is injectable via `DbConfig` for tests and environments.

```
db/
  engine.py          — Async engine, injectable config, DDL, state flags
  users.py           — User CRUD (session-free, import as `from app.db import users`)
  worlds.py          — World CRUD
  locations.py       — WorldLocation CRUD
  npcs.py            — WorldNPC CRUD
  lore_facts.py      — WorldLoreFact CRUD
  npc_links.py       — NPCLocationLink CRUD
  stat_defs.py       — WorldStatDefinition CRUD
  rules.py           — WorldRule CRUD
  import_export_queries.py — export_table(), upsert_batch(), vector rebuild
  db_management.py         — DB introspection (table list, columns, counts, create)
```

**Rules:**
- DB layer depends only on models (never import from services or routes)
- All `session`, `AsyncSession`, `select()`, `session.exec()`, `session.add()` stay inside this folder
