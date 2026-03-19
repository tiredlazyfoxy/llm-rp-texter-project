# Stage 1 Step 4 — World Editor (Admin SPA)

## Context

After models (step 2) and LLM management (step 3), this step builds the world editor UI in the admin SPA. This is where editors create and manage worlds, documents, stats, and rules. Document editing uses a plain text editor — LLM-assisted editing is added in step 5.

---

## Page 1: Worlds List

- Route: `/admin/worlds`
- Table/list of all worlds with name, status, created/modified dates
- Actions:
  - **View** world → navigates to world view page
  - **Create** new world
  - **Clone** existing world (deep copy: all documents, stats, rules, links)
  - **Delete** world — admin role only, blocked if world has active chats (show error)

---

## Page 2: World View (tabbed)

- Route: `/admin/worlds/:id`
- Tabs: Info, All Docs, Locations, NPCs, Lore Facts, Chats

**Info tab**: Read-only world overview (name, status badge, description, lore, counts, stats summary, rules summary). "Edit World" button links to `/admin/worlds/:id/edit`.

**Document tabs** (All Docs / Locations / NPCs / Lore Facts): Document table filtered by type. Create, upload, download all, reindex world, per-doc edit/download/delete.

**Chats tab**: Read-only list of chats for this world (author, date, message count). Placeholder until Stage 2.

---

## Page 3: World Edit

- Route: `/admin/worlds/:id/edit`
- Back button → `/admin/worlds/:id` (view page)

**Main fields**: name, description, lore (text area), system prompt (text area), initial message (text area — template for first chat message, supports `{character_name}`, `{location_name}`, `{location_summary}` placeholders), character template (text area with placeholder hints), status (draft/public/private/archived)

**World stats**: CRUD for world-scoped stat definitions (name, description, type: int/enum/set, default value, constraints)

**Character info**: character template preview, placeholder management (`{NAME}` mandatory + editor-defined custom placeholders)

**Character stats**: CRUD for character-scoped stat definitions (name, description, same types as world stats)

**Rules**: ordered list of rule strings, add/edit/delete/reorder

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
| POST | `/api/admin/worlds/:id/reindex` | Reindex all documents for this world |

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
| WorldsListPage | `/admin/worlds` | List, create, clone, delete worlds |
| WorldViewPage | `/admin/worlds/:id` | Tabbed view: info, documents, chats |
| WorldEditPage | `/admin/worlds/:id/edit` | Edit world fields, stats, rules |
| DocumentEditPage | `/admin/worlds/:id/documents/:docId/edit` | Edit document text |

---

## Role Permissions

| Action | Required Role |
|---|---|
| View worlds list | editor |
| Create/edit/clone world | editor |
| Delete world | admin (+ no active chats) |
| Manage documents | editor |
| Manage stats/rules | editor |
| Reindex world | editor |

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
- Per-world reindex available via "Reindex" button on world view page
- Calls `POST /api/admin/worlds/:id/reindex`
