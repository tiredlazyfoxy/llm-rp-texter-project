# Feature 003 — Agent Pipeline

Two-stage agent pipeline, generation plans, hidden stats. Admin model + backend implementation + per-mode flows (simple/chain) + per-area splits (backend/frontend).

## Files / References

- `architecture/quick-reference.md` — pipeline patterns
- Depends on Feature 002 (chat) and Feature 001 (admin)

## Facts

- Pipeline supports multiple modes (simple, chain).
- Each generation step may produce hidden state forwarded to next step.
- Step numbering reflects evolution: original step 001 (`001.agent_pipeline.md`) was reworked into a model-admin focused step (`001b.pipeline_model_admin.md`); step 002 split into `002`, `002a` (simple), `002b` (chain); step 003 split into `003a` (backend) and `003b` (frontend).
