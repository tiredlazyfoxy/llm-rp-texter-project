# Stage 1 Step 2 — World Models, Documents, Vector Storage, Stats & Rules

## Context

After login/auth (step 1), this step defines the core data models for the RPG world system. These are the foundational entities that everything else builds on: worlds, knowledge documents, vector search, character/world stats, and game rules. This step is **models and storage only** — no APIs or UI yet.

---

## 1. World Model

Top-level entity. Server can host multiple worlds. Editors (role >= editor) can create new worlds.

| Field | Type | Notes |
|---|---|---|
| `id` | int64 (snowflake) | Primary key |
| `name` | str | World name |
| `description` | str | World description |
| `lore` | str (text) | Visible to users — world lore/background |
| `system_prompt` | str (text) | Hidden from users — injected into LLM context |
| `character_template` | str (text) | Character description with `{PLACEHOLDER}` tokens — `{NAME}` is mandatory, editors can define additional custom placeholders. Users fill all placeholders when starting a chat. |
| `pipeline` | str (JSON) | Chat generation pipeline definition. Stored as JSON string in SQLite, default `"{}"`. Internal model TBD — for now treated as opaque JSON. |
| `status` | enum: draft / public / archived | Controls visibility |
| `created_at` | datetime | Auto-set on create |
| `modified_at` | datetime | Auto-set on create/update |

---

## 2. Knowledge Documents

Documents are **plain text** (uploaded as markdown or created inline via form). Stored in both **SQLite** (full text) and **vector storage** (chunked for search).

### 2a. Document Types — Separate Tables

Three knowledge types, each in its own table, all scoped to a world:

**Location** (`world_locations`):

| Field | Type | Notes |
|---|---|---|
| `id` | int64 (snowflake) | Primary key |
| `world_id` | int64 | FK → World |
| `name` | str | Location name |
| `content` | str (text) | Full document text (markdown) |
| `exits` | str (JSON array) \| None | Optional list of connected location IDs (int64 as strings). None = can travel anywhere ("teleport"). Reserved for future movement restrictions — not enforced in stage 1. |
| `created_at` | datetime | |
| `modified_at` | datetime | |

**NPC** (`world_npcs`):

| Field | Type | Notes |
|---|---|---|
| `id` | int64 (snowflake) | Primary key |
| `world_id` | int64 | FK → World |
| `name` | str | NPC name |
| `content` | str (text) | Full document text (markdown) |
| `created_at` | datetime | |
| `modified_at` | datetime | |

**Lore Fact** (`world_lore_facts`):

| Field | Type | Notes |
|---|---|---|
| `id` | int64 (snowflake) | Primary key |
| `world_id` | int64 | FK → World |
| `content` | str (text) | Full document text (markdown) |
| `created_at` | datetime | |
| `modified_at` | datetime | |

### 2b. Document Input

- **Upload**: markdown file, well-formatted
- **Create inline**: form with text editor
- Every document update triggers vector index rebuild for that document's chunks

### 2c. Location–NPC Relationships

Many-to-many link table with presence/exclusion semantics:

**NPC–Location Link** (`npc_location_links`):

| Field | Type | Notes |
|---|---|---|
| `id` | int64 (snowflake) | Primary key |
| `npc_id` | int64 | FK → NPC |
| `location_id` | int64 | FK → Location |
| `link_type` | enum: present / excluded | Default (no links) = NPC roams anywhere. 'excluded' restricts. 'present' pins to specific locations. |

---

## 3. Vector Storage (LanceDB)

LanceDB for vector search, scoped per world.

### Vector Chunk Record

| Field | Type | Notes |
|---|---|---|
| `id` | str | Chunk ID |
| `world_id` | int64 | Scope searches to specific world |
| `source_type` | enum: location / npc / lore_fact | What kind of knowledge |
| `source_id` | int64 | FK → source table record |
| `chunk_index` | int | Order within source document |
| `text` | str | Chunk text content |
| `vector` | float[] | Embedding vector |

