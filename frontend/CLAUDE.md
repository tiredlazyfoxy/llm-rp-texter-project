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
      pages/             — WorldsList, WorldEdit, DocumentsList, DocumentEdit, LlmServersPage
    api/                 — API client functions (chat.ts, llmServers.ts, ...)
    types/               — TypeScript .d.ts interfaces matching backend schemas
      user.d.ts, chat.d.ts, llmServer.d.ts
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

- `/admin/worlds` — WorldsList
- `/admin/worlds/:id/edit` — WorldEdit
- `/admin/worlds/:id/documents` — DocumentsList (locations, NPCs, lore)
- `/admin/llm-servers` — LlmServersPage

## Tech

- **Bundler**: Vite 6.3+
- **UI Library**: Mantine 7.17+ (@mantine/core, @mantine/form, @mantine/hooks)
- **State**: MobX 6.13+ (observable stores)
- **Routing**: History API
- **SSE**: fetch + ReadableStream (not EventSource — needs POST + auth headers)

## Typing

- **Strict TypeScript — no `any` anywhere**
- All API types in `src/types/` as `.d.ts` matching backend Pydantic schemas
- All API calls strongly typed end-to-end

## Key Constraints

- User and Admin SPAs are separate apps with separate builds
- They share **only** the login/auth flow
- Admin link shown in User SPA for admin-privileged users
- Dev: Vite proxies `/api` to localhost:8085
- Prod: nginx serves static builds, proxies `/api` to backend

## Commands

- Dev server: `npx vite --port 8094`
- Build: `npx vite build`

## See Also

- `architecture/quick-reference.md` — API endpoints, SSE protocol, data types
