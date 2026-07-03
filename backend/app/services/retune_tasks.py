"""Background retune task registry (Feature 015 / step 002).

In-memory, per-session registry that runs the step-001 retune core
(``retune_service.retune_session``) as a detached ``asyncio.Task``. Guarantees
at most one running job per session with cancel-and-restart semantics (design
decision D3). Safe as a process singleton because the backend runs a single
uvicorn worker (see feature ``context.md``).

Skeleton note (interface freeze): behavior is intentionally unimplemented — the
public surface below defines the frozen contract only. The detached runner MUST
reach the core via the module attribute ``retune_service.retune_session`` (kept
patchable for tests) rather than importing the symbol directly.

Signature reconciliation (recorded so test-coder and coder bind identically):
the step-001 core requires ``turn_number: int`` and ``accepted_content: str``,
but ``start(...)`` accepts neither an ``accepted_content`` nor a non-null
``turn_number``. The runner maps them as:
  - ``turn_number`` is ``None`` (manual trigger) -> pass ``0`` to the core
    (``turn_number`` is prompt/logging-only in the core and never gates);
  - no ``accepted_content`` at the ``start`` boundary -> pass ``""`` to the core
    (session-wide retune reads all reject rows; the accepted turn's text is not
    part of the background contract).
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypedDict

from app.services import retune_service  # seam: patch retune_service.retune_session

logger = logging.getLogger(__name__)


@dataclass
class RetuneJob:
    """A single in-flight background retune for one session."""

    task: "asyncio.Task[None]"
    running: bool
    started_at: datetime


class RetuneStatus(TypedDict):
    """Lightweight status snapshot for the service layer (step 004 maps to API)."""

    running: bool
    started_at: datetime | None


# Process-singleton state (single uvicorn worker — safe as module-level dicts).
_registry: dict[int, RetuneJob] = {}
_locks: dict[int, asyncio.Lock] = {}


def _get_lock(session_id: int) -> asyncio.Lock:
    """Return the per-session lock, creating it lazily on first use."""
    lock = _locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[session_id] = lock
    return lock


async def _cancel_and_await(job: RetuneJob) -> None:
    """Cancel an in-flight job's task and await its teardown (swallow cancel)."""
    job.task.cancel()
    try:
        await job.task
    except asyncio.CancelledError:
        pass
    except Exception:  # noqa: BLE001 - teardown of a job the runner already logged
        pass


async def start(
    session_id: int,
    user_id: int,
    world_id: int,
    model_id: str | None,
    turn_number: int | None,
) -> None:
    """Cancel any in-flight job for the session and start a fresh detached one.

    Fire-and-forget: returns without awaiting the retune core (D3
    cancel-and-restart). ``turn_number`` may be ``None`` (manual trigger).
    """
    async with _get_lock(session_id):
        existing = _registry.get(session_id)
        if existing is not None:
            await _cancel_and_await(existing)
            # Only clear if the teardown didn't already remove/replace it.
            if _registry.get(session_id) is existing:
                del _registry[session_id]

        task: "asyncio.Task[None]" = asyncio.create_task(
            _run(
                session_id=session_id,
                user_id=user_id,
                world_id=world_id,
                model_id=model_id,
                turn_number=turn_number,
            )
        )
        _registry[session_id] = RetuneJob(
            task=task,
            running=True,
            started_at=datetime.now(timezone.utc),
        )


async def _run(
    session_id: int,
    user_id: int,
    world_id: int,
    model_id: str | None,
    turn_number: int | None,
) -> None:
    """Detached runner: invoke the retune core, then clear own registry entry.

    Swallows ``asyncio.CancelledError`` and any core exception; in a ``finally``
    clears its registry entry only if it is still the registered job.
    """
    try:
        await retune_service.retune_session(
            session_id=session_id,
            user_id=user_id,
            world_id=world_id,
            turn_number=turn_number if turn_number is not None else 0,
            accepted_content="",
            model_id=model_id,
        )
    except asyncio.CancelledError:
        # Cancellation is normal (cancel-and-restart / stop) — swallow cleanly.
        pass
    except Exception:  # noqa: BLE001 - a failed retune must never leak out of the task
        logger.exception(
            "Background retune failed for session %s", session_id
        )
    finally:
        job = _registry.get(session_id)
        current = asyncio.current_task()
        if job is not None and job.task is current:
            job.running = False
            del _registry[session_id]


async def stop(session_id: int) -> None:
    """Cancel the in-flight job for the session (if any) without restarting it."""
    async with _get_lock(session_id):
        existing = _registry.get(session_id)
        if existing is None:
            return
        await _cancel_and_await(existing)
        if _registry.get(session_id) is existing:
            del _registry[session_id]


def status(session_id: int) -> RetuneStatus:
    """Return whether a job is currently running for the session and its start time."""
    job = _registry.get(session_id)
    if job is None:
        return RetuneStatus(running=False, started_at=None)
    return RetuneStatus(running=job.running, started_at=job.started_at)
