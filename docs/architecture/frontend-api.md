# Frontend — API Layer

How HTTP calls are organized, how DTOs are typed, and why there is no runtime validation.

## Folder shape

```
src/
  api/
    client.ts          # fetch wrapper, auth injection, error normalization, AbortSignal pass-through
    worlds.ts          # list, get, create, update, delete
    documents.ts       # locations, NPCs, lore, rules
    chats.ts           # chat sessions, messages, SSE helpers
    users.ts
    pipelines.ts
    llmServers.ts
    ...
  types/
    world.ts           # World, WorldCreateRequest, WorldUpdateRequest, ...
    document.ts
    chat.ts
    user.ts
    pipeline.ts
    ...
```

`api/` is **flat — one file per backend resource**. `types/` is **flat — one file per resource**, holding every DTO that crosses the wire for that resource.

## `api/client.ts` — the shared fetch wrapper

Every resource module goes through `client.ts`. Direct `fetch()` calls outside `client.ts` are a code-review failure. The client is responsible for:

- **No URL rewriting.** The `url` argument is passed straight to `fetch`. Resource modules supply absolute paths (`/api/admin/worlds`, ...) — typically via a per-module `BASE` constant. Vite proxies `/api` to `:8085` in dev; nginx mounts FastAPI at `/api` in prod.
- **Auth header injection** — reads the JWT from the registered token getter and attaches `Authorization: Bearer <token>`.
- **JSON parsing** on success.
- **Error normalization** — non-2xx responses become a typed `ApiError` with status, message, and (where present) a structured `details` object for field-level errors.
- **AbortSignal pass-through** — every request accepts `signal?: AbortSignal` and forwards it to `fetch`.

Sketch of the surface:

```ts
// src/api/client.ts
import { getToken } from '../auth';

export class ApiError extends Error {
  constructor(public status: number, message: string, public details?: unknown) {
    super(message);
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
}

export async function request<T>(url: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, {
    method: opts.method ?? 'GET',
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail ?? res.statusText, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
```

## Auth token

`client.ts` imports `getToken()` directly from `src/auth.ts`. Auth is module-level state (a plain `localStorage` read) — not a MobX store, not React state — so there's no circular-import risk and no observer concern.

Dependency direction stays one-way:

- `api/` imports from `auth.ts` (and only `auth.ts`).
- `auth.ts` does not import from `api/`.
- `pages/` and components import from `api/`.

Tests can swap the auth module via the test runner's module mock; no runtime injection layer is needed.

## `api/<resource>.ts` — typed functions, one per endpoint

Each resource module exports pure typed async functions corresponding to backend endpoints. Function signatures use DTOs from `types/`.

```ts
// src/api/worlds.ts

import { request } from './client';
import type { World, WorldCreateRequest, WorldUpdateRequest } from '../types/world';

const BASE = '/api/admin/worlds';

export const list = (signal?: AbortSignal): Promise<World[]> =>
  request<World[]>(BASE, { signal });

export const get = (id: string, signal?: AbortSignal): Promise<World> =>
  request<World>(`${BASE}/${id}`, { signal });

export const create = (payload: WorldCreateRequest, signal?: AbortSignal): Promise<World> =>
  request<World>(BASE, { method: 'POST', body: payload, signal });

export const update = (id: string, payload: WorldUpdateRequest, signal?: AbortSignal): Promise<World> =>
  request<World>(`${BASE}/${id}`, { method: 'PUT', body: payload, signal });

export const remove = (id: string, signal?: AbortSignal): Promise<void> =>
  request<void>(`${BASE}/${id}`, { method: 'DELETE', signal });
```

Conventions:

- **`signal?: AbortSignal`** is always the last argument.
- **Verbs from REST**: `list`, `get`, `create`, `update`, `remove` (or `del`). Avoid generic `fetch` / `save` names that hide intent.
- **Return types are DTOs from `types/`**, never `any`, never inline types.
- **Pass payloads as typed request DTOs**, not raw partials.

Import in state files via the resource namespace:

