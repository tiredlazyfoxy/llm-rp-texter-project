# admin/

Admin SPA — world and user management (served at `/admin`).

```
admin/
  App.tsx, main.tsx
  pages/             — WorldsList, WorldView, WorldEdit, WorldFieldEdit, DocumentEdit, PipelineStageEdit, LlmServersPage, DbManagementPage
  components/        — LlmChatPanel, PlaceholderPanel, PlaceholderSuggestions
  hooks/             — usePlaceholderAutocomplete (inline {PLACEHOLDER} autocomplete)
```

## Routes

- `/admin/worlds` — WorldsListPage
- `/admin/worlds/:id` — WorldViewPage (tabbed: Info, All Docs, Locations, NPCs, Lore Facts, Chats)
- `/admin/worlds/:id/edit` — WorldEditPage
- `/admin/worlds/:id/field/:fieldName` — WorldFieldEditPage (AI-assisted editing of description/system_prompt/initial_message)
- `/admin/worlds/:id/documents/:docId/edit` — DocumentEditPage
- `/admin/worlds/:id/pipeline/:stageIndex` — PipelineStageEditPage (pipeline stage prompt editor with LLM chat)
- `/admin/llm-servers` — LlmServersPage
- `/admin/database` — DbManagementPage
