# Frontend — Folder Layout

Where files live, what goes in each folder, and the grep rules that decide ambiguous cases.

## Canonical layout

The app is a Vite multi-page build with three entries: `login/`, `user/`, `admin/`. `login/` is a separate, simple entry — single screen, no router, no `<Page>State` machinery. Both SPAs share `api/`, `types/`, `utils/`, `auth.ts` at the `src/` root.

```
src/
  api/                        # HTTP layer — flat, one file per backend resource
    client.ts                 # fetch wrapper, auth header, error normalization, AbortSignal
    worlds.ts                 # list, get, create, update, remove
    documents.ts              # locations, NPCs, lore, rules
    chats.ts                  # chat sessions, messages, SSE helpers
    users.ts
    pipelines.ts
    llmServers.ts

  types/                      # full API surface — DTOs, flat (.d.ts or .ts)
    world.ts                  # World, WorldCreateRequest, WorldUpdateRequest, WorldStatus
    document.ts
    chat.ts
    user.ts
    pipeline.ts
    llmServer.ts

  utils/                      # shared utilities (formatDate, translationSettings, oocParser, ...)

  auth.ts                     # current user / token — module-level state, plain functions
                              # NOT a class, NOT a MobX store, NOT React state

  user/                       # User SPA
    main.tsx                  # entry — mounts router
    routes.tsx                # React Router config; Page wrappers passing `key={id}`
    pages/                    # flat — page component + adjacent state file
      ChatListPage.tsx        # observer, useState for state instance, single useEffect
      chatListPageState.ts    # state class + load/save/delete external functions
      ChatPage.tsx
      chatPageState.ts
    components/               # grouped by domain
      common/                 # generic primitives — Button, Modal, Input, LlmInputBar
      chats/                  # ChatRow, MessageBubble, ChatInput

  admin/                      # Admin SPA — same shape as user/
    main.tsx
    routes.tsx
    pages/                    # WorldsListPage, WorldEditPage, PipelineEditPage, ...
    components/
      common/
      worlds/
      pipelines/
      users/
      llm/

  login/                      # Login entry — separate Vite entry, no router, no <Page>State
    main.tsx
    Login.tsx                 # single page; small local form
```

Two non-obvious shape choices:

- **No `appState.ts`.** Auth is module-level (`auth.ts` — plain `getToken`/`getCurrentUser`/`logout`). Global settings are module-level (`utils/translationSettings.ts` — get/save with a private cache). They are read via plain function calls, not observables. If a global ever needs UI reactivity, that's the moment to introduce a single small observable — until then, don't.
- **No `hooks/` folder.** Custom hooks (`useX`) are not used. Reusable stateful UI behavior is expressed as a wrapper component owning a `<Component>State` class — see `frontend-state.md` and `frontend-components.md`.

## Grep rules — where does this thing go?

When a file's home is ambiguous, these rules decide:

### Rule 1: `types/` is everything used by the `api/` layer

> If a type appears in any `api/` function signature, it lives in `types/`.

That includes request DTOs, response DTOs, enum-like literal unions, and anything else that crosses the wire. State interfaces and component prop interfaces are **not** in `types/` — they live with their state or component. (Naming note: this folder is `types/` historically; semantically it is the "API DTOs" surface. Some files are `.d.ts`, some are `.ts` — both are fine.)

### Rule 2: state interfaces and component props live with their owner

> Page state interfaces / classes live in `pages/<page>PageState.ts`.
> Component prop interfaces live in the component file (`components/<domain>/X.tsx`).

No `types/` folder. No central `interfaces.ts`. Types live next to the code that owns them.

### Rule 3: mutation/load functions live with their state

> If a function takes `(state, args, signal)` and mutates that state, it belongs in the same file as the state.

`loadWorld`, `saveWorld`, `deleteWorld` go in `worldPageState.ts`. They are exported alongside the state class. The page imports both:

```ts
import { WorldPageState, loadWorld, saveWorld, deleteWorld } from './worldPageState';
```

### Rule 4: generic vs page-aware components

> If the component takes only primitives + callbacks, it's `components/common/`.
> If it takes a state slice or a domain object, it's `components/<domain>/`.

If a generic component starts taking domain types, it's no longer generic — move it.

### Rule 5: pure helpers go where they're used

