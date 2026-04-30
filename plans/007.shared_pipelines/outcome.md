# Feature 007 — Outcome / Documentation

After implementation, update the following docs:

- [ ] `architecture/quick-reference.md`
  - Add `pipelines` table to the DB tables section (id, name, description, kind, system_prompt, simple_tools, pipeline_config, agent_config, created_at, modified_at).
  - Update `worlds` table: drop `system_prompt`, `simple_tools`, `pipeline`, `agent_config`, `generation_mode`; add `pipeline_id` (FK pipelines.id, nullable).
  - Replace the "Generation Modes (feature 003)" subsection: dispatch is by `pipeline.kind`, not `world.generation_mode`; `world.pipeline_id` is required to start generation.
  - Note `World.lore` continues to be deprecated (unchanged by this feature).
  - Add new admin endpoints `/api/admin/pipelines` (CRUD) under "API Endpoints".
  - Move "Pipeline Config" subsection so it is owned by the Pipeline entity rather than World.
- [ ] `architecture/db-models.md` — same edits to canonical model reference.
- [ ] `architecture/backend.md` — update "Generation Modes" section to reflect dispatch via `pipeline.kind`.
- [ ] `backend/CLAUDE.md` — update Generation Modes block (mode now lives on Pipeline).
- [ ] `backend/app/models/CLAUDE.md` — list new `pipeline.py` model file.
- [ ] `backend/app/db/CLAUDE.md` — list new `pipelines.py` namespace module.
- [ ] `backend/app/services/CLAUDE.md` — list new `pipelines.py` service module.
- [ ] `backend/app/routes/CLAUDE.md` — note new `admin/pipelines.py` route module.
- [ ] `frontend/src/admin/CLAUDE.md` — add `/admin/pipelines`, `/admin/pipelines/:id` routes; list `PipelinesListPage`, `PipelineEditPage` (and `PipelineStageEditPage` migrating from world to pipeline scope).
- [ ] `frontend/src/api/CLAUDE.md` — list new `pipelines.ts`.
- [ ] `frontend/src/types/CLAUDE.md` — list new `pipeline.d.ts`.
- [ ] Update CLAUDE-memory project status note: feature 007 added.
