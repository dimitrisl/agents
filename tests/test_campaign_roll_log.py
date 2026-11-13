"""Tests for online Campaign Roll Log endpoint and WebSocket visibility isolation (#197).

Follows repo mongomock + TestClient pattern and verifies both 2014 Edition and
2024 Revision (5.5e) characters cleanly.
"""

from typing import Generator, List

import mongomock
import pytest
from fastapi.testclient import TestClient

from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter
from server.routers import websocket_router


class _AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._iter = None

    def __aiter__(self):
        self._iter = iter(list(self._cursor))
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self


class _AsyncCollection:
    def __init__(self, coll):
        self._coll = coll

    async def insert_one(self, *args, **kwargs):
        return self._coll.insert_one(*args, **kwargs)

    async def find_one(self, *args, **kwargs):
        return self._coll.find_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._coll.update_one(*args, **kwargs)

    async def update_many(self, *args, **kwargs):
        return self._coll.update_many(*args, **kwargs)

    async def delete_many(self, *args, **kwargs):
        return self._coll.delete_many(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._coll.delete_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._coll.count_documents(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursor(self._coll.find(*args, **kwargs))


class _AsyncDatabase:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name: str) -> _AsyncCollection:
        return _AsyncCollection(self._db[name])


CAMPAIGN = "Curse of Strahd"


@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def mock_db() -> _AsyncDatabase:
    client = mongomock.MongoClient()
    return _AsyncDatabase(client["phyrexian_forge_roll_log_test"])


@pytest.fixture
def auth_state():
    return {"user": {"id": "user_player_1", "username": "player1"}}


@pytest.fixture
def broadcasts(monkeypatch) -> List[dict]:
    recorded: List[dict] = []

    async def _record(campaign_id, message, characters=None, dm_only=False):
        recorded.append(
            {
                "campaign": campaign_id,
                "message": message,
                "characters": characters,
                "dm_only": dm_only,
            }
        )

    monkeypatch.setattr(websocket_router.manager, "broadcast", _record)
    return recorded


@pytest.fixture
def client(mock_db: _AsyncDatabase, auth_state: dict) -> Generator[TestClient, None, None]:
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: auth_state["user"]
    yield TestClient(app)
    app.dependency_overrides = original


def _seed_campaign(db: _AsyncDatabase, dnd_edition: str = "2014 Edition"):
    db["campaigns"]._coll.insert_one(
        {
            "campaign_name": CAMPAIGN,
            "owner_id": "user_dm",
            "dnd_edition": dnd_edition,
            "party": ["elara_c1.json", "kael_c2.json"],
        }
    )
    db["campaign_members"]._coll.insert_many(
        [
            {"campaign_id": CAMPAIGN, "user_id": "user_dm", "role": "dm", "character_id": None},
            {
                "campaign_id": CAMPAIGN,
                "user_id": "user_player_1",
                "role": "player",
                "character_id": "c1",
            },
            {
                "campaign_id": CAMPAIGN,
                "user_id": "user_player_2",
                "role": "player",
                "character_id": "c2",
            },
        ]
    )
    db["characters"]._coll.insert_many(
        [
            {
                "char_id": "c1",
                "char_name": "Elara",
                "owner_id": "user_player_1",
                "active_campaign": CAMPAIGN,
                "dnd_edition": dnd_edition,
            },
            {
                "char_id": "c2",
                "char_name": "Kael",
                "owner_id": "user_player_2",
                "active_campaign": CAMPAIGN,
                "dnd_edition": dnd_edition,
            },
        ]
    )


@pytest.mark.parametrize("edition", ["2014 Edition", "2024 Revision (5.5e)"])
def test_publish_public_sheet_roll_for_both_editions(
    client: TestClient, mock_db: _AsyncDatabase, broadcasts: List[dict], edition: str
):
    _seed_campaign(mock_db, dnd_edition=edition)

    res = client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/rolls",
        json={
            "char_name": "Elara",
            "roll_label": "Longsword Attack",
            "roll_type": "attack",
            "formula": "1d20+7",
            "natural_roll": 20,
            "rolls": [20],
            "modifier": 7,
            "total": 27,
            "mode": "normal",
            "is_crit": True,
            "is_fumble": False,
            "visibility": "public",
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    roll = body["roll"]
    assert roll["char_name"] == "Elara"
    assert roll["total"] == 27
    assert roll["is_crit"] is True
    assert roll["visibility"] == "public"
    assert roll["dnd_edition"] == edition

    assert len(broadcasts) == 1
    assert broadcasts[0]["dm_only"] is False
    assert broadcasts[0]["message"]["type"] == "campaign_roll"
    assert broadcasts[0]["message"]["payload"]["id"] == roll["id"]

    saved = mock_db["campaign_roll_logs"]._coll.find_one({"id": roll["id"]})
    assert saved is not None
    assert saved["dnd_edition"] == edition


def test_publish_dm_whisper_roll_broadcasts_dm_only(
    client: TestClient, mock_db: _AsyncDatabase, broadcasts: List[dict]
):
    _seed_campaign(mock_db, dnd_edition="2024 Revision (5.5e)")

    res = client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/rolls",
        json={
            "char_name": "Elara",
            "roll_label": "Stealth Check",
            "roll_type": "skill",
            "formula": "1d20+9",
            "natural_roll": 14,
            "rolls": [14],
            "modifier": 9,
            "total": 23,
            "visibility": "dm",
        },
    )

    assert res.status_code == 200
    assert res.json()["roll"]["visibility"] == "dm"
    assert len(broadcasts) == 1
    assert broadcasts[0]["dm_only"] is True
    assert broadcasts[0]["message"]["type"] == "campaign_roll"


def test_player_cannot_spoof_other_character_or_non_member(
    client: TestClient, mock_db: _AsyncDatabase, auth_state: dict
):
    _seed_campaign(mock_db)

    spoof_res = client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/rolls",
        json={
            "char_name": "Kael",
            "roll_label": "Athletics Check",
            "roll_type": "skill",
            "formula": "1d20+5",
            "total": 18,
            "visibility": "public",
        },
    )
    assert spoof_res.status_code == 403

    auth_state["user"] = {"id": "outsider_99", "username": "stranger"}
    outsider_res = client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/rolls",
        json={
            "char_name": "Elara",
            "roll_label": "Perception Check",
            "roll_type": "skill",
            "formula": "1d20+3",
            "total": 12,
            "visibility": "public",
        },
    )
    assert outsider_res.status_code == 403