> A pure helper used by exactly one state file lives in that state file (top-level function).
> A pure helper used by multiple state files lives in `components/common/` (if rendering-related) or a `utils/` file (if not).

`utils/` is allowed when justified — date formatters, snowflake-id helpers, debounce, deep-equal. Don't pre-create a `utils/` folder; add it when you have the second consumer.

### Rule 6: API errors are typed in `api/client.ts`

> `ApiError` and any error-mapping helpers live with the client.

State files import `ApiError` from `api/client` to do `instanceof` checks.

## File naming

| Kind | Convention | Example |
|------|-----------|---------|
| Page components | PascalCase, ends with `Page` | `WorldsPage.tsx` |
| Page state files | camelCase, ends with `PageState` | `worldsPageState.ts` |
| Components | PascalCase | `WorldEditForm.tsx` |
| Component state files | camelCase, ends with `State` | `llmInputState.ts` |
| Type/DTO files | camelCase singular | `world.ts`, `chat.ts` |
| API resource | camelCase plural | `worlds.ts`, `chats.ts` |
| Module-level state | camelCase | `auth.ts`, `translationSettings.ts` |

The `Page.tsx` / `pageState.ts` casing pair is intentional: components are PascalCase (React convention), supporting modules are camelCase.

## What is NOT here

- **No `appState.ts` and no root MobX store.** Auth and global settings are module-level state in `auth.ts` and `utils/translationSettings.ts` — plain functions, not classes.
- **No `models/` folder.** API DTOs live in `types/`. ("models" is the backend's word; the frontend folder is `types/`.)
- **No `containers/` vs `components/` split.** Pages are the only "containers" the app needs.
- **No `hooks/` folder, and no custom hooks.** `useState` (for stable instance ownership) and a single `useEffect` per page are written inline. Reusable stateful UI behavior goes in a wrapper component owning a `<Component>State` class instance.
- **No `stores/` folder.** Stores are page state and live in `pages/`.
- **No `services/` folder on the frontend.** That's a backend term. The frontend has `api/` (HTTP) and external mutation functions colocated with state.
- **No `contexts/` folder.** No React Context.
- **No `selectors/` folder.** Computed `get` properties replace selectors.

## Per-SPA structure

The User SPA and Admin SPA each own their `pages/` and `components/` subtrees under `src/user/` and `src/admin/`. They **share** `api/`, `types/`, `utils/`, `auth.ts`, and a small set of shared layout components (header, sidebar, modals) at `src/` root or `src/components/common/`. Login is its own Vite entry under `src/login/` and does not use the router or `<Page>State`.

Vite's multi-page build maps each entry to its own `index.html`. Both SPA build outputs plus the login entry are served by nginx in production (`/`, `/admin`, `/login`) and by Vite in dev (`:8094`).

## Dependency direction

The import graph flows in one direction:

```
main.tsx
  └─> routes.tsx
       └─> pages/<X>Page.tsx
            ├─> pages/<x>PageState.ts
            │    ├─> api/<resource>.ts
            │    │    └─> api/client.ts
            │    │         └─> auth.ts
            │    └─> types/<resource>.ts
            └─> components/<domain>/<X>.tsx
                 └─> components/common/<Y>.tsx
```

Forbidden imports:

- `api/` importing from `pages/` or `components/`. `api/` may import from `auth.ts` and `types/` only.
- `auth.ts` importing from `api/`. Auth is leaf-level module state.
- `components/common/` importing from any other folder (must stay generic).
- `components/<domain>/` importing from another `components/<other-domain>/`. Components compose within a domain; cross-domain composition is the page's job.
- `types/` importing from anywhere except other `types/` files (and only sparingly).

## Anti-patterns

- A `models/` folder for API DTOs. Use `types/`. (Don't double-bookkeep with both.)
- An `appState.ts` or root MobX store. Use `auth.ts` + per-page state.
- A `hooks/` folder full of custom hooks wrapping `useEffect` chains. Replace with `<Page>State` (for page concerns) or a wrapper component owning `<Component>State` (for reusable UI behavior).
- A component file with multiple unrelated components exported. One file per component.
- A page with no state file (`<Page>State.ts`). Even small pages should have one — even if it only holds an `AsyncStatus`.
- Cross-SPA imports between `user/` and `admin/`. Either duplicate or factor to `src/components/common/` or a shared module at `src/` root.
