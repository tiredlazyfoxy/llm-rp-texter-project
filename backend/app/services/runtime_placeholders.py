"""Pure runtime placeholder substitution helper.

PURPOSE
    Single, centralized substitution of the three runtime placeholder
    tokens recognized inside player-facing text:

        {CHARACTER_NAME}    -> session character name
        {LOCATION_NAME}     -> current (or starting) location name
        {LOCATION_SUMMARY}  -> current (or starting) location content

    Every chat-runtime substitution site (chat_service initial_message,
    chat_context location/lore/NPC content, chat_tools wrappers) calls
    this helper. No other module re-implements the .replace() logic.

DESIGN RATIONALE
    Lives in `services/` because both `chat_service.py` and
    `chat_context.py` consume it; placing it in `db/` would invert the
    layering. The helper is pure -- no I/O, no DB, no imports from
    `app.db.*` -- so keeping it here does not violate layer separation.

    Distinct from `app.db.worlds.rewrite_initial_message_tokens()`
    (introduced in feature 010 step 001), which performs a one-time
    source-data lowercase-to-uppercase normalization on stored
    `World.initial_message` rows. That helper edits the data; this
    helper substitutes runtime values into already-normalized text.
"""

from typing import TypedDict


class RuntimePlaceholderContext(TypedDict):
    character_name: str
    location_name: str
    location_summary: str


def apply_runtime_placeholders(
    text: str,
    ctx: RuntimePlaceholderContext | None,
) -> str:
    """Substitute the three runtime placeholder tokens in `text`.

        {CHARACTER_NAME}    -> ctx["character_name"]
        {LOCATION_NAME}     -> ctx["location_name"]
        {LOCATION_SUMMARY}  -> ctx["location_summary"]

    If `ctx` is None, returns `text` unchanged (editor-mode contract:
    leave literal tokens intact so the AI editor learns the syntax).

    Pure: no I/O. Idempotent on already-substituted text -- the helper
    only matches the literal uppercase token strings, so a second call
    on output that no longer contains those literals is a no-op.

    Lowercase variants like `{character_name}` are intentionally NOT
    substituted: the runtime contract is uppercase only (consistent
    with feature 010 step 001). Lowercase tokens in stored data are
    handled by the one-time source-data migration.
    """
    if ctx is None:
        return text
    return (
        text
        .replace("{CHARACTER_NAME}", ctx["character_name"])
        .replace("{LOCATION_NAME}", ctx["location_name"])
        .replace("{LOCATION_SUMMARY}", ctx["location_summary"])
    )
