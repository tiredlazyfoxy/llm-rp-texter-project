# Frontend — Pages and Routing

How pages relate to URLs, how state is created and disposed, and why the URL is the single source of cross-page truth.

## A page owns the route

**One route = one page = one fresh state instance per navigation.**

A page component is the only place that:

- Owns a `<Page>State` instance.
- Has a top-level `useEffect` that performs the initial load.
- Reads the URL (path params and query params).
- Disposes resources on unmount (abort in-flight requests).

Leaf components below the page never load data, never own page-scoped state, and never read the URL directly.

## Remount on path change

Path-param changes force a **remount** via React Router `key`:

```tsx
// routes.tsx
<Route path="/worlds/:id" element={<WorldPageRoute />} />

// WorldPageRoute.tsx
const WorldPageRoute = () => {
  const { id } = useParams();
  return <WorldPage key={id} id={id!} />;
};
```

Going `/worlds/123` → `/worlds/456` unmounts the old `WorldPage`, disposes its state and aborts its requests, then mounts a fresh one. The same mount-time `useEffect` handles the new load.

This is deliberate. The alternatives (`useEffect` with a deps array watching the param, or a "reload" method on the state) both require manually reasoning about cleanup, in-flight aborts, and partial state — easy to get wrong, hard to test, prone to staleness bugs. Remount-on-key trades one cheap React reconciliation for a guaranteed-clean lifecycle.

## Page component skeleton

Every page follows the same shape:

```tsx
import { observer } from 'mobx-react-lite';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { WorldPageState, loadWorld, saveWorld } from './worldPageState';

export const WorldPage = observer(({ id }: { id: string }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [state] = useState(() => new WorldPageState(id, searchParams));

  useEffect(() => {
    const ctrl = new AbortController();
    loadWorld(state, ctrl.signal);
    return () => {
      ctrl.abort();
      state.dispose();
    };
  }, []); // path-param changes remount the whole page; query params are not deps

  return (
    <div>
      {state.worldStatus === 'loading' && <Spinner />}
      {state.worldStatus === 'error' && <ErrorBanner message={state.worldError} />}
      {state.worldStatus === 'ready' && state.world && <WorldEditor state={state} />}
    </div>
  );
});
```

That is the page. No other `useEffect`. No other `useState`. No data-fetching in children.

## Query params are the persistence layer

Path params identify the resource (`/worlds/:id`). Query params persist **everything that should survive navigation, refresh, and bookmarking**:

- Filter (`?status=public`)
- Sort (`?sort=modified`)
- Mode (`?mode=edit`)
- Pagination cursor / offset
- Scroll-anchor / selected sub-item
- Tab selection on a tabbed page

Page state reads the query params on mount (via constructor or in the load function) and **mirrors the relevant ones back** when the user changes them.

```ts
export class WorldsPageState {
  search = '';
  sortBy: 'name' | 'modified' = 'name';
  worlds: World[] = [];
  worldsStatus: AsyncStatus = 'idle';
  worldsError: string | null = null;

  constructor(params: URLSearchParams) {
    this.search = params.get('q') ?? '';
    this.sortBy = (params.get('sort') as any) ?? 'name';
    makeAutoObservable(this);
  }
}
```

Mirroring is done in the event handler that changes the value, **not** in a `useEffect` watching the observable:

```tsx
<input
  value={state.search}
  onChange={(e) => {
    state.search = e.target.value;
    setSearchParams((p) => {
      if (e.target.value) p.set('q', e.target.value); else p.delete('q');
      return p;
    }, { replace: true });
  }}
/>
```

`replace: true` keeps the back-button history clean for high-frequency changes (typing in a filter box). Use `replace: false` for changes that meaningfully represent a separate "view" (switching tabs, applying a major filter).

## Query-param changes do NOT trigger reloads

A page **does not** install a `useEffect` watching the query string. Query-param changes are one of two things:

1. **Client-side derivations on already-loaded data.** Filter and sort produce different views via `get filteredWorlds`. The data set in memory is the same.
2. **An explicit reload triggered by the event handler that changed the param.** If `?page=2` requires a fresh fetch, the click handler that sets it also calls `loadWorlds(state, signal)`.

Never `useEffect(() => { reload(); }, [searchParams])`. That couples loading to render and breaks abort semantics.

## Path params changing on the same page

The standard answer is: they don't. Path-param changes remount the page via router `key`. If you find yourself wanting "stay on this page but switch the id," ask whether you actually want a remount (almost always yes — it's clean and free) or whether the thing you're switching is really a query param (e.g., a sub-selection) rather than a path param.