```ts
import * as worldsApi from '../api/worlds';
// ...
const worlds = await worldsApi.list(signal);
```

This keeps call sites self-documenting (`worldsApi.list(...)`, `chatsApi.sendMessage(...)`).

## `types/` — full API surface as DTOs

**Grep rule: if a type appears in any `api/` function signature, it lives in `types/`.**

Each `types/<resource>.ts` exports:

- The main shape (`World`).
- Request shapes (`WorldCreateRequest`, `WorldUpdateRequest`).
- Response shapes that differ from the main shape (`WorldListItem` if the list endpoint returns less than the detail).
- Enum-like literal unions (`type WorldStatus = 'draft' | 'public' | 'private' | 'archived'`).

```ts
// src/types/world.ts

export type WorldStatus = 'draft' | 'public' | 'private' | 'archived';

export interface World {
  id: string;
  name: string;
  description: string;
  characterTemplate: string;
  initialMessage: string;
  pipelineId: string | null;
  status: WorldStatus;
  ownerId: string | null;
  createdAt: string;
  modifiedAt: string;
}

export interface WorldCreateRequest {
  name: string;
  description: string;
  /* ... */
}

export interface WorldUpdateRequest {
  name?: string;
  description?: string;
  /* ... */
}
```

Conventions:

- **Single interface per concept** — wire shape == in-memory shape (we do no runtime transformation).
- **One file per resource**, flat.
- **No methods, no classes, no getters on data.** DTOs are pure shapes.
- **State interfaces and component prop interfaces live with their state/component, not in `types/`.**

## No runtime validation

We do **not** use zod, io-ts, runtypes, yup, or any other runtime schema validator at the API boundary.

```ts
// What we do
return (await res.json()) as World[];

// What we don't do
return WorldListSchema.parse(await res.json());  // NO
```

Reasons:

- Backend is Pydantic. Models are versioned in one place. If frontend and backend disagree, the fix is at source — adding a runtime schema on the frontend just bookkeeps the same constraint twice.
- No transformation layer means no "DTO vs domain model" duality. The shape we receive is the shape we use.
- Less code, fewer dependencies, clearer error stacks.
- Trade-off accepted: a backend shape change without a frontend type update will produce silent runtime mismatch rather than a parse error. We mitigate this with strict TypeScript and end-to-end testing. We do **not** add zod as a "safety net" — that's the kind of double-bookkeeping this rule rejects.

## Errors

`ApiError` is the single error shape thrown by the client. State files catch and translate to user-friendly messages or merge field errors into `serverErrors`:

```ts
try {
  const world = await worldsApi.update(state.id, state.toUpdateRequest(), signal);
  runInAction(() => { state.world = world; state.serverErrors = {}; });
} catch (err) {
  if (signal.aborted) return;
  if (err instanceof ApiError && err.status === 422 && err.details) {
    runInAction(() => { state.serverErrors = mapServerErrors(err.details); });
  } else {
    runInAction(() => { state.worldStatus = 'error'; state.worldError = String(err); });
  }
}
```

## SSE / streaming

SSE-based endpoints (chat generation) live in their resource module too — typically as a function that takes a callback or returns an async iterator and an abort handle. The same `signal` semantics apply. Implementation details belong in that file's leading comment, not duplicated across pages.

## Testing

- **Tests mock the `api/` module**, not `fetch`. State files don't know they're mocked.
- Each `api/<resource>.ts` is small enough to test by mocking the global `fetch` if needed, but state-level tests should treat `api/` as the boundary.
- `client.ts` is tested separately for auth injection, error normalization, and abort behavior.

## Anti-patterns

- `fetch(...)` in a state file or component. Move to `api/`.
- A backwards `auth → api → auth` import cycle. `auth.ts` must not import from `api/`.
- A type that crosses the wire but lives outside `types/`. Move it.
- `as any` on a response. Define the type in `types/`.
- zod / io-ts / runtypes anywhere in the runtime path. Don't add them.
- A `types/` type with methods or getters. Strip them; computed lives on state.
