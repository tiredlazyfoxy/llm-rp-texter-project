"""Chat preference retune service (Feature 014 / 015).

Session-scoped retune core: re-tunes the user's (user, world) ChatTuningProfile
via an LLM call, reading ALL reject rows across the whole session as evidence.
No turn gate and no SSE emitter live here — the core persists to the profile
only; the accept-turn gate and background scheduling live at the call sites
(steps 002/003).
"""

import logging
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


async def retune_session(
    session_id: int,
    user_id: int,
    world_id: int,
    turn_number: int,
    accepted_content: str,
    model_id: str | None,
) -> None:
    """Retune the (user, world) tuning profile from ALL session rejects.

    Session-scoped retune core (Feature 015). Reads every reject row for the
    session across all turns via ``feedback_db.list_by_session`` — no turn gate
    lives here. No-ops (no LLM call, no upsert) when ``model_id is None`` or the
    session has zero reject rows. Otherwise partitions rejects by scope
    (``plan``/``null`` -> plan dim, ``text``/``null`` -> tone dim), retunes the
    targeted dimension(s) via ``model_id`` using the reused ``_retune_dimension``
    helper, and upserts via ``tuning_profiles_db.upsert``. ``turn_number`` is
    retained for prompt/logging only and never gates. Persists to the profile
    only — no SSE emission.
    """
    rows = await feedback_db.list_by_session(session_id)
    rejections = [r for r in rows if r.verdict == "rejected"]
    if not rejections:
        # No session rejects: no LLM call, no profile change (DoD-5).
        return

    # A null-scope (whole-chain) reject counts toward BOTH dimensions.
    plan_rejects = [r for r in rejections if r.scope == "plan" or r.scope is None]
    tone_rejects = [r for r in rejections if r.scope == "text" or r.scope is None]
    retune_plan = bool(plan_rejects)
    retune_tone = bool(tone_rejects)

    if model_id is None:
        # No model to call — cannot produce revised text; no-op (DoD-4).
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

    await tuning_profiles_db.upsert(profile)
