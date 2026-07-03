"""Session-wide retune-core tests for feature 015 step 001.

Bound to the frozen step-001 skeleton (``## Skeleton`` in
``docs/plans/015.background_retune/001.session_wide_retune_core.md``):

- ``app.db.generation_feedback.list_by_session(session_id: int)
  -> list[ChatGenerationFeedback]`` — new sibling DAL; created_at-ascending
  ordering, no turn filter.
- ``app.services.retune_service.retune_session(session_id, user_id, world_id,
  turn_number, accepted_content, model_id) -> None`` — async; the renamed retune
  core (was ``maybe_retune``). **No emitter parameter.** Reads reject evidence
  from ``list_by_session`` (all turns), no-ops when ``model_id is None`` or when
  the session has zero rejects, partitions rejects by scope
  (``plan``/``null`` -> plan dim; ``text``/``null`` -> tone dim), runs one
  completion per targeted dimension, and persists via
  ``tuning_profiles_db.upsert(...)``.
- ``app.services.retune_service.RetuneEmitter`` — **removed** (DoD-7).

Expected values come from the step spec (Definition of done + Interface intent)
only — the implementation body is never read.

LLM boundary: the retune core obtains its client via
``get_llm_client_for_model`` and makes a non-tool ``chat`` call inside the
(unchanged) ``_retune_dimension`` helper. The fake is installed at the
consuming-module seam ``retune_service.get_llm_client_for_model`` and returns a
deterministic constant (``"RETUNED"``) so a targeted dimension's post-retune
value is distinguishable from its seeded initial value, and the number of
``chat`` calls equals the number of targeted dimensions (spec: "one
``_retune_dimension`` completion per targeted dimension").

Upsert boundary: ``tuning_profiles_db.upsert`` is a namespace-module DAL call
(``from app.db import tuning_profiles``); a spy is installed on the module
attribute ``app.db.tuning_profiles.upsert`` (visible through the service's
module reference) that records each call and still delegates to the real DAL so
persistence is observable via ``profiles_db.get``.

DB layer (``db/tuning_profiles``, ``db/generation_feedback``) is real against
the test DB engine; profiles/feedback are seeded with arbitrary snowflake ids
(FK enforcement is off in the test SQLite DB).

Red-gate note: the ``list_by_session`` and ``retune_session`` stubs raise
``NotImplementedError``; these tests assert the spec-correct behavior and
(correctly) fail until the coder implements the core.
"""

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from app.db import generation_feedback as feedback_db
from app.db import tuning_profiles as profiles_db
from app.models.chat_generation_feedback import ChatGenerationFeedback
from app.models.chat_tuning_profile import ChatTuningProfile
from app.services import retune_service
from app.services.snowflake import generate_id

# The fake LLM always returns this string; a targeted dimension's value becomes
# this after retune, while an untargeted dimension keeps its seeded initial.
RETUNED = "RETUNED"
INITIAL_PLAN = "INITIAL_PLAN"
INITIAL_TONE = "INITIAL_TONE"
ACCEPTED_CONTENT = "The accepted final prose."


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Fake LLM client for the retune completion (non-tool `chat`).
# ---------------------------------------------------------------------------