## Each page is independently loadable

**No "warm start" from a parent's loaded data.** Going from `/worlds` (which has the world list) to `/worlds/123` does **not** hand the cached world to the detail page. The detail page loads world `123` from the backend on mount.

Reasons:

- Deep-linking and refresh must work identically to navigation. If the only way the detail page works is via the list page, refresh breaks the app.
- The list response is often a summary; the detail page needs full data anyway.
- Reasoning about "what data did I get from where" is exactly the kind of cross-page coupling we're avoiding.

This is non-negotiable. Bandwidth on a small admin tool is not the bottleneck; consistency is.

A page state may own ancillary lookup data its child components need rather than letting children fetch on their own — `ChatPageState.world: WorldInfo | null` is the example, populated inside `loadChat` via a `listPublicWorlds()` filter. The page does the lookup; children read it as a slice.

## Create flow: shadow `/new` route vs inline modal

When a create surface has more than two or three fields, prefer a "shadow" `/<resource>/new` route that reuses the edit page (POST on first save, PUT thereafter — see `PipelineEditPage`'s shadow/edit modes in `pipelineEditPageState.ts`) over an inline create modal. Worlds and users keep their inline create modals because their create surfaces are small.

## No upward callbacks across pages

A common mistake: opening a modal child page that reports back to its parent ("the parent list should refresh now"). We don't do this.

The pattern is:

1. Save → API call → done.
2. Navigate back to the parent (or let the user do it).
3. Parent **remounts** (it was unmounted while the child was open) and refetches.

If you find yourself wanting `onSaveComplete` to bubble up, you've created cross-page coupling. The backend is the single source of truth — when in doubt, ask it again.

The exception is **nested routes that coexist in the same React tree** (see below). Those share state via prop-drilling because they share a mount.

## Modes as flags, mirrored to URL

View / edit mode, filter on / off, debug toggles — these are **observable flags on page state**, mirrored to query params so they survive refresh:

```ts
class WorldPageState {
  mode: 'view' | 'edit' = 'view';

  constructor(params: URLSearchParams) {
    this.mode = (params.get('mode') as any) ?? 'view';
    makeAutoObservable(this);
  }
}
```

The toggle handler updates both:

```tsx
const onEdit = () => {
  state.mode = 'edit';
  setSearchParams((p) => { p.set('mode', 'edit'); return p; });
};
```

## Nested routes and shared parent state

Nested routes that coexist in the same React tree (e.g., `/admin/pipelines/:id` containing a `/admin/pipelines/:id/stage/:idx` outlet) **share parent state via prop-drilling**, since they live in the same mount:

```tsx
<Route path="pipelines/:id" element={<PipelineLayout />}>
  <Route path="stage/:idx" element={<StageEditor />} />
</Route>
```

`PipelineLayout` owns `PipelinePageState` and passes it (or a slice) to `StageEditor` via Outlet context or explicit props. This is allowed because the parent and child share a lifetime; if the parent path changes, both unmount together.

## Active-route reads use `useLocation()`

In-SPA active-route highlighting (sidebar links, tab indicators) must read `useLocation().pathname`. `window.location.*` reads bypass router-driven re-render and silently break on client-side navigation. Cross-SPA redirects via `window.location.href = '/login/'` (and root `/`) remain explicitly allowed — those leave the SPA entirely.

## Disposal

The `useEffect` cleanup should:

1. Abort any in-flight request via the `AbortController`.
2. Optionally call a `dispose()` method on the state if it owns disposable resources (timers, EventSource subscriptions). Keep the dispose surface minimal.

```tsx
useEffect(() => {
  const controller = new AbortController();
  loadWorld(state, controller.signal);
  return () => {
    controller.abort();
    state.dispose?.();
  };
}, []);
```

The state instance itself doesn't need explicit disposal — when the component unmounts, the `useState`-held reference drops, and GC cleans up.

## Anti-patterns

- `useEffect` with deps watching a path param. Use router `key` for remount.
- `useEffect` with deps watching a query param. Handle in the event handler that changes it, or treat as a pure derivation.
- Passing loaded data from a list page to a detail page via router state or context. Refetch on the detail page.
- A modal child page that calls `onSave` to refresh the parent list. Let the parent remount and refetch.
- Multiple `useEffect`s in a page component. There should be exactly one — the mount/unmount pair.
