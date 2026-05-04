# user/

User SPA — player-facing chat interface (served at `/`).

```
user/
  App.tsx, main.tsx
  routes.tsx         — React Router route table (UserRoutes); per-path-param wrappers pass key={id}
  pages/             — ChatListPage, WorldSelectPage, CharacterSetupPage, ChatViewPage
  components/
    UserSidebar.tsx  — layout shell (kept at top level, not a domain component)
    chats/           — ChatInput, ChatMemoriesModal, ChatSettingsPanel,
                       MessageBubble, MessageHistory, StatsPanel,
                       SummaryBlock, ToolCallTrace
    worlds/          — WorldInfoModal
  stores/            — ChatStore.ts (MobX)
```

`UserSidebar.tsx` lives at the top level of `components/` as a layout-shell exception — it is not a domain component and does not belong under any per-domain subfolder.

Routing uses `react-router-dom`'s `BrowserRouter` mounted in `App.tsx`; the `<Routes>` table lives in `routes.tsx`.

## Routes

- `/` — ChatListPage (user's existing chats)
- `/worlds` — WorldSelectPage (pick a public world)
- `/worlds/:worldId/new` — CharacterSetupPage (fill template, pick location/model)
- `/chat/:chatId` — ChatViewPage (main chat with SSE streaming)
