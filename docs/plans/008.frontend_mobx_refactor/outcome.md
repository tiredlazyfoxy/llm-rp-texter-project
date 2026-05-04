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
- Step 003: `WorldInfoModal` (now under `frontend/src/user/components/worlds/`) is imported nowhere in `frontend/src/`. Possible impact: cleanup step should either delete it or restore the call site if a "world info" affordance was intended on the chat page.
- Step 003b: `admin/pages/WorldFieldEditPage.tsx` carries a permanently-disabled (`isPipelinePrompt = false`) pipeline-prompt branch — `<PlaceholderTextarea>`, `<PlaceholderPanel>`, "Load Default Template" button, and `getPipelineConfigOptions()` fetch — all dead since pipeline-prompt editing moved out in feature 007. Possible impact: the page's later migration step (or a cleanup pass) should delete the dead branch and the now-unused `PlaceholderPanel` / `getPipelineConfigOptions` imports, simplifying the page to a plain field editor.
- Step 003b: `LlmInputBar` derives the textarea-disabled state as `disabled || busy || isTranslating`. Callers that previously left the textarea enabled when only "send" was disabled (e.g., `LlmChatPanel` with no model selected) now grey out the textarea too — `disabled={!selectedModel}` propagates. Possible impact: if this uniform behavior is the new intent, mention it in `frontend-components.md` under the wrapper-component pattern; otherwise split into separate `inputDisabled`/`sendDisabled` props.
- Step 005: `ChatPageState` carries a `world: WorldInfo | null` field populated inside `loadChat` via `listPublicWorlds()` filter (parallels `WorldPageState.loadWorld`). Possible impact: `frontend-pages.md` could note the "page state owns ancillary lookup data needed by its child components" pattern, or `frontend-api.md` could flag that the lack of a `GET /api/chats/worlds/{id}` endpoint forces a list-then-filter — a future backend step could add a by-id endpoint.
- Step 005: `editMessage` and `compactUpTo` external functions surface API errors via `state.error: string | null` (a single field shared across all chat actions). Possible impact: `frontend-state.md` could acknowledge the "single error string per page state" pattern as the default, with field-level error mapping reserved for forms.
- Step 006: pre-migration `WorldViewPage` mirrored its tab to a path slug (`/admin/worlds/<id>/locations`) via `history.replaceState`, but `routes.tsx` only registered `/worlds/:worldId` — those slug URLs never round-tripped through the router. Migrated to `?tab=` query mirroring per the locked URL-as-state rule. Possible impact: `frontend-pages.md` already documents query-param mirroring; no doc change needed, but a one-line entry in `quick-reference.md` listing tab → query is the canonical example would help.
- Step 006: backend `update_world` returns FastAPI's default 422 shape (`{ detail: [{ loc, msg, type }, ...] }`) without app-side field mapping. `worldEditPageState.ts` includes a `mapServerErrors` that walks `detail[*].loc` and assigns to `serverErrors[field]`. Possible impact: if more form pages adopt server-error mapping, lift `mapServerErrors` (or a typed equivalent) to a shared `utils/forms.ts` and document the loc→field convention in `frontend-forms.md`.
- Step 006: `WorldEditPage`'s inline `StatFormModal`/`RuleFormModal` use class drafts (`StatDraft`/`RuleDraft`) declared in the page file, not in a sibling state file, since they're single-consumer subcomponents. Possible impact: `frontend-forms.md`'s "Modal-form drafts (component-local)" section could explicitly say "the draft class lives next to the modal in the same file when it has only one consumer".
- Step 006: `WorldViewPage` keeps the architecture-allowed component-local UI flags (`createOpen`, `hoveredId`, `expanded`/`overflows`, `uploadType`) as plain `useState`. The step's literal verification regex disallows any non-`useState(() => new ...)` form, but `frontend-state.md` line 41 explicitly lists "transient hover index, popover open flag" as legitimate component state. Possible impact: future step verification clauses should either narrow the regex (e.g., exclude `useState(false)` / `useState(null)` for boolean/null UI flags) or reference the architecture exception explicitly so the rule and the doc agree.
- Step 007: `PipelinesListPage`'s legacy "Create Pipeline" inline modal (collected name/kind/description and POSTed immediately) was replaced by a navigate to `/pipelines/new` — the form-page shadow mode now collects the same fields and POSTs on Save. This is a flow change without a feature change. Possible impact: `frontend-pages.md` (or `quick-reference.md`) could document the "shadow page replaces inline create modal" pattern as the canonical create flow when the create surface has more than two or three fields (worlds/users still use inline modals because they have small create surfaces).
- Step 007: `LlmChatPanel` migrated auto-scroll from a `useEffect([state.messages.length])` to a MobX `autorun` set up in the panel's mount `useEffect` and disposed on unmount. Possible impact: `frontend-state.md` already mentions `autorun` for "rare allowed effects"; could add an explicit example of the "single autorun started in the mount effect, disposed in cleanup" pattern (the autorun touches the specific observable fields it should react to, then performs the imperative side-effect).
- Step 007: `PlaceholderTextarea` exposes an imperative `controllerRef` of shape `{ insertAtCursor(text: string): void }` for callers that need cursor-position insertion without owning the underlying DOM ref. Possible impact: `frontend-components.md`'s wrapper-component section could codify this as the canonical escape valve when a wrapper component needs to expose a small named imperative API to its parent (preferred over re-exposing internal refs).
- Step 009: `frontend/tsconfig.json` now sets `"noEmit": true` so a stray `tsc` invocation can't re-emit `.js` siblings into `frontend/src/`. Possible impact: a one-line note in `frontend/CLAUDE.md` ("`tsc` is type-check only — Vite owns emit") would make the constraint discoverable; alternatively add `frontend/src/**/*.js` to the project-root `.gitignore` as a belt-and-suspenders guard.
- Step 009: cross-SPA shared modals `ChangePasswordModal` and `TranslationSettingsModal` are kept on plain `useState` form fields with a documented exception in `components/CLAUDE.md`. Possible impact: `frontend-forms.md` (or `frontend-components.md`) could codify the "tiny single-screen modal with no reactive interaction outside its own form" exception explicitly so future callers know the bar for staying outside the canonical draft+observer pattern.
- Step 009: `AppSidebar.tsx` and `UserSidebar.tsx` switched from `window.location.pathname` to `useLocation().pathname`. Possible impact: `frontend-pages.md` (or `quick-reference.md`) could note that any active-route highlighting in sidebars must use `useLocation()` — `window.location.*` reads inside an SPA bypass router-driven re-render and silently break on client-side navigation.

---

## Applied 2026-05-05

- Up-front architecture changes (per `status.md`) were applied before steps began.
- Per-step `frontend/**/CLAUDE.md` updates landed inside their respective steps (per the plan).
- Verifier-fix doc edits to `frontend-api.md` (no `/api` auto-prefix; per-module `BASE`) and `frontend-pages.md` (`ctrl.abort(); state.dispose();`) accepted as-is.
- Observation follow-ups applied: B1/B2 in `frontend-state.md`; B3/B4/B5 in `frontend-pages.md`; B6/B7/B8 in `frontend-components.md`; B9 in `frontend-forms.md`; B10 in `frontend/CLAUDE.md`; B11 in `quick-reference.md`.
- Rejected: `WorldInfoModal` unused (already deleted in step 009); dead `isPipelinePrompt` branch (already removed in step 006); verification-regex narrowing (planner-process concern, not architecture).
- Deferred to backlog: lifting duplicated `mapServerErrors` (across `worldEditPageState`/`pipelineEditPageState`/`documentEditPageState`) to a shared `utils/forms.ts` — code change, not a doc change.
