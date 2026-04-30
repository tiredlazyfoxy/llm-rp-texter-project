# user/

User SPA — player-facing chat interface (served at `/`).

```
user/
  App.tsx, main.tsx
  pages/             — ChatListPage, WorldSelectPage, CharacterSetupPage, ChatViewPage
  components/        — MessageHistory, MessageBubble, StatsPanel,
                       ChatInput, ToolCallTrace, ChatSettingsPanel
  stores/            — ChatStore.ts (MobX)
```

## Routes

- `/` — ChatListPage (user's existing chats)
- `/worlds` — WorldSelectPage (pick a public world)
- `/worlds/:worldId/new` — CharacterSetupPage (fill template, pick location/model)
- `/chat/:chatId` — ChatViewPage (main chat with SSE streaming)
