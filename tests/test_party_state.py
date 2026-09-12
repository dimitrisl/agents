"""The DM writing a hero's hit points and conditions back to the database.

Until this endpoint existed the Live Party Tracker was a lie: damage and
conditions lived in one browser, the player saw nothing and a refresh threw the
session away. These lock in who may write, what may be written, and that the
table is told.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app

CAMPAIGN = "The Obsidian Citadel"
CHAR_ID = "hero_1"
URL = f"/api/v1/campaigns/{CAMPAIGN}/party/{CHAR_ID}/state"


def _character(**overrides):
    return {
        "char_id": CHAR_ID,
        "char_name": "Lyra Meadowlark",
        "hp_max": 25,
        "hp_current": 25,
        "conditions": [],
        "active_campaign": CAMPAIGN,
        **overrides,
    }


@pytest.fixture
def table(monkeypatch):
    """A campaign with one DM, one hero, and a socket nobody has to open."""
    broadcasts = []

    from server.routers import websocket_router

    async def _record(campaign_id, message, characters=None):
        broadcasts.append((campaign_id, message, characters))

    monkeypatch.setattr(websocket_router.manager, "broadcast", _record)

    state = {"character": _character(), "role": "dm"}

    chars = MagicMock()
    chars.find_one = AsyncMock(side_effect=lambda q: state["character"])
    chars.update_one = AsyncMock(return_value=MagicMock())

    members = MagicMock()
    members.find_one = AsyncMock(
        side_effect=lambda q: {"role": state["role"]} if state["role"] else None
    )

    app.dependency_overrides[get_database] = lambda: {
        "characters": chars,
        "campaign_members": members,
    }
    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_1", "username": "dm"}

    yield {
        "client": TestClient(app),
        "chars": chars,
        "state": state,
        "broadcasts": broadcasts,
    }

    app.dependency_overrides.clear()


def test_dm_can_write_hit_points(table):
    response = table["client"].patch(URL, json={"hp_current": 12})

    assert response.status_code == 200
    body = response.json()
    assert body["hp_current"] == 12
    assert body["char_name"] == "Lyra Meadowlark"

    _, update = table["chars"].update_one.await_args.args
    assert update == {"$set": {"hp_current": 12}}


def test_only_the_touched_field_is_written(table):
    """A hit-point edit must not blank the conditions set from the other tab."""
    table["client"].patch(URL, json={"hp_current": 12})

    _, update = table["chars"].update_one.await_args.args
    assert "conditions" not in update["$set"]


def test_hit_points_are_clamped_to_the_hero_s_own_range(table):
    assert table["client"].patch(URL, json={"hp_current": -40}).json()["hp_current"] == 0
    assert table["client"].patch(URL, json={"hp_current": 999}).json()["hp_current"] == 25


def test_conditions_are_deduplicated_and_trimmed(table):
    response = table["client"].patch(
        URL, json={"conditions": ["Poisoned", " poisoned ", "Prone", "  "]}
    )

    assert response.json()["conditions"] == ["Poisoned", "Prone"]


def test_the_table_is_told(table):
    table["client"].patch(URL, json={"hp_current": 3})

    assert len(table["broadcasts"]) == 1
    campaign_id, message, characters = table["broadcasts"][0]
    assert campaign_id == CAMPAIGN
    assert message["type"] == "party_update"
    assert message["payload"]["hp_current"] == 3
    # Untargeted: everyone at the table sees who is bloodied.
    assert characters is None


def test_a_player_may_not_write_the_party_s_state(table):
    table["state"]["role"] = "player"

    response = table["client"].patch(URL, json={"hp_current": 1})

    assert response.status_code == 403
    table["chars"].update_one.assert_not_awaited()


def test_a_non_member_is_refused(table):
    table["state"]["role"] = None

    assert table["client"].patch(URL, json={"hp_current": 1}).status_code == 403


def test_a_hero_from_another_table_is_refused(table):
    table["state"]["character"] = _character(active_campaign="Some Other Campaign")

    response = table["client"].patch(URL, json={"hp_current": 1})

    assert response.status_code == 403
    table["chars"].update_one.assert_not_awaited()


def test_a_missing_character_is_a_404(table):
    table["state"]["character"] = None

    assert table["client"].patch(URL, json={"hp_current": 1}).status_code == 404


def test_an_empty_payload_is_rejected(table):
    response = table["client"].patch(URL, json={})

    assert response.status_code == 400
    table["chars"].update_one.assert_not_awaited()
    assert table["broadcasts"] == []
