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

## Observations

- Step 001: `World.system_prompt`, `simple_tools`, `pipeline`, `generation_mode`, `agent_config` columns are now write-dead — they remain on the SQLModel and in `_world_to_dict`/`_dict_to_world` for backward-compat with old `.jsonl.gz` exports and as a one-shot rollback safety net for the manual migration. Possible impact: schedule a follow-up cleanup feature to drop these columns, drop the legacy keys from `db_import_export.py`, and remove the SQLModel fields once all production DBs have been migrated and a couple of release cycles have soaked.
- Step 001: `DefaultTemplates` (frontend) gained the `director` key to match the backend `default_templates` shape — `backend/app/models/schemas/worlds.py` already declared `director: str` on `DefaultTemplatesResponse`, but the frontend `.d.ts` was missing it. Possible impact: noted only because the type was incomplete — no change required to architecture docs.
- Step 001: `WorldFieldEditPage` previously handled `system_prompt` (world field) plus a `pipeline_prompt` AI-helper branch. With `system_prompt` moving to Pipeline, the page lost both responsibilities; `FieldName` is now `"description" | "initial_message"`. Step 002 §8 will move the pipeline-prompt AI-helper to `PipelineStageEditPage` against a Pipeline. Possible impact: when finalizing, update `frontend/src/admin/CLAUDE.md` to reflect that `WorldFieldEditPage` only edits world-owned text fields and that pipeline-prompt AI editing lives under the pipeline routes.
- Step 001: §H stub deviation — `WorldEditPage.tsx` no longer contains the generation-mode pickers, system-prompt textarea, simple-tool multi-select, or stage list. It shows a placeholder `<Text>Pipeline picker — see step 002</Text>`. Step 002 must replace this placeholder with the real `<Select>` + "Edit pipeline" link before the feature is shippable; the world editor is currently functional only for non-pipeline fields.
- Step 001: `WorldEditPage` has no `pipeline_id` editing UI yet — the state is loaded and saved, but the user cannot change it from the world editor. Step 002's pipeline picker is mandatory for end-to-end shippability.
- Step 002: New `get_world_agnostic_tools()` / `WORLD_AGNOSTIC_TOOL_DEFINITIONS` in `backend/app/services/admin_tools.py` cleanly separate the "shared/global" tool surface (only `web_search` today) from the world-scoped admin tools. Possible impact: mention in `architecture/backend.md` and `backend/app/services/CLAUDE.md` (admin tools section) so future tools are deliberately classified as world-scoped or world-agnostic before being added.
- Step 002: The pipeline-prompt editor system prompt now lives in a dedicated `build_pipeline_prompt_editor_system()` builder inside `world_field_editor_system_prompt.py` (kept in the same file for proximity to the related world-field builder). Possible impact: `backend/app/services/prompts/CLAUDE.md` could note this dual role of the file, or — if the architect prefers a stricter one-prompt-per-file rule — split into `pipeline_prompt_editor_system_prompt.py` as a follow-up.
- Step 002: `LlmChatPanelProps.worldId` is now optional. Callers that previously always passed `worldId` continue to work; the only caller intentionally omitting it is the new `PipelineStageEditPage`. Possible impact: when finalizing, the admin-frontend section of `frontend/CLAUDE.md` can note that the LLM chat panel supports both world-scoped and world-agnostic modes.

