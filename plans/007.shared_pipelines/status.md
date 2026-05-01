# Feature 007 — Status

| Step | File                           | Status | Verifier | Date       |
|------|--------------------------------|--------|----------|------------|
| 001  | `001.data_model.md`            | done   | self     | 2026-05-01 |
| 002  | `002.pipeline_admin_ui.md`     | planned | —       | —          |

## Files Changed

### Step 001 — Pipeline Data Model + DB + API + One-Time Migration

Backend:
- `backend/app/models/pipeline.py` — NEW: `Pipeline` SQLModel + `PipelineKind` enum.
- `backend/app/models/world.py` — added `pipeline_id` FK column (legacy pipeline columns retained but write-dead).
- `backend/app/models/schemas/pipeline.py` — added `PipelineResponse`, `PipelinesListResponse`, `CreatePipelineRequest`, `UpdatePipelineRequest`.
- `backend/app/models/schemas/worlds.py` — dropped `system_prompt`/`simple_tools`/`pipeline`/`generation_mode`/`agent_config` from world schemas; added `pipeline_id`.
- `backend/app/db/engine.py` — registered `app.models.pipeline` import; added `ALTER TABLE worlds ADD COLUMN pipeline_id BIGINT` migration.
- `backend/app/db/pipelines.py` — NEW: session-free CRUD (`get_by_id`, `list_all`, `create`, `update`, `delete`, `is_referenced`).
- `backend/app/services/pipelines.py` — NEW: validation + CRUD orchestration (`_validate_kind`, `_validate_pipeline_config`, `_validate_simple_tools`, plus list/get/create/update/delete with 404/409 semantics).
- `backend/app/services/world_editor.py` — removed `_VALID_GENERATION_MODES`, `_validate_pipeline_json`, `_validate_simple_tools`; refactored `create_world`/`update_world`/`clone_world` to use `pipeline_id` (verifies pipeline exists).
- `backend/app/services/chat_agent_service.py` — added `_resolve_pipeline` helper; `generate_response`/`regenerate_response` now dispatch on `pipeline.kind` and thread `pipeline` into the chosen generation service.
- `backend/app/services/simple_generation_service.py` — `generate_simple_response`/`regenerate_simple_response`/`_run_generation` now accept `Pipeline` arg; reads `pipeline.system_prompt` and `pipeline.simple_tools` instead of world fields.
- `backend/app/services/chain_generation_service.py` — `generate_chain_response`/`regenerate_chain_response`/`_run_chain_generation` accept `Pipeline` arg; parses `PipelineConfig` from `pipeline.pipeline_config`.
- `backend/app/routes/admin/pipelines.py` — NEW router at `/api/admin/pipelines` with list/create/get/update/delete + relocated `/config-options`. `/config-options` declared before `/{pipeline_id}` to avoid path collision.
- `backend/app/routes/admin/worlds.py` — `_world_to_response` and `WorldDetailResponse` builder updated to drop dropped fields and emit `pipeline_id`; removed the `/pipeline-config` endpoint.
- `backend/app/main.py` — registered `pipelines_router`.
- `backend/app/services/db_import_export.py` — added `_pipeline_to_dict` / `_dict_to_pipeline` converters; `("pipelines", ...)` inserted in `TABLE_REGISTRY` BEFORE `("worlds", ...)` to satisfy the FK on import; `_world_to_dict`/`_dict_to_world` now include `pipeline_id` while keeping legacy keys for backward compat.

Frontend:
- `frontend/src/types/pipeline.d.ts` — NEW: `PipelineItem`, `PipelinesListResponse`, `CreatePipelineRequest`, `UpdatePipelineRequest`, plus relocated `PipelineStage`, `PipelineConfig`, `PlaceholderInfo`, `ToolCatalogEntry`, `DefaultTemplates`, `PipelineConfigOptions`.
- `frontend/src/types/world.d.ts` — dropped `system_prompt`/`simple_tools`/`pipeline`/`generation_mode`/`agent_config` from world types; added `pipeline_id`; removed relocated pipeline interfaces.
- `frontend/src/api/pipelines.ts` — NEW client (`listPipelines`, `getPipeline`, `createPipeline`, `updatePipeline`, `deletePipeline`, `getPipelineConfigOptions`).
- `frontend/src/api/worlds.ts` — removed `getPipelineConfigOptions` and its `PipelineConfigOptions` import.
- `frontend/src/admin/pages/WorldEditPage.tsx` — stub: removed all generation-mode UI (state, JSX, save logic) per §H deviation; replaced with `<Text>Pipeline picker — see step 002</Text>` placeholder; pipelineId field threaded through save.
- `frontend/src/admin/pages/PipelineStageEditPage.tsx` — stub: replaced full body with relocation `<Alert>` notice (step 002 will replace with the proper editor).
- `frontend/src/admin/pages/WorldFieldEditPage.tsx` — moved `PipelineConfigOptions`/`getPipelineConfigOptions` imports to pipeline module; dropped `system_prompt` from the `FieldName` enum (no longer a world field); `isPipelinePrompt` is now always false (the pipeline-prompt branch will be re-introduced in step 002 against pipelines).
- `frontend/src/admin/pages/WorldViewPage.tsx` — removed the `world.system_prompt` display block (no longer on the world).
- `frontend/src/admin/components/PlaceholderPanel.tsx` — `PlaceholderInfo` import switched to `types/pipeline`.
- `frontend/src/admin/components/PlaceholderSuggestions.tsx` — same import switch.
- `frontend/src/admin/hooks/usePlaceholderAutocomplete.ts` — same import switch.

## Notes & Issues

### Step 001 — Scope deviations (user-approved)

- **Bundled minimal step-002 fixes** to keep `npx vite build` green at the end of step 001. Per the user's explicit choice ("Bundle minimal step-002 fixes"), `WorldEditPage.tsx` and `PipelineStageEditPage.tsx` were stubbed (placeholders) and `WorldFieldEditPage.tsx` / `WorldViewPage.tsx` / placeholder components were patched to compile against the new world shape. Step 002 will replace these stubs with the real Pipelines admin UI and re-wire the AI-assisted pipeline-prompt editor.
- **§8 manual migration script** (`backend/migrate_007.py`) intentionally NOT committed — it lives in `001.data_model.md` as paste-runnable text and must be run manually against the production DB before existing worlds can chat. New installs are unaffected.

### Step 001 — Verification

- Backend: `pytest` collected zero tests (no automated tests configured in this repo). Import-smoke check (`python -c "import app.main, app.routes.admin.pipelines, ..."`) passed cleanly. The five `/api/admin/pipelines*` routes mount correctly with `/config-options` declared before `/{pipeline_id}`.
- Frontend: `npx tsc --noEmit` exits 0 (clean strict TypeScript). `npx vite build` succeeds end-to-end (~6s, all bundles emitted).
- No `git add` / `git commit` performed (project policy: explicit user permission required).
