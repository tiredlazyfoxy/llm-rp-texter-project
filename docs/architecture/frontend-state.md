# Frontend — State Management

Deep dive on MobX usage, the state ladder, and the rules around React hooks. Read `frontend.md` first for the high-level picture.

## Library: MobX, only

MobX is the single state library. **No Redux, no Zustand, no React Query, no React Context.** The reasons matter:

- MobX gives precise, scoped re-renders without manual selectors or memoization.
- It allows two-way binding (direct `state.field = value` from components) which is the most ergonomic shape for forms.
- Observable + computed (`get`) is a complete substitute for selectors, derived stores, and effect-based syncing.

`enforceActions: 'always'` is **not** enabled. The two-way-binding case is legitimate and common; forcing every assignment through an action adds ceremony without benefit. We use `runInAction` only for multi-field mutations that must be atomic.

## Observer everywhere

**Every component is wrapped in `observer`.** No exceptions:

```tsx
import { observer } from 'mobx-react-lite';

export const WorldRow = observer(({ world }: WorldRowProps) => {
  return <tr>...</tr>;
});
```

Forgetting `observer` is a code-review failure. It is not a "leaf-only" rule, not a "container-only" rule. Every component, every time. Even ones that don't currently read observables — they will eventually, and a missing `observer` produces silent staleness rather than a loud error.

## The state ladder

Three layers, each with a clear lifetime and purpose:

| Layer | Where it lives | Lifetime | Holds |
|-------|----------------|----------|-------|
| Module-level globals | `src/auth.ts`, `src/utils/translationSettings.ts` | App boot → page unload | Auth token + current user, global settings (translation defaults, ...) |
| `<Page>State` | `src/<spa>/pages/<page>PageState.ts`, instantiated by the page on mount | Page mount → unmount | Loaded data, drafts, modes, pagination, status flags |
| `<Component>State` | Defined inline or in a sibling file, owned by the component | Component mount → unmount | Local UI state too noisy to lift |

**Globals are plain module state, not a MobX store, not a class.** Auth and global settings are read via plain function calls (`getToken()`, `getTranslationSettings()`). React components don't need to react to them — auth changes navigate away, settings changes are explicit user actions that re-read on next use. If a future global truly needs to be reactive in the UI, that's the moment to introduce a single small observable; until then, **don't**.

