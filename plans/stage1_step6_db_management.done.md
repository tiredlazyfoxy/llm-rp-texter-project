# Stage 1 Step 6: DB Management Admin Page

## Context

The admin interface needs a "Database" page for DB introspection and maintenance. Currently there's no way to see what tables exist, whether they match model definitions, or manage import/export from within the admin UI. This page gives admins visibility into DB state and tools to fix schema drift or missing tables.

## What It Does

- Lists all registered SQLModel classes with their table names and record counts
- Detects schema drift: compares model fields vs actual SQLite columns
- Creates missing tables (per model)
- Export all data (reuses existing zip/JSONL.gz export)
- Import data from zip (reuses existing import)

---

## Backend

### 1. DB Layer: `backend/app/db/db_management.py` (NEW)

Raw SQLite introspection queries, session-managed internally.

Functions:
- `get_existing_tables() -> list[str]` — `SELECT name FROM sqlite_master WHERE type='table'`
- `get_table_columns(table_name: str) -> list[ColumnInfo]` — `PRAGMA table_info(table_name)`
- `get_record_count(table_name: str) -> int` — `SELECT COUNT(*) FROM table_name`
- `create_table(table_obj)` — `table_obj.create(bind=engine, checkfirst=True)` via `run_sync`

Uses `get_standalone_session()` and engine from `app.db.engine`.

### 2. Schemas: `backend/app/models/schemas/db_management.py` (NEW)

```python
class ColumnInfoSchema(BaseModel):
    name: str
    type: str

class TableStatusSchema(BaseModel):
    class_name: str
    table_name: str
    table_exists: bool
    record_count: int | None
    schema_status: str  # "ok" | "drift" | "missing"
    model_fields: list[ColumnInfoSchema]
    table_columns: list[ColumnInfoSchema]
    missing_columns: list[str]  # in model but not in table
    extra_columns: list[str]    # in table but not in model

class DbStatusResponse(BaseModel):
    tables: list[TableStatusSchema]
```

### 3. Service: `backend/app/services/db_management.py` (NEW)

- Imports `TABLE_REGISTRY` from `db_import_export.py`
- For each registered model: extract model columns from `model_class.__table__.columns`, compare with actual DB columns via `db_management` db layer
- Returns list of `TableStatusInfo` (TypedDict)

Functions:
- `get_db_status() -> list[TableStatusInfo]`
- `create_missing_table(table_name: str)` — lookup model by table_name, call db layer

### 4. Route: `backend/app/routes/admin/db_management.py` (NEW)

Prefix: `/api/admin/db`, all endpoints require admin role.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/db` | Get status of all tables |
| POST | `/api/admin/db/tables/{table_name}/create` | Create a missing table |
| GET | `/api/admin/db/export` | Download full DB export (zip) |
| POST | `/api/admin/db/import` | Upload and import zip file |

### 5. Wire up: `backend/app/main.py` (MODIFY)

Mount the new router.

### 6. Rename: `backend/app/services/db_import_export.py` (MODIFY)

Rename `_TABLE_REGISTRY` → `TABLE_REGISTRY` (make it public for service import).

---

## Frontend

### 7. Types: `frontend/src/types/dbManagement.d.ts` (NEW)

Matches backend schemas: `TableStatus`, `ColumnInfo`, `DbStatusResponse`.

### 8. API Client: `frontend/src/api/dbManagement.ts` (NEW)

- `getDbStatus()` — GET, returns `TableStatus[]`
- `createTable(tableName)` — POST
- `exportDb()` — GET, blob download (raw fetch, not authRequest — binary response)
- `importDb(file)` — POST FormData (raw fetch — multipart, not JSON)

### 9. Page: `frontend/src/admin/pages/DbManagementPage.tsx` (NEW)

Layout (follows existing page pattern):
- Title "Database" + global action buttons (Export All, Import)
- Table with columns: Class, Table, Records, Status, Actions
- Status badges: green=ok, yellow=drift, red=missing
- "Create Table" button on missing rows
- Expandable detail or modal for drift rows showing field comparison (model vs table columns, highlighting missing/extra)

### 10. Routing: `frontend/src/admin/App.tsx` (MODIFY)

- Add `{ icon: IconDatabase, label: "Database", href: "/admin/database" }` to NAV_ITEMS
- Add route: `if (path.startsWith("/admin/database")) return <DbManagementPage />`

---

## Key Files to Reuse

- `backend/app/services/db_import_export.py` — `TABLE_REGISTRY`, `export_all()`, `import_all()`
- `backend/app/db/engine.py` — `get_standalone_session()`, engine access, `_engine`
- `backend/app/db/import_export_queries.py` — pattern for raw SQL via engine
- `backend/app/routes/llm_servers.py` — pattern for admin route structure
- `frontend/src/admin/pages/LlmServersPage.tsx` — pattern for page component

## Implementation Order

1. Backend DB layer (`db/db_management.py`)
2. Backend schemas (`models/schemas/db_management.py`)
3. Rename `_TABLE_REGISTRY` → `TABLE_REGISTRY` in `db_import_export.py`
4. Backend service (`services/db_management.py`)
5. Backend route (`routes/admin/db_management.py`)
6. Wire up in `main.py`
7. Frontend types (`types/dbManagement.d.ts`)
8. Frontend API client (`api/dbManagement.ts`)
9. Frontend page (`admin/pages/DbManagementPage.tsx`)
10. Frontend routing (`admin/App.tsx`)

## Verification

1. Start backend: `uvicorn app.main:app --port 8085 --reload`
2. Start frontend: `npm run dev`
3. Login as admin, navigate to /admin/database
4. Verify all 9 model classes show with correct counts and "ok" status
5. Test export — downloads zip file
6. Test import — upload the exported zip, verify counts remain
7. To test "missing" status: manually drop a table in SQLite, refresh page, verify badge shows red, click "Create Table", verify it recreates
8. To test "drift": manually add/remove a column in SQLite, refresh, verify yellow badge and field comparison detail
