# Feature 008 — Status

Steps are planned and implemented one at a time. This file tracks per-step status and lists files changed.

## Up-front architecture updates (pre-step)

Already applied (locked decisions baked into the docs before any step is planned):

- `docs/architecture/frontend.md` — types/ name kept, AppState removed, login-as-separate-entry noted, folder layout updated.
- `docs/architecture/frontend-state.md` — state ladder shows module-level globals instead of AppState; "no custom useX hooks" rule added.
- `docs/architecture/frontend-api.md` — types/ name; `client.ts` reads `getToken()` directly from `auth.ts` (no DI/injection layer).
- `docs/architecture/frontend-components.md` — wrapper-component-with-internal-state-class pattern added (the LlmInputBar shape); custom-hook anti-pattern added.
- `docs/architecture/frontend-layout.md` — types/ kept, no `appState.ts`, no `hooks/` folder, per-SPA structure under `src/user/` and `src/admin/`, login entry noted.
- `docs/architecture/quick-reference.md` — folder layout, state ladder, hard rules updated.
- `docs/architecture/README.md` — front-matter updated.
- `docs/architecture/CLAUDE.md` — frontend-api.md description updated.

## Steps

| Step | Title | Status |
|------|-------|--------|
| 001 | Routing foundation | planned |
| 002 | API client.ts + ApiError + AbortSignal | planned |
| 003 | Component folder reorg | planned |
| 003b | Hooks → wrapper components | planned |
| 004 | User SPA non-chat pages | planned |
| 005 | Chat refactor (singleton → ChatPageState) | planned |
| 006 | Admin worlds domain | planned |
| 007 | Admin pipelines domain | planned |
| 008 | Admin users / LLM / DB | planned |
| 009 | Cleanup pass | planned |

## Files changed (cumulative)

(populated per step on completion)
