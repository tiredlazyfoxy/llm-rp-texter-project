"""Retune-service / accept-trigger tests for feature 014 step 004.

Bound to the frozen step-004 skeleton (``## Skeleton`` in status.md):

- ``app.services.retune_service.maybe_retune(session_id, user_id, world_id,
  turn_number, accepted_content, model_id, emitter=None) -> None`` — async.
- ``app.services.retune_service.RetuneEmitter =
  Callable[[str, dict[str, str]], Awaitable[None]]`` — the emitter type.
- ``app.services.chat_service.continue_chat(session_id, user_id,
  variant_index) -> None`` — accept hook (writes one ``approved`` feedback row
  then calls ``maybe_retune``).

Expected values come from the step spec (Definition of done + Interface intent)
only — never from the implementation, which is not read.

LLM boundary: ``maybe_retune`` obtains its client via
``get_llm_client_for_model`` and makes a non-tool ``chat`` call. The fake is
installed at the consuming-module seam ``retune_service.get_llm_client_for_model``
and returns a deterministic constant (``"RETUNED"``) so a targeted dimension's
post-retune value is distinguishable from its seeded initial value, and the
number of LLM calls equals the number of targeted dimensions (Interface intent:
"only the targeted dimension(s) are sent to the LLM").

DB layer (``db/tuning_profiles``, ``db/generation_feedback``) is real against
the test DB engine; profiles/feedback are seeded with arbitrary snowflake ids
(FK enforcement is off in the test SQLite DB, as the step-001/003 tests rely on).

Red-gate note: the ``maybe_retune`` stub raises ``NotImplementedError`` and is
wired unconditionally into ``continue_chat``; these tests assert the
spec-correct behavior and (correctly) fail until the coder implements the
service.
"""

import json
from datetime import datetime, timezone

import pytest

from app.db import chats as chats_db
from app.db import generation_feedback as feedback_db
from app.db import tuning_profiles as profiles_db
from app.db import worlds as worlds_db
from app.models.chat_generation_feedback import ChatGenerationFeedback
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.chat_state_snapshot import ChatStateSnapshot
from app.models.chat_tuning_profile import ChatTuningProfile
from app.models.pipeline import Pipeline, PipelineKind
from app.models.schemas.pipeline import PipelineConfig, PipelineStage
from app.models.world import World, WorldStatus
from app.services import chain_generation_service, chat_service, retune_service
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
# Fake LLM client for the retune call (non-tool `chat`).
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
            created_at=_now(),
        )
    )


# ===========================================================================
# DoD-1 — clean accept (zero rejected rows): no LLM call, profile unchanged.
# ===========================================================================


async def test_clean_accept_makes_no_llm_call_and_leaves_profile__DoD1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-1: with zero `rejected` rows for the turn, maybe_retune makes NO LLM
    # call and does not change the profile. An `approved` row is present to show
    # it is specifically the rejected-row count (zero) that gates the retune.
    fake = _install_fake_retune_llm(monkeypatch)
    user_id, world_id, session_id, turn = (
        generate_id(),
        generate_id(),
        generate_id(),
        1,
    )
    await _seed_profile(user_id, world_id, INITIAL_PLAN, INITIAL_TONE)
    await _add_feedback(session_id, turn, verdict="approved")

    captured: list[tuple[str, dict]] = []

    async def emitter(event_name: str, payload: dict) -> None:
        captured.append((event_name, payload))

    await retune_service.maybe_retune(
        session_id, user_id, world_id, turn, ACCEPTED_CONTENT, "mock-model", emitter
    )

    assert fake.calls == []  # no LLM call on a clean turn
    stored = await profiles_db.get(user_id, world_id)
    assert stored is not None
    assert stored.plan_tuning == INITIAL_PLAN  # unchanged
    assert stored.tone_tuning == INITIAL_TONE  # unchanged
    assert captured == []  # early return -> no tuning_update emitted


# ===========================================================================
# DoD-2 — single-scope reject retunes only that dimension (and sends only it).
# ===========================================================================


