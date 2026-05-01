# admin/

Admin SPA — world and user management (served at `/admin`).

```
admin/
  App.tsx, main.tsx
  pages/             — WorldsList, WorldView, WorldEdit, WorldFieldEdit, DocumentEdit, PipelinesList, PipelineEdit, PipelineStageEdit, LlmServersPage, DbManagementPage
  components/        — LlmChatPanel, PlaceholderPanel, PlaceholderSuggestions
  hooks/             — usePlaceholderAutocomplete (inline {PLACEHOLDER} autocomplete)
```

## Routes

- `/admin/worlds` — WorldsListPage
- `/admin/worlds/:id` — WorldViewPage (tabbed: Info, All Docs, Locations, NPCs, Lore Facts, Chats)
- `/admin/worlds/:id/edit` — WorldEditPage (Pipeline picker; pipeline editing happens under `/admin/pipelines/:id`)
- `/admin/worlds/:id/field/:fieldName` — WorldFieldEditPage (AI-assisted editing of `description` / `initial_message`; `system_prompt` is no longer a world field — it lives on the Pipeline)
- `/admin/worlds/:id/documents/:docId/edit` — DocumentEditPage
- `/admin/pipelines` — PipelinesListPage
- `/admin/pipelines/new` — PipelineEditPage in **shadow mode**: a frontend-only draft (not in DB). With `?cloneFrom=<sourceId>` the form pre-fills from the source pipeline; Save materializes the record via `POST /api/admin/pipelines` and redirects to `/admin/pipelines/<new-id>`; Back discards.
- `/admin/pipelines/:id` — PipelineEditPage in **edit mode** (existing record).
- `/admin/pipelines/:id/stage/:stageIndex` — PipelineStageEditPage (pipeline stage prompt editor with LLM chat)
- `/admin/llm-servers` — LlmServersPage
- `/admin/database` — DbManagementPage
