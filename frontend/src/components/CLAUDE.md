# components/

Cross-SPA shared components. Flat layout — every file here is shared by both the User and Admin SPAs.

## Layout shells

- `AppLayout.tsx` — top-level shell (header + sidebar + content slot)
- `AppHeader.tsx` — top bar
- `AppSidebar.tsx` — collapsible sidebar shell consumed by SPA-specific sidebars
- `ChangePasswordModal.tsx` — modal opened from the user menu
- `TranslationSettingsModal.tsx` — modal for the global translation settings cache (`utils/translationSettings.ts`)

## Shared input wrappers

- `LlmInputBar.tsx` (+ `llmInputState.ts`) — controlled textarea bundled with translate/revert/send/stop UI. Internal state class `LlmInputState` is owned per mount; mutation lives in external functions (`startTranslate`, `revertTranslate`, `stopTranslate`, `clearTranslateError`, `onValueEdit`). Caller passes `value`/`onChange`; optional `translateFn` enables translation, `before`/`extras` are slot props for caller-specific rows. Used by `user/components/chats/ChatInput.tsx` and `admin/components/llm/LlmChatPanel.tsx`.

## Conventions

- No custom `useX` hooks. Reusable stateful UI behavior is a wrapper component owning a `<Component>State` class — see `LlmInputBar` for the canonical pattern.
- A state class lives next to its component as `<componentName>State.ts`; mutation functions take `(state, ...args)` and live in the same file.

## Documented exceptions

- `ChangePasswordModal.tsx` and `TranslationSettingsModal.tsx` are intentionally kept on plain `useState` form fields rather than the canonical draft+observer pattern. Each is a small, single-screen modal opened rarely from the user menu, with no reactive interaction with anything outside its own form. Migrating to a `<Draft>` class + external `submit*(draft, signal)` would be purely cosmetic. If either modal grows new fields, cross-form validation, or shared state with the page, migrate it then. They remain unwrapped by `observer` for the same reason — no observable reads.