def test_messages_history_redacts_other_players_dm_rolls(
    client: TestClient, mock_db: _AsyncDatabase, auth_state: dict
):
    _seed_campaign(mock_db, dnd_edition="2024 Revision (5.5e)")

    # Player 1 throws one public and one DM-only roll
    client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/rolls",
        json={
            "char_name": "Elara",
            "roll_label": "Perception",
            "roll_type": "skill",
            "formula": "1d20+4",
            "total": 15,
            "visibility": "public",
        },
    )
    client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/rolls",
        json={
            "char_name": "Elara",
            "roll_label": "Sleight of Hand",
            "roll_type": "skill",
            "formula": "1d20+8",
            "total": 22,
            "visibility": "dm",
        },
    )

    # Player 2 should see public roll, NOT Player 1's DM roll
    auth_state["user"] = {"id": "user_player_2", "username": "player2"}
    p2_msgs = client.get(f"/api/v1/campaigns/{CAMPAIGN}/messages").json()
    p2_labels = [r["roll_label"] for r in p2_msgs["roll_logs"]]
    assert p2_labels == ["Perception"]

    # Player 1 sees both (including their own DM roll)
    auth_state["user"] = {"id": "user_player_1", "username": "player1"}
    p1_msgs = client.get(f"/api/v1/campaigns/{CAMPAIGN}/messages").json()
    p1_labels = [r["roll_label"] for r in p1_msgs["roll_logs"]]
    assert set(p1_labels) == {"Perception", "Sleight of Hand"}

    # DM sees both
    auth_state["user"] = {"id": "user_dm", "username": "dm"}
    dm_msgs = client.get(f"/api/v1/campaigns/{CAMPAIGN}/messages").json()
    dm_labels = [r["roll_label"] for r in dm_msgs["roll_logs"]]
    assert set(dm_labels) == {"Perception", "Sleight of Hand"}