Component state is reserved for genuinely component-local concerns (e.g., a transient hover index, a popover open flag, the input bar's translation buffer) — most pages won't have it.

## State is data + computed, never effectful methods

A state object is:

- **Observable fields** — the raw shape.
- **`get` computed properties** — pure derivations of those fields (validation, isDirty, isValid, canSubmit, filtered/sorted views).

A state object is **not**:

- A class with `load()`, `save()`, `delete()`, or any method that calls APIs.
- A place for side effects.

```ts
// Good
export class WorldsPageState {
  worlds: World[] = [];
  worldsStatus: AsyncStatus = 'idle';
  worldsError: string | null = null;
  search = '';
  sortBy: 'name' | 'modified' = 'name';

  constructor() { makeAutoObservable(this); }

  get filteredWorlds(): World[] {
    const q = this.search.toLowerCase();
    const matched = q ? this.worlds.filter(w => w.name.toLowerCase().includes(q)) : this.worlds;
    return [...matched].sort(/* by this.sortBy */);
  }
}

// Bad — effectful methods on state
class WorldsPageState {
  async load() { /* fetch + assign */ }   // NO
  async save(w: World) { /* ... */ }       // NO
}
```

## Effectful operations are external functions

All loads, saves, deletes — anything that touches the network or has side effects — are **top-level functions** in the same file as the page state, taking `(state, args, signal)`:

```ts
export async function loadWorlds(
  state: WorldsPageState,
  signal: AbortSignal,
): Promise<void> {
  state.worldsStatus = 'loading';
  state.worldsError = null;
  try {
    const worlds = await api.worlds.list(signal);
    runInAction(() => {
      state.worlds = worlds;
      state.worldsStatus = 'ready';
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.worldsStatus = 'error';
      state.worldsError = String(err);
    });
  }
}

export async function deleteWorld(
  state: WorldsPageState,
  worldId: string,
  signal: AbortSignal,
): Promise<void> {
  await api.worlds.delete(worldId, signal);
  runInAction(() => {
    state.worlds = state.worlds.filter(w => w.id !== worldId);
  });
}
```

This shape is deliberate:

- State stays inspectable and predictable.
- Tests for state are pure and synchronous; tests for effectful functions mock `api/`.
- Same file means everything related to one page is in two files (`<Page>.tsx` + `<page>PageState.ts`) — easy to find, easy to grep.

## Mutation rules

- **Trivial single-field assignment from components is fine** — `state.search = e.target.value` in an `onChange`. No action required, no `runInAction`.
- **Multi-field mutations wrap in `runInAction`** to ensure atomic observers fire once:

  ```ts
  runInAction(() => {
    state.worlds = worlds;
    state.worldsStatus = 'ready';
  });
  ```
- **Stores expose derivations, not setters.** Writing `state.filteredCount` is wrong — use a `get filteredCount` computed.

## React hook rules

### `useState`

**Not for reactive state.** The only allowed use is owning a stable instance across re-renders:

```tsx
const PageComponent = observer(() => {
  // Allowed: useState as a memoization primitive
  const [state] = useState(() => new WorldsPageState());

  // ... never:
  // const [count, setCount] = useState(0);  // NO — use observable instead
});
```

### `useEffect`

**Lives only at the page-component level.** Only two valid jobs:

1. **Initial load on mount.**
2. **Cleanup / abort on unmount.**

```tsx
useEffect(() => {
  const controller = new AbortController();
  loadWorlds(state, controller.signal);
  return () => controller.abort();
}, []); // empty deps — pages remount on path change via router key
```

Forbidden uses:

- **In leaf components.** Leaves never have effects; orchestration lives at the page.
- **For derivations.** Use `get computed` instead.
- **For prop-watching.** If a path-param changes, the page remounts via router `key`. If a query-param changes, handle it in the event handler that changed it (or treat it as filter-only and re-derive).

The empty-deps `useEffect` is the only deps array you should write. If you find yourself adding values to it, stop and reconsider.

### `useCallback`, `useMemo`

**Don't use them.** `observer` re-renders are scoped to the component that read the changed observable; referential stability of props is irrelevant. The only memoization primitive in play is `useState(() => ...)` for stable instance ownership.

### `useReducer`

Don't use it. MobX observables + actions cover the same ground without indirection.

### Custom hooks (`useX`)

**Don't write them.** Anywhere a custom hook is tempting, the answer is one of:

- It owns reactive UI state for a specific control (translate-with-revert on a textarea, autocomplete dropdown, ...) → write it as a **wrapper component** with a private `<Component>State` class instance owned via `useState(() => new XState())`.
- It owns state for a whole page → it's `<Page>State`, not a hook.
- It's effectful and was extracted "for reuse" → it's an external `(state, args, signal)` function colocated with the relevant state file.

This is non-negotiable. A `useX` that returns `{ doThing, isThingHappening, ... }` is just a state class with worse ergonomics — you can't inspect it, you can't pass it down, you can't test it without a renderer. Replace it with a class.

### `autorun` for rare imperative side-effects

When an imperative side-effect must fire whenever specific observables change (e.g. auto-scrolling a chat panel as messages stream), use a single `autorun` started in the mount `useEffect` and disposed in the cleanup. Read the specific fields the effect should react to — `autorun` tracks exactly what it reads. Modeled on `LlmChatPanel`:

```tsx
useEffect(() => {
  const dispose = autorun(() => {
    const last = state.messages[state.messages.length - 1];
    void state.messages.length;
    void last?.content?.length;
    void last?.thinking?.length;
    void last?.toolCalls?.length;
    scrollToBottom();
  });
  return dispose;
}, []);
```

This replaces a `useEffect` with a deps array watching reactive values — `autorun` re-runs precisely when any tracked observable changes, with no manual deps.

## Async resource trio

Every loadable resource on a state object follows the same shape:

```ts
worlds: World[];                                                   // the data
worldsStatus: 'idle' | 'loading' | 'ready' | 'error';              // status
worldsError: string | null;                                        // last error message
```

Rules:

- **No wrapper type.** No `AsyncValue<T>`, no `Resource<T>`, no `mobx-utils fromPromise`.
- **No boolean flags.** `isLoading: boolean` is forbidden — `status === 'loading'` is the canonical check.
- **Naming**: `<name>` / `<name>Status` / `<name>Error`. Plural data fields use plural names (`worlds`, `worldsStatus`).
- **Status transitions** happen inside the load function via `runInAction` — components never touch `Status` directly.

A page with three loadables has three trios. There is no aggregation type — components compose UI by reading the specific status they care about.

Action errors (post-load mutations like edit/delete/compact) typically surface via a single `state.error: string | null` shared across the actions on a page state — see `chatPageState.ts`. Field-level error mapping (`serverErrors`) is reserved for form drafts (`worldEditPageState`, `pipelineEditPageState`); see `frontend-forms.md`.

## When state lives where

| Concern | Layer |
|---------|-------|
| Auth token, current user | Module-level (`auth.ts`) — plain functions |
| Global settings (translation defaults, etc.) | Module-level (`utils/translationSettings.ts`) |
| List of worlds for the worlds page | `WorldsPageState` |
| Draft of a world being edited | `WorldPageState` |
| Selected tab on a multi-tab settings page | `SettingsPageState` (or sub-slice) |
| Translation buffer / canRevert for an input bar | `LlmInputState` — component-local class instance |
| Hover index on a long list (UI only) | Component-local — small `class` instance via `useState(() => ...)` |

The default answer is "page state." Component state is for self-contained UI behaviors (input bar, autocomplete dropdown). Globals are plain module functions, never a class.

## Anti-patterns

- `useState` holding domain data (a list, a draft, a status). Move it to page state.
- `useEffect` watching a deps array of more than zero. Replace with router-key remount or event-handler logic.
- A method on a state class that calls `api.*`. Move it to a top-level function.
- `isLoading: boolean` instead of the trio. Replace with `<name>Status: AsyncStatus`.
- `useCallback` "for stable refs." Delete it.
- React Context for state. Pass props instead.
