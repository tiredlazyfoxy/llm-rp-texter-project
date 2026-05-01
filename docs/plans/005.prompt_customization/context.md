# Feature 005 — Prompt Customization

Admin-configurable prompts, dynamic prompt injection engine, optional director stage.

## Files / References

- Builds on Feature 003 (pipeline)
- `docs/architecture/quick-reference.md`

## Facts

- Director stage commits a single `{DECISION}` via `set_decision`; threaded via `DecisionState`.
- Any tool stage listing `set_decision` acts as director.
