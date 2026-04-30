# Feature 003 — Agent Pipeline

Two-stage agent pipeline, generation plans, hidden stats. Admin model + backend implementation + per-mode flows (simple/chain) + per-area splits (backend/frontend).

## Files / References

- `architecture/quick-reference.md` — pipeline patterns
- Depends on Feature 002 (chat) and Feature 001 (admin)

## Facts

- Pipeline supports multiple modes (simple, chain).
- Each generation step may produce hidden state forwarded to next step.
- Step numbering reflects evolution: original step1 (`1.agent_pipeline.md`) was reworked into a model-admin focused step (`1b.pipeline_model_admin.md`); step2 split into `2`, `2a` (simple), `2b` (chain); step3 split into `3a` (backend) and `3b` (frontend).
