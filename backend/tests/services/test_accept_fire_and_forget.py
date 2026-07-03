"""Accept-path fire-and-forget tests for feature 015 step 003.

Bound to the frozen step-003 skeleton (``## Skeleton`` in
``docs/plans/015.background_retune/status.md``). Relevant frozen surface:

- ``chat_service._record_accept_and_retune(session_id: int, user_id: int,
  chat: ChatSession, accepted_content: str, accepted_plan_json: str | None)
  -> None`` — the vestigial ``emitter`` parameter is GONE.
- The accept hook writes one ``verdict="approved"`` ``ChatGenerationFeedback``
  row via ``feedback_db.create(...)``, then applies the D2 gate: it reads the
  accepted turn's rows via ``feedback_db.list_by_turn(session_id, turn_number)``
  and ONLY if that turn already has >=1 ``verdict="rejected"`` row does it call
  the fire-and-forget seam ``retune_tasks.start(session_id, user_id, world_id,
  model_id, turn_number)``. A clean turn (no rejects) schedules nothing.
- ``retune_tasks.start`` is the fire-and-forget seam: the accept path must NOT
  await the retune LLM (``retune_service.retune_session``). The accepted turn is
  ``chat.current_turn`` (the only turn source on the passed ``ChatSession``).

Seams (mirroring the project's namespace-module patch convention used by the
step-002 tests, which patch ``app.services.retune_service.retune_session``):
- the background scheduler is patched at ``app.services.retune_tasks.start``;
- the inline retune core is patched at
  ``app.services.retune_service.retune_session`` (a recorder) so we can assert
  the accept path does NOT await it and so the current (pre-implementation) stub
  body cannot reach a real LLM.

model_id source note: the retune ``model_id`` is read off the ``chat`` object.
The spec/interface does not pin which model field feeds it, so both
``tool_model_id`` and ``text_model_id`` are seeded to the SAME value; whichever
field the hook reads, ``model_id`` equals that value — no over-specification.

Expected values come only from the step spec (Definition of done + Interface
intent) and the frozen skeleton — the implementation body is never read.

Red-gate note: the frozen stub body still performs the OLD inline retune and
does not apply the gate or call ``retune_tasks.start``; these tests assert the
spec-correct behavior and (correctly) fail until the coder implements it.
"""

import asyncio
import inspect
from datetime import datetime, timezone

import pytest

from app.db import generation_feedback as feedback_db
from app.models.chat_generation_feedback import ChatGenerationFeedback
from app.models.chat_session import ChatSession
from app.services import chat_service, retune_service
from app.services.snowflake import generate_id

MODEL_ID = "mock-model"
ACCEPTED_CONTENT = "The accepted final prose."
ACCEPTED_PLAN_JSON = '{"plan": "accepted"}'
ACCEPTED_TURN = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_chat(user_id: int, world_id: int, current_turn: int = ACCEPTED_TURN) -> ChatSession:
    """In-memory ChatSession passed to the hook. Both model fields carry the
    same id so the model_id assertion is robust to which field the hook reads."""
    now = _now()
    return ChatSession(
        id=generate_id(),
        user_id=user_id,
        world_id=world_id,
        character_name="Hero",
        character_description="A brave adventurer.",
        current_turn=current_turn,
        tool_model_id=MODEL_ID,
        text_model_id=MODEL_ID,
        created_at=now,
        modified_at=now,
    )


async def _add_feedback(
    session_id: int,
    turn_number: int,
    verdict: str,
    scope: str | None = None,
) -> None:
    await feedback_db.create(
        ChatGenerationFeedback(
            id=generate_id(),
            session_id=session_id,
            turn_number=turn_number,
            verdict=verdict,
            scope=scope,
            comment=None,
            content_snapshot="discarded text",
            plan_snapshot=None,
            created_at=_now(),
        )
    )


class FakeStart:
    """Records each ``retune_tasks.start(...)`` invocation. Returns immediately
    (models the fire-and-forget seam that returns before the LLM runs)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(
        self,
        session_id=None,
        user_id=None,
        world_id=None,
        model_id=None,
        turn_number=None,
    ) -> None:
        self.calls.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "world_id": world_id,
                "model_id": model_id,
                "turn_number": turn_number,
            }
        )


class FakeRetuneCore:
    """Recorder installed at the inline-retune seam. The accept path must NOT
    await this; if it is called at all the fire-and-forget contract is broken."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, *args, **kwargs) -> None:
        self.calls.append({"args": args, "kwargs": kwargs})


def _install_seams(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeStart, FakeRetuneCore]:
    start = FakeStart()
    core = FakeRetuneCore()
    monkeypatch.setattr("app.services.retune_tasks.start", start, raising=False)
    monkeypatch.setattr(
        "app.services.retune_service.retune_session", core, raising=False
    )
    return start, core


async def _approved_rows(session_id: int, turn_number: int) -> list[ChatGenerationFeedback]:
    rows = await feedback_db.list_by_turn(session_id, turn_number)
    return [r for r in rows if r.verdict == "approved"]


# ===========================================================================
# DoD-1 — accept returns without awaiting the retune LLM (non-blocking): it
#         delegates to the fire-and-forget seam, leaving the retune scheduled
#         but not run inline.
# ===========================================================================