@pytest.mark.parametrize(
    "reject_scope,changes_plan,changes_tone",
    [
        ("plan", True, False),
        ("text", False, True),
    ],
)
async def test_single_scope_retunes_only_that_dimension__DoD2(
    monkeypatch: pytest.MonkeyPatch,
    reject_scope: str,
    changes_plan: bool,
    changes_tone: bool,
) -> None:
    # DoD-2: only `plan`-scoped reject(s) -> plan_tuning updated, tone_tuning
    # unchanged; only `text`-scoped reject(s) -> tone_tuning updated, plan_tuning
    # unchanged. Exactly one dimension is sent to the LLM (one chat call).
    fake = _install_fake_retune_llm(monkeypatch)
    user_id, world_id, session_id, turn = (
        generate_id(),
        generate_id(),
        generate_id(),
        1,
    )
    await _seed_profile(user_id, world_id, INITIAL_PLAN, INITIAL_TONE)
    await _add_feedback(session_id, turn, verdict="rejected", scope=reject_scope)

    await retune_service.maybe_retune(
        session_id, user_id, world_id, turn, ACCEPTED_CONTENT, "mock-model"
    )

    stored = await profiles_db.get(user_id, world_id)
    assert stored is not None
    assert stored.plan_tuning == (RETUNED if changes_plan else INITIAL_PLAN)
    assert stored.tone_tuning == (RETUNED if changes_tone else INITIAL_TONE)
    # Only the targeted dimension was sent to the LLM.
    assert len(fake.calls) == 1


# ===========================================================================
# DoD-3 — null-scope (whole-chain) reject retunes BOTH dimensions.
# ===========================================================================


async def test_null_scope_reject_retunes_both_dimensions__DoD3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-3: a null-scope (whole-chain) reject counts as both -> plan_tuning AND
    # tone_tuning are both retuned, and both dimensions are sent to the LLM
    # (two chat calls).
    fake = _install_fake_retune_llm(monkeypatch)
    user_id, world_id, session_id, turn = (
        generate_id(),
        generate_id(),
        generate_id(),
        1,
    )
    await _seed_profile(user_id, world_id, INITIAL_PLAN, INITIAL_TONE)
    await _add_feedback(session_id, turn, verdict="rejected", scope=None)

    await retune_service.maybe_retune(
        session_id, user_id, world_id, turn, ACCEPTED_CONTENT, "mock-model"
    )

    stored = await profiles_db.get(user_id, world_id)
    assert stored is not None
    assert stored.plan_tuning == RETUNED
    assert stored.tone_tuning == RETUNED
    assert len(fake.calls) == 2  # both dimensions sent to the LLM


# ===========================================================================
# DoD-4 — retuned value persisted via upsert and re-fetchable (created if
#         absent; the untargeted dimension keeps its existing/default value).
# ===========================================================================


