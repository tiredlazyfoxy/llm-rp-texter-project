# user/

User SPA — player-facing chat interface (served at `/`).

```
user/
  App.tsx, main.tsx
  routes.tsx         — React Router route table (UserRoutes); per-path-param wrappers pass key={id} + worldId prop
  pages/             — Each page is a (`<Page>.tsx` + `<page>PageState.ts`) pair:
                       ChatListPage / chatListPageState,
                       WorldPage    / worldPageState,
                       CharacterSetupPage / characterSetupPageState
                         — Feature 011: explicit "Character Name" input above template-variable inputs;
                           sole source of truth for `chat.character_name` (no longer derived from
                           `state.variables["NAME"]`).
                       ChatViewPage / chatPageState
                         — Feature 012: header trigger for `StatEditorDrawer` shown to admin/editor.
  components/
    UserSidebar.tsx  — layout shell (kept at top level, not a domain component).
                       Backed by `userSidebarState.ts`, a module-level singleton MobX class
                       (documented exception in `frontend-state.md`) so the sidebar reflects
                       cross-page mutations (e.g. `character_name` saved in chat settings)
                       without remounting the SPA shell.
    chats/           — ChatInput, ChatMemoriesModal, ChatSettingsPanel,
                       MessageBubble, MessageHistory, StatsPanel, StatEditorDrawer,
                       SummaryBlock, ToolCallTrace
                       — `ChatSettingsPanel` (Feature 011) edits `character_name` in addition to
                         tool/text models; trim-and-reject validation, disabled submit on empty.
                       — `StatEditorDrawer` (Feature 012) is admin-or-editor gated
                         (`role === "admin" || role === "editor"`); submits `PUT /api/chats/:id/stats`
                         and refreshes via `getChatDetail` re-fetch + `mergeChatDetail` (no SSE).
```

`UserSidebar.tsx` lives at the top level of `components/` as a layout-shell exception — it is not a domain component and does not belong under any per-domain subfolder.

Routing uses `react-router-dom`'s `BrowserRouter` mounted in `App.tsx`; the `<Routes>` table lives in `routes.tsx`.

## Routes

- `/` — ChatListPage (user's existing chats)
- `/worlds/:worldId` — WorldPage (single world overview + Start New Chat / Edit World)
- `/worlds/:worldId/new` — CharacterSetupPage (fill template, pick location/model)
- `/chat/:chatId` — ChatViewPage (main chat with SSE streaming)
