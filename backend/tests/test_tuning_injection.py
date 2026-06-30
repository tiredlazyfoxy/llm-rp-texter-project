"""Tuning-injection tests for feature 014 (chat_preference_tuning) step 002.

Covers the placeholder plumbing that injects per-(user, world) tuning text into
chain-stage prompts via two new placeholders — ``PLAN_TUNING`` (tool/planning
stages) and ``TONE_TUNING`` (writer stage) — bound to the frozen step-002
skeleton:

- ``placeholder_registry`` — ``PLACEHOLDER_REGISTRY`` / ``VALID_PLACEHOLDERS``
- ``prompt_injection.resolve_prompt_template(template, **values)``
- ``chain_generation_service._build_placeholder_values(...)``
- ``default_templates`` — ``DEFAULT_TOOL_PROMPT`` / ``DEFAULT_DIRECTOR_PROMPT`` /
  ``DEFAULT_WRITER_PROMPT``

Expected values come from the step spec / DoD only. Collaborator objects
(``ChatContext`` / chat) are stand-ins (``MagicMock``); the only assertions made
are on the ``PLAN_TUNING`` / ``TONE_TUNING`` keys the spec promises, so the test
makes no assumption about how the other placeholder values are assembled.

DoD-4 / DoD-5 bind to the frozen ``_load_tuning(chat) -> tuple[str, str]`` seam
(it reads only ``chat.user_id`` / ``chat.world_id``) together with the step-001
data layer (``db.tuning_profiles.upsert``) — no full chain run needed.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.db import tuning_profiles as profiles_db
from app.models.chat_tuning_profile import ChatTuningProfile
from app.services.chain_generation_service import (
    _build_placeholder_values,
    _load_tuning,
)
from app.services.prompts.default_templates import (
    DEFAULT_DIRECTOR_PROMPT,
    DEFAULT_TOOL_PROMPT,
    DEFAULT_WRITER_PROMPT,
)
from app.services.prompts.placeholder_registry import (
    PLACEHOLDER_REGISTRY,
    VALID_PLACEHOLDERS,
)
from app.services.prompts.prompt_injection import resolve_prompt_template
from app.services.snowflake import generate_id


def _make_profile(
    *, user_id: int, world_id: int, plan_tuning: str, tone_tuning: str
) -> ChatTuningProfile:
    """Build a ChatTuningProfile (service layer assigns the snowflake id),
    matching the step-001 data-layer test convention."""
    now = datetime.now(timezone.utc)
    return ChatTuningProfile(
        id=generate_id(),
        user_id=user_id,
        world_id=world_id,
        plan_tuning=plan_tuning,
        tone_tuning=tone_tuning,
        created_at=now,
        modified_at=now,
    )

# ---------------------------------------------------------------------------
# DoD-1 — registry / VALID_PLACEHOLDERS carry the two new placeholders
# ---------------------------------------------------------------------------


def test_registry_contains_tuning_placeholders__DoD1() -> None:
    # DoD-1: PLACEHOLDER_REGISTRY registers PLAN_TUNING and TONE_TUNING.
    names = {entry["name"] for entry in PLACEHOLDER_REGISTRY}
    assert "PLAN_TUNING" in names
    assert "TONE_TUNING" in names


def test_valid_placeholders_contains_tuning__DoD1() -> None:
    # DoD-1: VALID_PLACEHOLDERS (derived from the registry) contains both names.
    assert "PLAN_TUNING" in VALID_PLACEHOLDERS
    assert "TONE_TUNING" in VALID_PLACEHOLDERS


# ---------------------------------------------------------------------------
# DoD-2 — resolve_prompt_template substitutes both tuning tokens
# ---------------------------------------------------------------------------


def test_resolve_substitutes_both_tuning_tokens__DoD2() -> None:
    # DoD-2: a template containing {PLAN_TUNING} and {TONE_TUNING} has both
    # tokens replaced by the supplied values.
    template = "Plan: {PLAN_TUNING} | Tone: {TONE_TUNING}"

    result = resolve_prompt_template(template, PLAN_TUNING="A", TONE_TUNING="B")

    assert result == "Plan: A | Tone: B"
    assert "{PLAN_TUNING}" not in result
    assert "{TONE_TUNING}" not in result


# ---------------------------------------------------------------------------
# DoD-3 — _build_placeholder_values maps the tuning strings (empty by default)
# ---------------------------------------------------------------------------


def test_build_placeholder_values_maps_supplied_tuning__DoD3() -> None:
    # DoD-3: the returned map's PLAN_TUNING / TONE_TUNING keys equal the
    # supplied tuning strings. Context / chat are stand-ins; only the tuning
    # keys are asserted.
    context = MagicMock()
    chat = MagicMock()

    values = _build_placeholder_values(
        context,
        chat,
        turn_facts="",
        turn_decisions="",
        tools_desc="",
        plan_tuning="PLAN-XYZ",
        tone_tuning="TONE-XYZ",
    )

    assert values["PLAN_TUNING"] == "PLAN-XYZ"
    assert values["TONE_TUNING"] == "TONE-XYZ"


def test_build_placeholder_values_defaults_empty_tuning__DoD3() -> None:
    # DoD-3: when no tuning is supplied, both keys are present and empty strings.
    context = MagicMock()
    chat = MagicMock()

    values = _build_placeholder_values(
        context,
        chat,
        turn_facts="",
        turn_decisions="",
        tools_desc="",
    )

    assert values["PLAN_TUNING"] == ""
    assert values["TONE_TUNING"] == ""


# ---------------------------------------------------------------------------
# DoD-6 — default templates embed the new tokens
# ---------------------------------------------------------------------------


def test_default_tool_prompt_has_plan_tuning_token__DoD6() -> None:
    # DoD-6: DEFAULT_TOOL_PROMPT embeds the {PLAN_TUNING} token.
    assert "{PLAN_TUNING}" in DEFAULT_TOOL_PROMPT


def test_default_director_prompt_has_plan_tuning_token__DoD6() -> None:
    # DoD-6: DEFAULT_DIRECTOR_PROMPT embeds the {PLAN_TUNING} token.
    assert "{PLAN_TUNING}" in DEFAULT_DIRECTOR_PROMPT


def test_default_writer_prompt_has_tone_tuning_token__DoD6() -> None:
    # DoD-6: DEFAULT_WRITER_PROMPT embeds the {TONE_TUNING} token.
    assert "{TONE_TUNING}" in DEFAULT_WRITER_PROMPT


# ---------------------------------------------------------------------------
# DoD-4 — stored profile is loaded and flows into the placeholder map
# ---------------------------------------------------------------------------


async def test_load_tuning_returns_stored_profile_values__DoD4() -> None:
    # DoD-4: with a profile stored for the chat's (user_id, world_id),
    # _load_tuning returns exactly that profile's (plan_tuning, tone_tuning).
    user_id = generate_id()
    world_id = generate_id()
    await profiles_db.upsert(
        _make_profile(
            user_id=user_id,
            world_id=world_id,
            plan_tuning="prefer terse plans",
            tone_tuning="prefer wry tone",
        )
    )
    chat = SimpleNamespace(user_id=user_id, world_id=world_id)

    plan_tuning, tone_tuning = await _load_tuning(chat)

    assert plan_tuning == "prefer terse plans"
    assert tone_tuning == "prefer wry tone"


async def test_loaded_profile_injected_into_placeholder_map__DoD4() -> None:
    # DoD-4: the loaded values compose through into the placeholder map —
    # PLAN_TUNING / TONE_TUNING carry the stored profile's strings, which is
    # what the tool-stage / writer-stage prompts substitute.
    user_id = generate_id()
    world_id = generate_id()
    await profiles_db.upsert(
        _make_profile(
            user_id=user_id,
            world_id=world_id,
            plan_tuning="plan-from-profile",
            tone_tuning="tone-from-profile",
        )
    )
    chat = SimpleNamespace(user_id=user_id, world_id=world_id)

    plan_tuning, tone_tuning = await _load_tuning(chat)
    values = _build_placeholder_values(
        MagicMock(),
        MagicMock(),
        turn_facts="",
        turn_decisions="",
        tools_desc="",
        plan_tuning=plan_tuning,
        tone_tuning=tone_tuning,
    )

    assert values["PLAN_TUNING"] == "plan-from-profile"
    assert values["TONE_TUNING"] == "tone-from-profile"


# ---------------------------------------------------------------------------
# DoD-5 — no profile row → empty tuning strings, no error
# ---------------------------------------------------------------------------


async def test_load_tuning_no_profile_returns_empty__DoD5() -> None:
    # DoD-5: with no profile stored for the (user_id, world_id), _load_tuning
    # returns ("", "") and does not raise.
    chat = SimpleNamespace(user_id=generate_id(), world_id=generate_id())

    plan_tuning, tone_tuning = await _load_tuning(chat)

    assert plan_tuning == ""
    assert tone_tuning == ""
