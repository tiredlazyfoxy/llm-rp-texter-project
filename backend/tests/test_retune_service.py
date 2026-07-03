"""RETIRED — superseded by feature 015 step 001.

This file previously bound to feature 014's ``retune_service.maybe_retune`` /
``RetuneEmitter`` symbols. Feature 015 step 001 renamed the retune core to
``retune_service.retune_session`` and removed the ``RetuneEmitter`` alias and
the ``tuning_update`` SSE emission entirely (see the step's ``## Skeleton``), so
the old bindings no longer exist and this file could not collect.

Its still-relevant, emitter-free coverage is re-expressed against the frozen
step-001 interface in:

    backend/tests/services/test_retune_service_session_wide.py

The old emitter/SSE-based assertions (``tuning_update`` frames, the emitter
parameter) were intentionally NOT migrated: feature 015 removes that transport
(design decision D1), so asserting it would contradict the current spec. The old
auto-commit accept-and-retune repro belongs to the step-003 accept call site,
not the step-001 core.

Left as an intentionally empty (no-test) module to retire the stale bindings.
"""
