# Plans Folder

Working area for planning documents, task breakdowns, and drafts.

## Rules

- This folder is **tracked in git** — plans are committed for retrospective
- All plans go here during planning mode — **not** in `~/.claude/plans/`
- **Backlog**: `backlog.<idea_name>.md` — new ideas, not yet scheduled
- **Scheduled**: `stageN_stepM_somename.md` — promoted from backlog for execution
- **Done**: `stageN_stepM_somename.done.md` — completed, kept for retrospective
- Move finalized docs to `architecture/` when approved

## Lifecycle

1. New idea → create `backlog.<idea_name>.md`
2. Ready for execution → rename to `stageN_stepM_<name>.md`
3. Completed → rename to `stageN_stepM_<name>.done.md`
