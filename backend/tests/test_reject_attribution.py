"""Reject-attribution / scoped-regenerate tests for feature 014 step 003.

Bound to the frozen step-003 skeleton:

- ``app.models.schemas.chat.RegenerateRequest`` — **changed**: added
  ``scope: Literal["plan", "text"] | None = None`` and
  ``comment: str | None = None`` (alongside the existing
  ``turn_number: int | None = None``).
- ``app.services.chain_generation_service.regenerate_chain_response(
  session_id, user_id, caller_role, pipeline, scope=None, comment=None)`` —
  sync def returning an async generator of SSE strings.

Expected values come from the step spec / DoD only.

The chain-regenerate tests build a fresh chain harness (no full-chain test
existed before): a public ``World``, a chain ``Pipeline`` (one ``tool`` + one
``writer`` stage), a ``ChatSession`` at turn 1 with an active user message and an
active assistant message carrying a ``generation_plan``. The LLM is mocked at the
consuming-module seam ``chain_generation_service.get_llm_client_for_model``; the
fake records each ``chat_with_tools`` call (writer stage uses ``max_loops==20``;
the tool stage uses a different value) and feeds writer prose via ``on_delta``.

Red-gate note: ``scope="text"`` (writer-only) is an unimplemented stub raising
``NotImplementedError``, and the rejected-feedback write (DoD-4) is not yet
added — those tests assert the spec-correct behavior and will (correctly) fail
until the coder implements them.
"""

from datetime import datetime, timezone
from typing import Literal, get_args, get_origin, get_type_hints

import pytest
from pydantic import ValidationError

from app.db import chats as chats_db
from app.db import generation_feedback as feedback_db
from app.db import worlds as worlds_db
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.chat_state_snapshot import ChatStateSnapshot
from app.models.pipeline import Pipeline, PipelineKind
from app.models.schemas.chat import RegenerateRequest
from app.models.schemas.pipeline import PipelineConfig, PipelineStage
from app.models.world import World, WorldStatus
from app.services import chain_generation_service
from app.services.snowflake import generate_id

# Discarded assistant message's stored plan; the marker lets DoD-2 assert the
# prior plan reached the writer (writer-only path reuses it).
PRIOR_PLAN = (
    '{"collected_data":"PRIOR_PLAN_MARKER","stat_updates":[],"decisions":[]}'
)
DISCARDED_CONTENT = "The door creaks open."


# ---------------------------------------------------------------------------
# DoD-1 — RegenerateRequest round-trips scope/comment and still validates
#         with both omitted (defaults null/None).
# ---------------------------------------------------------------------------


def test_regenerate_request_defaults_null_when_omitted__DoD1() -> None:
    # DoD-1: with both new fields omitted, scope and comment default to None
    # (preserving existing callers). turn_number also stays optional/None.
    req = RegenerateRequest()

    assert req.scope is None
    assert req.comment is None
    assert req.turn_number is None


def test_regenerate_request_round_trips_scope_text_and_comment__DoD1() -> None:
    # DoD-1: scope="text" + a comment round-trip onto the model unchanged.
    req = RegenerateRequest(scope="text", comment="tone is off")

    assert req.scope == "text"
    assert req.comment == "tone is off"


def test_regenerate_request_round_trips_scope_plan__DoD1() -> None:
    # DoD-1: scope="plan" round-trips (the other allowed literal).
    req = RegenerateRequest(scope="plan", comment="redo the whole plan")

    assert req.scope == "plan"
    assert req.comment == "redo the whole plan"


def test_regenerate_request_accepts_explicit_null_scope_and_comment__DoD1() -> None:
    # DoD-1: explicitly passing None for both still validates and stays None.
    req = RegenerateRequest(scope=None, comment=None, turn_number=3)

    assert req.scope is None
    assert req.comment is None
    assert req.turn_number == 3


def test_regenerate_request_round_trips_through_json_body__DoD1() -> None:
    # DoD-1: a JSON-style request body (what the route parses) round-trips the
    # new fields through model validation.
    req = RegenerateRequest.model_validate(
        {"turn_number": 2, "scope": "text", "comment": "shorter please"}
    )

    assert req.turn_number == 2
    assert req.scope == "text"
    assert req.comment == "shorter please"


@pytest.mark.parametrize("bad_scope", ["pl&text", "writer", "Plan", "TEXT", "both", ""])
def test_regenerate_request_rejects_invalid_scope_literal__DoD1(bad_scope: str) -> None:
    # DoD-1: scope is constrained to the literals "plan" | "text" | null — any
    # other string is rejected by validation.
    with pytest.raises(ValidationError):
        RegenerateRequest(scope=bad_scope)


