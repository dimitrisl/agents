"""
Unit tests for campaign member_count computation in list_campaigns.
"""

import asyncio

import mongomock
from fastapi.testclient import TestClient

from backend.services.user_admin_service import delete_user_cascade
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter


class _AsyncCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor
        self._iter = None

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    async def to_list(self, length=None):
        items = list(self._cursor)
        return items[:length] if length is not None else items

    def __aiter__(self):
        self._iter = iter(list(self._cursor))
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _AsyncColWrapper:
    def __init__(self, col):
        self._col = col

    async def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._col.insert_one(*args, **kwargs)

    async def insert_many(self, *args, **kwargs):
        return self._col.insert_many(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def update_many(self, *args, **kwargs):
        return self._col.update_many(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._col.delete_one(*args, **kwargs)

    async def delete_many(self, *args, **kwargs):
        return self._col.delete_many(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._col.count_documents(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursorWrapper(self._col.find(*args, **kwargs))


class _AsyncDBWrapper:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name):
        return _AsyncColWrapper(self._db[name])

    def __getattr__(self, name):
        return _AsyncColWrapper(getattr(self._db, name))


def test_list_campaigns_returns_accurate_member_count():
    limiter.reset()
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["phyrexian_forge_test_member_count"]
    db = _AsyncDBWrapper(raw_db)

    # Seed campaign
    raw_db["campaigns"].insert_one(
        {
            "campaign_name": "Test Campaign 741886",
            "owner_id": "dm_user",
            "party": ["grom.json", "elara.json", "therion.json"],
            "dnd_edition": "2014 Edition",
            "notes": "Testing",
            "role": "dm",
        }
    )

    # Seed 4 members (1 DM + 3 Players)
    raw_db["campaign_members"].insert_many(
        [
            {"campaign_id": "Test Campaign 741886", "user_id": "dm_user", "role": "dm"},
            {
                "campaign_id": "Test Campaign 741886",
                "user_id": "player_1",
                "role": "player",
                "character_id": "grom_id",
            },
            {
                "campaign_id": "Test Campaign 741886",
                "user_id": "player_2",
                "role": "player",
                "character_id": "elara_id",
            },
            {
                "campaign_id": "Test Campaign 741886",
                "user_id": "player_3",
                "role": "player",
                "character_id": "therion_id",
            },
        ]
    )

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_user", "username": "dm_user"}

    try:
        client = TestClient(app)
        # 1. As DM
        resp = client.get("/api/v1/campaigns/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        campaign = data[0]
        assert campaign["campaign_name"] == "Test Campaign 741886"
        assert campaign["member_count"] == 4
        assert len(campaign["party"]) == 3

        # 2. As Player
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "player_1",
            "username": "player_1",
        }
        resp_p = client.get("/api/v1/campaigns/")
        assert resp_p.status_code == 200, resp_p.text
        data_p = resp_p.json()
        assert len(data_p) == 1
        campaign_p = data_p[0]
        assert campaign_p["campaign_name"] == "Test Campaign 741886"
        assert campaign_p["role"] == "player"
        assert campaign_p["member_count"] == 4
        assert len(campaign_p["party"]) == 3
    finally:
        app.dependency_overrides.pop(get_database, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_delete_user_cascade_removes_canonical_party_filenames():
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["phyrexian_forge_test_cascade_party"]
    db = _AsyncDBWrapper(raw_db)

    raw_db["users"].insert_many(
        [
            {"id": "admin_1", "username": "admin_1", "is_admin": True},
            {"id": "player_grom", "username": "grom_user", "is_admin": False},
        ]
    )
    raw_db["characters"].insert_one(
        {
            "char_id": "223c921a-f276-462e-939f-93de5ce26b53",
            "char_name": "Grom",
            "owner_id": "player_grom",
            "active_campaign": "Test Campaign 741886",
        }
    )
    raw_db["campaigns"].insert_one(
        {
            "campaign_name": "Test Campaign 741886",
            "owner_id": "dm_user",
            "party": [
                "grom_223c921a-f276-462e-939f-93de5ce26b53.json",
                'kaelen_"whisperwind"_thorne_47ca5436.json',
            ],
            "role": "dm",
        }
    )
    raw_db["campaign_members"].insert_many(
        [
            {"campaign_id": "Test Campaign 741886", "user_id": "dm_user", "role": "dm"},
            {
                "campaign_id": "Test Campaign 741886",
                "user_id": "player_grom",
                "role": "player",
                "character_id": "223c921a-f276-462e-939f-93de5ce26b53",
            },
        ]
    )

    asyncio.run(
        delete_user_cascade(
            db, "player_grom", {"id": "admin_1", "username": "admin_1", "is_admin": True}
        )
    )

    camp_after = raw_db["campaigns"].find_one({"campaign_name": "Test Campaign 741886"})
    assert camp_after["party"] == ['kaelen_"whisperwind"_thorne_47ca5436.json']
    members_after = list(raw_db["campaign_members"].find({"campaign_id": "Test Campaign 741886"}))
    assert len(members_after) == 1
    assert members_after[0]["user_id"] == "dm_user"
