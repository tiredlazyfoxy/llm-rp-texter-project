# Frontend

Vite multi-page application — TypeScript, React, MobX, Mantine UI.

## Directory Structure

```text
frontend/
  src/                   — Source (see src/CLAUDE.md)
    login/               — Login/setup page (separate entry point)
    user/                — User SPA (served at /)
    admin/               — Admin SPA (served at /admin)
    api/                 — API client functions
    types/               — TypeScript .d.ts interfaces matching backend schemas
    utils/               — Shared utilities
  index.html             — User SPA entry
  admin/index.html       — Admin SPA entry
  login/index.html       — Login entry
  vite.config.ts         — Multi-page build, dev proxy to :8085
  package.json
  tsconfig.json
```

See per-folder `CLAUDE.md` files for contents and routes.

## Applications

- **Login page** (served at `/login`) — Auth flow, DB setup
- **User SPA** (served at `/`) — Player-facing chat interface
- **Admin SPA** (served at `/admin`) — World and user management

## Tech

- **Bundler**: Vite 6.3+
- **UI Library**: Mantine 7.17+ (@mantine/core, @mantine/form, @mantine/hooks)
- **State**: MobX 6.13+ (observable stores)
- **Routing**: History API
- **SSE**: fetch + ReadableStream (not EventSource — needs POST + auth headers). Events: token, thinking, tool_call_start/result, phase, status, stat_update, variants_update, user_ack, done, error. Backend filters editor-only events by caller_role.

## Typing

- **Strict TypeScript — no `any` anywhere**
- All API types in `src/types/` as `.d.ts` matching backend Pydantic schemas
- All API calls strongly typed end-to-end

## Date Formatting

- **All dates use `formatDate()` from `src/utils/formatDate.ts`** — no inline date formatting
- Format: ISO date (`YYYY-MM-DD`), or time only (`HH:MM`) if the date is today
- Never use locale-dependent formats (no `toLocaleDateString()`)

## Debug Mode

Editor+ users have a debug toggle in chat settings. When enabled:
- Tool calls show full arguments + results (no truncation)
- Thinking content displayed in collapsible panels
- Generation plan visible (chain mode: facts, decisions, stat_updates — collected via planning tools)
- Hidden stats revealed with indicator badge

When disabled: clean message display, brief status text only.

## Key Constraints

- User and Admin SPAs are separate apps with separate builds
- They share **only** the login/auth flow
- Admin link shown in User SPA for admin-privileged users
- Dev: Vite proxies `/api` to localhost:8085
- Prod: nginx serves static builds, proxies `/api` to backend

## Commands

- Dev server: `npx vite --port 8094`
- Build: `npx vite build`

## Production Docker

- `frontend/Dockerfile` — multi-stage: Node 20 build → nginx:alpine
- Build output copied to `/usr/share/nginx/html`
- nginx config: `nginx/prod.conf` (multi-SPA fallback for `/`, `/admin`, `/login`)
- Build context is repo root (not `frontend/`)

## See Also

- `docs/architecture/quick-reference.md` — API endpoints, SSE protocol, data types
