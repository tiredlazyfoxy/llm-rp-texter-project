"""Chat preference retune service (Feature 014).

On accept of a turn that had >=1 reject, re-tunes the user's (user, world)
ChatTuningProfile via an LLM call and emits an editor-only ``tuning_update``
event. Self-gating: a clean turn (zero rejected feedback rows) never reaches the
LLM call.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from llm.message import LLMMessage

from app.db import generation_feedback as feedback_db
from app.db import tuning_profiles as tuning_profiles_db
from app.models.chat_generation_feedback import ChatGenerationFeedback
from app.models.chat_tuning_profile import ChatTuningProfile
from app.services import snowflake as snowflake_svc
from app.services.llm_chat import get_llm_client_for_model
from app.services.prompts import build_retune_prompt

logger = logging.getLogger(__name__)

# Emitter abstraction for the editor-only ``tuning_update`` SSE event.
# Called as ``await emitter(event_name, payload)``. The caller (accept hook or
# generation flow) owns editor-role gating and the queue/transport; maybe_retune
# only invokes it with the post-retune values when one is supplied. The
# non-streaming accept hook passes ``None``.
RetuneEmitter = Callable[[str, dict[str, str]], Awaitable[None]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _retune_dimension(
    dimension: str,
    current_tuning: str,
    rejections: list[ChatGenerationFeedback],
    accepted_content: str,
    model_id: str,
) -> str:
    """Run one non-tool LLM completion to produce a revised tuning string."""
    prompt = build_retune_prompt(dimension, current_tuning, rejections, accepted_content)
    messages: list[LLMMessage] = [
        {"role": "user", "content": "Produce the revised tuning instruction now."}
    ]
    client = await get_llm_client_for_model(model_id)
    async with client:
        result = await client.chat(messages, system=prompt, stream=False)
    return (result or "").strip()


async def maybe_retune(
    session_id: int,
    user_id: int,
    world_id: int,
    turn_number: int,
    accepted_content: str,
    model_id: str | None,
    emitter: RetuneEmitter | None = None,
) -> None:
    """Retune the (user, world) tuning profile if the turn had >=1 reject.

    Loads the turn's feedback rows; returns immediately (no LLM call) when there
    are zero rejected rows. Otherwise partitions rejects by scope, retunes the
    targeted dimension(s) via the shared LLM client using ``model_id``, upserts
    the profile, and emits ``tuning_update`` with the post-retune values when an
    emitter is supplied.
    """
    rows = await feedback_db.list_by_turn(session_id, turn_number)
    rejections = [r for r in rows if r.verdict == "rejected"]
    if not rejections:
        # Clean accept: no LLM call, no profile change, no emission (DoD-1).
        return

    # A null-scope (whole-chain) reject counts toward BOTH dimensions.
    plan_rejects = [r for r in rejections if r.scope == "plan" or r.scope is None]
    tone_rejects = [r for r in rejections if r.scope == "text" or r.scope is None]
    retune_plan = bool(plan_rejects)
    retune_tone = bool(tone_rejects)

    if model_id is None:
        # No model to call — cannot produce revised text; no-op (see Notes).
        logger.info(
            "Skipping retune for (user=%d, world=%d) turn=%d: no text model on session",
            user_id, world_id, turn_number,
        )
        return

    profile = await tuning_profiles_db.get(user_id, world_id)
    current_plan = profile.plan_tuning if profile else ""
    current_tone = profile.tone_tuning if profile else ""

    new_plan = current_plan
    new_tone = current_tone

    if retune_plan:
        new_plan = await _retune_dimension(
            "plan", current_plan, plan_rejects, accepted_content, model_id,
        )
    if retune_tone:
        new_tone = await _retune_dimension(
            "text", current_tone, tone_rejects, accepted_content, model_id,
        )

    now = _now()
    if profile is None:
        profile = ChatTuningProfile(
            id=snowflake_svc.generate_id(),
            user_id=user_id,
            world_id=world_id,
            plan_tuning=new_plan,
            tone_tuning=new_tone,
            created_at=now,
            modified_at=now,
        )
    else:
        # Preserve id/created_at and the untargeted dimension; bump modified_at.
        profile.plan_tuning = new_plan
        profile.tone_tuning = new_tone
        profile.modified_at = now

    saved = await tuning_profiles_db.upsert(profile)

    if emitter is not None:
        await emitter(
            "tuning_update",
            {
                "plan_tuning": saved.plan_tuning,
                "tone_tuning": saved.tone_tuning,
                "world_id": str(world_id),
            },
        )
