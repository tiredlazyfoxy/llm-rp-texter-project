# utils/

Shared utilities used across SPAs.

- `formatDate.ts` — **All dates must use this**. ISO date (`YYYY-MM-DD`) or time only (`HH:MM`) if today. Never use locale-dependent formats (`toLocaleDateString()`).
- `translationSettings.ts` — **Canonical global-settings pattern**: a module-level cache (`_settings`) plus `loadTranslationSettings()` / `getTranslationSettings()` / `saveTranslationSettings(s)` (and `isTranslationSettingsLoaded()`). Synchronous read, async load/save against the backend. This is the shape new global settings caches should follow — same module-level get/save shape as `auth.ts`, sanctioned by `frontend-state.md` as the only allowed module-level mutable state alongside `auth.ts`.
- `modelSettings.ts` — Tool/text model config (`ModelConfig`) cached in `localStorage`. Same get/save shape as the global-settings pattern, but synchronous (storage-backed, no backend round-trip).
- `oocParser.ts` — `extractUserInstructions(text)` strips `(( ... ))` OOC instructions out of message text and returns `{ content, userInstructions }`.
