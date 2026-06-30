"""Data-layer tests for feature 014 (chat_preference_tuning) step 001.

Covers the two new persistent shapes and their db access / cascade / JSONL
round-trip, bound to the frozen step-001 skeleton:

- ``ChatTuningProfile`` (table ``chat_tuning_profiles``) + ``db/tuning_profiles``
- ``ChatGenerationFeedback`` (table ``chat_generation_feedback``) +
  ``db/generation_feedback``
- JSONL import/export to_dict/from_dict pairs in ``services/db_import_export``
- ``db/chats.delete_session`` feedback cascade

Expected values come from the step spec / DoD only. Snowflake ids are assigned
in test (acting as the service layer) via ``snowflake.generate_id``.
"""

import json
from datetime import datetime, timedelta, timezone

from app.db import chats as chats_db
from app.db import generation_feedback as feedback_db
from app.db import tuning_profiles as profiles_db
from app.models.chat_generation_feedback import ChatGenerationFeedback
from app.models.chat_session import ChatSession
from app.models.chat_tuning_profile import ChatTuningProfile
from app.services.db_import_export import (
    _chat_generation_feedback_to_dict,
    _chat_tuning_profile_to_dict,
    _dict_to_chat_generation_feedback,
    _dict_to_chat_tuning_profile,
)
from app.services.snowflake import generate_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> datetime:
    """Normalize to aware-UTC for the SQLite tz-drop gotcha."""
    return dt.replace(tzinfo=timezone.utc)


def _make_profile(
    *,
    user_id: int,
    world_id: int,
    plan_tuning: str = "",
    tone_tuning: str = "",
    profile_id: int | None = None,
) -> ChatTuningProfile:
    now = _now()
    return ChatTuningProfile(
        id=profile_id if profile_id is not None else generate_id(),
        user_id=user_id,
        world_id=world_id,
        plan_tuning=plan_tuning,
        tone_tuning=tone_tuning,
        created_at=now,
        modified_at=now,
    )


def _make_feedback(
    *,
    session_id: int,
    turn_number: int,
    verdict: str,
    content_snapshot: str,
    scope: str | None = None,
    comment: str | None = None,
    plan_snapshot: str | None = None,
    created_at: datetime | None = None,
) -> ChatGenerationFeedback:
    return ChatGenerationFeedback(
        id=generate_id(),
        session_id=session_id,
        turn_number=turn_number,
        verdict=verdict,
        scope=scope,
        comment=comment,
        content_snapshot=content_snapshot,
        plan_snapshot=plan_snapshot,
        created_at=created_at if created_at is not None else _now(),
    )


async def _create_chat_session() -> ChatSession:
    """Create a real ChatSession row (FK target for feedback cascade)."""
    now = _now()
    chat = ChatSession(
        id=generate_id(),
        user_id=generate_id(),
        world_id=generate_id(),
        current_location_id=None,
        character_name="Tester",
        character_description="",
        character_stats="{}",
        world_stats="{}",
        current_turn=0,
        status="active",
        tool_model_id=None,
        tool_temperature=0.7,
        tool_repeat_penalty=1.0,
        tool_top_p=1.0,
        text_model_id=None,
        text_temperature=0.7,
        text_repeat_penalty=1.0,
        text_top_p=1.0,
        user_instructions="",
        generation_variants="[]",
        created_at=now,
        modified_at=now,
    )
    return await chats_db.create_session(chat)


# ---------------------------------------------------------------------------
# DoD-1 — both tables built by create_all (insert a row, read it back)
# ---------------------------------------------------------------------------


async def test_tuning_profile_table_insert_read_back__DoD1() -> None:
    # DoD-1: ChatTuningProfile table exists after init_db() — row round-trips.
    user_id = generate_id()
    world_id = generate_id()
    profile = _make_profile(
        user_id=user_id, world_id=world_id, plan_tuning="p", tone_tuning="t"
    )

    await profiles_db.upsert(profile)
    stored = await profiles_db.get(user_id, world_id)

    assert stored is not None
    assert stored.user_id == user_id
    assert stored.world_id == world_id
    assert stored.plan_tuning == "p"
    assert stored.tone_tuning == "t"


