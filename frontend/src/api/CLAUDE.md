# api/

API client functions. Strongly typed end-to-end against `src/types/` definitions.

## Conventions

- **`client.ts`** is the shared fetch wrapper. Every JSON call goes through `request<T>(url, { method, body, signal })`.
  - `body` is a plain JS value — the client JSON-serializes.
  - Non-2xx responses throw `ApiError(status, message, details)`.
  - 204 No Content returns `undefined`.
  - `signal` is optional; pass it to abort in-flight requests on unmount.
- Every public function in `<resource>.ts` accepts an optional `signal: AbortSignal` as its **last** argument.
- Multipart uploads and blob downloads use raw `fetch()` with `authHeaders()` (no Content-Type JSON) and call `throwApiError(res)` on failure.
- Streaming endpoints (SSE) live in `sse.ts`, `translateStream.ts`, and inline in `chat.ts`. They create their own `AbortController` and return it; the caller stores it and aborts on unmount.

## Files

- `client.ts` — `request<T>`, `authHeaders()`, `ApiError`, `throwApiError`. The only place `fetch` is wrapped.
- `auth.ts` — `getAuthStatus`, `login`, `setupCreate`, `setupImport`, `changePassword`. Login/setup endpoints don't require auth.
- `worlds.ts` — worlds, documents, stats, rules, npc-location-links (admin).
- `pipelines.ts`, `llmServers.ts`, `dbManagement.ts`, `admin.ts` — admin resources.
- `chat.ts` — user chat sessions, messages, summaries, plus SSE streamers (sendMessage, regenerateMessage, compactChatStream).
- `llmChat.ts` — admin LLM chat panel + admin translate.
- `userSettings.ts` — current user's settings (translation defaults, model list).
- `sse.ts`, `translateStream.ts` — SSE helpers consumed by `chat.ts` and `llmChat.ts`.
