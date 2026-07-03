"""Retune REST API tests for feature 015 step 004.

Bound to the frozen step-004 skeleton (``## Skeleton`` in
``docs/plans/015.background_retune/status.md``). Relevant frozen surface:

- Routes on the existing chat prefix ``/api/chats`` (auth dep
  ``Depends(_require_player)``), all returning ``RetuneStatusResponse``:
  - ``POST /api/chats/{chat_id}/retune``      -> ``tuning_service.trigger_retune(int(chat_id), caller.id)``
  - ``POST /api/chats/{chat_id}/retune/stop`` -> ``tuning_service.stop_retune(int(chat_id), caller.id)``
  - ``GET  /api/chats/{chat_id}/retune/status`` -> ``tuning_service.get_retune_status(int(chat_id), caller.id)``
- ``RetuneStatusResponse(BaseModel)``: ``running: bool``, ``plan_tuning: str``,
  ``tone_tuning: str``, ``world_id: str`` (world_id serialized as a string;
  ``started_at`` deliberately omitted from the schema).
- Frozen binding decisions: ``session_id == chat.id``,
  ``model_id == chat.text_model_id``, ``world_id == chat.world_id``.
- Ownership is **404-only**: a non-owner or a missing chat yields
  ``HTTPException(status_code=404, detail="Chat not found")``. There is NO 403.
- Manual trigger passes ``turn_number=None`` to ``retune_tasks.start(...)`` — it
  ignores the D2 turn-gate (the manual button always fires).

Seams (mirroring the namespace-module patch convention used by the step-002/003
tests):
- The background registry is real (``app.services.retune_tasks``); the retune
  LLM core is patched at ``app.services.retune_service.retune_session`` with a
  controllable fake that blocks on an ``asyncio.Event`` so a job can be held
  "running" while the API is polled (DoD-1/DoD-2).
- For DoD-5 the scheduler itself is spied at ``app.services.retune_tasks.start``
  to capture the arguments the service passes (proving ``turn_number=None``).

Endpoints are reached through the real FastAPI app (``http_client`` fixture)
with an authenticated player caller (``player_user`` fixture). Chats are created
in the test DB via ``db/chats`` owned by the caller; a second player is created
inline for the ownership-rejection test. Profiles are seeded directly via
``db/tuning_profiles``.

Expected values come only from the step spec (Definition of done + Interface
intent) and the frozen skeleton — the implementation body is never read. The
``tuning_service`` retune bodies raise ``NotImplementedError`` per the skeleton
contract, so these tests assert the spec-correct behavior and (correctly) fail
red until the coder implements them.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from app.db import chats as chats_db
from app.db import tuning_profiles as profiles_db
from app.db import users as users_db
from app.models.chat_session import ChatSession
from app.models.chat_tuning_profile import ChatTuningProfile
from app.models.user import User, UserRole
from app.services import auth as auth_service
from app.services import retune_tasks
from app.services.snowflake import generate_id

pytestmark = pytest.mark.asyncio

MODEL_ID = "mock-model"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_chat_in_db(
    user_id: int,
    world_id: int,
    *,
    text_model_id: str | None = MODEL_ID,
    current_turn: int = 3,
) -> ChatSession:
    """Persist a ChatSession owned by ``user_id``. session_id == chat.id."""
    now = _now()
    chat = ChatSession(
        id=generate_id(),
        user_id=user_id,
        world_id=world_id,
        current_location_id=None,
        character_name="Hero",
        character_description="A brave adventurer.",
        character_stats="{}",
        world_stats="{}",
        current_turn=current_turn,
        status="active",
        tool_model_id=text_model_id,
        tool_temperature=0.7,
        tool_repeat_penalty=1.0,
        tool_top_p=1.0,
        text_model_id=text_model_id,
        text_temperature=0.7,
        text_repeat_penalty=1.0,
        text_top_p=1.0,
        user_instructions="",
        generation_variants="[]",
        created_at=now,
        modified_at=now,
    )
    return await chats_db.create_session(chat)


async def _create_player() -> tuple[User, str]:
    """A second authenticated player (for the ownership-rejection test)."""
    salt, pwdhash, signing_key = auth_service.create_user_credentials("password123")
    user = User(
        id=generate_id(),
        username=f"player_{generate_id()}",
        pwdhash=pwdhash,
        salt=salt,
        role=UserRole.player,
        jwt_signing_key=signing_key,
        last_key_update=_now(),
    )
    await users_db.create(user)
    token = auth_service.create_token(user)
    return user, token


async def _seed_profile(
    user_id: int,
    world_id: int,
    *,
    plan_tuning: str,
    tone_tuning: str,
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


# ---------------------------------------------------------------------------
# Controllable fake retune core: blocks on an asyncio.Event so a real
# background job (driven by the real registry) stays "running" while the API is
# polled. Released/cancelled deterministically by the test or the cleanup
# fixture.
# ---------------------------------------------------------------------------


class FakeCore:
    def __init__(self) -> None:
        self.release = asyncio.Event()

    async def __call__(self, *args, **kwargs) -> None:
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            raise  # the runner swallows; a well-behaved core re-raises


class FakeStart:
    """Spy for ``retune_tasks.start`` — records each invocation's arguments.

    Parameter order matches the frozen step-002 signature
    ``start(session_id, user_id, world_id, model_id, turn_number)`` so positional
    or keyword calls both map correctly.
    """

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


def _install_blocking_core(monkeypatch: pytest.MonkeyPatch) -> FakeCore:
    fake = FakeCore()
    monkeypatch.setattr(
        "app.services.retune_service.retune_session", fake, raising=False
    )
    return fake


def _install_start_spy(monkeypatch: pytest.MonkeyPatch) -> FakeStart:
    spy = FakeStart()
    monkeypatch.setattr("app.services.retune_tasks.start", spy, raising=False)
    return spy


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out waiting for condition")


@pytest.fixture(autouse=True)
async def _clean_registry():
    """Isolate the module-level registry/locks and ensure no background task
    leaks past a test (mirrors the step-002 registry test harness)."""
    retune_tasks._registry.clear()
    retune_tasks._locks.clear()
    yield
    tasks = [job.task for job in retune_tasks._registry.values()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    retune_tasks._registry.clear()
    retune_tasks._locks.clear()


def _assert_valid_status_body(body: dict) -> None:
    """A valid RetuneStatusResponse: the four frozen fields with their types
    (world_id serialized as a string; started_at intentionally absent)."""
    assert isinstance(body["running"], bool)
    assert isinstance(body["plan_tuning"], str)
    assert isinstance(body["tone_tuning"], str)
    assert isinstance(body["world_id"], str)


# ===========================================================================
# DoD-1 — POST /{chat_id}/retune starts a background job for the chat's session
#         (the real registry reports running afterward) and returns a valid
#         RetuneStatusResponse.
# ===========================================================================


async def test_trigger_starts_background_job_and_returns_status__DoD1(
    http_client, player_user: tuple[User, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-1: triggering a retune schedules a background job on the chat's
    # session (session_id == chat.id); the real registry reports running=True,
    # and the endpoint returns a valid RetuneStatusResponse (200).
    owner, token = player_user
    fake = _install_blocking_core(monkeypatch)
    chat = await _create_chat_in_db(owner.id, generate_id())

    resp = await http_client.post(
        f"/api/chats/{chat.id}/retune", headers=_auth(token)
    )

    try:
        assert resp.status_code == 200, resp.text
        body = resp.json()
        _assert_valid_status_body(body)
        # The registry genuinely has a live job for this session.
        assert retune_tasks.status(chat.id)["running"] is True
        # ...and the returned status reflects that live job.
        assert body["running"] is True
    finally:
        fake.release.set()  # let the blocked job finish so cleanup is quick


# ===========================================================================
# DoD-2 — POST /{chat_id}/retune/stop cancels the running job; a subsequent
#         GET /{chat_id}/retune/status reports running=false.
# ===========================================================================


async def test_stop_cancels_running_job_then_status_idle__DoD2(
    http_client, player_user: tuple[User, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-2: after a trigger the session is running; POST .../retune/stop cancels
    # it and a following GET .../retune/status reports running=false.
    owner, token = player_user
    _install_blocking_core(monkeypatch)
    chat = await _create_chat_in_db(owner.id, generate_id())

    trigger = await http_client.post(
        f"/api/chats/{chat.id}/retune", headers=_auth(token)
    )
    assert trigger.status_code == 200, trigger.text
    assert retune_tasks.status(chat.id)["running"] is True

    stop = await http_client.post(
        f"/api/chats/{chat.id}/retune/stop", headers=_auth(token)
    )
    assert stop.status_code == 200, stop.text
    _assert_valid_status_body(stop.json())
    # Cancelled at the registry level — no live job remains.
    assert retune_tasks.status(chat.id)["running"] is False

    status = await http_client.get(
        f"/api/chats/{chat.id}/retune/status", headers=_auth(token)
    )
    assert status.status_code == 200, status.text
    assert status.json()["running"] is False


# ===========================================================================
# DoD-3 — GET /{chat_id}/retune/status returns RetuneStatusResponse with the
#         correct running flag and the current profile's plan_tuning /
#         tone_tuning / world_id (ids serialized as strings).
# ===========================================================================


async def test_status_returns_profile_values_and_string_world_id__DoD3(
    http_client, player_user: tuple[User, str],
) -> None:
    # DoD-3: with no running job, GET status reports running=false and surfaces
    # the stored (user, world) profile's plan_tuning / tone_tuning, plus the
    # chat's world_id serialized as a string.
    owner, token = player_user
    world_id = generate_id()
    chat = await _create_chat_in_db(owner.id, world_id)
    await _seed_profile(
        owner.id, world_id, plan_tuning="be concise", tone_tuning="be warm"
    )

    resp = await http_client.get(
        f"/api/chats/{chat.id}/retune/status", headers=_auth(token)
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    _assert_valid_status_body(body)
    assert body["running"] is False  # no job was started
    assert body["plan_tuning"] == "be concise"
    assert body["tone_tuning"] == "be warm"
    assert body["world_id"] == str(world_id)  # id serialized as a string
    assert isinstance(body["world_id"], str)


# ===========================================================================
# DoD-4 — a caller who does not own the chat is rejected (404) on all three
#         endpoints (ownership is 404-only; detail "Chat not found").
# ===========================================================================


@pytest.mark.parametrize(
    "method,suffix",
    [("POST", "/retune"), ("POST", "/retune/stop"), ("GET", "/retune/status")],
    ids=["trigger", "stop", "status"],
)
async def test_non_owner_rejected_404__DoD4(
    http_client,
    player_user: tuple[User, str],
    method: str,
    suffix: str,
) -> None:
    # DoD-4: a chat owned by one player, called by a different authenticated
    # player, yields 404 "Chat not found" on every retune endpoint (no 403 path).
    owner, _owner_token = player_user
    chat = await _create_chat_in_db(owner.id, generate_id())
    _other, other_token = await _create_player()

    resp = await http_client.request(
        method, f"/api/chats/{chat.id}{suffix}", headers=_auth(other_token)
    )

    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Chat not found"


# ===========================================================================
# DoD-5 — the manual trigger ignores the D2 turn-gate: it starts a job even for
#         a turn context with zero rejects, calling retune_tasks.start with
#         turn_number=None (and the frozen session/user/world/model bindings).
# ===========================================================================


async def test_manual_trigger_ignores_turn_gate_turn_number_none__DoD5(
    http_client, player_user: tuple[User, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-5: no reject rows exist for the chat (a context the auto-trigger gate
    # would NOT fire on), yet the manual trigger schedules a job. The scheduler
    # is spied to prove it is called exactly once with turn_number=None (the
    # manual binding) plus session_id/user_id/world_id/model_id from the chat.
    owner, token = player_user
    spy = _install_start_spy(monkeypatch)
    world_id = generate_id()
    # No feedback rows seeded => zero session rejects => gate would block auto.
    chat = await _create_chat_in_db(owner.id, world_id, text_model_id=MODEL_ID)

    resp = await http_client.post(
        f"/api/chats/{chat.id}/retune", headers=_auth(token)
    )

    assert resp.status_code == 200, resp.text
    assert len(spy.calls) == 1  # manual button fired despite the empty gate
    call = spy.calls[0]
    assert call["turn_number"] is None  # ignores the D2 turn-gate
    assert call["session_id"] == chat.id  # session_id == chat.id
    assert call["user_id"] == owner.id
    assert call["world_id"] == world_id  # world_id == chat.world_id
    assert call["model_id"] == MODEL_ID  # model_id == chat.text_model_id
