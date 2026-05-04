# admin/

Admin SPA — world and user management (served at `/admin`).

```
admin/
  App.tsx, main.tsx
  routes.tsx         — React Router route table (AdminRoutes); per-path-param wrappers pass key={id} + path-param props
  pages/             — All admin pages follow the (`<Page>.tsx` + `<page>PageState.ts`) pair pattern:
                       WorldsListPage        / worldsListPageState,
                       WorldViewPage         / worldViewPageState,
                       WorldEditPage         / worldEditPageState,
                       WorldFieldEditPage    / worldFieldEditPageState,
                       DocumentEditPage      / documentEditPageState,
                       PipelinesListPage     / pipelinesListPageState,
                       PipelineEditPage      / pipelineEditPageState,
                       PipelineStageEditPage / pipelineStageEditPageState,
                       UsersPage             / usersPageState,
                       LlmServersPage        / llmServersPageState,
                       DbManagementPage      / dbManagementPageState
  components/
    users/           — CreateUserModal, SetPasswordModal, SetRoleModal — each is observer-wrapped
                       and owns a component-local draft class (held via `useState(() => new XDraft())`)
                       with external `submit*(draft, args, signal)` mutation fns colocated in the
                       same file.
    pipelines/       — PlaceholderPanel, PlaceholderSuggestions, PlaceholderTextarea (+ placeholderAutocompleteState.ts).
                       PlaceholderTextarea exposes an optional `controllerRef` of type
                       `PlaceholderTextareaController` ({ insertAtCursor(text) }) for callers that
                       need cursor-position insertion (e.g. PipelineStageEditPage's PlaceholderPanel).
    llm/             — LlmChatPanel (+ llmChatPanelState.ts) — public props unchanged; per-mount
                       internal state class with external (state, args, signal) mutation fns.
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
- `/admin/pipelines/new` — PipelineEditPage in **shadow mode**: a frontend-only draft (not in DB). Starts blank by default; with `?cloneFrom=<sourceId>` the form pre-fills from the source pipeline. Save materializes the record via `POST /api/admin/pipelines` and redirects to `/admin/pipelines/<new-id>`; Back discards. The `?cloneFrom` query param is read in the route wrapper via `useSearchParams` and passed as the `cloneFromId` prop — pages do not read `window.location.search`.
- `/admin/pipelines/:id` — PipelineEditPage in **edit mode** (existing record).
- `/admin/pipelines/:id/stage/:stageIndex` — PipelineStageEditPage (pipeline stage prompt editor with LLM chat)
- `/admin/llm-servers` — LlmServersPage
- `/admin/database` — DbManagementPage
