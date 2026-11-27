"""Regression tests for per-item recipient targeting in campaign loot distribution (#222)."""

from unittest.mock import AsyncMock, patch

import mongomock
import pytest
from fastapi.testclient import TestClient

from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app


class _AsyncCollection:
    """Thin async wrapper around a mongomock collection for FastAPI TestClient tests."""

    def __init__(self, col):
        self._col = col

    async def find_one(self, query, *args, **kwargs):
        return self._col.find_one(query, *args, **kwargs)

    async def update_one(self, filt, update, *args, **kwargs):
        return self._col.update_one(filt, update, *args, **kwargs)


class _AsyncDB:
    def __init__(self):
        self._db = mongomock.MongoClient().db

    def __getitem__(self, name):
        return _AsyncCollection(self._db[name])


@pytest.fixture
def loot_env():
    async_db = _AsyncDB()
    dm_user = {"id": "dm_1", "username": "DungeonMaster", "is_admin": False}

    async_db._db["campaigns"].insert_one(
        {"campaign_name": "Mirrodin", "owner_id": "dm_1", "party": []}
    )
    async_db._db["campaign_members"].insert_one(
        {"campaign_id": "Mirrodin", "user_id": "dm_1", "role": "dm"}
    )
    async_db._db["characters"].insert_many(
        [
            {
                "char_id": "seraphina_id",
                "char_name": "Seraphina Vale",
                "owner_id": "p1",
                "active_campaign": "Mirrodin",
                "stats": {"STR": 10, "DEX": 14, "CON": 12, "INT": 12, "WIS": 10, "CHA": 16},
                "proficiency_bonus": 2,
                "currency": {"pp": 0, "gp": 10, "ep": 0, "sp": 0, "cp": 0},
                "equipment": [],
                "weapons": [],
                "features_traits": [],
                "spells": {},
                "prepared_spells": [],
                "version": 1,
            },
            {
                "char_id": "kaelen_id",
                "char_name": "Kaelen Vane",
                "owner_id": "p2",
                "active_campaign": "Mirrodin",
                "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 12, "CHA": 14},
                "proficiency_bonus": 2,
                "currency": {"pp": 0, "gp": 10, "ep": 0, "sp": 0, "cp": 0},
                "equipment": [],
                "weapons": [],
                "features_traits": [],
                "spells": {},
                "prepared_spells": [],
                "version": 1,
            },
        ]
    )

    app.dependency_overrides[get_current_user] = lambda: dm_user
    app.dependency_overrides[get_database] = lambda: async_db
    try:
        with (
            patch("server.routers.websocket_router.manager.broadcast", new_callable=AsyncMock),
            TestClient(app) as client,
        ):
            yield client, async_db._db
    finally:
        app.dependency_overrides.clear()