def test_regenerate_request_scope_literal_arguments__DoD1() -> None:
    # DoD-1: the declared type for `scope` admits exactly the spec literals
    # "plan" and "text" (plus None). The annotation is
    # `Literal["plan", "text"] | None`, so the union's members are the
    # Literal object and NoneType — flatten to reach the literal strings.
    hints = get_type_hints(RegenerateRequest)
    union_members = get_args(hints["scope"])

    assert type(None) in union_members  # the `| None` part
    literal_members = [m for m in union_members if get_origin(m) is Literal]
    assert len(literal_members) == 1
    assert set(get_args(literal_members[0])) == {"plan", "text"}


# ---------------------------------------------------------------------------
# Chain-regenerate harness (DoD-2..DoD-5)
# ---------------------------------------------------------------------------

# Writer stage is invoked with max_loops==20; tool/planning stage uses a
# different value — this is how the tests distinguish which stages ran.
_WRITER_MAX_LOOPS = 20


class FakeLLMClient:
    """Async-context LLM client stand-in. Records each chat_with_tools call so
    tests can assert which stages ran; feeds writer prose via on_delta."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __aenter__(self) -> "FakeLLMClient":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def chat_with_tools(
        self,
        messages,
        *args,
        max_loops=None,
        on_delta=None,
        system=None,
        **kwargs,
    ):
        self.calls.append(
            {"max_loops": max_loops, "messages": messages, "system": system}
        )
        if on_delta is not None:
            await on_delta("Regenerated prose.")
        return "Regenerated prose."


def _install_fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLMClient:
    """Patch the LLM-client factory in the consuming module. One shared client
    so `.calls` accumulates across both stages."""
    fake = FakeLLMClient()

    async def _fake_get_client(model_id):
        return fake

    monkeypatch.setattr(
        "app.services.chain_generation_service.get_llm_client_for_model",
        _fake_get_client,
    )
    return fake


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


async def _setup_chain_chat(prior_plan: str | None) -> tuple[ChatSession, int]:
    """Create a public world + chain session at turn 1 with an active user
    message and an active assistant message carrying `prior_plan`.
    Returns (chat, user_id)."""
    now = datetime.now(timezone.utc)
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
        text_model_id=None,
        tool_model_id=None,
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
            generation_plan=prior_plan,
            is_active_variant=True,
            created_at=now,
        )
    )
    return chat, user_id


async def _drive(
    pipeline: Pipeline,
    chat: ChatSession,
    user_id: int,
    *,
    scope=None,
    comment=None,
    caller_role: str = "editor",
) -> list[str]:
    """Drive the regenerate async generator to completion, collecting SSE
    frames (so the background run + _finalize_chain complete)."""
    frames: list[str] = []
    async for frame in chain_generation_service.regenerate_chain_response(
        chat.id, user_id, caller_role, pipeline, scope=scope, comment=comment
    ):
        frames.append(frame)
    return frames


def _event_names(frames: list[str]) -> list[str]:
    names: list[str] = []
    for frame in frames:
        for line in frame.splitlines():
            if line.startswith("event:"):
                names.append(line.split(":", 1)[1].strip())
    return names


def _writer_calls(fake: FakeLLMClient) -> list[dict]:
    return [c for c in fake.calls if c["max_loops"] == _WRITER_MAX_LOOPS]


def _tool_calls(fake: FakeLLMClient) -> list[dict]:
    return [c for c in fake.calls if c["max_loops"] != _WRITER_MAX_LOOPS]


# ---------------------------------------------------------------------------
# DoD-2 — scope="text" runs only the writer stage(s), reusing the prior plan.
# ---------------------------------------------------------------------------


async def test_scope_text_runs_writer_only_with_prior_plan__DoD2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-2: a regenerate with scope="text" re-runs ONLY the writer stage — the
    # tool/planning stage is NOT re-run — and the writer receives the PRIOR plan
    # (the discarded message's generation_plan).
    fake = _install_fake_llm(monkeypatch)
    chat, user_id = await _setup_chain_chat(PRIOR_PLAN)
    pipeline = _make_chain_pipeline()

    await _drive(pipeline, chat, user_id, scope="text")

    assert _tool_calls(fake) == []  # planning/tool stage skipped
    writer_calls = _writer_calls(fake)
    assert len(writer_calls) >= 1  # writer stage ran
    # Prior plan fed to the writer (build_writing_plan_message reuses it).
    assert "PRIOR_PLAN_MARKER" in str(writer_calls[0]["messages"])


# ---------------------------------------------------------------------------
# DoD-3 — scope="plan" and scope omitted/None run the full chain (re-plan).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scope", ["plan", None])
async def test_scope_plan_or_none_runs_full_chain__DoD3(
    monkeypatch: pytest.MonkeyPatch, scope
) -> None:
    # DoD-3: scope="plan" (and scope omitted/None) runs the FULL chain —
    # planning (tool) stage re-executed AND the writer stage runs.
    fake = _install_fake_llm(monkeypatch)
    chat, user_id = await _setup_chain_chat(PRIOR_PLAN)
    pipeline = _make_chain_pipeline()

    await _drive(pipeline, chat, user_id, scope=scope)

    assert len(_tool_calls(fake)) >= 1  # planning re-executed
    assert len(_writer_calls(fake)) >= 1  # writer ran too


# ---------------------------------------------------------------------------
# DoD-4 — every regenerate writes exactly one rejected feedback row.
# ---------------------------------------------------------------------------


async def test_regen_writes_single_rejected_feedback_with_comment__DoD4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-4: a whole-chain regen writes exactly one ChatGenerationFeedback row
    # with verdict="rejected", the given scope/comment, and the discarded
    # content + plan snapshots.
    _install_fake_llm(monkeypatch)
    chat, user_id = await _setup_chain_chat(PRIOR_PLAN)
    pipeline = _make_chain_pipeline()

    await _drive(pipeline, chat, user_id, scope="plan", comment="too purple")

    rows = await feedback_db.list_by_turn(chat.id, 1)
    assert len(rows) == 1
    row = rows[0]
    assert row.verdict == "rejected"
    assert row.scope == "plan"
    assert row.comment == "too purple"
    assert row.content_snapshot == DISCARDED_CONTENT
    assert row.plan_snapshot == PRIOR_PLAN


async def test_regen_writes_rejected_feedback_null_scope_comment__DoD4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-4: with scope omitted and no comment, the single row still records
    # verdict="rejected" and stores null scope/comment (snapshots intact).
    _install_fake_llm(monkeypatch)
    chat, user_id = await _setup_chain_chat(PRIOR_PLAN)
    pipeline = _make_chain_pipeline()

    await _drive(pipeline, chat, user_id, scope=None, comment=None)

    rows = await feedback_db.list_by_turn(chat.id, 1)
    assert len(rows) == 1
    row = rows[0]
    assert row.verdict == "rejected"
    assert row.scope is None
    assert row.comment is None
    assert row.content_snapshot == DISCARDED_CONTENT
    assert row.plan_snapshot == PRIOR_PLAN


async def test_regen_feedback_null_plan_snapshot_when_absent__DoD4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-4: when the discarded message had no generation_plan, plan_snapshot is
    # null while content_snapshot still captures the discarded text.
    _install_fake_llm(monkeypatch)
    chat, user_id = await _setup_chain_chat(None)  # no prior plan
    pipeline = _make_chain_pipeline()

    await _drive(pipeline, chat, user_id, scope="plan", comment=None)

    rows = await feedback_db.list_by_turn(chat.id, 1)
    assert len(rows) == 1
    assert rows[0].verdict == "rejected"
    assert rows[0].plan_snapshot is None
    assert rows[0].content_snapshot == DISCARDED_CONTENT


# ---------------------------------------------------------------------------
# DoD-5 — regen appends the discarded generation to variants + variants_update.
# ---------------------------------------------------------------------------


async def test_regen_appends_variant_and_emits_variants_update__DoD5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-5: a regen appends the discarded generation to variants and emits a
    # variants_update event (accept/variant flow intact).
    _install_fake_llm(monkeypatch)
    chat, user_id = await _setup_chain_chat(PRIOR_PLAN)
    pipeline = _make_chain_pipeline()

    frames = await _drive(pipeline, chat, user_id, scope=None)

    assert "variants_update" in _event_names(frames)
    refreshed = await chats_db.get_session_by_id(chat.id)
    assert refreshed is not None
    assert DISCARDED_CONTENT in refreshed.generation_variants


async def test_writer_only_regen_appends_variant_and_emits_update__DoD5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-5: the writer-only (scope="text") path also appends the discarded
    # generation to variants and emits variants_update. (Fails at the red gate
    # until the writer-only branch is implemented — correct.)
    _install_fake_llm(monkeypatch)
    chat, user_id = await _setup_chain_chat(PRIOR_PLAN)
    pipeline = _make_chain_pipeline()

    frames = await _drive(pipeline, chat, user_id, scope="text")

    assert "variants_update" in _event_names(frames)
    refreshed = await chats_db.get_session_by_id(chat.id)
    assert refreshed is not None
    assert DISCARDED_CONTENT in refreshed.generation_variants