def test_websocket_dm_only_roll_isolation_for_live_sockets(
    client: TestClient, mock_db: _AsyncDatabase, monkeypatch: pytest.MonkeyPatch
):
    async def fake_token(token: str):
        return {"id": token}

    async def fake_ws_db():
        return mock_db

    monkeypatch.setattr(websocket_router, "get_current_user_from_token", fake_token)
    monkeypatch.setattr(websocket_router, "get_database", fake_ws_db)
    websocket_router.manager.active_connections.clear()

    _seed_campaign(mock_db, dnd_edition="2024 Revision (5.5e)")

    with client.websocket_connect(f"/ws/campaigns/{CAMPAIGN}") as dm_ws:
        dm_ws.send_json({"type": "auth", "token": "user_dm"})
        dm_ws.receive_json()  # presence_sync

        with client.websocket_connect(f"/ws/campaigns/{CAMPAIGN}") as p2_ws:
            p2_ws.send_json({"type": "auth", "token": "user_player_2", "character": "Kael"})
            p2_ws.receive_json()  # presence_sync
            p2_ws.receive_json()  # presence_update for Kael online
            dm_ws.receive_json()  # presence_update for Kael online

            res = client.post(
                f"/api/v1/campaigns/{CAMPAIGN}/rolls",
                json={
                    "char_name": "elara",
                    "roll_label": "Secret Perception",
                    "roll_type": "skill",
                    "formula": "1d20+6",
                    "natural_roll": 19,
                    "rolls": [19],
                    "modifier": 6,
                    "total": 25,
                    "visibility": "dm",
                },
            )
            assert res.status_code == 200
            # Canonical casing from character doc preserved
            assert res.json()["roll"]["char_name"] == "Elara"

            dm_msg = dm_ws.receive_json()
            assert dm_msg["type"] == "campaign_roll"
            assert dm_msg["payload"]["visibility"] == "dm"
            assert dm_msg["payload"]["total"] == 25

            # Confirm P2 socket did NOT receive the dm-only frame (heartbeat still works cleanly)
            p2_ws.send_json({"type": "ping"})
            assert p2_ws.receive_json() == {"type": "pong"}


@pytest.mark.parametrize("edition", ["2014 Edition", "2024 Revision (5.5e)"])
def test_player_with_two_characters_rolls_and_whispers_disambiguated(
    client: TestClient, mock_db: _AsyncDatabase, auth_state: dict, edition: str
):
    """A single user controlling two characters in the same campaign (even with matching names)
    routes rolls and whispers by char_id while keeping sender_username & char_name intact."""
    mock_db["campaigns"]._coll.insert_one(
        {
            "campaign_name": CAMPAIGN,
            "owner_id": "user_dm",
            "invite_code": "DUAL99",
            "dnd_edition": edition,
            "party": ["lyra_c_main.json"],
        }
    )
    mock_db["campaign_members"]._coll.insert_many(
        [
            {"campaign_id": CAMPAIGN, "user_id": "user_dm", "role": "dm", "character_id": None},
            {
                "campaign_id": CAMPAIGN,
                "user_id": "user_player_1",
                "role": "player",
                "character_id": "c_main",
                "character_ids": ["c_main"],
            },
        ]
    )
    mock_db["characters"]._coll.insert_many(
        [
            {
                "char_id": "c_main",
                "char_name": "Lyra",
                "owner_id": "user_player_1",
                "active_campaign": CAMPAIGN,
                "dnd_edition": edition,
            },
            {
                "char_id": "c_alt",
                "char_name": "Lyra",
                "owner_id": "user_player_1",
                "dnd_edition": edition,
            },
        ]
    )

    auth_state["user"] = {"id": "user_player_1", "username": "player1"}
    join_res = client.post(
        "/api/v1/campaigns/join",
        json={"invite_code": "DUAL99", "character_id": "c_alt"},
    )
    assert join_res.status_code == 200

    # Joining again with the already-enrolled character must return 409
    dup_res = client.post(
        "/api/v1/campaigns/join",
        json={"invite_code": "DUAL99", "character_id": "c_alt"},
    )
    assert dup_res.status_code == 409

    # Roll from second character explicitly via char_id
    roll_res = client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/rolls",
        json={
            "char_id": "c_alt",
            "char_name": "Lyra",
            "roll_label": "Stealth Check",
            "roll_type": "skill",
            "formula": "1d20+6",
            "total": 19,
            "visibility": "public",
        },
    )
    assert roll_res.status_code == 200
    roll = roll_res.json()["roll"]
    assert roll["char_id"] == "c_alt"
    assert roll["char_name"] == "Lyra"
    assert roll["sender_username"] == "player1"
    assert roll["dnd_edition"] == edition

    # Whisper as second character explicitly via sender_character_id
    whisper_res = client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/whisper",
        json={"recipient": "DM", "message": "Scouting ahead.", "sender_character_id": "c_alt"},
    )
    assert whisper_res.status_code == 200
    whisper = whisper_res.json()["whisper"]
    assert whisper["sender"] == "Lyra"
    assert whisper["sender_username"] == "player1"
    assert whisper["sender_character_id"] == "c_alt"


