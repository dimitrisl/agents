"""Answering — or failing to answer — a roll request the DM sent.

Before #26 the player's client threw the dice by itself the moment a request
arrived, so there was only ever one outcome to record. Now the player chooses how
to roll, or lets the prompt lapse, and both of those have to reach the DM: a total
with the mode that produced it, or a request marked as never answered.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app

CAMPAIGN = "The Obsidian Citadel"
REQUEST_ID = "req_1"
MISS_URL = f"/api/v1/campaigns/{CAMPAIGN}/roll-request/{REQUEST_ID}/miss"
RESULT_URL = f"/api/v1/campaigns/{CAMPAIGN}/roll-request/{REQUEST_ID}/result"


def _roll_request(**overrides):
    return {
        "id": REQUEST_ID,
        "char_filename": "lyra_hero1.json",
        "char_name": "Lyra Meadowlark",
        "roll_type": "skill",
        "stat": "Perception",
        "reason": "Did you hear that?",
        "status": "pending",
        "result": None,
        "is_secret": False,
        **overrides,
    }


@pytest.fixture
def table(monkeypatch):
    """One campaign, one pending request, and a socket nobody has to open."""
    broadcasts = []

    from server.routers import websocket_router

    async def _record(campaign_id, message, characters=None):
        broadcasts.append((campaign_id, message, characters))

    monkeypatch.setattr(websocket_router.manager, "broadcast", _record)

    state = {
        "campaign": {"campaign_name": CAMPAIGN, "roll_requests": [_roll_request()]},
        "role": "player",
        "modified": 1,
    }

    characters = MagicMock()
    characters.find_one = AsyncMock(return_value=None)
    campaigns = MagicMock()
    campaigns.find_one = AsyncMock(side_effect=lambda q: state["campaign"])
    campaigns.update_one = AsyncMock(
        side_effect=lambda *a, **k: MagicMock(modified_count=state["modified"])
    )

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
            self.update_one = AsyncMock(side_effect=self._update_one)
            self.update_many = AsyncMock(side_effect=self._update_many)
            self.insert_one = AsyncMock(side_effect=self._insert_one)
            self.delete_one = AsyncMock(side_effect=self._delete_one)

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

        async def _insert_one(self, doc):
            # Tests don't usually assert on inserted docs directly via this mock,
            # but if they do, we'll just ignore it or append it
            return MagicMock(inserted_id="mock_id")

        async def _update_one(self, query, update, upsert=False):
            doc = await self.find_one(query)
            if doc:
                return MagicMock(modified_count=self.state.get("modified", 1))
            return MagicMock(modified_count=0)

        async def _update_many(self, query, update):
            return MagicMock(modified_count=self.state.get("modified", 1))

        async def _delete_one(self, query):
            return MagicMock(deleted_count=1)

    whispers = MockCollection(state, "whispers")
    roll_requests = MockCollection(state, "roll_requests")

    db_dict = {
        "campaigns": campaigns,
        "campaign_roll_requests": roll_requests,
        "campaign_members": members,
        "characters": characters,
        "campaign_whispers": whispers,
    }
    app.dependency_overrides[get_database] = lambda: db_dict

    app.dependency_overrides[get_current_user] = lambda: {"id": "player_1", "username": "lyra"}

    yield {
        "client": TestClient(app),
        "campaigns": campaigns,
        "campaign_roll_requests": roll_requests,
        "state": state,
        "broadcasts": broadcasts,
    }

    app.dependency_overrides.clear()


class TestMissingARoll:
    def test_a_lapsed_request_is_recorded_as_missed(self, table):
        response = table["client"].post(MISS_URL, json={})

        assert response.status_code == 200
        query, update = table["campaign_roll_requests"].update_one.await_args.args
        assert update["$set"]["status"] == "missed"
        assert "missed_at" in update["$set"]

    def test_only_a_pending_request_may_be_missed(self, table):
        """
        The filter is the whole safety story: a result landing in the same instant
        wins, and the miss becomes a no-op rather than erasing a real roll.
        """
        table["client"].post(MISS_URL, json={})

        query, _ = table["campaign_roll_requests"].update_one.await_args.args
        assert query.get("status") == "pending"

    def test_a_roll_that_arrived_first_is_not_overwritten(self, table):
        table["state"]["modified"] = 0

        response = table["client"].post(MISS_URL, json={})

        assert response.status_code == 200
        assert response.json()["message"] == "Roll request was already answered"
        # Nothing changed, so the table is told nothing.
        assert table["broadcasts"] == []

    def test_the_dm_is_told(self, table):
        table["client"].post(MISS_URL, json={})

        assert len(table["broadcasts"]) == 1
        campaign_id, message, characters = table["broadcasts"][0]
        assert campaign_id == CAMPAIGN
        assert message["type"] == "roll_result"
        assert message["payload"]["status"] == "missed"
        assert characters == ["Lyra Meadowlark"]

    def test_an_unknown_request_is_a_404(self, table):
        table["state"]["campaign"] = {"campaign_name": CAMPAIGN, "roll_requests": []}

        assert table["client"].post(MISS_URL, json={}).status_code == 404

    def test_a_missing_campaign_is_a_404(self, table):
        table["state"]["campaign"] = None

        assert table["client"].post(MISS_URL, json={}).status_code == 404

    def test_a_non_member_is_refused(self, table):
        table["state"]["role"] = None

        assert table["client"].post(MISS_URL, json={}).status_code == 403
        table["campaigns"].update_one.assert_not_awaited()


class TestHowTheRollWasMade:
    def test_the_mode_reaches_the_dm(self, table):
        response = table["client"].post(
            RESULT_URL,
            json={
                "total": 23,
                "expression": "1d20 (17) +6",
                "raw": 17,
                "rolls": [4, 17],
                "modifier": 6,
                "mode": "advantage",
                "situational_bonus": 2,
            },
        )

        assert response.status_code == 200
        _, update = table["campaign_roll_requests"].update_one.await_args.args
        result = update["$set"]["result"]
        assert result["mode"] == "advantage"
        assert result["situational_bonus"] == 2

    def test_a_client_that_sends_neither_still_resolves(self, table):
        """The fields are additive: an older client must keep working unchanged."""
        response = table["client"].post(
            RESULT_URL,
            json={
                "total": 18,
                "expression": "1d20 (12) +6",
                "raw": 12,
                "rolls": [12],
                "modifier": 6,
            },
        )

        assert response.status_code == 200
        _, update = table["campaign_roll_requests"].update_one.await_args.args
        result = update["$set"]["result"]
        assert result["mode"] == "normal"
        assert result["situational_bonus"] == 0
