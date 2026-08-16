"""Delivery rules for the live campaign channel.

These lock in who is allowed to see what: a whisper meant for one hero must not
travel down another player's socket, and a client must never be able to publish
into the room by hand.
"""

from typing import List, Optional

import pytest
from fastapi import Body, FastAPI
from fastapi.testclient import TestClient

from server.routers import websocket_router

CAMPAIGN = "The Obsidian Citadel"


async def _accept_any_token(token):
    return {"id": token}


class AsyncMockCursor:
    def __init__(self, token):
        self.token = token

    async def find_one(self, query):
        if self.token == "dm":
            return {"role": "dm"}
        return {"role": "player"}


class MockDB:
    def __getitem__(self, item):
        # We need the token to know what role to return.
        # A hack is to just return a cursor that magically knows, but how?
        # Actually, let's just make find_one return what we want.
        pass


async def _mock_get_database():
    class DBCollectionMock:
        async def find_one(self, query):
            # We encoded the user id in the token which becomes the user_id in the query!
            user_id = query.get("user_id", "player")
            if user_id.startswith("dm"):
                return {"role": "dm"}
            return {"role": "player"}

    class DBMock:
        def __getitem__(self, name):
            return DBCollectionMock()

    return DBMock()


@pytest.fixture
def channel(monkeypatch):
    """An app with only the WebSocket channel mounted — no database needed."""
    monkeypatch.setattr(websocket_router, "get_current_user_from_token", _accept_any_token)
    monkeypatch.setattr(websocket_router, "get_database", _mock_get_database)

    app = FastAPI()
    app.include_router(websocket_router.router)

    @app.post("/publish")
    async def publish(  # stands in for the REST endpoints that really publish
        message: dict = Body(...), characters: Optional[List[str]] = Body(None)
    ):
        await websocket_router.manager.broadcast(CAMPAIGN, message, characters=characters)
        return {"ok": True}

    with TestClient(app) as client:
        yield client

    websocket_router.manager.active_connections.clear()


def socket_url(role: str, character: Optional[str] = None) -> str:
    # Use the role as the token so the mock DB knows who this is
    url = f"/ws/campaigns/{CAMPAIGN.replace(' ', '%20')}?token={role}&role={role}"
    return url + (f"&character={character}" if character else "")


def assert_silent(socket, who: str):
    """A socket is silent when the next frame it sees is its own pong."""
    socket.send_json({"type": "ping"})
    received = socket.receive_json()
    assert received == {"type": "pong"}, f"{who} received traffic it should not see: {received}"


def test_heartbeat_is_answered_privately(channel):
    with channel.websocket_connect(socket_url("player", "Valeros")) as valeros:
        assert_silent(valeros, "Valeros")


def test_client_cannot_publish_into_the_room(channel):
    with (
        channel.websocket_connect(socket_url("dm")) as dm,
        channel.websocket_connect(socket_url("player", "Ezren")) as ezren,
    ):
        ezren.send_json({"type": "whisper", "payload": {"sender": "DM", "message": "forged"}})
        assert_silent(ezren, "Ezren")
        assert_silent(dm, "DM")


def test_private_whisper_reaches_only_recipient_and_dm(channel):
    with (
        channel.websocket_connect(socket_url("dm")) as dm,
        channel.websocket_connect(socket_url("player", "Valeros")) as valeros,
        channel.websocket_connect(socket_url("player", "Ezren")) as ezren,
    ):
        channel.post(
            "/publish",
            json={"message": {"type": "whisper", "id": "w1"}, "characters": ["Valeros", "DM"]},
        )

        assert valeros.receive_json()["id"] == "w1"
        assert dm.receive_json()["id"] == "w1"
        assert_silent(ezren, "Ezren")


def test_roll_request_and_result_reach_the_hero_and_the_dm(channel):
    with (
        channel.websocket_connect(socket_url("dm")) as dm,
        channel.websocket_connect(socket_url("player", "Valeros")) as valeros,
        channel.websocket_connect(socket_url("player", "Ezren")) as ezren,
    ):
        channel.post(
            "/publish",
            json={"message": {"type": "roll_request", "id": "r1"}, "characters": ["Valeros"]},
        )
        assert valeros.receive_json()["id"] == "r1"
        assert dm.receive_json()["id"] == "r1"

        channel.post(
            "/publish",
            json={"message": {"type": "roll_result", "id": "r1"}, "characters": ["Valeros"]},
        )
        assert valeros.receive_json()["id"] == "r1"
        assert dm.receive_json()["id"] == "r1"

        assert_silent(ezren, "Ezren")


def test_table_wide_whisper_reaches_everyone(channel):
    with (
        channel.websocket_connect(socket_url("dm")) as dm,
        channel.websocket_connect(socket_url("player", "Valeros")) as valeros,
        channel.websocket_connect(socket_url("player", "Ezren")) as ezren,
    ):
        channel.post("/publish", json={"message": {"type": "whisper", "id": "all"}})

        for who, socket in (("dm", dm), ("valeros", valeros), ("ezren", ezren)):
            assert socket.receive_json()["id"] == "all", who


def test_character_matching_ignores_case_and_padding(channel):
    with channel.websocket_connect(socket_url("player", "Valeros")) as valeros:
        channel.post(
            "/publish",
            json={"message": {"type": "whisper", "id": "w2"}, "characters": ["  valeros "]},
        )
        assert valeros.receive_json()["id"] == "w2"


def test_disconnect_empties_the_room(channel):
    with channel.websocket_connect(socket_url("player", "Valeros")):
        assert websocket_router.manager.active_connections[CAMPAIGN]

    assert CAMPAIGN not in websocket_router.manager.active_connections
