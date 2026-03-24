# Frontend

Vite multi-page application — TypeScript, React, MobX, Mantine UI.

## Directory Structure

```text
frontend/
  src/
    login/               — Login/setup page (separate entry point)
      main.tsx, Login.tsx
    user/                — User SPA (served at /)
      App.tsx, main.tsx
      pages/             — ChatListPage, WorldSelectPage, CharacterSetupPage, ChatViewPage
      components/        — MessageHistory, MessageBubble, VariantSelector, StatsPanel,
                           ChatInput, ToolCallTrace, ChatSettingsPanel
      stores/            — ChatStore.ts (MobX)
    admin/               — Admin SPA (served at /admin)
      App.tsx, main.tsx
      pages/             — WorldsList, WorldView, WorldEdit, DocumentEdit, PipelineStageEdit, LlmServersPage, DbManagementPage
    utils/               — Shared utilities (formatDate.ts, ...)
    api/                 — API client functions (chat.ts, llmServers.ts, dbManagement.ts, ...)
    types/               — TypeScript .d.ts interfaces matching backend schemas
      user.d.ts, chat.d.ts, llmServer.d.ts, dbManagement.d.ts
  index.html             — User SPA entry
  admin/index.html       — Admin SPA entry
  login/index.html       — Login entry
  vite.config.ts         — Multi-page build, dev proxy to :8085
  package.json
  tsconfig.json
```

## Applications

- **Login page** (served at `/login`) — Auth flow, DB setup
- **User SPA** (served at `/`) — Player-facing chat interface
- **Admin SPA** (served at `/admin`) — World and user management

## User SPA Routes

- `/` — ChatListPage (user's existing chats)
- `/worlds` — WorldSelectPage (pick a public world)
- `/worlds/:worldId/new` — CharacterSetupPage (fill template, pick location/model)
- `/chat/:chatId` — ChatViewPage (main chat with SSE streaming)

## Admin SPA Routes

- `/admin/worlds` — WorldsListPage
- `/admin/worlds/:id` — WorldViewPage (tabbed: Info, All Docs, Locations, NPCs, Lore Facts, Chats)
- `/admin/worlds/:id/edit` — WorldEditPage
- `/admin/worlds/:id/field/:fieldName` — WorldFieldEditPage (AI-assisted editing of description/system_prompt/initial_message)
- `/admin/worlds/:id/documents/:docId/edit` — DocumentEditPage
- `/admin/worlds/:id/pipeline/:stageIndex` — PipelineStageEditPage (pipeline stage prompt editor with LLM chat)
- `/admin/llm-servers` — LlmServersPage
- `/admin/database` — DbManagementPage

## Tech

- **Bundler**: Vite 6.3+
- **UI Library**: Mantine 7.17+ (@mantine/core, @mantine/form, @mantine/hooks)
- **State**: MobX 6.13+ (observable stores)
- **Routing**: History API
- **SSE**: fetch + ReadableStream (not EventSource — needs POST + auth headers). Events: token, thinking, tool_call_start/result, phase, status, stat_update, done, error. Backend filters editor-only events by caller_role.

## Typing

- **Strict TypeScript — no `any` anywhere**
- All API types in `src/types/` as `.d.ts` matching backend Pydantic schemas
- All API calls strongly typed end-to-end

## Date Formatting

- **All dates use `formatDate()` from `src/utils/formatDate.ts`** — no inline date formatting
- Format: ISO date (`YYYY-MM-DD`), or time only (`HH:MM`) if the date is today
- Never use locale-dependent formats (no `toLocaleDateString()`)

## Debug Mode

Editor+ users have a debug toggle in chat settings. When enabled:
- Tool calls show full arguments + results (no truncation)
- Thinking content displayed in collapsible panels
- Generation plan visible (chain mode: facts, decisions, stat_updates — collected via planning tools)
- Hidden stats revealed with indicator badge

When disabled: clean message display, brief status text only.

## Key Constraints

- User and Admin SPAs are separate apps with separate builds
- They share **only** the login/auth flow
- Admin link shown in User SPA for admin-privileged users
- Dev: Vite proxies `/api` to localhost:8085
- Prod: nginx serves static builds, proxies `/api` to backend

## Commands

- Dev server: `npx vite --port 8094`
- Build: `npx vite build`

## Production Docker

- `frontend/Dockerfile` — multi-stage: Node 20 build → nginx:alpine
- Build output copied to `/usr/share/nginx/html`
- nginx config: `nginx/prod.conf` (multi-SPA fallback for `/`, `/admin`, `/login`)
- Build context is repo root (not `frontend/`)

## See Also

- `architecture/quick-reference.md` — API endpoints, SSE protocol, data types
