# Plans Folder

Working area for feature planning. Tracked in git for retrospective.

## Layout

```
docs/plans/
  <NNN>.<feature_name>/         # NNN = 3-digit feature number, sorts the list
    context.md                  # required — global planner context for the feature: files, references, facts
    outcome.md                  # required — documentation changes to be made after implementation
    status.md                   # required — per-step status + files changed (just a list)
    <SSS>.<name>.md             # required per step — the plan: what will change (SSS = 3-digit step number)
    <SSS>.context.md            # optional — extra planner context scoped to a single step
  backlog/
    <idea_name>.md              # ideas not yet promoted to a feature
```

- `<SSS>` is a 3-digit step label (e.g. `001`, `001b`, `002a`). Sub-step letter suffixes are allowed when a step is split or reworked.
- Step files inside a feature share the feature's `context.md`; only add `<SSS>.context.md` when that step needs context the others don't.

## Lifecycle

1. **New idea** → `docs/plans/backlog/<idea_name>.md`
2. **Promote to feature** → create `docs/plans/<NNN>.<feature_name>/` with `context.md`, `outcome.md`, `status.md`, and at least one `<SSS>.<name>.md`
3. **Implement** → update `status.md` per step (mark done, list files changed)
4. **Finalize** → after the feature is delivered, apply `outcome.md` to `docs/architecture/` and CLAUDE docs

## Rules

- Final architecture docs go to `docs/architecture/`, not here.
- Every feature folder must have all three required files (`context.md`, `outcome.md`, `status.md`) plus at least one step plan.
