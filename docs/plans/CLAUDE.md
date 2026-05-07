# Plans Folder

Working area for feature planning. Tracked in git for retrospective.

Two parallel tracks live here:

- **Multi-step features** under `docs/plans/<NNN>.<feature_name>/` — planned by `/planner`, implemented step-by-step by `/coder`.
- **Fast features** under `docs/plans/fast/<NNN>.<name>/` — small features or large bug fixes a single coder pass can deliver. Planned and implemented in one session via `/fast-feature`.

Both end with the architect applying their `outcome.md` to `docs/architecture/`.

## Layout

```
docs/plans/
  <NNN>.<feature_name>/         # multi-step feature (NNN = 3-digit feature number, own counter)
    context.md                  # required — feature-wide planner context
    outcome.md                  # required — doc changes for finalization
    status.md                   # required — per-step status + files changed
    <SSS>.<name>.md             # required per step — the step plan (SSS = 3-digit step number)
    <SSS>.context.md            # optional — extra planner context scoped to a single step

  fast/                         # fast track — single-pass features and standalone fixes
    <NNN>.<name>/               # NNN = 3-digit, own counter starting at 001
      context.md                # required — feature-wide context
      plan.md                   # required — the single plan (no per-step files)
      status.md                 # required — single row + Files Changed + (optional) Bug Fixes + Notes & Issues
      outcome.md                # required — doc changes for finalization

  backlog/
    <idea_name>.md              # ideas not yet promoted to a feature
```

- `<SSS>` (multi-step) is a 3-digit step label (e.g. `001`, `001b`, `002a`). Sub-step letter suffixes are allowed when a step is split or reworked.
- Step files inside a multi-step feature share the feature's `context.md`; only add `<SSS>.context.md` when that step needs context the others don't.
- The `fast/` counter is independent of the multi-step counter. Pick the next free `NNN` by listing `docs/plans/fast/`.

## Lifecycle

### Multi-step

1. **New idea** → `docs/plans/backlog/<idea_name>.md`
2. **Promote to feature** → create `docs/plans/<NNN>.<feature_name>/` with `context.md`, `outcome.md`, `status.md`, and at least one `<SSS>.<name>.md`
3. **Implement** → update `status.md` per step (mark done, list files changed)
4. **Finalize** → after the feature is delivered, apply `outcome.md` to `docs/architecture/` and CLAUDE docs

### Fast

1. **Identify a small feature or large bug fix** the user wants to ship in one session.
2. **Create** `docs/plans/fast/<NNN>.<name>/` with `context.md`, `plan.md`, `outcome.md`, and seeded `status.md` (single row, Status `pending`).
3. **Implement** in the same session — coder updates `status.md` Files Changed; orchestrator finalizes the row to `done` / `PASS` after verifier returns.
4. **Finalize** — same as multi-step: architect applies `outcome.md`.

A bug fix on an already-completed fast feature appends a `## Bug Fixes` section to `status.md`; the row's Status stays `done` (same convention as multi-step).

## When to use which track

Use **fast** when **all** of these hold:

- The work is one logical change (a single feature slice, a focused bug, a small refactor) rather than a coordinated set across layers.
- Roughly 50–300 lines of code change; one or two test files.
- No mid-flight dependency between sub-parts (i.e. you wouldn't need to merge sub-step A before starting sub-step B).
- No design ambiguity that would need user input mid-implementation.

Use **multi-step** otherwise — schema + service + UI + tests across layers, anything needing review between sub-steps, or anything where rolling back one piece without the others is meaningful.

## Promotion: fast → multi-step

If a fast feature turns out to be too large (mid-planning or mid-implementation), **stop and promote**. The `/fast-feature` skill and `fast-planner` agent are required to recommend promotion when scope clearly exceeds the fast bar; coder/verifier may also raise it via the escape valve.

Mechanics:

1. Stop work in the current fast folder. Do not split `plan.md` into step files in place.
2. Move or copy `context.md` and any draft `outcome.md` notes into a new `docs/plans/<NNN>.<feature_name>/` folder under the multi-step counter.
3. Delete the `docs/plans/fast/<NNN>.<name>/` folder (or leave it as a backlog seed, your call — but it is no longer the source of truth).
4. Re-enter via `/planner` to produce step files.

The user makes the call; the agents only recommend.

## Rules

- Final architecture docs go to `docs/architecture/`, not here.
- Multi-step feature folders must have all three required files (`context.md`, `outcome.md`, `status.md`) plus at least one step plan.
- Fast feature folders must have all four required files (`context.md`, `plan.md`, `outcome.md`, `status.md`).
- The two counters (multi-step `NNN` and fast `NNN`) are independent. Don't try to keep them aligned.
