# admin/

Admin SPA — world and user management (served at `/admin`).

```
admin/
  App.tsx, main.tsx
  routes.tsx         — React Router route table (AdminRoutes); per-path-param wrappers pass key={id}
  pages/             — WorldsList, WorldView, WorldEdit, WorldFieldEdit, DocumentEdit, PipelinesList, PipelineEdit, PipelineStageEdit, LlmServersPage, DbManagementPage
  components/
    users/           — CreateUserModal, SetPasswordModal, SetRoleModal
    pipelines/       — PlaceholderPanel, PlaceholderSuggestions
    llm/             — LlmChatPanel
```

The `admin/components/` top level holds no loose files — every component lives in its domain subfolder.

Routing uses `react-router-dom`'s `BrowserRouter` with `basename="/admin"` mounted in `App.tsx`; the `<Routes>` table in `routes.tsx` is written without the `/admin` prefix.

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
