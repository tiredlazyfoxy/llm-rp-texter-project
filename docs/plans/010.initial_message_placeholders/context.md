# Feature 010 — Initial Message Placeholders

## Goal

Bring the same placeholder UX that the pipeline stage editor offers
(panel of clickable badges + inline `{PARTIAL` autocomplete) to the
world's `initial_message` field in `WorldFieldEditPage`. Normalize
the runtime placeholder tokens to UPPERCASE everywhere
(`{CHARACTER_NAME}`, `{LOCATION_NAME}`, `{LOCATION_SUMMARY}`),
including a one-time data migration of existing worlds.

## Resolved decisions (from orchestrator briefing)

1. **Reuse strategy** — move the existing pipeline placeholder
   components to a shared admin folder and reuse them on
   `WorldFieldEditPage`. Identical UX to the pipeline editor.
2. **Source of placeholder list** — hard-coded constants on the
   frontend; no new backend endpoint.
3. **Casing** — uppercase everywhere. Lowercase tokens in existing
   worlds are migrated.
4. **Scope** — `initial_message` only. The `description` field on
   `WorldFieldEditPage` keeps its plain `<Textarea>`.

## Placeholders exposed in the new UI

| Token                  | Replacement (runtime)                              | Category |
|------------------------|----------------------------------------------------|----------|
| `{CHARACTER_NAME}`     | Chat session character name                        | Character |
| `{LOCATION_NAME}`      | Starting location name                             | Location  |
| `{LOCATION_SUMMARY}`   | Starting location content / summary                | Location  |

(Categories mirror the pipeline registry's `category` field on
`PlaceholderInfo`. We reuse `PlaceholderInfo` directly — no
duplicate type.)

## Files involved across multiple steps

### Frontend
- `frontend/src/admin/components/pipelines/PlaceholderTextarea.tsx`
  — to be moved (steps 002, 003).
- `frontend/src/admin/components/pipelines/PlaceholderPanel.tsx`
  — to be moved (steps 002, 003).
- `frontend/src/admin/components/pipelines/PlaceholderSuggestions.tsx`
  — to be moved (step 002).
- `frontend/src/admin/components/pipelines/placeholderAutocompleteState.ts`
  — to be moved (step 002). The `getPartial` regex `/^[A-Z_]*$/`
  (~line 85) already matches the uppercase convention; no logic
  change needed.
- `frontend/src/admin/pages/PipelineStageEditPage.tsx`
  — imports updated after the move (step 002).
- `frontend/src/admin/pages/WorldFieldEditPage.tsx`
  — gains placeholder UI for `initial_message` (step 003).
- `frontend/src/admin/pages/worldFieldEditPageState.ts`
  — referenced (read-only) for `WorldFieldName` (step 003).
- `frontend/src/types/pipeline.d.ts`
  — defines `PlaceholderInfo`, reused as-is.

### Backend
- `backend/app/services/chat_service.py`
  — runtime substitution at lines 425-432 (step 001).
- `backend/app/services/prompts/world_field_editor_system_prompt.py`
  — placeholder list in docstring at lines ~43-47 (step 001).
- World JSONL importer (location to be confirmed by coder when
  reading the harvested codebase — see `001.context.md`)
  — decision on import-path normalization (step 001).
- One-time idempotent migration in the DB init path (step 001).

## Cross-cutting constraints

- **Frontend folder convention** (see
  `docs/architecture/frontend-layout.md` Rule 4 and
  `frontend/src/admin/CLAUDE.md`): page-aware components live under
  `components/<domain>/`. The placeholder components are admin-only
  and shared between two domains (pipelines, worlds), so the right
  home is a new domain folder `frontend/src/admin/components/placeholders/`.
- **Layer separation** (see `backend/CLAUDE.md`): the migration
  must touch DB rows through the `db/` layer. No `session` /
  `select()` outside `db/`.
- **JSONL import/export rule** (see project `CLAUDE.md`): a
  data-content change does not change the export shape, but the
  importer should not re-introduce lowercase tokens from old
  backups (see "Open trade-off" below).
- **Strict typing** — no `any` on the frontend, Pydantic /
  TypedDict on the backend.
- **`observer` everywhere** — every new/modified component stays
  wrapped in `observer`.

## Open trade-off — JSONL import behavior

Two acceptable choices for handling old (lowercase-token) backups
on re-import:

A. Apply the same uppercase substitution at the importer for
   `World.initial_message`. Pro: re-importing a pre-migration
   backup yields a normalized DB. Con: a small amount of import-
   path code that "knows" about a one-time migration.

B. Leave the importer untouched and rely solely on the startup
   migration to normalize after import (since the migration is
   idempotent and runs on every boot, an old backup imported into
   a running system would be normalized on the next start).

Plan picks **A** — apply the substitution at both the import path
and the startup migration. Reason: the importer is the only path
that can introduce stale tokens after the migration has already
run (e.g. an admin importing an old backup mid-session would
otherwise see lowercase tokens until the next process restart).
The substitution is a 3-line change reused from a shared helper,
so the cost is negligible.

## References

- `docs/plans/CLAUDE.md` — plan layout and lifecycle.
- `docs/architecture/frontend-components.md` — generic vs page-
  aware components, `controllerRef` pattern (see "Imperative API
  escape valve").
- `docs/architecture/frontend-layout.md` — Rule 4 (folder
  convention for components).
- `frontend/src/admin/CLAUDE.md` — current admin component
  layout, including `PlaceholderTextareaController` shape.
- `backend/CLAUDE.md` — layer separation, JSONL import/export
  policy.

## Vocabulary

- **Placeholder token** — the literal `{CHARACTER_NAME}` text
  inside an `initial_message` value.
- **Placeholder info** — the `PlaceholderInfo` DTO
  (`{ name, description, category }`) consumed by
  `PlaceholderPanel` / `PlaceholderTextarea`.
- **Placeholders folder** — the new shared admin folder
  `frontend/src/admin/components/placeholders/` introduced by
  step 002.
