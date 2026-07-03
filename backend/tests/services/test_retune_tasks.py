"""Background retune task-registry tests for feature 015 step 002.

Bound to the frozen step-002 skeleton (``## Skeleton`` in
``docs/plans/015.background_retune/status.md``). Relevant frozen surface:

- ``app.services.retune_tasks`` module with:
  - ``@dataclass RetuneJob(task, running, started_at)`` — internal job record.
  - ``class RetuneStatus(TypedDict): running: bool; started_at: datetime | None``.
  - ``_registry: dict[int, RetuneJob]`` — per-session job registry.
  - ``_locks: dict[int, asyncio.Lock]`` — per-session lock map.
  - ``async def start(session_id, user_id, world_id, model_id, turn_number)
    -> None`` — fire-and-forget scheduler (NOTE: model_id precedes turn_number).
  - ``async def _run(...) -> None`` — detached runner.
  - ``async def stop(session_id) -> None``.
  - ``def status(session_id) -> RetuneStatus`` — plain def, registry read only.

Seam: the runner reaches the retune core via the module attribute
``app.services.retune_service.retune_session`` (not a direct symbol import), so
tests patch ``app.services.retune_service.retune_session`` with a controllable
fake coroutine. No real LLM or DB calls are made.

Signature reconciliation (frozen binding decision, asserted below): the core is
``retune_session(session_id, user_id, world_id, turn_number, accepted_content,
model_id)``. ``start(...)`` omits ``accepted_content`` and allows
``turn_number=None``. The runner maps ``turn_number`` ``None`` -> ``0`` and the
absent ``accepted_content`` -> ``""`` when calling the core.

Expected values come only from the step spec (Definition of done + Interface
intent) and the frozen skeleton — the implementation body is never read.

Red-gate note: ``start``/``_run``/``stop``/``status`` are stubs until the coder
implements them; these tests assert the spec-correct behavior and (correctly)
fail until then.
"""

import asyncio
from datetime import datetime

import pytest

from app.services import retune_tasks
from app.services.snowflake import generate_id

MODEL_ID = "mock-model"


# ---------------------------------------------------------------------------
# Controllable fake retune core.
#
# Blocks on an asyncio.Event so a background job can be held "running" while the
# test observes status(...) mid-flight, then released or cancelled
# deterministically. Records every invocation's arguments so the test can assert
# which signal reached the core (cancel-and-restart / reconciliation).
# ---------------------------------------------------------------------------


class FakeCore:
    def __init__(self) -> None:
        # One dict per invocation, keyed by the frozen core parameter names.
        self.calls: list[dict] = []
        # Test releases this to let a blocked core invocation complete.
        self.release = asyncio.Event()
        # How many invocations observed a CancelledError (cancel-and-restart).
        self.cancelled_count = 0
        # When set, a released invocation raises this instead of returning.
        self.raise_after_release: BaseException | None = None

    async def __call__(
        self,
        session_id=None,
        user_id=None,
        world_id=None,
        turn_number=None,
        accepted_content=None,
        model_id=None,
    ) -> None:
        self.calls.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "world_id": world_id,
                "turn_number": turn_number,
                "accepted_content": accepted_content,
                "model_id": model_id,
            }
        )
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled_count += 1
            raise  # a well-behaved core re-raises; the RUNNER must swallow it
        if self.raise_after_release is not None:
            raise self.raise_after_release


