# Frontend Architecture

## Overview

Two SPAs (User and Admin) built with **TypeScript + React + MobX + Vite**, served as a Vite multi-page build. Each SPA has its own entry point but shares the same conventions, state library, API layer, and folder layout.

This document is the entry point. Detailed rules live in:

- `frontend-state.md` — MobX, observer, useState/useEffect rules, async resource trio
- `frontend-pages.md` — Page lifecycle, route ownership, URL-driven loads, query-param persistence
- `frontend-components.md` — Component rules, generic vs page-aware, splitting growing components
- `frontend-api.md` — `api/` layer, `types/` (DTOs), `client.ts`, no runtime validation
- `frontend-forms.md` — Draft state, validation as computed, submit flow, server vs client errors
- `frontend-layout.md` — Folder structure, what lives where, grep rules

These docs are authoritative. The current codebase will be refactored to match them.

## Core principles

The frontend follows a small set of strong rules that work as a system. Loosening any one of them breaks the others. They are listed here as the high-level shape; each linked doc explains the reasoning and the corner cases.

### State

- **MobX, only.** No Redux, no Zustand, no React Query, no React Context.
- **Every component is wrapped in `observer`.** No exceptions; missing `observer` is a code-review failure.
- **No `useState` for reactive state.** `useState` is permitted only as a memoization primitive to own a stable instance: `const [state] = useState(() => createPageState())`.
- **`useEffect` only at the page-component level**, only for initial load on mount and cleanup on unmount. Never in leaf components, never for derivations, never for prop-watching.
- **No `useCallback`.** Observer + MobX makes referential prop stability irrelevant.
- **`enforceActions: 'always'` is OFF.** It punishes the legitimate two-way-binding case.

### Routes and pages

- **A page owns the browser route.** One route = one page = one fresh state instance per navigation.
- **URL path-param changes force a remount** via React Router `key`. Going `/worlds/123` → `/worlds/456` unmounts and remounts; the same mount-time `useEffect` handles the new load.
- **Query-param changes** (filter/sort/mode) are handled either client-side on already-loaded data or by direct event-handler calls. Never by `useEffect` watching the query string.
- **Each page loads its own data by id from the URL.** No "warm start" from a parent's loaded data — every page must be deep-linkable.
- **No upward callbacks across pages.** Save → API → done. Returning to a parent route remounts and refetches. Backend is the only source of truth across pages.
- **URL query params are the persistence layer** for filter, sort, mode, scroll-anchor — anything that should survive navigation, refresh, or bookmarking.

### State shape

Three layers, each with a clear lifetime:

| Layer | Lifetime | Holds |
|-------|----------|-------|
| Module-level globals | App boot → unload | Auth token (`auth.ts`), global settings (`utils/translationSettings.ts`). Plain module state — **not** a class, not a MobX store |
| `<Page>State` | Page mount → unmount | Loaded data, drafts, modes, pagination, status flags |
| `<Component>State` | Component mount → unmount | Local UI state too noisy to bubble up |

- **State is observable data + pure `get` computed derivations.** No effectful methods on state objects (no `load()`, no `save()`, no `delete()`).
- **All effectful operations are external functions** taking `(state, args, signal)`, writing via `runInAction` for multi-field mutations. They live in the same file as the page state.
- **Direct trivial single-field assignment from components is allowed** (`state.search = e.target.value`). Multi-field changes wrap in `runInAction`. Stores expose **derivations**, not setters.

### Components

- **Pure props, no React context.** Stores and slices are passed explicitly down the tree.
- **Generic components** (Button, Modal, Input, Select) take primitives + callbacks only — no domain knowledge.
- **Page-aware components** (WorldRow, WorldEditForm) take state slices.
- **Page-specific orchestration and event handlers live as inner functions inside the component**, closing over `state` and props. They are not extracted to top-level "to keep the component small."
- **A growing component is split into smaller observer subcomponents** — each owning its slice of JSX and its own inner handlers. State stays in the page (or a sub-slice passed as a prop).
- **External top-level functions are reserved for genuinely reusable code** (API calls, generic loaders, pure helpers, validators) — not as a refactor target for size.

### Data and API

