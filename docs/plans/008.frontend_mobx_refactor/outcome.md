# Feature 008 — Outcome (post-implementation doc updates)

The architecture docs in `docs/architecture/` have already been updated up-front to reflect the locked decisions for this refactor (see `context.md`). The outcome of this feature is therefore primarily about **per-folder `CLAUDE.md` files inside `frontend/`**, plus any small architecture corrections that surface during implementation.

## Per-step CLAUDE.md updates

CLAUDE.md updates happen **inside the step that touches the relevant folder**, not in a batched final pass. This list catalogs the files that will end up touched across the feature so we can verify completeness at the end.

- `frontend/CLAUDE.md` — note multi-page entries (`/`, `/admin`, `/login`), MobX-state-per-page rule reference, custom-hooks-not-allowed reference. Update once routing + state pattern is in.
- `frontend/src/CLAUDE.md` — refresh layout summary (per-SPA structure, shared `api/`/`types/`/`utils/`/`auth.ts`, no `appState.ts`).
- `frontend/src/api/CLAUDE.md` — list `client.ts` (renamed) + `ApiError`, mention `AbortSignal` convention. Note auth-token read pattern (direct import from `auth.ts`).
- `frontend/src/types/CLAUDE.md` — confirm folder stays named `types/` (it's the API DTO surface despite the name); list current modules.
- `frontend/src/user/CLAUDE.md` — replace ChatStore singleton mention with per-page state pattern; list pages and route table; note `routes.tsx` location.
- `frontend/src/admin/CLAUDE.md` — same shape as user; remove `hooks/` mention; list components in their new domain subfolders.
- `frontend/src/login/CLAUDE.md` — note that login is intentionally simpler (no router, no `<Page>State`).
- `frontend/src/utils/CLAUDE.md` — note `translationSettings.ts` is the global-settings pattern (module-level cache, get/save).
- New per-domain `CLAUDE.md` files under `components/` if domain folders end up justifying them.

## Architecture corrections that may surface

If during implementation we discover the architecture docs are wrong about something concrete (a rule that doesn't fit the actual code, an example that doesn't compile, a pattern the codebase has reasons to deviate from), the architect updates the relevant `frontend-*.md` file as part of the same step. Architecture docs and code stay in sync.

The expected updates **at this point** (not yet applied) are limited to:

- Possibly tightening the `routes.tsx` pattern in `frontend-pages.md` once we see how the per-SPA shape actually composes with login as a separate entry.
- Possibly noting cross-SPA-shared layout components (`AppHeader`, `AppLayout`, `AppSidebar`) as a recognized exception to "components live under their SPA" — they are shared layout shells.

## CLAUDE.md project-wide

- `CLAUDE.md` (project root) — no expected change; the project rules already point to `docs/architecture/` for frontend rules.
- `~/.claude/.../memory/MEMORY.md` — auto-memory will be updated separately as the user's session preferences evolve; not part of this feature's outcome.

## Verification at feature close

When all steps are done, the architect (or a final review pass) confirms:

1. Every `frontend/**/CLAUDE.md` file referenced above has been updated by the step that touched it.
2. No `appState.ts`, no `models/` folder, no `hooks/` folders exist in `frontend/src/`.
3. No custom `useX` hooks remain (grep `^export function use[A-Z]` and `^function use[A-Z]` should return nothing in `frontend/src/`).
4. Every component file imports `observer` and is wrapped with it.
5. Every page has a sibling `<page>PageState.ts` and a single mount/unmount `useEffect`.
6. `frontend/src/api/client.ts` exists with `ApiError` and `AbortSignal` plumbing; no `fetch(` outside `src/api/`.
7. The architecture docs and the actual code agree.

## Observations

- Step 001: many stray compiled `.js` files exist next to `.tsx` files across `frontend/src/` (untracked). Possible impact: add a guard to `frontend/CLAUDE.md` (or the cleanup step) noting `tsconfig.json` should keep `noEmit` true (Vite handles emit) and the leftover `.js` files should be removed; consider a `.gitignore` rule for `src/**/*.js` to prevent accidental check-in.