async def test_generation_feedback_table_insert_read_back__DoD1() -> None:
    # DoD-1: ChatGenerationFeedback table exists after init_db() — row round-trips.
    session_id = generate_id()
    feedback = _make_feedback(
        session_id=session_id,
        turn_number=1,
        verdict="approved",
        content_snapshot="hello world",
    )

    await feedback_db.create(feedback)
    rows = await feedback_db.list_by_turn(session_id, 1)

    assert [r.id for r in rows] == [feedback.id]
    assert rows[0].content_snapshot == "hello world"
    assert rows[0].verdict == "approved"


# ---------------------------------------------------------------------------
# DoD-2 — tuning_profiles.get / upsert semantics
# ---------------------------------------------------------------------------


async def test_get_returns_none_for_unknown_pair__DoD2() -> None:
    # DoD-2: get returns None for an unknown (user_id, world_id) pair.
    result = await profiles_db.get(generate_id(), generate_id())
    assert result is None


async def test_upsert_then_get_returns_stored_row__DoD2() -> None:
    # DoD-2: after upsert, get returns the stored plan_tuning / tone_tuning.
    user_id = generate_id()
    world_id = generate_id()
    profile = _make_profile(
        user_id=user_id,
        world_id=world_id,
        plan_tuning="be concise",
        tone_tuning="be warm",
    )

    await profiles_db.upsert(profile)
    stored = await profiles_db.get(user_id, world_id)

    assert stored is not None
    assert stored.plan_tuning == "be concise"
    assert stored.tone_tuning == "be warm"


async def test_second_upsert_updates_in_place__DoD2() -> None:
    # DoD-2: a second upsert for the same (user, world) updates in place —
    # same row id, new values, not a duplicate.
    user_id = generate_id()
    world_id = generate_id()
    first = _make_profile(
        user_id=user_id,
        world_id=world_id,
        plan_tuning="v1-plan",
        tone_tuning="v1-tone",
    )
    await profiles_db.upsert(first)

    existing = await profiles_db.get(user_id, world_id)
    assert existing is not None
    original_id = existing.id

    # Service flow: mutate the loaded row and upsert again (same id).
    existing.plan_tuning = "v2-plan"
    existing.tone_tuning = "v2-tone"
    await profiles_db.upsert(existing)

    updated = await profiles_db.get(user_id, world_id)
    assert updated is not None
    assert updated.id == original_id  # in place — no new row / id churn
    assert updated.plan_tuning == "v2-plan"
    assert updated.tone_tuning == "v2-tone"


# ---------------------------------------------------------------------------
# DoD-3 — generation_feedback create / list_by_turn order / delete_by_session
# ---------------------------------------------------------------------------


async def test_list_by_turn_orders_by_created_at_asc__DoD3() -> None:
    # DoD-3: list_by_turn returns rows for the (session, turn) in created_at
    # ascending order, regardless of insertion order, filtered by turn.
    session_id = generate_id()
    turn = 5

    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t_early = base
    t_mid = base + timedelta(seconds=10)
    t_late = base + timedelta(seconds=20)

    # Insert out of created_at order (and out of id order) so an id-based or
    # insertion-based sort would produce a different result.
    await feedback_db.create(
        _make_feedback(
            session_id=session_id,
            turn_number=turn,
            verdict="rejected",
            content_snapshot="mid",
            created_at=t_mid,
        )
    )
    await feedback_db.create(
        _make_feedback(
            session_id=session_id,
            turn_number=turn,
            verdict="rejected",
            content_snapshot="early",
            created_at=t_early,
        )
    )
    await feedback_db.create(
        _make_feedback(
            session_id=session_id,
            turn_number=turn,
            verdict="approved",
            content_snapshot="late",
            created_at=t_late,
        )
    )
    # A row for a different turn must be excluded.
    await feedback_db.create(
        _make_feedback(
            session_id=session_id,
            turn_number=turn + 1,
            verdict="rejected",
            content_snapshot="other-turn",
            created_at=t_early,
        )
    )

    rows = await feedback_db.list_by_turn(session_id, turn)

    assert [r.content_snapshot for r in rows] == ["early", "mid", "late"]


