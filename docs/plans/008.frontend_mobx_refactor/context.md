# Feature 008 — Frontend MobX Refactor

## Goal

Bring the frontend in line with the rules in `docs/architecture/frontend*.md`:

- Page-owned MobX state (`<Page>State` class instance per route mount, per-mount remount via React Router `key`).
- External `(state, args, signal)` mutation functions colocated with state — no effectful methods on state.
- `observer` on every component, `useState` only as a memoization primitive, single mount/unmount `useEffect` per page.
- HTTP isolated in `src/api/`, all calls accept `AbortSignal`, errors normalized through `ApiError`.
- DTOs in `src/types/` (kept under that name), reusable stateful UI behavior expressed as wrapper components owning `<Component>State` classes — **no custom `useX` hooks**.
- Auth + global settings stay as module-level state in `auth.ts` and `utils/translationSettings.ts` — **no `AppState` class**.
- Login is a separate Vite entry, **outside React Router**, and stays simple (no `<Page>State` machinery).

## Scope (the gap to close)

Today's frontend, per the harvest in this feature's planning chat:

- **User SPA** has partial MobX (one large `ChatStore` singleton in `user/stores/ChatStore.ts`, ~720 lines). Other user pages (`ChatListPage`, `CharacterSetupPage`, `WorldPage`) use raw `useState`/`useEffect`. Singleton must become a per-mount `ChatPageState`.
- **Admin SPA** has zero MobX. All 11 pages (`WorldsListPage`, `WorldViewPage`, `WorldEditPage`, `WorldFieldEditPage`, `DocumentEditPage`, `PipelinesListPage`, `PipelineEditPage`, `PipelineStageEditPage`, `LlmServersPage`, `DbManagementPage`, `UsersPage`) are raw `useState`/`useEffect`. ~250+ hook occurrences to migrate.
- **Routing** is regex over `window.location.pathname` inside `user/App.tsx` and `admin/App.tsx`. No React Router, no path-param remount keys. Replace with `react-router-dom` per SPA, with per-page route wrappers passing `key={id}`.
- **Login** is its own Vite entry today and stays that way — single screen, plain `useState` form, redirected to via `window.location.href = '/login/'` from `auth.logout()`. Out of scope for the router refactor.
- **API layer** is mostly correct: `src/api/` exists, all 12 `fetch(` calls live there, `request.ts` ≈ canonical `client.ts`. Missing: `ApiError` class, `AbortSignal` pass-through, file rename to `client.ts`.
- **Types**: `src/types/` (`.d.ts`) stays — naming kept as historical, semantically equivalent to architecture `models/`.
- **Custom hooks**: `src/hooks/useTranslation.ts` (used by `ChatInput`, `LlmChatPanel`) and `src/admin/hooks/usePlaceholderAutocomplete.ts` (used by `PipelineStageEditPage`). Both replaced by wrapper components — `LlmInputBar` (variant C: caller owns `LlmInputState`, slot props `before`/`extras`, baked-in textarea + translate/revert + send/stop) and `PlaceholderTextarea`. Both `hooks/` folders deleted.
- **Components**: flat in `user/components/` and `admin/components/` plus shared `src/components/` for layout. Reorganize into `common/` + per-domain subfolders.

## Locked decisions (do not re-litigate during steps)

1. **Keep `types/` folder name.** API DTOs do not move to `models/`. Architecture docs already updated.
2. **No `appState.ts`, no root MobX store.** Globals = `auth.ts` (module-level functions over `localStorage`) + `utils/translationSettings.ts` (private cache + get/save). React reads them via plain function calls; if a global ever needs UI reactivity, that's the moment to introduce a single small observable — not now.
3. **No custom hooks.** `useX` is replaced by wrapper components owning `<Component>State` instances. `LlmInputBar` is the canonical example.
4. **Login stays a separate Vite entry**, outside React Router. The routing migration is per-SPA only.
5. **CLAUDE.md updates per step.** Each step that changes folder shape or component layout updates the relevant `frontend/src/**/CLAUDE.md` files in the same step. No batched cleanup at the end.
6. **`LlmInputBar` shape is variant C** (see chat with planner): `<LlmInputBar state={LlmInputState} translateFn busy onSend onStop before={...} extras={...} />`. State class lives next to the component. Translation API/streaming logic is in external functions in the same file. Built-in: textarea, translate button, revert button, translate-error banner, send/stop swap. Slots: `before` (OOC preview, status row), `extras` (regenerate, page-specific buttons).
7. **API client rename `request.ts` → `client.ts`** with `ApiError` class + `AbortSignal` pass-through. Auth token read directly from `auth.ts` (`import { getToken }`) — no DI/injection layer. `auth.ts` does not import from `api/` (no cycle).
8. **React Router DOM** is the routing library, added per-SPA. `routes.tsx` per SPA. Path-param pages get a route wrapper passing `key={id}` for remount-on-change.

## Files and references

### Architecture (target — already updated for this feature)

- `docs/architecture/frontend.md`
- `docs/architecture/frontend-state.md`
- `docs/architecture/frontend-pages.md`
- `docs/architecture/frontend-components.md`
- `docs/architecture/frontend-api.md`
- `docs/architecture/frontend-forms.md`
- `docs/architecture/frontend-layout.md`
- `docs/architecture/quick-reference.md`
- `docs/architecture/README.md`

### Frontend code (sources to refactor)

- `frontend/src/api/` — 12 modules incl. `request.ts` (→ `client.ts`), `auth.ts`, `chat.ts`, `worlds.ts`, `pipelines.ts`, `llmServers.ts`, `dbManagement.ts`, `llmChat.ts`, `userSettings.ts`, `translateStream.ts`, `sse.ts`, `admin.ts`
- `frontend/src/types/` — `.d.ts` files; stays under this name
- `frontend/src/auth.ts` — module-level auth (already correct shape)
- `frontend/src/utils/translationSettings.ts` — module-level global settings (already correct shape)
- `frontend/src/hooks/useTranslation.ts` — to be deleted; replaced by `LlmInputBar` + `LlmInputState`
- `frontend/src/admin/hooks/usePlaceholderAutocomplete.ts` — to be deleted; replaced by `PlaceholderTextarea`
- `frontend/src/user/` — User SPA: `App.tsx`, `main.tsx`, `pages/`, `components/`, `stores/ChatStore.ts`
- `frontend/src/admin/` — Admin SPA: `App.tsx`, `main.tsx`, `pages/`, `components/`
- `frontend/src/login/` — Login entry; stays as-is structurally (small refactor only)
- `frontend/src/components/` — shared layout (`AppHeader`, `AppLayout`, `AppSidebar`, `ChangePasswordModal`, `TranslationSettingsModal`)
- `frontend/CLAUDE.md`, `frontend/src/CLAUDE.md`, and all per-folder `CLAUDE.md` files — kept in sync per step

### Plan layout

Steps will be added to this folder one at a time as `<NNN>.<name>.md`, with `<NNN>.context.md` for step-specific context when needed. Steps are not all written up-front — each step is planned just before it is implemented, so each step file can reflect the actual state left by the previous step.

## Out of scope

- Backend changes. This is a frontend refactor — backend APIs and SSE protocols are unchanged.
- New features. No UI features added or removed. Behavior parity is the bar.
- Login flow changes beyond the auth-related globals (login keeps its current structure).
- Cross-SPA shared package extraction. Today's "shared at `src/` root" pattern is good enough; defer factoring until concrete duplication is painful.
- Test infrastructure. The architecture docs reference test patterns; we do not introduce tests as part of this refactor unless a step requires one for safety.