def _install_fake_core(monkeypatch: pytest.MonkeyPatch) -> FakeCore:
    fake = FakeCore()
    monkeypatch.setattr(
        "app.services.retune_service.retune_session", fake, raising=False
    )
    return fake


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    """Poll ``predicate`` (giving the event loop turns) until true or timeout."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out waiting for condition")


@pytest.fixture(autouse=True)
async def _clean_registry():
    """Isolate the module-level registry/locks between tests and ensure no
    background task leaks past a test."""
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


# ===========================================================================
# DoD-1 — running -> idle transition (and start->core reconciliation).
# ===========================================================================


async def test_status_running_then_idle_after_completion__DoD1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-1: after start(...), status(session_id) reports running; after the job
    # completes, status(session_id) reports idle. A manual-style trigger
    # (turn_number=None) also exercises the frozen reconciliation: the core is
    # called with turn_number 0 and accepted_content "".
    fake = _install_fake_core(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()

    await retune_tasks.start(
        session_id=sid,
        user_id=uid,
        world_id=wid,
        model_id=MODEL_ID,
        turn_number=None,
    )

    # Background job is scheduled and running (blocked in the core).
    await _wait_until(lambda: len(fake.calls) == 1)
    snap = retune_tasks.status(sid)
    assert snap["running"] is True
    assert isinstance(snap["started_at"], datetime)

    # Reconciliation: turn_number None -> 0, absent accepted_content -> "".
    call = fake.calls[0]
    assert call["session_id"] == sid
    assert call["user_id"] == uid
    assert call["world_id"] == wid
    assert call["model_id"] == MODEL_ID
    assert call["turn_number"] == 0
    assert call["accepted_content"] == ""

    # Let the core finish; the runner clears the registry -> idle.
    task = retune_tasks._registry[sid].task
    fake.release.set()
    await _wait_until(lambda: task.done())

    idle = retune_tasks.status(sid)
    assert idle["running"] is False
    assert idle["started_at"] is None


# ===========================================================================
# DoD-2 — two start()s for one session never leave two live tasks.
# ===========================================================================


async def test_second_start_cancels_first_single_live_job__DoD2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-2: a second start(...) for the same session cancels the in-flight job
    # and leaves exactly one live/registered job (cancel-and-restart).
    fake = _install_fake_core(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()

    await retune_tasks.start(
        session_id=sid, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=11
    )
    await _wait_until(lambda: len(fake.calls) == 1)
    first_task = retune_tasks._registry[sid].task

    await retune_tasks.start(
        session_id=sid, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=22
    )
    await _wait_until(lambda: len(fake.calls) == 2)

    # The first task was torn down; a single, different live job remains.
    assert first_task.done() is True
    assert fake.cancelled_count >= 1
    current = retune_tasks._registry[sid].task
    assert current is not first_task
    assert current.done() is False
    assert retune_tasks.status(sid)["running"] is True


# ===========================================================================
# DoD-3 — the restart runs the core with the latest arguments.
# ===========================================================================


async def test_restart_uses_latest_arguments__DoD3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-3: the second start(...) restarts with the newly supplied signal — the
    # live job runs the core with the newest turn_number, not the stale one.
    fake = _install_fake_core(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()

    await retune_tasks.start(
        session_id=sid, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=11
    )
    await _wait_until(lambda: len(fake.calls) == 1)

    await retune_tasks.start(
        session_id=sid, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=22
    )
    await _wait_until(lambda: len(fake.calls) == 2)

    # First invocation carried the stale signal; the newest carries the latest.
    assert fake.calls[0]["turn_number"] == 11
    latest = fake.calls[-1]
    assert latest["turn_number"] == 22
    assert latest["session_id"] == sid
    assert latest["model_id"] == MODEL_ID


# ===========================================================================
# DoD-4 — stop() cancels and leaves the session idle with no replacement.
# ===========================================================================


async def test_stop_cancels_and_no_replacement__DoD4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-4: stop(session_id) cancels the running job and leaves the session idle
    # with NO replacement job scheduled.
    fake = _install_fake_core(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()

    await retune_tasks.start(
        session_id=sid, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=7
    )
    await _wait_until(lambda: len(fake.calls) == 1)
    task = retune_tasks._registry[sid].task

    await retune_tasks.stop(sid)

    # Job cancelled and removed; session idle; no new core invocation scheduled.
    assert task.done() is True
    assert fake.cancelled_count >= 1
    assert sid not in retune_tasks._registry
    idle = retune_tasks.status(sid)
    assert idle["running"] is False
    assert idle["started_at"] is None
    assert len(fake.calls) == 1  # no replacement invoked the core again


# ===========================================================================
# DoD-5 — two different sessions run independently.
# ===========================================================================


async def test_two_sessions_run_independently__DoD5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-5: start(...) for two different sessions leaves both running
    # independently (registry is keyed per session).
    fake = _install_fake_core(monkeypatch)
    s1, s2 = generate_id(), generate_id()
    uid, wid = generate_id(), generate_id()

    await retune_tasks.start(
        session_id=s1, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=1
    )
    await retune_tasks.start(
        session_id=s2, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=2
    )
    await _wait_until(lambda: len(fake.calls) == 2)

    assert s1 in retune_tasks._registry
    assert s2 in retune_tasks._registry
    assert retune_tasks.status(s1)["running"] is True
    assert retune_tasks.status(s2)["running"] is True

    t1 = retune_tasks._registry[s1].task
    t2 = retune_tasks._registry[s2].task
    assert t1 is not t2
    assert t1.done() is False
    assert t2.done() is False
    # Neither session's job cancelled the other's.
    assert fake.cancelled_count == 0


# ===========================================================================
# DoD-6 — runner swallows cancellation AND core errors, clearing the registry
#         in success, cancel, and error completion paths.
# ===========================================================================


async def test_runner_success_path_clears_registry__DoD6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-6 (success path): a cleanly completing core leaves no exception on the
    # task and clears the registry entry.
    fake = _install_fake_core(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()

    await retune_tasks.start(
        session_id=sid, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=1
    )
    await _wait_until(lambda: len(fake.calls) == 1)
    task = retune_tasks._registry[sid].task

    fake.release.set()
    await _wait_until(lambda: task.done())

    assert task.cancelled() is False
    assert task.exception() is None
    assert sid not in retune_tasks._registry
    assert retune_tasks.status(sid)["running"] is False


async def test_runner_swallows_cancellation_and_clears_registry__DoD6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-6 (cancel path): cancelling the detached task does NOT propagate
    # CancelledError out of the task (swallowed cleanly), and the registry entry
    # is cleared.
    fake = _install_fake_core(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()

    await retune_tasks.start(
        session_id=sid, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=1
    )
    await _wait_until(lambda: len(fake.calls) == 1)
    task = retune_tasks._registry[sid].task

    task.cancel()
    await _wait_until(lambda: task.done())

    # Swallowed, not propagated: the task is not marked cancelled and holds no
    # exception.
    assert task.cancelled() is False
    assert task.exception() is None
    assert sid not in retune_tasks._registry
    assert retune_tasks.status(sid)["running"] is False


async def test_runner_swallows_core_exception_and_clears_registry__DoD6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-6 (error path): a core exception is log-and-swallowed — it never
    # propagates out of the detached task — and the registry entry is cleared.
    fake = _install_fake_core(monkeypatch)
    fake.raise_after_release = RuntimeError("core boom")
    sid, uid, wid = generate_id(), generate_id(), generate_id()

    await retune_tasks.start(
        session_id=sid, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=1
    )
    await _wait_until(lambda: len(fake.calls) == 1)
    task = retune_tasks._registry[sid].task

    fake.release.set()
    await _wait_until(lambda: task.done())

    assert task.cancelled() is False
    assert task.exception() is None  # error swallowed, not propagated
    assert sid not in retune_tasks._registry
    assert retune_tasks.status(sid)["running"] is False


# ===========================================================================
# DoD-7 — start() returns promptly without awaiting core completion.
# ===========================================================================


async def test_start_returns_without_awaiting_core__DoD7(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DoD-7: start(...) schedules the core and returns before it completes. The
    # fake core blocks forever (release is never set); reaching the assertions
    # after `await start(...)` proves start did not await completion.
    fake = _install_fake_core(monkeypatch)
    sid, uid, wid = generate_id(), generate_id(), generate_id()

    await retune_tasks.start(
        session_id=sid, user_id=uid, world_id=wid, model_id=MODEL_ID, turn_number=1
    )

    # start returned though the core can never finish (release un-set) ->
    # non-blocking scheduling.
    await _wait_until(lambda: len(fake.calls) == 1)
    assert retune_tasks.status(sid)["running"] is True
    assert retune_tasks._registry[sid].task.done() is False