async def test_accept_delegates_to_background_seam_without_awaiting_llm__DoD1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-1: on accept of a turn that had a reject, the hook schedules the
    # background retune (retune_tasks.start) and returns WITHOUT awaiting the
    # inline retune LLM (retune_service.retune_session). Proof: after the hook
    # completes, the background seam was invoked but the LLM core was never run
    # during the request coroutine.
    start, core = _install_seams(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()
    chat = _build_chat(uid, wid)
    await _add_feedback(sid, chat.current_turn, verdict="rejected", scope="plan")

    # wait_for guards against a regression that blocks the accept path on the LLM.
    await asyncio.wait_for(
        chat_service._record_accept_and_retune(
            sid, uid, chat, ACCEPTED_CONTENT, ACCEPTED_PLAN_JSON
        ),
        timeout=5.0,
    )

    # Retune was handed to the fire-and-forget scheduler...
    assert len(start.calls) == 1
    # ...and the accept path did NOT await the retune LLM inline.
    assert core.calls == []


# ===========================================================================
# DoD-2 — accepted turn had >=1 reject -> background retune scheduled with the
#         session/user/world/model/turn arguments.
# ===========================================================================


async def test_reject_present_schedules_background_retune_with_args__DoD2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-2: when the accepted turn (chat.current_turn) already has a rejected
    # row, retune_tasks.start(...) is invoked exactly once with session_id,
    # user_id, world_id (from chat), model_id (from chat), and the accepted turn.
    start, _core = _install_seams(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()
    chat = _build_chat(uid, wid)
    await _add_feedback(sid, chat.current_turn, verdict="rejected", scope="text")

    await chat_service._record_accept_and_retune(
        sid, uid, chat, ACCEPTED_CONTENT, ACCEPTED_PLAN_JSON
    )

    assert len(start.calls) == 1
    call = start.calls[0]
    assert call["session_id"] == sid
    assert call["user_id"] == uid
    assert call["world_id"] == wid
    assert call["model_id"] == MODEL_ID
    assert call["turn_number"] == chat.current_turn


# ===========================================================================
# DoD-3 — clean accept (zero reject rows on the turn) schedules nothing.
# ===========================================================================


async def test_clean_accept_schedules_nothing__DoD3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-3: when the accepted turn has NO rejected rows, retune_tasks.start is
    # NOT invoked (the gate blocks the auto-trigger). The approved row is still
    # written (gate-independent), proving the hook ran rather than early-exiting.
    start, _core = _install_seams(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()
    chat = _build_chat(uid, wid)  # no reject seeded on this turn

    await chat_service._record_accept_and_retune(
        sid, uid, chat, ACCEPTED_CONTENT, ACCEPTED_PLAN_JSON
    )

    assert start.calls == []  # clean turn -> no background retune scheduled
    approved = await _approved_rows(sid, chat.current_turn)
    assert len(approved) == 1  # hook still executed the accept write


# ===========================================================================
# DoD-4 — the approved feedback row is written regardless of gate outcome.
# ===========================================================================


@pytest.mark.parametrize("with_reject", [False, True], ids=["clean_turn", "reject_turn"])
async def test_approved_row_written_regardless_of_gate__DoD4(
    monkeypatch: pytest.MonkeyPatch,
    with_reject: bool,
) -> None:
    # DoD-4: accepting always writes exactly one verdict="approved"
    # ChatGenerationFeedback row for the accepted turn, whether or not the gate
    # fires. The approved row snapshots the accepted content.
    _install_seams(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()
    chat = _build_chat(uid, wid)
    if with_reject:
        await _add_feedback(sid, chat.current_turn, verdict="rejected", scope="plan")

    await chat_service._record_accept_and_retune(
        sid, uid, chat, ACCEPTED_CONTENT, ACCEPTED_PLAN_JSON
    )

    approved = await _approved_rows(sid, chat.current_turn)
    assert len(approved) == 1
    assert approved[0].verdict == "approved"
    assert approved[0].content_snapshot == ACCEPTED_CONTENT


# ===========================================================================
# DoD-5 — the chain auto-commit's accept touchpoint produces no tuning_update
#         SSE frame: the hook takes no emitter and yields no frames at all.
# ===========================================================================


def test_accept_hook_produces_no_tuning_update_frame__DoD5() -> None:
    # DoD-5: the tuning_update SSE event is gone. The chain auto-commit reaches
    # retune only through _record_accept_and_retune, whose frozen interface has
    # no `emitter` parameter (the removed pending_frames/_emit buffer that once
    # carried tuning_update) and which is a plain coroutine (not an async
    # generator) so it can yield no SSE frames whatsoever.
    hook = chat_service._record_accept_and_retune
    assert inspect.iscoroutinefunction(hook)
    assert not inspect.isasyncgenfunction(hook)

    params = set(inspect.signature(hook).parameters)
    assert "emitter" not in params  # emitter/tuning_update buffer removed
    # Bound to the frozen step-003 signature exactly.
    assert params == {
        "session_id",
        "user_id",
        "chat",
        "accepted_content",
        "accepted_plan_json",
    }


# ===========================================================================
# DoD-6 — retune_service exposes no emitter surface and emits no tuning_update.
# ===========================================================================


def test_retune_service_has_no_emitter_surface__DoD6() -> None:
    # DoD-6: the dead emitter plumbing is gone from retune_service — no
    # RetuneEmitter type alias and no `emitter` parameter on the retune core, so
    # there is no channel through which a tuning_update could be emitted.
    assert not hasattr(retune_service, "RetuneEmitter")
    assert not hasattr(retune_service, "maybe_retune")
    sig = inspect.signature(retune_service.retune_session)
    assert "emitter" not in sig.parameters
