# Docs Folder

Top-level documentation root. Contains the project's authoritative documentation and feature planning.

## Layout

- `architecture/` — Final, approved architecture and design documentation (system overview, backend, auth, deployment, dev environment, db models, quick reference)
- `plans/` — Working area for feature planning, tracked in git for retrospective. One folder per feature (`<NNN>.<feature_name>/`) plus `backlog/` for unscheduled ideas

## Rules

- `architecture/` is for **final, approved** documentation only — produced and maintained by the architect
- `plans/` is the planner's working area — feature folders contain `context.md`, `outcome.md`, `status.md`, and one or more `<SSS>.<name>.md` step plans
- After a feature is delivered, the architect applies its `outcome.md` to update `architecture/`
- See `architecture/CLAUDE.md` and `plans/CLAUDE.md` for details on each subfolder
