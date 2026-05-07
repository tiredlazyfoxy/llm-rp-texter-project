# Docs Folder

Top-level documentation root. Contains the project's authoritative documentation and feature planning.

## Layout

- `architecture/` — Final, approved architecture and design documentation (system overview, backend, auth, deployment, dev environment, db models, quick reference)
- `plans/` — Working area for feature planning, tracked in git for retrospective. Two parallel tracks:
  - Multi-step features: `plans/<NNN>.<feature_name>/` (planned by `/planner`, implemented step-by-step by `/coder`)
  - Fast features: `plans/fast/<NNN>.<name>/` (single-pass small features or large bug fixes via `/fast-feature`)
  - Plus `plans/backlog/` for unscheduled ideas

## Rules

- `architecture/` is for **final, approved** documentation only — produced and maintained by the architect
- `plans/` is the planner's / fast-feature's working area:
  - Multi-step folders contain `context.md`, `outcome.md`, `status.md`, and one or more `<SSS>.<name>.md` step plans
  - Fast folders contain `context.md`, `plan.md`, `outcome.md`, `status.md` (no step files)
- After a feature is delivered (multi-step or fast), the architect applies its `outcome.md` to update `architecture/`
- See `architecture/CLAUDE.md` and `plans/CLAUDE.md` for details on each subfolder