def test_per_item_recipient_id_routes_exclusively_to_second_player(loot_env):
    """Per-item recipient_id delivers item exclusively to target character even without item_recipient_id."""
    client, raw_db = loot_env

    resp = client.post(
        "/api/v1/campaigns/Mirrodin/loot/distribute",
        json={
            "character_ids": ["seraphina_id", "kaelen_id"],
            "currency": {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 0},
            "items": [
                {
                    "name": "Periapt of Wound Closure",
                    "description": "Stabilize at start of turn",
                    "recipient_id": "kaelen_id",
                }
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recipients"] == ["Kaelen Vane"]

    seraphina = raw_db["characters"].find_one({"char_id": "seraphina_id"})
    kaelen = raw_db["characters"].find_one({"char_id": "kaelen_id"})
    assert seraphina["equipment"] == []
    assert seraphina["version"] == 1
    assert [it["name"] for it in kaelen["equipment"]] == ["Periapt of Wound Closure"]
    assert kaelen["version"] == 2


def test_multiple_items_different_recipients_with_split_currency(loot_env):
    """Distinct per-item recipient_id / recipient_char_id route per item while splitting currency to all."""
    client, raw_db = loot_env

    resp = client.post(
        "/api/v1/campaigns/Mirrodin/loot/distribute",
        json={
            "character_ids": ["seraphina_id", "kaelen_id"],
            "currency": {"pp": 0, "gp": 20, "ep": 0, "sp": 0, "cp": 0},
            "split_currency": True,
            "items": [
                {
                    "name": "Wand of Warmage",
                    "type": "item",
                    "recipient_id": "seraphina_id",
                },
                {
                    "name": "Sun Blade",
                    "type": "weapon",
                    "damage_dice": "1d8",
                    "recipient_char_id": "kaelen_id",
                },
                {
                    "name": "Potion of Healing",
                    "type": "item",
                },
            ],
        },
    )
    assert resp.status_code == 200

    seraphina = raw_db["characters"].find_one({"char_id": "seraphina_id"})
    kaelen = raw_db["characters"].find_one({"char_id": "kaelen_id"})

    assert seraphina["currency"]["gp"] == 20
    assert kaelen["currency"]["gp"] == 20
    assert [it["name"] for it in seraphina["equipment"]] == [
        "Wand of Warmage",
        "Potion of Healing",
    ]
    assert seraphina["weapons"] == []
    assert [it["name"] for it in kaelen["equipment"]] == ["Potion of Healing"]
    assert [w["name"] for w in kaelen["weapons"]] == ["Sun Blade"]


def test_top_level_item_recipient_id_remains_backward_compatible(loot_env):
    """Top-level item_recipient_id directs items without explicit recipient_id, and unknown IDs do not leak."""
    client, raw_db = loot_env

    resp = client.post(
        "/api/v1/campaigns/Mirrodin/loot/distribute",
        json={
            "character_ids": ["seraphina_id", "kaelen_id"],
            "item_recipient_id": "kaelen_id",
            "items": [
                {"name": "Bag of Holding", "type": "item"},
                {"name": "Lost Relic", "type": "item", "recipient_id": "non_existent_char"},
            ],
        },
    )
    assert resp.status_code == 200

    seraphina = raw_db["characters"].find_one({"char_id": "seraphina_id"})
    kaelen = raw_db["characters"].find_one({"char_id": "kaelen_id"})
    assert seraphina["equipment"] == []
    assert [it["name"] for it in kaelen["equipment"]] == ["Bag of Holding"]


@pytest.mark.parametrize("edition", ["2014 Edition", "2024 Revision (5.5e)"])
def test_per_character_ws_awards_isolate_targeted_items_and_quantity(edition):
    """WS loot_distributed payload carries exact per_character currency & items across 2014/2024."""
    async_db = _AsyncDB()
    dm_user = {"id": "dm_1", "username": "DungeonMaster", "is_admin": False}
    async_db._db["campaigns"].insert_one(
        {"campaign_name": "Vault", "owner_id": "dm_1", "dnd_edition": edition, "party": []}
    )
    async_db._db["campaign_members"].insert_one(
        {"campaign_id": "Vault", "user_id": "dm_1", "role": "dm"}
    )
    async_db._db["characters"].insert_many(
        [
            {
                "char_id": "hero_a",
                "char_name": "Lyra",
                "owner_id": "p1",
                "active_campaign": "Vault",
                "dnd_edition": edition,
                "stats": {"STR": 10, "DEX": 16, "CON": 12, "INT": 12, "WIS": 12, "CHA": 14},
                "proficiency_bonus": 2,
                "currency": {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 0},
                "equipment": [],
                "weapons": [],
                "version": 1,
            },
            {
                "char_id": "hero_b",
                "char_name": "Bram",
                "owner_id": "p2",
                "active_campaign": "Vault",
                "dnd_edition": edition,
                "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
                "proficiency_bonus": 2,
                "currency": {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 0},
                "equipment": [],
                "weapons": [],
                "version": 1,
            },
        ]
    )

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: dm_user
    app.dependency_overrides[get_database] = lambda: async_db
    try:
        with patch(
            "server.routers.websocket_router.manager.broadcast", new_callable=AsyncMock
        ) as mock_broadcast:
            client = TestClient(app)
            resp = client.post(
                "/api/v1/campaigns/Vault/loot/distribute",
                json={
                    "character_ids": ["hero_a", "hero_b"],
                    "split_currency": True,
                    "currency": {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 3},
                    "item_recipient_id": "hero_b",
                    "items": [
                        {
                            "name": "Potion of Healing",
                            "type": "item",
                            "quantity": 3,
                            "weight": 0.5,
                        }
                    ],
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["per_character"]["hero_a"] == {
                "currency": {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 2},
                "items": [],
            }
            assert data["per_character"]["hero_b"] == {
                "currency": {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 1},
                "items": ["3x Potion of Healing"],
            }
            ws_payload = mock_broadcast.call_args.args[1]["payload"]
            assert ws_payload["per_character"] == data["per_character"]

            # Verify persisted MongoDB character documents
            hero_a = async_db._db["characters"].find_one({"char_id": "hero_a"})
            hero_b = async_db._db["characters"].find_one({"char_id": "hero_b"})
            assert hero_a["currency"]["cp"] == 2
            assert hero_a["equipment"] == []
            assert hero_b["currency"]["cp"] == 1
            assert len(hero_b["equipment"]) == 1
            assert hero_b["equipment"][0]["quantity"] == 3
            assert hero_b["equipment"][0]["resolved_weight_lb"] == 0.5
            assert hero_b["total_weight_lb"] == pytest.approx(1.5, abs=0.05)

            # Award official SRD Shield +2 without ac_bonus override -> stats_service resolves +4 AC
            shield_resp = client.post(
                "/api/v1/campaigns/Vault/loot/distribute",
                json={
                    "character_ids": ["hero_b"],
                    "items": [
                        {
                            "name": "Shield +2",
                            "description": "A shield is made from wood or metal.",
                            "type": "item",
                            "weight": 6,
                        }
                    ],
                },
            )
            assert shield_resp.status_code == 200
            hero_b_after = async_db._db["characters"].find_one({"char_id": "hero_b"})
            shield_entry = next(e for e in hero_b_after["equipment"] if e["name"] == "Shield +2")
            assert shield_entry["ac_bonus"] == 0
            shield_entry["equipped"] = True

            from backend.services.stats_service import calculate_ac

            # Base 10 + DEX (+1) + Shield (+2) + Magic (+2) = 15
            ac_val = calculate_ac(
                hero_b_after["stats"]["DEX"],
                hero_b_after["equipment"],
                char_class="Fighter",
                edition=edition,
            )
            assert ac_val == 15
    finally:
        app.dependency_overrides = orig