- **Domain data is TS interfaces only.** `Message`, `World`, `NPC` are pure shapes that match wire JSON 1:1. No methods, no classes, no getters on data.
- **No runtime validation at the API boundary.** Trust the TS types. `response.json() as World[]`. If the backend changes shape, fix at source — no double-bookkeeping with zod.
- **All HTTP calls live in `src/api/`.** State files never call `fetch` directly.
- **One `api/<resource>.ts` module per backend resource**, exporting typed async functions; each accepts an optional `AbortSignal`.
- **`types/` holds the full API surface as DTOs.** Grep rule: if a type appears in any `api/` function signature, it lives in `types/`. (The folder is named `types/` for historical reasons; semantically it is the API DTO surface.)

### Async resource trio

Every loadable resource on a state object is a triple — no wrapper types, no booleans:

```ts
worlds: World[]                       // the data
worldsStatus: 'idle' | 'loading' | 'ready' | 'error'
worldsError: string | null
```

No `AsyncValue<T>`, no `isLoading`, no `mobx-utils fromPromise`.

### Forms

- **Drafts live in page state** for page-level forms; modal-dialog drafts may live in component-local state.
- **Validation is `get` computed derivations on state** — `get errors`, `get isValid`, `get isDirty`, `get canSubmit`. Pure functions of observable fields.
- **Server-side field errors are stored separately** (e.g., `serverErrors: Partial<DraftErrors>`) and unioned with client-derived errors in the computed `errors` getter.
- **Submit flow**: an inner closure on the form component calls `if (!state.canSubmit) return;` then invokes the external `saveX(state, signal)` function.

## Folder layout (canonical)

The app is a Vite multi-page build with three entries: `login/` (separate entry, outside React Router), `user/` (User SPA), `admin/` (Admin SPA). Each SPA owns its own `pages/` and `components/`; `api/`, `types/`, `utils/`, and `auth.ts` are shared at `src/` root.

```
src/
  api/                        # HTTP layer — flat, one file per resource
    client.ts                 # fetch wrapper, auth header, error normalization, AbortSignal
    worlds.ts
    documents.ts
    chats.ts
    users.ts
  types/                      # full API surface — DTOs only, flat (.d.ts or .ts)
    world.ts                  # World, WorldCreateRequest, WorldUpdateRequest, ...
    document.ts
    chat.ts
    user.ts
  utils/                      # shared utilities (formatDate, translationSettings, ...)
  user/                       # User SPA
    main.tsx, App.tsx, routes.tsx
    pages/                    # flat — page component + adjacent state file
      ChatListPage.tsx
      chatListPageState.ts    # state class + load/save/delete external functions
    components/               # grouped by domain
      common/                 # generic primitives — Button, Modal, LlmInputBar
      chats/                  # ChatRow, MessageBubble, ChatInput
  admin/                      # Admin SPA — same shape as user/
  login/                      # Login entry (no router, no MobX page state)
  auth.ts                     # current user / token — module-level state, not a class
```

Login is a separate, simple entry: it doesn't carry the `<Page>State` machinery — it's a single screen with a small local form. Both SPAs use React Router with `key={id}`-based path-param remount; login does not.

See `frontend-layout.md` for the complete grep rules and what lives where.

## What is deliberately not done

- **No React Context.** Stores are passed by props. If a future need is real, it will be added as a documented amendment, not assumed today.
- **No runtime schema validation** (zod, io-ts, etc.). The backend is the single source of truth for shapes; mismatches are fixed at source.
- **No `useCallback`, no `useMemo` for stability.** Observer rerenders are scoped; referential stability is irrelevant.
- **No `useReducer`.** MobX observable + actions cover the same ground without the indirection.
- **No global event bus.** Cross-page communication goes through the backend.
- **No optimistic updates by default.** Pages reload their data on relevant actions.

## Reading order for new contributors

1. This file — the rules at a glance.
2. `frontend-state.md` — internalize the state model before touching anything.
3. `frontend-pages.md` — understand page lifecycle and URL ownership.
4. `frontend-components.md` — component rules, splitting strategy.
5. `frontend-api.md` and `frontend-forms.md` — practical patterns when you start writing code.
6. `frontend-layout.md` — to find where a new file should go.
