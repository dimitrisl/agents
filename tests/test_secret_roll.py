"""A secret roll: the DM rolls against the hero's sheet and the hero is never told.

Asking a player to roll is already telling them something happened. So a secret
roll is not "a request with a padlock on it" — it is thrown server-side, and every
path that could leak it back to the player has to stay shut: the socket, and the
history their client replays on every reconnect.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app

CAMPAIGN = "The Obsidian Citadel"
ROLL_URL = f"/api/v1/campaigns/{CAMPAIGN}/roll-request"
MESSAGES_URL = f"/api/v1/campaigns/{CAMPAIGN}/messages"

HERO = {
    "char_id": "hero1",
    "char_name": "Lyra Meadowlark",
    "active_campaign": CAMPAIGN,
    "proficiency_bonus": 3,
    "stats": {"STR": 10, "DEX": 18, "CON": 14, "INT": 12, "WIS": 16, "CHA": 8},
    "saving_throws": ["DEX"],
    "skill_proficiencies": ["Perception"],
}


def _ask(**overrides):
    return {
        "char_filename": "lyra_hero1.json",
        "char_name": "Lyra Meadowlark",
        "roll_type": "ability_check",
        "stat": "WIS",
        "reason": "Something moves in the dark",
        "is_secret": True,
        **overrides,
    }


@pytest.fixture
def table(monkeypatch):
    broadcasts = []

    from server.routers import websocket_router

    async def _record(campaign_id, message, characters=None, dm_only=False):
        broadcasts.append(
            {
                "campaign": campaign_id,
                "message": message,
                "characters": characters,
                "dm_only": dm_only,
            }
        )

    monkeypatch.setattr(websocket_router.manager, "broadcast", _record)

    state = {
        "campaign": {"campaign_name": CAMPAIGN, "roll_requests": [], "whispers": []},
        "role": "dm",
        "character": dict(HERO),
    }

    campaigns = MagicMock()
    campaigns.find_one = AsyncMock(side_effect=lambda q: state["campaign"])
    campaigns.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    campaigns.update_many = AsyncMock(return_value=MagicMock(modified_count=0))

    characters = MagicMock()
    characters.find_one = AsyncMock(side_effect=lambda q: state["character"])

    members = MagicMock()
    members.find_one = AsyncMock(
        side_effect=lambda q: {"role": state["role"]} if state["role"] else None
    )

    class AsyncIterator:
        def __init__(self, items):
            self.items = list(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.items:
                raise StopAsyncIteration
            return self.items.pop(0)

    class MockCollection:
        def __init__(self, state_dict, key):
            self.state = state_dict
            self.key = key

        def _get_data(self):
            campaign = self.state.get("campaign", {})
            raw_list = campaign.get(self.key, [])
            data = []
            for d in raw_list:
                # Inject campaign_name if missing, so it behaves like the real collection
                if "campaign_name" not in d:
                    d["campaign_name"] = campaign.get("campaign_name", "The Obsidian Citadel")
                if "_id" not in d:
                    d["_id"] = f"mock_{d.get('id', 'new')}"
                data.append(d)
            return data

        async def find_one(self, query):
            for item in self._get_data():
                match = True
                for k, v in query.items():
                    if item.get(k) != v:
                        match = False
                        break
                if match:
                    return item
            return None

        def find(self, query):
            results = []
            for item in self._get_data():
                match = True
                for k, v in query.items():
                    if item.get(k) != v:
                        match = False
                        break
                if match:
                    results.append(item.copy())
            return AsyncIterator(results)

        async def insert_one(self, doc):
            # Tests don't usually assert on inserted docs directly via this mock,
            # but if they do, we'll just ignore it or append it
            return MagicMock(inserted_id="mock_id")

        async def update_one(self, query, update, upsert=False):
            doc = await self.find_one(query)
            if doc:
                return MagicMock(modified_count=self.state.get("modified", 1))
            return MagicMock(modified_count=0)

        async def update_many(self, query, update):
            return MagicMock(modified_count=self.state.get("modified", 1))

        async def delete_one(self, query):
            return MagicMock(deleted_count=1)

    whispers = MockCollection(state, "whispers")
    roll_requests = MockCollection(state, "roll_requests")

    db_dict = {
        "campaigns": campaigns,
        "campaign_members": members,
        "characters": characters,
        "campaign_whispers": whispers,
        "campaign_roll_requests": roll_requests,
    }
    app.dependency_overrides[get_database] = lambda: db_dict

    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_1", "username": "dm"}

    yield {
        "client": TestClient(app),
        "campaigns": campaigns,
        "state": state,
        "broadcasts": broadcasts,
    }

    app.dependency_overrides.clear()


class TestTheRollItself:
    def test_it_is_already_rolled_when_the_dm_asks_for_it(self, table):
        response = table["client"].post(ROLL_URL, json=_ask())

        assert response.status_code == 200
        request = response.json()["request"]
        assert request["status"] == "resolved"
        assert request["rolled_by"] == "dm"
        assert request["result"]["total"] == request["result"]["raw"] + 3

    def test_it_uses_the_hero_s_own_modifier(self, table):
        """WIS 16 is +3, and the hero never had to be asked what it was."""
        result = table["client"].post(ROLL_URL, json=_ask()).json()["request"]["result"]

        assert result["modifier"] == 3
        assert result["expression"].endswith("+3")

    def test_a_save_picks_up_proficiency(self, table):
        """DEX 18 (+4) with a proficient DEX save (+3)."""
        body = _ask(roll_type="saving_throw", stat="DEX")

        result = table["client"].post(ROLL_URL, json=body).json()["request"]["result"]

        assert result["modifier"] == 7

    def test_a_hero_with_no_sheet_still_gets_a_roll(self, table):
        """Mid-scene is the wrong moment to refuse the DM a d20."""
        table["state"]["character"] = None

        result = table["client"].post(ROLL_URL, json=_ask()).json()["request"]["result"]

        assert result["modifier"] == 0
        assert 1 <= result["raw"] <= 20

    def test_it_does_not_cancel_a_roll_the_player_is_answering(self, table):
        """The hero knows nothing about this one, so it must not disturb their prompt."""
        table["client"].post(ROLL_URL, json=_ask())

        table["campaigns"].update_many.assert_not_awaited()


class TestNothingReachesThePlayer:
    def test_the_socket_message_is_dm_only(self, table):
        table["client"].post(ROLL_URL, json=_ask())

        assert len(table["broadcasts"]) == 1
        sent = table["broadcasts"][0]
        assert sent["dm_only"] is True
        # Never a roll_request: that is the message the player's client prompts on.
        assert sent["message"]["type"] == "roll_result"

    def test_an_ordinary_request_still_goes_to_the_hero(self, table):
        table["client"].post(ROLL_URL, json=_ask(is_secret=False))

        sent = table["broadcasts"][0]
        assert sent["dm_only"] is False
        assert sent["message"]["type"] == "roll_request"
        assert sent["characters"] == ["Lyra Meadowlark"]

    def test_history_withholds_it_from_the_player(self, table):
        """
        The leak that would undo the whole feature: the player's client replays
        `/messages` on every reconnect, so a secret roll left in there arrives a
        few seconds late instead of never.
        """
        table["state"]["campaign"]["roll_requests"] = [
            {"id": "open", "char_name": "Lyra Meadowlark", "is_secret": False},
            {"id": "hidden", "char_name": "Lyra Meadowlark", "is_secret": True},
        ]
        table["state"]["role"] = "player"

        body = table["client"].get(MESSAGES_URL).json()

        assert [r["id"] for r in body["roll_requests"]] == ["open"]

    def test_the_dm_still_sees_everything(self, table):
        table["state"]["campaign"]["roll_requests"] = [
            {"id": "open", "char_name": "Lyra Meadowlark", "is_secret": False},
            {"id": "hidden", "char_name": "Lyra Meadowlark", "is_secret": True},
        ]

        body = table["client"].get(MESSAGES_URL).json()

        assert [r["id"] for r in body["roll_requests"]] == ["open", "hidden"]
