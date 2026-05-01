# Feature 007 — Shared Pipelines

Extract pipelines from the World model into a standalone reusable entity. Pipelines (the prompt/flow definitions — simple, chain, or agentic) currently live inline on each world. This feature moves them into their own DB table; worlds reference a pipeline by FK. The pipeline shape itself (`PipelineConfig`, stages, etc.) does not change — only ownership and storage.

Branch: `feature/shared-chains` (already in progress, master is the main branch).

## Files / References

- `docs/architecture/quick-reference.md` — DB models, API endpoints, generation modes
- `backend/CLAUDE.md`, `backend/app/CLAUDE.md`, `backend/app/db/CLAUDE.md`, `backend/app/services/CLAUDE.md`, `backend/app/models/CLAUDE.md`, `backend/app/routes/CLAUDE.md`
- `frontend/CLAUDE.md`, `frontend/src/CLAUDE.md`, `frontend/src/admin/CLAUDE.md`, `frontend/src/types/CLAUDE.md`, `frontend/src/api/CLAUDE.md`
- `docs/plans/CLAUDE.md` — feature folder layout
- Feature 003 (`docs/plans/003.agent_pipeline/`) — original pipeline design
- Feature 005 (`docs/plans/005.prompt_customization/`) — placeholder/tool catalog, default templates

## Current State (pre-feature)

### Backend

- `backend/app/models/world.py` — `World` table has inline pipeline storage:
  - `system_prompt: str` (used in simple mode)
  - `simple_tools: str` (JSON list, simple mode)
  - `pipeline: str` (JSON `PipelineConfig`, chain mode)
  - `agent_config: str` (JSON, future agentic mode)
  - `generation_mode: str` ("simple" | "chain" | "agentic")
- `backend/app/models/schemas/pipeline.py` — `PipelineConfig`, `PipelineStage` (unchanged shape)
- `backend/app/models/schemas/worlds.py` — `WorldResponse`, `WorldDetailResponse`, `CreateWorldRequest`, `UpdateWorldRequest` carry pipeline fields directly
- `backend/app/db/worlds.py` — World CRUD, session-free
- `backend/app/services/world_editor.py` — validates `pipeline` (via `PipelineConfig.model_validate_json`) and `simple_tools`; threads them through `create_world`/`update_world`/`clone_world`
- `backend/app/services/chain_generation_service.py` (line ~613) — runtime consumer: `pipeline = PipelineConfig.model_validate_json(world.pipeline)`
- `backend/app/services/simple_generation_service.py` — uses `world.system_prompt` and `world.simple_tools`
- `backend/app/services/chat_agent_service.py` — dispatches on `world.generation_mode`
- `backend/app/services/db_import_export.py` — `_world_to_dict` / `_dict_to_world` serialize pipeline fields
- `backend/app/routes/admin/worlds.py` — `_world_to_response()` and `WorldDetailResponse` builders include pipeline fields; `GET /api/admin/worlds/pipeline-config` returns static config (placeholders, tools, default templates)

### Frontend

- `frontend/src/types/world.d.ts` — `WorldItem`, `WorldDetail`, `UpdateWorldRequest` carry `pipeline`, `system_prompt`, `simple_tools`, `generation_mode`, `agent_config`. Also defines `PipelineConfig`, `PipelineStage`, `PipelineConfigOptions`.
- `frontend/src/api/worlds.ts` — calls world CRUD; `getPipelineConfigOptions()` for static options
- `frontend/src/admin/pages/WorldEditPage.tsx` — single page that owns ALL pipeline UI (lines ~500–756): generation mode picker, simple-mode system-prompt + tool multiselect, chain-mode stage list with per-stage tool/prompt/model/order/enabled controls, and validation warnings
- `frontend/src/admin/pages/PipelineStageEditPage.tsx` — per-stage prompt editor (route `/admin/worlds/:id/pipeline/:stageIndex`); reads/writes `world.pipeline`
- `frontend/src/admin/App.tsx` — admin SPA routing + nav items
- Nav: Users, Worlds, LLM Servers, Database

## Facts

- IDs are Snowflake int64, serialized as string in JSON. Use `app.services.snowflake.generate_id()`.
- DB layer is session-free (`from app.db import worlds` then `await worlds.get_by_id(id)`). Sessions/`select()`/`session.exec()` may not leak out of `db/`.
- Services depend on `db/`; routes depend on services.
- Every DB-persistent model MUST have JSONL import/export (gzipped JSONL per table; UPSERT semantics; streaming; updated in `services/db_import_export.py` `TABLE_REGISTRY`).
- All API contracts strictly typed: Pydantic `BaseModel` backend, matching `.d.ts` frontend.
- Lightweight DDL migration pattern: `init_db()` runs `CREATE TABLE IF NOT EXISTS`; new columns added via `ALTER TABLE ... ADD COLUMN` wrapped in try/except (see `engine.py` line 78-86).
- `generation_mode` STAYS on the World ("which mode this world uses"). The Pipeline entity stores the mode-specific definition (system_prompt+simple_tools for simple, stages for chain, agent_config for agentic).
- This is a one-time migration: production data exists, but the migration is documented as a manual paste-once script — not committed automated migration code.

## Decisions

- **Pipeline is a single table** holding all three mode shapes (simple / chain / agentic) — not three tables. Justification: keeps the `World.pipeline_id` FK simple; `Pipeline.kind` discriminator selects which fields are meaningful; mirrors existing in-world layout where all three coexist.
- **`generation_mode` moves OFF the world and ONTO the pipeline as `kind`.** A world picks a pipeline; the pipeline tells the runtime which flow to use. This avoids the bug class where `world.generation_mode == "chain"` but the picked pipeline is shaped for "simple".
- **`World.pipeline_id` is nullable**: a world without a pipeline is a draft. Worlds without a pipeline cannot start generation (400 in `chat_agent_service`).
- **No automatic migration on start** — the manual one-time script (Step 002) handles it. New installs get clean shape from `init_db()`.
- **Old World columns (`system_prompt`, `simple_tools`, `pipeline`, `agent_config`, `generation_mode`) stay in the schema but become unused** after migration (Step 002 leaves them populated for one-shot rollback). A follow-up cleanup step is out of scope for this feature.
- **No FK cascade**: deleting a Pipeline that is referenced by any World is rejected with 409. Worlds must be re-pointed first.