def test_same_character_name_two_players_isolation_and_username_labels(
    client: TestClient, mock_db: _AsyncDatabase, auth_state: dict
):
    """Two different players with identically named characters ('Thorin') must never
    cross-read private whispers, and roll logs preserve char_id + sender_username."""
    mock_db["campaigns"]._coll.insert_one(
        {
            "campaign_name": CAMPAIGN,
            "owner_id": "user_dm",
            "dnd_edition": "2024 Revision (5.5e)",
            "party": ["thorin_t1.json", "thorin_t2.json"],
        }
    )
    mock_db["campaign_members"]._coll.insert_many(
        [
            {"campaign_id": CAMPAIGN, "user_id": "user_dm", "role": "dm", "character_id": None},
            {
                "campaign_id": CAMPAIGN,
                "user_id": "user_p1",
                "role": "player",
                "character_id": "t1",
                "character_ids": ["t1"],
            },
            {
                "campaign_id": CAMPAIGN,
                "user_id": "user_p2",
                "role": "player",
                "character_id": "t2",
                "character_ids": ["t2"],
            },
        ]
    )
    mock_db["users"]._coll.insert_many(
        [
            {"id": "user_dm", "username": "dm"},
            {"id": "user_p1", "username": "alice"},
            {"id": "user_p2", "username": "bob"},
        ]
    )
    mock_db["characters"]._coll.insert_many(
        [
            {
                "char_id": "t1",
                "char_name": "Thorin",
                "owner_id": "user_p1",
                "active_campaign": CAMPAIGN,
            },
            {
                "char_id": "t2",
                "char_name": "Thorin",
                "owner_id": "user_p2",
                "active_campaign": CAMPAIGN,
            },
        ]
    )

    # Alice throws with t1
    auth_state["user"] = {"id": "user_p1", "username": "alice"}
    r1 = client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/rolls",
        json={
            "char_id": "t1",
            "char_name": "Thorin",
            "roll_label": "Athletics",
            "roll_type": "skill",
            "formula": "1d20+5",
            "total": 21,
            "visibility": "public",
        },
    )
    assert r1.status_code == 200
    assert r1.json()["roll"]["char_id"] == "t1"
    assert r1.json()["roll"]["sender_username"] == "alice"

    # Alice CANNOT spoof Bob's char_id t2
    spoof = client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/rolls",
        json={
            "char_id": "t2",
            "char_name": "Thorin",
            "roll_label": "Deception",
            "roll_type": "skill",
            "formula": "1d20",
            "total": 10,
            "visibility": "public",
        },
    )
    assert spoof.status_code == 403

    # DM sends a private whisper specifically to Bob's Thorin (t2)
    auth_state["user"] = {"id": "user_dm", "username": "dm"}
    w_res = client.post(
        f"/api/v1/campaigns/{CAMPAIGN}/whisper",
        json={
            "recipient": "Thorin",
            "recipient_character_id": "t2",
            "message": "Bob-only secret clue",
        },
    )
    assert w_res.status_code == 200
    assert w_res.json()["whisper"]["recipient_user_id"] == "user_p2"
    assert w_res.json()["whisper"]["recipient_character_id"] == "t2"

    # Alice's /messages must NOT leak Bob's private whisper even though both are named 'Thorin'
    auth_state["user"] = {"id": "user_p1", "username": "alice"}
    alice_msgs = client.get(f"/api/v1/campaigns/{CAMPAIGN}/messages").json()
    assert [w["message"] for w in alice_msgs["whispers"]] == []

    # Bob's /messages DOES see it
    auth_state["user"] = {"id": "user_p2", "username": "bob"}
    bob_msgs = client.get(f"/api/v1/campaigns/{CAMPAIGN}/messages").json()
    assert [w["message"] for w in bob_msgs["whispers"]] == ["Bob-only secret clue"]


