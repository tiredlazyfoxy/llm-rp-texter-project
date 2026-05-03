# user/

User SPA — player-facing chat interface (served at `/`).

```
user/
  App.tsx, main.tsx
  routes.tsx         — React Router route table (UserRoutes); per-path-param wrappers pass key={id}
  pages/             — ChatListPage, WorldSelectPage, CharacterSetupPage, ChatViewPage
  components/        — MessageHistory, MessageBubble, StatsPanel,
                       ChatInput, ToolCallTrace, ChatSettingsPanel
  stores/            — ChatStore.ts (MobX)
```

Routing uses `react-router-dom`'s `BrowserRouter` mounted in `App.tsx`; the `<Routes>` table lives in `routes.tsx`.

## Routes

- `/` — ChatListPage (user's existing chats)
- `/worlds` — WorldSelectPage (pick a public world)
- `/worlds/:worldId/new` — CharacterSetupPage (fill template, pick location/model)
- `/chat/:chatId` — ChatViewPage (main chat with SSE streaming)
