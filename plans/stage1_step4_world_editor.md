# Stage 1 Step 4 — World Editor (Admin SPA)

## Context

After models (step 2) and LLM management (step 3), this step builds the world editor UI in the admin SPA. This is where editors create and manage worlds, documents, stats, and rules. Document editing uses a plain text editor — LLM-assisted editing is added in step 5.

---

## Page 1: Worlds List

- Route: `/admin/worlds`
- Table/list of all worlds with name, status, created/modified dates
- Actions:
  - **Create** new world
  - **Edit** existing world → navigates to world edit page
  - **Clone** existing world (deep copy: all documents, stats, rules, links)
  - **Delete** world — admin role only, blocked if world has active chats (show error)

---

## Page 2: World Edit

- Route: `/admin/worlds/:id/edit`
- Sections (documents are a separate page):

**Main fields**: name, description, lore (text area), system prompt (text area), initial message (text area — template for first chat message, supports `{character_name}`, `{location_name}`, `{location_summary}` placeholders), character template (text area with placeholder hints), status (draft/public/archived)

**World stats**: CRUD for world-scoped stat definitions (name, description, type: int/enum/set, default value, constraints)

**Character info**: character template preview, placeholder management (`{NAME}` mandatory + editor-defined custom placeholders)

**Character stats**: CRUD for character-scoped stat definitions (name, description, same types as world stats)

**Rules**: ordered list of rule strings, add/edit/delete/reorder

---

## Page 3: Documents Management

- Route: `/admin/worlds/:id/documents`
- Display: single table with type column (location/npc/lore_fact), filterable by type. Single table for now, but design components so it can be split into separate tabs later if needed. Vector search always spans all types regardless of UI layout.
- Columns: name (if applicable), type, excerpt, dates
- Actions:
  - **Create** new document (select type) → navigates to document edit page
  - **Edit** document → navigates to document edit page
  - **Delete** document(s)
  - **Upload** file(s) — markdown, upsert logic (match by name + type, update existing or create new)
  - **Download** single document as `.md` file
  - **Multi-select + download** as zip
  - **Download all** as zip

---

## Page 4: Document Edit

- Route: `/admin/worlds/:id/documents/:docId/edit`
- Layout varies by document type — fields shown/hidden based on `doc_type`
- Save triggers vector index rebuild for this document

### NPC Editor

- Name field
- Content textarea (markdown)
- Type indicator: `npc`
- **Available Locations** — multi-select picker of world locations (creates `present` links). No selections = NPC roams anywhere (default)
- **Prohibited Locations** — multi-select picker of world locations (creates `excluded` links)
- If exactly one Available location → auto-marked as **exclusive** (badge/color on the selected location)

### Location Editor

- Name field
- Content textarea (markdown)
- Type indicator: `location`
- Exits field (optional list of connected location IDs)
- **Linked NPCs** — multi-select picker of world NPCs (creates `present` links on NPC side)
- **Prohibited NPCs** — multi-select picker of world NPCs (creates `excluded` links on NPC side)
- NPCs that are exclusive to this location (only one `present` link, pointing here) shown with badge/color

### Lore Fact Editor

- Content textarea only (markdown)
- Type indicator: `lore_fact`
- No name field, no link fields

---

## API Endpoints

### Worlds
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/admin/worlds` | List all worlds |
| POST | `/api/admin/worlds` | Create world |
| GET | `/api/admin/worlds/:id` | Get world details |
| PUT | `/api/admin/worlds/:id` | Update world |
| POST | `/api/admin/worlds/:id/clone` | Clone world (deep copy) |
| DELETE | `/api/admin/worlds/:id` | Delete world (admin only, check active chats) |

### Documents (scoped to world)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/admin/worlds/:id/documents` | List documents (filterable by type) |
| POST | `/api/admin/worlds/:id/documents` | Create document |
| GET | `/api/admin/worlds/:id/documents/:docId` | Get document |
| PUT | `/api/admin/worlds/:id/documents/:docId` | Update document (triggers vector rebuild) |
| DELETE | `/api/admin/worlds/:id/documents/:docId` | Delete document |
| POST | `/api/admin/worlds/:id/documents/upload` | Upload markdown file(s), upsert |
| GET | `/api/admin/worlds/:id/documents/:docId/download` | Download single as .md |
| POST | `/api/admin/worlds/:id/documents/download` | Download selected as zip |
| GET | `/api/admin/worlds/:id/documents/download-all` | Download all as zip |

### Stats & Rules (scoped to world)
| Method | Path | Purpose |
|---|---|---|
| GET/POST/PUT/DELETE | `/api/admin/worlds/:id/stats` | CRUD stat definitions |
| GET/POST/PUT/DELETE | `/api/admin/worlds/:id/rules` | CRUD rules (with ordering) |

### NPC-Location Links
| Method | Path | Purpose |
|---|---|---|
| GET/POST/DELETE | `/api/admin/worlds/:id/npc-location-links` | Manage links |

---

## Frontend Components (Admin SPA)

| Component | Route | Purpose |
|---|---|---|
| WorldsList | `/admin/worlds` | List, create, clone, delete worlds |
| WorldEdit | `/admin/worlds/:id/edit` | Edit world fields, stats, rules |
| DocumentsList | `/admin/worlds/:id/documents` | Manage documents, upload, download |
| DocumentEdit | `/admin/worlds/:id/documents/:docId/edit` | Edit document text |

---

## Role Permissions

| Action | Required Role |
|---|---|
| View worlds list | editor |
| Create/edit/clone world | editor |
| Delete world | admin (+ no active chats) |
| Manage documents | editor |
| Manage stats/rules | editor |

---

## Embedding Integration

Document saves trigger vector indexing via the configured embedding server.

### Flow

1. Document created/updated -> saved to DB -> `vector_storage.index_document()` called
2. `index_document()` chunks text, calls `embedding.embed_texts()` using the designated LLM server
3. Embedded chunks stored in LanceDB

### When No Embedding Server Configured

- Document saves **succeed** -- data is persisted to DB
- Vector indexing is **skipped** -- `index_document()` returns `IndexResult(indexed=False, warning="...")`
- API response includes `embedding_warning` so frontend can show a notice

### Reindexing

- Admin triggers full reindex via "Reindex Vectors" button on DB Management page
- Calls `POST /api/admin/db/reindex-vectors`
- Required after changing embedding model -- old vectors are incompatible
- Reindex is **not** automatic on model change -- admin must trigger manually
