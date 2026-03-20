# Refactoring — Stage 1 Steps 1-2

## Context

After implementing stage1_step1 (auth/login) and stage1_step2 (world models), two issues need addressing:
1. `session.execute()` is deprecated in SQLModel — must use `session.exec()` everywhere
2. DB queries are mixed into services and routes — need clean DB/Service layer separation for testability

---

## 1. Replace Deprecated `session.execute()` with `session.exec()`

SQLModel's `session.exec()` returns scalars directly — no `.scalars()` call needed.

**Before:**
```python
result = await session.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()
# or
result = await session.execute(select(World))
items = result.scalars().all()
```

**After:**
```python
user = (await session.exec(select(User).where(User.id == user_id))).one_or_none()
# or
items = (await session.exec(select(World))).all()
```

### Files to update

| File | Lines | Count |
|---|---|---|
| `backend/app/services/auth.py` | 67, 93 | 2 |
| `backend/app/routes/auth.py` | 71 | 1 |
| `backend/app/services/db_import_export.py` | 67, 122, 166, 208, 248, 286, 336, 374 | 8 |
| `backend/app/services/vector_storage.py` | 262, 267, 272 | 3 |

**Total: 14 occurrences across 4 files.**

---

## 2. DB/Service Layer Separation

### Problem

Currently:
- `services/auth.py` (`verify_token`, `get_current_user`) does direct DB queries
- `routes/auth.py` (login handler) does direct DB queries
- No dedicated DB access layer — queries are scattered

### Target Architecture

```
routes/          — HTTP layer: parse request, call service, format response
  └→ services/   — Business logic: auth, validation, orchestration (NO direct DB)
       └→ db/    — Data access: all select/insert/update/delete queries
```

**New directory:** `backend/app/db/`

### New File: `backend/app/db/__init__.py`
Empty.

### New File: `backend/app/db/user_queries.py`

Pure DB query functions. Every function takes `session: AsyncSession` as first parameter.

```python
async def get_user_by_id(session, user_id: int) -> User | None
async def get_user_by_username(session, username: str) -> User | None
async def create_user(session, user: User) -> User
async def update_user(session, user: User) -> None
```

### Refactor: `backend/app/services/auth.py`

**Remove:** all `session.execute()` / `select()` calls and `get_session()` import.

- `verify_token(token)` → split into:
  - Keep pure JWT decode logic in auth.py
  - DB lookup moves to `get_current_user()` which calls `db/user_queries.py`
- `get_current_user(credentials, session)` → add `session` as FastAPI dependency, call `user_queries.get_user_by_id(session, user_id)`

### Refactor: `backend/app/routes/auth.py`

**Remove:** direct `select(User)` / `session.execute()` / `session.add()` calls.

- Login handler: call `user_queries.get_user_by_username(session, username)` instead of inline query
- After successful login: call `user_queries.update_user(session, user)` instead of inline `session.add/commit/refresh`

### Refactor: `backend/app/services/database.py`

- `create_database()` — call `user_queries.create_user(session, admin)` instead of inline `session.add/commit/refresh`

---

## 3. Update Documentation

### Update: `backend/CLAUDE.md`

Add a **Layer Separation** section after "Data Modeling":

```markdown
## Layer Separation

- **`routes/`** — HTTP layer only: parse requests, call services, format responses. No business logic, no direct DB queries.
- **`services/`** — Business logic: authentication, validation, orchestration. Receives session from route, passes to db layer. No `select()`, `session.exec()`, or `session.add()`.
- **`db/`** — Data access: all DB queries (select, insert, update, delete). Every function takes `session: AsyncSession` as first parameter. Pure queries, no business logic.
- **`models/`** — SQLModel table definitions + Pydantic schemas. No logic.

### Rules
- Routes depend on services and db
- Services depend on db (never import from routes)
- DB layer depends only on models (never import from services or routes)
- Import/export (`db_import_export.py`) lives in `services/` because it's serialization logic that calls db layer
```

### Update: `CLAUDE.md` (root)

Add to Backend Conventions:

```markdown
## Backend Layer Separation

- **routes/** — HTTP only (parse request, call service, return response)
- **services/** — Business logic (no direct DB queries)
- **db/** — All DB queries (every function takes `session` as first param)
- Services and routes never call `session.exec()` directly — always go through `db/` layer
```

---

## File Summary

| Action | File |
|--------|------|
| Create | `backend/app/db/__init__.py` |
| Create | `backend/app/db/user_queries.py` |
| Modify | `backend/app/services/auth.py` — remove DB queries, use db layer |
| Modify | `backend/app/routes/auth.py` — remove DB queries, use db layer |
| Modify | `backend/app/services/database.py` — use db layer for admin user creation |
| Modify | `backend/app/services/db_import_export.py` — replace `execute` with `exec` |
| Modify | `backend/app/services/vector_storage.py` — replace `execute` with `exec` |
| Modify | `backend/CLAUDE.md` — add Layer Separation section |
| Modify | `CLAUDE.md` (root) — add Backend Layer Separation rule |

---

## Verification

1. Start backend: `cd backend && uvicorn app.main:app --port 8085`
2. `GET /api/auth/status` → `{ "needs_setup": true }`
3. `POST /api/auth/setup/create` → JWT returned
4. `POST /api/auth/login` → JWT returned
5. `POST /api/auth/login` with wrong password → `Wrong credentials`
6. Grep for `session.execute` in backend — should return 0 hits
7. Grep for `select(` in routes/ and services/auth.py — should return 0 hits