### Key behaviors

- On document **create/update**: chunk the text, embed, delete old chunks for that `source_id`, insert new chunks
- On document **delete**: delete all chunks for that `source_id`
- **Search**: filter by `world_id`, optionally by `source_type`
- Embedding model TBD (configurable — will be part of LLM client setup)

### Dependency

- Add `lancedb` to `pyproject.toml`

---

## 4. Stats System

Stats are **defined per world** (schema/template) and **valued per chat session** (character stats) or per world instance (world stats).

### 4a. Stat Definitions (per world)

**Stat Definition** (`world_stat_definitions`):

| Field | Type | Notes |
|---|---|---|
| `id` | int64 (snowflake) | Primary key |
| `world_id` | int64 | FK → World |
| `name` | str | Stat name (e.g. "health", "weather") |
| `description` | str | Human-readable explanation sent to LLM so it understands the stat's meaning (e.g. "Physical well-being, 0 = dead, 100 = full health") |
| `scope` | enum: character / world | Who this stat belongs to |
| `stat_type` | enum: int / enum / set | Value type |
| `default_value` | str (JSON) | Default value — int: "50", enum: "sunny", set: '["fire","ice"]' |
| `min_value` | int \| None | For int type: minimum (0) |
| `max_value` | int \| None | For int type: maximum (100) |
| `enum_values` | str (JSON array) \| None | For enum/set types: list of allowed values |

### 4b. Stat Types

- **int**: integer 0–100 (e.g. health, fatigue, hunger)
- **enum**: single value from a defined list (e.g. weather: sunny/rainy/stormy)
- **set**: multiple values from a defined list (e.g. active_buffs: ["fire_resist", "speed"])

### 4c. Runtime Stat Values

Stat values live in the **chat session** context (defined in a later step). For now we only define the schema/template here.

---

## 5. Rules

Strict restriction rules defined per world, stored as text strings, evaluated by LLM during gameplay.

**World Rule** (`world_rules`):

| Field | Type | Notes |
|---|---|---|
| `id` | int64 (snowflake) | Primary key |
| `world_id` | int64 | FK → World |
| `rule_text` | str | Natural language rule referencing stats |
| `order` | int | Display/evaluation order |

### Examples

- "If health < 10 the character can't run"
- "If fatigue > 90 the character falls asleep"
- "If weather is 'stormy' outdoor travel takes double time"

Rules reference character stats and world stats by name. The LLM receives all applicable rules in context and enforces them.

---

## 6. DB Import/Export Extensions

All new tables must have JSONL import/export support (per project convention). Extend `db_import_export.py` with:

- `export_worlds()` / `import_worlds()`
- `export_world_locations()` / `import_world_locations()`
- `export_world_npcs()` / `import_world_npcs()`
- `export_world_lore_facts()` / `import_world_lore_facts()`
- `export_npc_location_links()` / `import_npc_location_links()`
- `export_world_stat_definitions()` / `import_world_stat_definitions()`
- `export_world_rules()` / `import_world_rules()`

Vector index is **rebuilt from source documents** on import (not exported directly).

---

## Summary of New Tables

| Table | Scope | Key Fields |
|---|---|---|
| `worlds` | Global | name, description, lore, system_prompt, character_template, pipeline, status |
| `world_locations` | Per world | name, content, exits |
| `world_npcs` | Per world | name, content |
| `world_lore_facts` | Per world | content |
| `npc_location_links` | Per world | npc_id, location_id, link_type (present/excluded) |
| `world_stat_definitions` | Per world | name, scope (char/world), stat_type (int/enum/set), defaults, constraints |
| `world_rules` | Per world | rule_text, order |
| Vector chunks (LanceDB) | Per world | source_type, source_id, chunk text + embedding |

---

## Open Questions for Later Steps

- Embedding model choice and configuration
- Text chunking strategy (size, overlap)
- Chat session model (where runtime stat values live)
- World editor UI (admin SPA)
- How character template placeholders are defined/validated