async def test_retune_persists_and_creates_profile_when_absent__DoD4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-4: with no prior profile, a plan-scoped retune creates the (user,
    # world) profile (fresh snowflake id), persists the new plan_tuning, and it
    # is re-fetchable; the untargeted tone_tuning keeps its default ("").
    _install_fake_retune_llm(monkeypatch)
    user_id, world_id, session_id, turn = (
        generate_id(),
        generate_id(),
        generate_id(),
        1,
    )
    assert await profiles_db.get(user_id, world_id) is None  # absent to start
    await _add_feedback(session_id, turn, verdict="rejected", scope="plan")

    await retune_service.maybe_retune(
        session_id, user_id, world_id, turn, ACCEPTED_CONTENT, "mock-model"
    )

    stored = await profiles_db.get(user_id, world_id)
    assert stored is not None  # created and re-fetchable for the same pair
    assert stored.user_id == user_id
    assert stored.world_id == world_id
    assert stored.plan_tuning == RETUNED
    assert stored.tone_tuning == ""  # untargeted dimension preserved (default)
    assert isinstance(stored.id, int)


# ===========================================================================
# DoD-6 — maybe_retune emits a `tuning_update` event with the post-retune
#         plan_tuning / tone_tuning (and world_id), via the stub emitter.
# ===========================================================================


async def test_maybe_retune_emits_tuning_update_with_post_retune_values__DoD6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-6: maybe_retune invokes the RetuneEmitter with event name
    # "tuning_update" and a payload carrying the POST-retune plan_tuning /
    # tone_tuning plus world_id (all strings). Plan-only reject: plan_tuning is
    # the retuned value, tone_tuning is the unchanged seeded value.
    _install_fake_retune_llm(monkeypatch)
    user_id, world_id, session_id, turn = (
        generate_id(),
        generate_id(),
        generate_id(),
        1,
    )
    await _seed_profile(user_id, world_id, INITIAL_PLAN, INITIAL_TONE)
    await _add_feedback(session_id, turn, verdict="rejected", scope="plan")

    captured: list[tuple[str, dict]] = []

    async def emitter(event_name: str, payload: dict) -> None:
        captured.append((event_name, payload))

    await retune_service.maybe_retune(
        session_id, user_id, world_id, turn, ACCEPTED_CONTENT, "mock-model", emitter
    )

    updates = [(name, payload) for name, payload in captured if name == "tuning_update"]
    assert len(updates) == 1
    _, payload = updates[0]
    assert payload["plan_tuning"] == RETUNED  # post-retune value
    assert payload["tone_tuning"] == INITIAL_TONE  # untargeted, unchanged
    assert payload["world_id"] == str(world_id)  # world id as a string
    assert all(isinstance(v, str) for v in payload.values())


# ===========================================================================
# DoD-5 — the accept path (continue_chat) writes exactly one `approved`
#         ChatGenerationFeedback row for the accepted turn.
# ===========================================================================
#
# To reach continue_chat's accept path with real variants, the known-good
# step-003 regenerate harness is used to produce a turn that has been
# regenerated (so the session holds a discarded variant and a `rejected`
# feedback row); continue_chat then accepts a variant. The LLM is mocked at
# both consuming seams (chain regen + retune) so the accept completes.

_WRITER_MAX_LOOPS = 20
DISCARDED_CONTENT = "The door creaks open."
PRIOR_PLAN = (
    '{"collected_data":"PRIOR_PLAN_MARKER","stat_updates":[],"decisions":[]}'
)


class FakeChainLLM:
    """Chain-generation LLM stand-in (tool + writer stages)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __aenter__(self) -> "FakeChainLLM":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def chat_with_tools(
        self, messages, *args, max_loops=None, on_delta=None, system=None, **kwargs
    ):
        self.calls.append({"max_loops": max_loops})
        if on_delta is not None:
            await on_delta("Regenerated prose.")
        return "Regenerated prose."


def _make_chain_pipeline() -> Pipeline:
    cfg = PipelineConfig(
        stages=[
            PipelineStage(step_type="tool", name="Plan", tools=[], model_id="mock-model"),
            PipelineStage(step_type="writer", name="Write", tools=[], model_id="mock-model"),
        ]
    )
    return Pipeline(
        id=generate_id(),
        name=f"chain-{generate_id()}",
        kind=PipelineKind.chain,
        pipeline_config=cfg.model_dump_json(),
    )


async def _setup_chain_chat() -> tuple[ChatSession, int]:
    now = _now()
    user_id = generate_id()

    world = World(
        id=generate_id(),
        name=f"w-{generate_id()}",
        status=WorldStatus.public,
        created_at=now,
        modified_at=now,
    )
    await worlds_db.create(world)

    chat = ChatSession(
        id=generate_id(),
        user_id=user_id,
        world_id=world.id,
        current_location_id=None,
        character_name="Hero",
        character_description="",
        character_stats="{}",
        world_stats="{}",
        current_turn=1,
        status="active",
        text_model_id="mock-model",
        tool_model_id="mock-model",
        user_instructions="",
        generation_variants="[]",
        created_at=now,
        modified_at=now,
    )
    await chats_db.create_session(chat)

    await chats_db.create_snapshot(
        ChatStateSnapshot(
            id=generate_id(),
            session_id=chat.id,
            turn_number=0,
            location_id=None,
            character_stats="{}",
            world_stats="{}",
            created_at=now,
        )
    )
    await chats_db.create_message(
        ChatMessage(
            id=generate_id(),
            session_id=chat.id,
            role="user",
            content="I open the door.",
            turn_number=1,
            is_active_variant=True,
            created_at=now,
        )
    )
    await chats_db.create_message(
        ChatMessage(
            id=generate_id(),
            session_id=chat.id,
            role="assistant",
            content=DISCARDED_CONTENT,
            turn_number=1,
            generation_plan=PRIOR_PLAN,
            is_active_variant=True,
            created_at=now,
        )
    )
    return chat, user_id


async def test_accept_writes_exactly_one_approved_feedback_row__DoD5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-5: accepting a turn via continue_chat writes exactly one `approved`
    # ChatGenerationFeedback row for that turn. The turn is first regenerated
    # (producing a variant + one `rejected` row), then accepted.
    chain_fake = FakeChainLLM()

    async def _chain_factory(model_id):
        return chain_fake

    monkeypatch.setattr(
        "app.services.chain_generation_service.get_llm_client_for_model",
        _chain_factory,
    )
    _install_fake_retune_llm(monkeypatch)

    chat, user_id = await _setup_chain_chat()
    pipeline = _make_chain_pipeline()

    # Regenerate (whole chain) -> appends a variant + writes a `rejected` row.
    async for _ in chain_generation_service.regenerate_chain_response(
        chat.id, user_id, "editor", pipeline, scope=None, comment=None
    ):
        pass

    # Accept a viewed variant -> writes exactly one `approved` row.
    await chat_service.continue_chat(chat.id, user_id, 0)

    rows = await feedback_db.list_by_turn(chat.id, 1)
    approved = [r for r in rows if r.verdict == "approved"]
    assert len(approved) == 1


# ===========================================================================
# BUG-FIX REPRO — implicit accept (auto-commit) must retune.
# Defends step-004 DoD-5 / context.md decision 2: "Retune trigger = on accept,
# only after the turn had >=1 reject." Keeping a regenerated message and
# sending the next message (variant_index=None with variants present) IS an
# accept and MUST fire the same accept-and-retune path as the explicit accept.
#
# reproduces: after regenerate + keep-and-continue, plan_tuning/tone_tuning stay
# empty because the auto-commit branch clears variants without writing an
# `approved` feedback row or calling maybe_retune.
#
# Assertions below are the SPEC-CORRECT (post-fix) behavior, so this test is
# RED against the current auto-commit branch and turns green only once that
# branch performs the accept-and-retune.
# ===========================================================================


async def test_implicit_accept_autocommit_triggers_retune__bugfix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Turn 1 is regenerated (whole chain, null scope) -> one `rejected` row +
    # a discarded variant on the session. The user keeps the regenerated output
    # and sends the NEXT message with variant_index=None, which routes into the
    # implicit-accept auto-commit branch. Per decision 2 this is an accept of a
    # turn that had a reject, so: (a) the (user, world) profile is retuned on
    # BOTH dimensions (null-scope reject counts as both) and (b) exactly one
    # `approved` feedback row is written for turn 1.
    chain_fake = FakeChainLLM()

    async def _chain_factory(model_id):
        return chain_fake

    monkeypatch.setattr(
        "app.services.chain_generation_service.get_llm_client_for_model",
        _chain_factory,
    )
    _install_fake_retune_llm(monkeypatch)

    chat, user_id = await _setup_chain_chat()
    pipeline = _make_chain_pipeline()

    # No profile exists before the interaction.
    assert await profiles_db.get(user_id, chat.world_id) is None

    # Regenerate (whole chain, null scope) -> writes a `rejected` row at turn 1
    # and leaves a discarded variant on the session.
    async for _ in chain_generation_service.regenerate_chain_response(
        chat.id, user_id, "editor", pipeline, scope=None, comment=None
    ):
        pass

    # Implicit accept: send the next message with variant_index=None while a
    # variant is pending -> the auto-commit branch keeps turn 1's output and
    # must accept-and-retune it.
    async for _ in chain_generation_service.generate_chain_response(
        chat.id, user_id, "The next thing I do.", "editor", pipeline, variant_index=None
    ):
        pass

    # (a) The turn had a null-scope reject -> both dimensions retuned + persisted.
    stored = await profiles_db.get(user_id, chat.world_id)
    assert stored is not None
    assert stored.plan_tuning == RETUNED
    assert stored.tone_tuning == RETUNED

    # (b) Exactly one `approved` feedback row for the accepted turn 1.
    rows = await feedback_db.list_by_turn(chat.id, 1)
    approved = [r for r in rows if r.verdict == "approved"]
    assert len(approved) == 1


# ===========================================================================
# BUG-FIX REPRO — streaming implicit accept must EMIT the `tuning_update`
# SSE frame live to an editor caller.
#
# Defends context.md "SSE protocol" (the editor-only `tuning_update` event so
# the debug preferences panel refreshes live) / step-006 DoD-5, emitted per
# step 004. The retune runs and persists on the streaming implicit-accept path,
# but that path calls the accept helper with emitter=None, so no `tuning_update`
# frame is emitted on the active generation stream — the panel only updates
# after a manual refresh.
#
# reproduces: "I see it's generating the tune, but it doesn't update on UI
# without the refresh" — no `tuning_update` frame is yielded by the streaming
# accept path.
#
# The assertions below are the SPEC-CORRECT (post-fix) behavior: a single
# `tuning_update` frame IS emitted to the editor carrying the retuned profile.
# The test is therefore RED now (emitter=None -> no frame) and turns green once
# the streaming accept path emits the frame.
# ===========================================================================


def _find_sse_events(frames: list[str], name: str) -> list[dict]:
    """Parse yielded SSE frame strings and return the JSON payloads of every
    frame whose event line is ``event: <name>``.

    Each frame is ``f"event: {name}\\ndata: {json}\\n\\n"`` (see the ``sse()``
    helper): the first line is ``event: <name>`` and the ``data: `` line is
    compact JSON.
    """
    found: list[dict] = []
    for frame in frames:
        lines = frame.split("\n")
        if not lines:
            continue
        if lines[0].strip() != f"event: {name}":
            continue
        for line in lines[1:]:
            if line.startswith("data: "):
                found.append(json.loads(line[len("data: ") :]))
                break
    return found


async def test_streaming_implicit_accept_emits_tuning_update_frame__bugfix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Turn 1 is regenerated (whole chain, null scope) -> one `rejected` row + a
    # discarded variant. The editor keeps that output and sends the NEXT message
    # with variant_index=None, routing into the streaming implicit-accept
    # auto-commit branch. Per the SSE protocol this accept-and-retune of an
    # editor's stream MUST yield an editor-only `tuning_update` frame carrying
    # the post-retune profile (a null-scope reject retunes BOTH dims -> both
    # "RETUNED").
    chain_fake = FakeChainLLM()

    async def _chain_factory(model_id):
        return chain_fake

    monkeypatch.setattr(
        "app.services.chain_generation_service.get_llm_client_for_model",
        _chain_factory,
    )
    _install_fake_retune_llm(monkeypatch)

    chat, user_id = await _setup_chain_chat()
    pipeline = _make_chain_pipeline()

    # Regenerate (whole chain, null scope) -> writes a `rejected` row at turn 1
    # and leaves a discarded variant on the session.
    async for _ in chain_generation_service.regenerate_chain_response(
        chat.id, user_id, "editor", pipeline, scope=None, comment=None
    ):
        pass

    # Streaming implicit accept AS EDITOR: collect the yielded SSE frames.
    frames: list[str] = []
    async for frame in chain_generation_service.generate_chain_response(
        chat.id, user_id, "The next thing I do.", "editor", pipeline, variant_index=None
    ):
        frames.append(frame)

    updates = _find_sse_events(frames, "tuning_update")
    assert len(updates) == 1  # exactly one live `tuning_update` frame to the editor
    payload = updates[0]
    # Null-scope reject retunes both dimensions -> both become RETUNED.
    assert payload["plan_tuning"] == RETUNED
    assert payload["tone_tuning"] == RETUNED
    assert payload["world_id"] == str(chat.world_id)  # world id carried as a string
    assert isinstance(payload["world_id"], str)


# ===========================================================================
# DoD-7 — [manual/live] coherence of retuned text with a real LLM. Out of
#         scope for automated tests (no model call); no test written.
# ===========================================================================
