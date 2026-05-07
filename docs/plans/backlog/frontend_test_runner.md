# Frontend Test Runner

Bootstrap a frontend test runner so step plans stop writing test bullets that have no runner to satisfy.

## Motivation

Status notes from features 005, 010, and 012 all flag the absence of any frontend test framework — no `vitest`, no `jsdom`, no `@testing-library`, no `*.test.*` / `*.spec.*` files anywhere under `frontend/src/`. Step plans keep requesting tests "next to the existing ones" — there are none. Today, frontend changes are verified manually via `npm run build` (tsc + vite).

## Scope

- Add devDeps: `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/dom`, `@testing-library/user-event`.
- New `vitest.config.ts` (or extend `vite.config.ts`) with jsdom env + path aliases.
- Wire `npm test` and `npm run test:watch` in `package.json`.
- Update `tsconfig` `types` / `include` so `vitest`'s globals + jsdom DOM types resolve.
- One worked example test per category (pure helper, MobX state class, observer component) so future plans have a precedent to point at.
- Update `frontend/CLAUDE.md` to point at the runner and document the conventions.

## Out of scope

- Backfilling tests for already-shipped features (10, 12, etc.). The runner ships first; coverage grows organically.

## Open questions

- Mock layer for `api/` modules — explicit `vi.mock('@/api/chats')` in each test, or a shared `__mocks__/api/` setup file? Default: explicit per-test until a shared shape emerges.
- DOM-event helpers — `@testing-library/user-event` is the standard; `fireEvent` is a fallback when ergonomics matter.