async def test_delete_by_session_removes_feedback__DoD3() -> None:
    # DoD-3: delete_by_session removes all of the session's feedback rows.
    session_id = generate_id()
    turn = 2
    await feedback_db.create(
        _make_feedback(
            session_id=session_id,
            turn_number=turn,
            verdict="rejected",
            content_snapshot="a",
        )
    )
    await feedback_db.create(
        _make_feedback(
            session_id=session_id,
            turn_number=turn,
            verdict="approved",
            content_snapshot="b",
        )
    )
    assert len(await feedback_db.list_by_turn(session_id, turn)) == 2

    await feedback_db.delete_by_session(session_id)

    assert await feedback_db.list_by_turn(session_id, turn) == []


# ---------------------------------------------------------------------------
# DoD-4 — JSONL export -> import round-trip (to_dict / from_dict pairs)
# ---------------------------------------------------------------------------


def test_tuning_profile_jsonl_round_trip__DoD4() -> None:
    # DoD-4: ChatTuningProfile survives a to_dict -> JSON -> from_dict round-trip
    # with all fields intact.
    profile = _make_profile(
        user_id=generate_id(),
        world_id=generate_id(),
        plan_tuning="keep plans tight",
        tone_tuning="keep tone dry",
    )

    restored = _dict_to_chat_tuning_profile(
        json.loads(json.dumps(_chat_tuning_profile_to_dict(profile)))
    )

    assert restored.id == profile.id
    assert restored.user_id == profile.user_id
    assert restored.world_id == profile.world_id
    assert restored.plan_tuning == profile.plan_tuning
    assert restored.tone_tuning == profile.tone_tuning
    assert _utc(restored.created_at) == _utc(profile.created_at)
    assert _utc(restored.modified_at) == _utc(profile.modified_at)


def test_generation_feedback_jsonl_round_trip_with_nulls__DoD4() -> None:
    # DoD-4: ChatGenerationFeedback round-trips with null scope / comment /
    # plan_snapshot intact.
    feedback = _make_feedback(
        session_id=generate_id(),
        turn_number=1,
        verdict="approved",
        content_snapshot="accepted text",
        scope=None,
        comment=None,
        plan_snapshot=None,
    )

    restored = _dict_to_chat_generation_feedback(
        json.loads(json.dumps(_chat_generation_feedback_to_dict(feedback)))
    )

    assert restored.id == feedback.id
    assert restored.session_id == feedback.session_id
    assert restored.turn_number == 1
    assert restored.verdict == "approved"
    assert restored.scope is None
    assert restored.comment is None
    assert restored.plan_snapshot is None
    assert restored.content_snapshot == "accepted text"
    assert _utc(restored.created_at) == _utc(feedback.created_at)


def test_generation_feedback_jsonl_round_trip_populated__DoD4() -> None:
    # DoD-4: ChatGenerationFeedback round-trips with all non-null fields intact.
    feedback = _make_feedback(
        session_id=generate_id(),
        turn_number=7,
        verdict="rejected",
        content_snapshot="too purple",
        scope="text",
        comment="tone is off",
        plan_snapshot='{"steps": [1, 2]}',
    )

    restored = _dict_to_chat_generation_feedback(
        json.loads(json.dumps(_chat_generation_feedback_to_dict(feedback)))
    )

    assert restored.id == feedback.id
    assert restored.session_id == feedback.session_id
    assert restored.turn_number == 7
    assert restored.verdict == "rejected"
    assert restored.scope == "text"
    assert restored.comment == "tone is off"
    assert restored.content_snapshot == "too purple"
    assert restored.plan_snapshot == '{"steps": [1, 2]}'
    assert _utc(restored.created_at) == _utc(feedback.created_at)


# ---------------------------------------------------------------------------
# DoD-5 — delete_session cascades to feedback
# ---------------------------------------------------------------------------


async def test_delete_session_cascades_feedback__DoD5() -> None:
    # DoD-5: db.chats.delete_session removes the session's feedback rows —
    # none orphaned after the session is deleted.
    session = await _create_chat_session()
    turn = 1
    await feedback_db.create(
        _make_feedback(
            session_id=session.id,
            turn_number=turn,
            verdict="rejected",
            content_snapshot="x",
        )
    )
    await feedback_db.create(
        _make_feedback(
            session_id=session.id,
            turn_number=turn,
            verdict="approved",
            content_snapshot="y",
        )
    )
    assert len(await feedback_db.list_by_turn(session.id, turn)) == 2

    await chats_db.delete_session(session.id)

    assert await feedback_db.list_by_turn(session.id, turn) == []
