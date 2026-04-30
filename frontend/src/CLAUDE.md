# src/

Frontend source — multi-page Vite app with three entry points.

- `login/` — Login/setup page (separate entry point)
- `user/` — User SPA (served at `/`)
- `admin/` — Admin SPA (served at `/admin`)
- `api/` — API client functions (chat.ts, llmServers.ts, dbManagement.ts, ...)
- `types/` — TypeScript `.d.ts` interfaces matching backend schemas (user.d.ts, chat.d.ts, llmServer.d.ts, dbManagement.d.ts)
- `utils/` — Shared utilities (formatDate.ts, ...)

See each subfolder's `CLAUDE.md` for details.