def test_websocket_roll_request_reaches_owner_on_alt_char_and_never_homonym_peer(
    client: TestClient, mock_db: _AsyncDatabase, auth_state: dict, monkeypatch: pytest.MonkeyPatch
):
    """Targeted roll_request delivered via user_ids wakes the player even while viewing their
    other hero, and never leaks to a different player sharing the target hero's char_name."""

    async def fake_token(token: str):
        return {"id": token}

    async def fake_ws_db():
        return mock_db

    monkeypatch.setattr(websocket_router, "get_current_user_from_token", fake_token)
    monkeypatch.setattr(websocket_router, "get_database", fake_ws_db)
    websocket_router.manager.active_connections.clear()

    mock_db["campaigns"]._coll.insert_one(
        {
            "campaign_name": CAMPAIGN,
            "owner_id": "user_dm",
            "party": ["thorin_t1.json", "aria_t_alt.json", "thorin_t2.json"],
        }
    )
    mock_db["campaign_members"]._coll.insert_many(
        [
            {"campaign_id": CAMPAIGN, "user_id": "user_dm", "role": "dm", "character_id": None},
            {
                "campaign_id": CAMPAIGN,
                "user_id": "user_p1",
                "role": "player",
                "character_id": "t1",
                "character_ids": ["t1", "t_alt"],
            },
            {
                "campaign_id": CAMPAIGN,
                "user_id": "user_p2",
                "role": "player",
                "character_id": "t2",
                "character_ids": ["t2"],
            },
        ]
    )
    mock_db["characters"]._coll.insert_many(
        [
            {
                "char_id": "t1",
                "char_name": "Thorin",
                "owner_id": "user_p1",
                "active_campaign": CAMPAIGN,
            },
            {
                "char_id": "t_alt",
                "char_name": "Aria",
                "owner_id": "user_p1",
                "active_campaign": CAMPAIGN,
            },
            {
                "char_id": "t2",
                "char_name": "Thorin",
                "owner_id": "user_p2",
                "active_campaign": CAMPAIGN,
            },
        ]
    )

    with client.websocket_connect(f"/ws/campaigns/{CAMPAIGN}") as p1_ws:
        # Player 1 is currently active on their 2nd character 'Aria'
        p1_ws.send_json({"type": "auth", "token": "user_p1", "character": "Aria"})
        p1_ws.receive_json()  # presence_sync
        p1_ws.receive_json()  # presence_update Aria online

        with client.websocket_connect(f"/ws/campaigns/{CAMPAIGN}") as p2_ws:
            # Player 2 has homonym 'Thorin'
            p2_ws.send_json({"type": "auth", "token": "user_p2", "character": "Thorin"})
            p2_ws.receive_json()  # presence_sync
            p2_ws.receive_json()  # presence_update Thorin online
            p1_ws.receive_json()  # presence_update Thorin online

            # DM requests a roll specifically for Player 1's Thorin (t1)
            auth_state["user"] = {"id": "user_dm", "username": "dm"}
            req_res = client.post(
                f"/api/v1/campaigns/{CAMPAIGN}/roll-request",
                json={
                    "char_filename": "thorin_t1.json",
                    "char_name": "Thorin",
                    "target_char_id": "t1",
                    "roll_type": "saving_throw",
                    "stat": "DEX",
                    "reason": "Pit Trap",
                },
            )
            assert req_res.status_code == 200
            assert req_res.json()["request"]["target_char_id"] == "t1"

            # Player 1 receives the roll_request even while on Aria's sheet
            p1_msg = p1_ws.receive_json()
            assert p1_msg["type"] == "roll_request"
            assert p1_msg["payload"]["target_char_id"] == "t1"
            assert p1_msg["payload"]["char_name"] == "Thorin"

            # Player 2 (homonym 'Thorin') does NOT receive it
            p2_ws.send_json({"type": "ping"})
            assert p2_ws.receive_json() == {"type": "pong"}
