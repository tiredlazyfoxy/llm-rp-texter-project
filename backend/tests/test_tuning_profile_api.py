"""Profile API transport tests for feature 014 (chat_preference_tuning) step 005.

Bound to the frozen step-005 skeleton (``## Skeleton`` in status.md):

- ``GET  /api/chats/tuning-profile/{world_id}`` →
  ``get_tuning_profile(world_id: str, caller=Depends(_require_player)) ->
  TuningProfileResponse`` — calls ``tuning_service.get_profile(caller.id,
  int(world_id))``.
- ``PUT  /api/chats/tuning-profile/{world_id}`` →
  ``update_tuning_profile(world_id: str, req: UpdateTuningProfileRequest,
  caller=Depends(_require_player)) -> TuningProfileResponse`` — calls
  ``tuning_service.update_profile(caller.id, int(world_id), req)``.

The endpoints are reached through the real FastAPI app (``http_client`` fixture)
with an authenticated player caller (``player_user`` fixture). Profiles are
seeded directly via ``db/tuning_profiles`` where a pre-existing row is required.

Response/request JSON shapes come from the step-001 Pydantic schemas as mirrored
by the frozen frontend DTOs in the skeleton record:
- response: ``{id: str, world_id: str, plan_tuning: str, tone_tuning: str}``
  (ids serialize as strings — project convention).
- update request: ``{plan_tuning: str, tone_tuning: str}``.

Expected values come from the step spec (Definition of done + Interface intent)
only — never from the implementation. The ``tuning_service`` stub bodies raise
``NotImplementedError`` (per the skeleton contract notes), so the GET/PUT
endpoints fail until the coder implements ``get_profile`` / ``update_profile``;
these tests assert the spec-correct behavior and (correctly) fail red until then.

FK enforcement is off in the test SQLite DB, so an arbitrary snowflake world id
needs no backing ``World`` row (the service keys only on ``(user_id, world_id)``).
"""

from datetime import datetime, timezone

import pytest

from app.db import tuning_profiles as profiles_db
from app.models.chat_tuning_profile import ChatTuningProfile
from app.models.user import User
from app.services.snowflake import generate_id


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _seed_profile(
    user_id: int,
    world_id: int,
    *,
    plan_tuning: str,
    tone_tuning: str,
) -> int:
    """Seed a stored profile row for the (user, world) pair. Returns its id."""
    now = _now()
    profile = ChatTuningProfile(
        id=generate_id(),
        user_id=user_id,
        world_id=world_id,
        plan_tuning=plan_tuning,
        tone_tuning=tone_tuning,
        created_at=now,
        modified_at=now,
    )
    await profiles_db.upsert(profile)
    return profile.id


# ===========================================================================
# DoD-1 — GET returns empty-string defaults when no row exists, and the
#         stored values when a row is present.
# ===========================================================================


async def test_get_returns_empty_defaults_when_no_row__DoD1(
    http_client, player_user: tuple[User, str],
) -> None:
    # DoD-1: with no profile row for the (current user, world), GET returns a
    # profile whose plan_tuning / tone_tuning are the empty-string defaults; the
    # world id echoes as a string and the id serializes as a string.
    player, token = player_user
    world_id = generate_id()
    # No seeding — the pair has no stored row.

    resp = await http_client.get(
        f"/api/chats/tuning-profile/{world_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan_tuning"] == ""  # empty-string default
    assert body["tone_tuning"] == ""  # empty-string default
    assert body["world_id"] == str(world_id)
    assert isinstance(body["id"], str)  # ids serialize as strings


async def test_get_returns_stored_values_when_row_present__DoD1(
    http_client, player_user: tuple[User, str],
) -> None:
    # DoD-1: when a row exists for the (current user, world), GET returns its
    # stored plan_tuning / tone_tuning (and the stored id, as a string).
    player, token = player_user
    world_id = generate_id()
    seeded_id = await _seed_profile(
        player.id, world_id, plan_tuning="be concise", tone_tuning="be warm"
    )

    resp = await http_client.get(
        f"/api/chats/tuning-profile/{world_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan_tuning"] == "be concise"
    assert body["tone_tuning"] == "be warm"
    assert body["world_id"] == str(world_id)
    assert body["id"] == str(seeded_id)  # stored id, serialized as a string


# ===========================================================================
# DoD-2 — PUT replaces plan_tuning / tone_tuning, persists, and a subsequent
#         GET returns the new values; id serializes as a string.
# ===========================================================================


async def test_put_replaces_persists_and_get_reflects__DoD2(
    http_client, player_user: tuple[User, str],
) -> None:
    # DoD-2: PUT with new plan_tuning / tone_tuning returns those values (id as a
    # string); the values persist (db layer) and a subsequent GET returns them.
    player, token = player_user
    world_id = generate_id()

    put_resp = await http_client.put(
        f"/api/chats/tuning-profile/{world_id}",
        json={"plan_tuning": "plan v1", "tone_tuning": "tone v1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert put_resp.status_code == 200, put_resp.text
    put_body = put_resp.json()
    assert put_body["plan_tuning"] == "plan v1"
    assert put_body["tone_tuning"] == "tone v1"
    assert put_body["world_id"] == str(world_id)
    assert isinstance(put_body["id"], str)  # id serializes as a string

    # Persisted in the data layer under the (current user, world) pair.
    stored = await profiles_db.get(player.id, world_id)
    assert stored is not None
    assert stored.plan_tuning == "plan v1"
    assert stored.tone_tuning == "tone v1"

    # A subsequent GET returns the new values (and the same id).
    get_resp = await http_client.get(
        f"/api/chats/tuning-profile/{world_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200, get_resp.text
    get_body = get_resp.json()
    assert get_body["plan_tuning"] == "plan v1"
    assert get_body["tone_tuning"] == "tone v1"
    assert get_body["id"] == put_body["id"]


# ===========================================================================
# DoD-3 — a second PUT updates in place (no duplicate profile row for the
#         same user+world).
# ===========================================================================


async def test_second_put_updates_in_place_no_duplicate__DoD3(
    http_client, player_user: tuple[User, str],
) -> None:
    # DoD-3: a second PUT for the same (user, world) updates in place — same
    # profile id (no id churn / duplicate row), and GET + the db layer reflect
    # the second PUT's values.
    player, token = player_user
    world_id = generate_id()

    first = await http_client.put(
        f"/api/chats/tuning-profile/{world_id}",
        json={"plan_tuning": "plan v1", "tone_tuning": "tone v1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200, first.text
    first_id = first.json()["id"]

    second = await http_client.put(
        f"/api/chats/tuning-profile/{world_id}",
        json={"plan_tuning": "plan v2", "tone_tuning": "tone v2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second.status_code == 200, second.text
    second_body = second.json()

    # Same id across both PUTs => updated in place, not a new/duplicate row.
    assert second_body["id"] == first_id
    assert second_body["plan_tuning"] == "plan v2"
    assert second_body["tone_tuning"] == "tone v2"

    # The single stored row reflects the second PUT (same id, new values).
    stored = await profiles_db.get(player.id, world_id)
    assert stored is not None
    assert str(stored.id) == first_id
    assert stored.plan_tuning == "plan v2"
    assert stored.tone_tuning == "tone v2"

    # A subsequent GET returns the second PUT's values under the same id.
    get_resp = await http_client.get(
        f"/api/chats/tuning-profile/{world_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200, get_resp.text
    get_body = get_resp.json()
    assert get_body["id"] == first_id
    assert get_body["plan_tuning"] == "plan v2"
    assert get_body["tone_tuning"] == "tone v2"
