# Frontend — Folder Layout

Where files live, what goes in each folder, and the grep rules that decide ambiguous cases.

## Canonical layout

```
src/
  api/                        # HTTP layer — flat, one file per backend resource
    client.ts                 # fetch wrapper, auth injection, error normalization
    worlds.ts                 # list, get, create, update, remove
    documents.ts              # locations, NPCs, lore, rules
    chats.ts                  # chat sessions, messages, SSE helpers
    users.ts
    pipelines.ts
    llmServers.ts

  models/                     # full API surface — DTOs only, flat
    world.ts                  # World, WorldCreateRequest, WorldUpdateRequest, WorldStatus
    document.ts
    chat.ts
    user.ts
    pipeline.ts
    llmServer.ts

  pages/                      # flat — page component + adjacent state file
    WorldsPage.tsx            # the list page component (observer, useState for state, single useEffect)
    worldsPageState.ts        # state class + factory + load/save/delete external functions
    WorldPage.tsx
    worldPageState.ts
    DocumentsPage.tsx
    documentsPageState.ts
    ChatPage.tsx
    chatPageState.ts
    PipelinePage.tsx
    pipelinePageState.ts
    LoginPage.tsx
    loginPageState.ts

  components/                 # grouped by domain; prop interfaces live in the component file
    common/                   # generic primitives — Button, Modal, Input, Select, Spinner, ErrorBanner, Tabs
    worlds/                   # WorldRow, WorldEditForm, WorldList
    documents/
    chats/
    users/
    pipelines/

  appState.ts                 # app-wide state (auth token, current user) — instantiated in main.tsx
  routes.tsx                  # React Router config; nested routes; Page wrappers that pass `key={id}`
  main.tsx                    # entry — instantiates AppState, configures api/client, mounts router
```

## Grep rules — where does this thing go?

When a file's home is ambiguous, these rules decide:

### Rule 1: `models/` is everything used by the `api/` layer

> If a type appears in any `api/` function signature, it lives in `models/`.

That includes request DTOs, response DTOs, enum-like literal unions, and anything else that crosses the wire. State interfaces and component prop interfaces are **not** in `models/` — they live with their state or component.

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
| Models | camelCase singular | `world.ts`, `chat.ts` |
| API resource | camelCase plural | `worlds.ts`, `chats.ts` |
| App-level state | camelCase | `appState.ts` |

The `Page.tsx` / `pageState.ts` casing pair is intentional: components are PascalCase (React convention), supporting modules are camelCase.

## What is NOT here

- **No `types/` folder.** Types live with the code that owns them; DTOs in `models/`.
- **No `containers/` vs `components/` split.** Pages are the only "containers" the app needs.
- **No `hooks/` folder.** We barely use hooks. The few we have (`useState` for instance ownership, a single `useEffect` per page) are inline.
- **No `stores/` folder.** Stores are page state and live in `pages/`.
- **No `services/` folder on the frontend.** That's a backend term. The frontend has `api/` (HTTP) and external mutation functions colocated with state.
- **No `contexts/` folder.** No React Context.
- **No `selectors/` folder.** Computed `get` properties replace selectors.

## Per-SPA structure

The User SPA and Admin SPA each have their own `src/` tree following this layout. Shared code (e.g., the login flow) is duplicated or factored to a small shared package — to be decided when concrete duplication appears. Today the rule is: **each SPA is self-contained**; do not pre-create shared layers.

Vite's multi-page build maps each SPA to its own `index.html` entry. Both build outputs are served by nginx in production (`/` and `/admin`) and by Vite in dev (`:8094` for User, `:8094/admin` or a separate port for Admin — see `dev-environment.md`).

## Dependency direction

The import graph flows in one direction:

```
main.tsx
  └─> routes.tsx
       └─> pages/<X>Page.tsx
            ├─> pages/<x>PageState.ts
            │    ├─> api/<resource>.ts
            │    │    └─> api/client.ts
            │    │         └─> models/<resource>.ts
            │    └─> models/<resource>.ts
            └─> components/<domain>/<X>.tsx
                 └─> components/common/<Y>.tsx

appState.ts is referenced from main.tsx; api/client.ts is configured with appState's token getter via injection
```

Forbidden imports:

- `api/` importing from `pages/`, `components/`, or `appState`.
- `components/common/` importing from any other folder (must stay generic).
- `components/<domain>/` importing from another `components/<other-domain>/`. Components compose within a domain; cross-domain composition is the page's job.
- `models/` importing from anywhere except other `models/` files (and only sparingly).

## Anti-patterns

- A `types/` folder. Move types to where they are used (`models/`, state files, component files).
- A `hooks/` folder full of custom hooks wrapping `useEffect` chains. Replace with computed + page-level `useEffect`.
- A component file with multiple unrelated components exported. One file per component.
- A page with no state file (`<Page>State.ts`). Even small pages should have one — even if it only holds an `AsyncStatus`.
- Cross-SPA imports without a shared package. Either duplicate or factor; don't reach.
