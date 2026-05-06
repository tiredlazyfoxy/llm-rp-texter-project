"""Pydantic-level tests for the `character_name` validator on
`CreateChatRequest` and `UpdateChatSettingsRequest`.

The validator must:
- reject empty / whitespace-only inputs (raise ValidationError);
- trim leading/trailing whitespace and persist the trimmed value;
- accept ``None`` on the optional update field.
"""

import pytest
from pydantic import ValidationError

from app.models.schemas.chat import (
    CreateChatRequest,
    ModelConfig,
    UpdateChatSettingsRequest,
)


def _create_payload(character_name: str) -> dict[str, object]:
    return {
        "world_id": "1",
        "character_name": character_name,
        "template_variables": {},
        "starting_location_id": "2",
        "tool_model": ModelConfig().model_dump(),
        "text_model": ModelConfig().model_dump(),
    }


# ---------------------------------------------------------------------------
# CreateChatRequest
# ---------------------------------------------------------------------------


def test_create_request_rejects_empty_character_name() -> None:
    with pytest.raises(ValidationError):
        CreateChatRequest(**_create_payload(""))


@pytest.mark.parametrize("value", ["   ", "\t", "\n", " \t \n "])
def test_create_request_rejects_whitespace_only_character_name(value: str) -> None:
    with pytest.raises(ValidationError):
        CreateChatRequest(**_create_payload(value))


def test_create_request_trims_character_name() -> None:
    req = CreateChatRequest(**_create_payload("  Aria  "))
    assert req.character_name == "Aria"


def test_create_request_accepts_non_empty_character_name() -> None:
    req = CreateChatRequest(**_create_payload("Aria"))
    assert req.character_name == "Aria"


# ---------------------------------------------------------------------------
# UpdateChatSettingsRequest
# ---------------------------------------------------------------------------


def test_update_request_accepts_none_character_name() -> None:
    req = UpdateChatSettingsRequest()
    assert req.character_name is None


def test_update_request_accepts_explicit_none_character_name() -> None:
    req = UpdateChatSettingsRequest(character_name=None)
    assert req.character_name is None


def test_update_request_rejects_empty_character_name() -> None:
    with pytest.raises(ValidationError):
        UpdateChatSettingsRequest(character_name="")


@pytest.mark.parametrize("value", ["   ", "\t", "\n", " \t \n "])
def test_update_request_rejects_whitespace_only_character_name(value: str) -> None:
    with pytest.raises(ValidationError):
        UpdateChatSettingsRequest(character_name=value)


def test_update_request_trims_character_name() -> None:
    req = UpdateChatSettingsRequest(character_name="  Bob  ")
    assert req.character_name == "Bob"


def test_update_request_accepts_non_empty_character_name() -> None:
    req = UpdateChatSettingsRequest(character_name="Bob")
    assert req.character_name == "Bob"