class FakeRetuneLLM:
    """Async-context LLM stand-in. Records each non-tool `chat` call so tests
    can assert the call count (= number of targeted dimensions); returns the
    deterministic RETUNED string as the revised tuning text."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __aenter__(self) -> "FakeRetuneLLM":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def chat(self, *args, **kwargs) -> str:
        self.calls.append({"args": args, "kwargs": kwargs})
        return RETUNED


def _install_fake_retune_llm(monkeypatch: pytest.MonkeyPatch) -> FakeRetuneLLM:
    fake = FakeRetuneLLM()

    async def _factory(model_id):
        return fake

    monkeypatch.setattr(
        "app.services.retune_service.get_llm_client_for_model",
        _factory,
        raising=False,
    )
    return fake


def _spy_upsert(monkeypatch: pytest.MonkeyPatch) -> list[ChatTuningProfile]:
    """Record every ``tuning_profiles.upsert`` call while still delegating to
    the real DAL. Patched on the module attribute so the service's namespace
    reference (``tuning_profiles_db.upsert``) resolves to the spy."""
    calls: list[ChatTuningProfile] = []
    original = profiles_db.upsert

    async def _spy(profile: ChatTuningProfile) -> None:
        calls.append(profile)
        return await original(profile)

    monkeypatch.setattr("app.db.tuning_profiles.upsert", _spy)
    return calls


# ---------------------------------------------------------------------------
# Seeding helpers.
# ---------------------------------------------------------------------------


async def _seed_profile(
    user_id: int, world_id: int, plan_tuning: str, tone_tuning: str
) -> None:
    now = _now()
    await profiles_db.upsert(
        ChatTuningProfile(
            id=generate_id(),
            user_id=user_id,
            world_id=world_id,
            plan_tuning=plan_tuning,
            tone_tuning=tone_tuning,
            created_at=now,
            modified_at=now,
        )
    )


async def _add_feedback(
    session_id: int,
    turn_number: int,
    verdict: str,
    scope: str | None = None,
    comment: str | None = None,
    created_at: datetime | None = None,
) -> None:
    await feedback_db.create(
        ChatGenerationFeedback(
            id=generate_id(),
            session_id=session_id,
            turn_number=turn_number,
            verdict=verdict,
            scope=scope,
            comment=comment,
            content_snapshot="discarded text",
            plan_snapshot=None,
            created_at=created_at if created_at is not None else _now(),
        )
    )


# ===========================================================================
# DoD-1 — list_by_session returns all turns' rows, created_at ascending,
#         excluding other sessions.
# ===========================================================================


async def test_list_by_session_multi_turn_ordered_excludes_others__DoD1() -> None:
    # DoD-1: list_by_session(session_id) returns rows across every turn of the
    # session, ordered by created_at ascending, and excludes rows belonging to
    # other sessions. Rows are inserted OUT of created_at order (and across two
    # turns) so a wrong/absent ordering is caught; a same-timeframe row on
    # another session must not leak in.
    session_id = generate_id()
    other_session_id = generate_id()
    base = _now()

    # Inserted out of chronological order to prove created_at sorting (not
    # insertion order). Comments used only as stable identifiers.
    await _add_feedback(
        session_id, 2, verdict="rejected", scope="text",
        comment="second", created_at=base + timedelta(seconds=20),
    )
    await _add_feedback(
        session_id, 1, verdict="rejected", scope="plan",
        comment="first", created_at=base + timedelta(seconds=10),
    )
    await _add_feedback(
        session_id, 2, verdict="approved",
        comment="third", created_at=base + timedelta(seconds=30),
    )
    # A row on a different session in the same timeframe must be excluded.
    await _add_feedback(
        other_session_id, 1, verdict="rejected", scope="plan",
        comment="other", created_at=base + timedelta(seconds=15),
    )

    rows = await feedback_db.list_by_session(session_id)

    assert [r.comment for r in rows] == ["first", "second", "third"]
    assert all(r.session_id == session_id for r in rows)
    assert "other" not in [r.comment for r in rows]
    # Spans multiple turns of the same session.
    assert {r.turn_number for r in rows} == {1, 2}


# ===========================================================================
# DoD-2 — retune core aggregates rejects across ALL turns of the session.
# ===========================================================================


async def test_retune_aggregates_rejects_across_turns__DoD2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-2: a plan-scoped reject on turn 1 and a text-scoped reject on turn 2
    # must BOTH contribute to the dimension evidence. Aggregating all turns
    # therefore retunes the plan dimension (from turn 1) AND the tone dimension
    # (from turn 2). If the core read only a single turn, exactly one dimension
    # would remain unchanged.
    fake = _install_fake_retune_llm(monkeypatch)
    user_id, world_id, session_id = generate_id(), generate_id(), generate_id()
    await _seed_profile(user_id, world_id, INITIAL_PLAN, INITIAL_TONE)
    await _add_feedback(session_id, 1, verdict="rejected", scope="plan")
    await _add_feedback(session_id, 2, verdict="rejected", scope="text")

    await retune_service.retune_session(
        session_id, user_id, world_id, 2, ACCEPTED_CONTENT, "mock-model"
    )

    stored = await profiles_db.get(user_id, world_id)
    assert stored is not None
    # Turn 1 (plan) contributed -> plan retuned; turn 2 (text) contributed ->
    # tone retuned. Both turns fed the evidence.
    assert stored.plan_tuning == RETUNED
    assert stored.tone_tuning == RETUNED
    # Two targeted dimensions -> two completions.
    assert len(fake.calls) == 2


# ===========================================================================
# DoD-3 — dimension partitioning preserved; only targeted dims run a completion.
# ===========================================================================


@pytest.mark.parametrize(
    "reject_scope,expect_plan,expect_tone,expected_calls",
    [
        ("plan", RETUNED, INITIAL_TONE, 1),  # plan-scope feeds only plan dim
        ("text", INITIAL_PLAN, RETUNED, 1),  # text-scope feeds only tone dim
        (None, RETUNED, RETUNED, 2),         # null-scope feeds BOTH dims
    ],
)
async def test_dimension_partitioning_by_scope__DoD3(
    monkeypatch: pytest.MonkeyPatch,
    reject_scope: str | None,
    expect_plan: str,
    expect_tone: str,
    expected_calls: int,
) -> None:
    # DoD-3: plan/null scoped rejects feed the plan dimension, text/null scoped
    # rejects feed the tone dimension, and only the targeted dimension(s) run a
    # completion. A single reject of each scope exercises the partitioning; the
    # untargeted dimension keeps its seeded initial and no extra completion runs.
    fake = _install_fake_retune_llm(monkeypatch)
    user_id, world_id, session_id = generate_id(), generate_id(), generate_id()
    await _seed_profile(user_id, world_id, INITIAL_PLAN, INITIAL_TONE)
    await _add_feedback(session_id, 1, verdict="rejected", scope=reject_scope)

    await retune_service.retune_session(
        session_id, user_id, world_id, 1, ACCEPTED_CONTENT, "mock-model"
    )

    stored = await profiles_db.get(user_id, world_id)
    assert stored is not None
    assert stored.plan_tuning == expect_plan
    assert stored.tone_tuning == expect_tone
    # Only the targeted dimension(s) were sent to the LLM.
    assert len(fake.calls) == expected_calls


# ===========================================================================
# DoD-4 — core no-ops (no LLM call, no upsert) when model_id is None.
# ===========================================================================


async def test_no_op_when_model_id_none__DoD4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-4: with a valid reject present but model_id=None, the core makes NO
    # LLM call and performs NO upsert; the existing profile is left untouched.
    fake = _install_fake_retune_llm(monkeypatch)
    user_id, world_id, session_id = generate_id(), generate_id(), generate_id()
    await _seed_profile(user_id, world_id, INITIAL_PLAN, INITIAL_TONE)
    await _add_feedback(session_id, 1, verdict="rejected", scope="plan")

    upserts = _spy_upsert(monkeypatch)  # installed AFTER seeding

    await retune_service.retune_session(
        session_id, user_id, world_id, 1, ACCEPTED_CONTENT, None
    )

    assert fake.calls == []      # no LLM call
    assert upserts == []         # no upsert
    stored = await profiles_db.get(user_id, world_id)
    assert stored is not None
    assert stored.plan_tuning == INITIAL_PLAN  # unchanged
    assert stored.tone_tuning == INITIAL_TONE  # unchanged


# ===========================================================================
# DoD-5 — core no-ops when the session has zero reject rows.
# ===========================================================================


async def test_no_op_when_zero_session_rejects__DoD5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-5: with a non-null model_id but zero `rejected` rows in the session
    # (only an `approved` row present), the core is a fast no-op: no LLM call,
    # no upsert, profile unchanged.
    fake = _install_fake_retune_llm(monkeypatch)
    user_id, world_id, session_id = generate_id(), generate_id(), generate_id()
    await _seed_profile(user_id, world_id, INITIAL_PLAN, INITIAL_TONE)
    await _add_feedback(session_id, 1, verdict="approved")

    upserts = _spy_upsert(monkeypatch)  # installed AFTER seeding

    await retune_service.retune_session(
        session_id, user_id, world_id, 1, ACCEPTED_CONTENT, "mock-model"
    )

    assert fake.calls == []      # no LLM call on a session with no rejects
    assert upserts == []         # no upsert
    stored = await profiles_db.get(user_id, world_id)
    assert stored is not None
    assert stored.plan_tuning == INITIAL_PLAN  # unchanged
    assert stored.tone_tuning == INITIAL_TONE  # unchanged


# ===========================================================================
# DoD-6 — retuned result persisted via tuning_profiles_db.upsert(...).
# ===========================================================================


async def test_retune_persists_via_upsert__DoD6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-6: on a session with rejects and a non-null model_id, the retuned
    # result is persisted via tuning_profiles_db.upsert(...) — the upsert is
    # invoked with the post-retune value and the profile is re-fetchable.
    _install_fake_retune_llm(monkeypatch)
    user_id, world_id, session_id = generate_id(), generate_id(), generate_id()
    await _seed_profile(user_id, world_id, INITIAL_PLAN, INITIAL_TONE)
    await _add_feedback(session_id, 1, verdict="rejected", scope="plan")

    upserts = _spy_upsert(monkeypatch)  # installed AFTER seeding

    await retune_service.retune_session(
        session_id, user_id, world_id, 1, ACCEPTED_CONTENT, "mock-model"
    )

    # upsert was called to persist the retuned profile.
    assert len(upserts) >= 1
    assert any(p.plan_tuning == RETUNED for p in upserts)
    # ...and the persisted value is re-fetchable.
    stored = await profiles_db.get(user_id, world_id)
    assert stored is not None
    assert stored.plan_tuning == RETUNED


# ===========================================================================
# DoD-7 — retune_service no longer exposes RetuneEmitter and the core signature
#         has no emitter parameter.
# ===========================================================================


def test_no_emitter_surface__DoD7() -> None:
    # DoD-7: the RetuneEmitter type alias is removed from retune_service and the
    # retune core (retune_session) accepts no emitter parameter.
    assert not hasattr(retune_service, "RetuneEmitter")
    sig = inspect.signature(retune_service.retune_session)
    assert "emitter" not in sig.parameters
