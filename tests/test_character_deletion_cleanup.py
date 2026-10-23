import os

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.utils.image_utils import PORTRAIT_DIR
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app


class _AsyncCollection:
    """Async facade over mongomock collection for unit & integration testing."""

    def __init__(self, coll):
        self._coll = coll

    async def find_one(self, query=None, *args, **kwargs):
        return self._coll.find_one(query or {}, *args, **kwargs)

    async def update_one(self, query, update, upsert=False):
        class Result:
            def __init__(self, res):
                self.modified_count = res.modified_count
                self.matched_count = res.matched_count
                self.upserted_id = res.upserted_id

        res = self._coll.update_one(query, update, upsert=upsert)
        return Result(res)

    async def update_many(self, query, update, upsert=False):
        class Result:
            def __init__(self, res):
                self.modified_count = res.modified_count
                self.matched_count = res.matched_count
                self.upserted_id = res.upserted_id

        res = self._coll.update_many(query, update, upsert=upsert)
        return Result(res)

    async def delete_one(self, query):
        class Result:
            def __init__(self, res):
                self.deleted_count = res.deleted_count

        res = self._coll.delete_one(query)
        return Result(res)

    async def delete_many(self, query):
        class Result:
            def __init__(self, res):
                self.deleted_count = res.deleted_count

        res = self._coll.delete_many(query)
        return Result(res)

    async def insert_one(self, doc):
        return self._coll.insert_one(doc)

    class _AsyncCursor:
        def __init__(self, cursor):
            self.items = list(cursor)
            self.idx = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.idx < len(self.items):
                item = self.items[self.idx]
                self.idx += 1
                return item
            raise StopAsyncIteration

    def find(self, query=None, *args, **kwargs):
        return self._AsyncCursor(self._coll.find(query or {}, *args, **kwargs))

    async def count_documents(self, query):
        return self._coll.count_documents(query)


class _MockAsyncDB:
    def __init__(self):
        self._db = mongomock.MongoClient().db

    def __getitem__(self, name):
        return _AsyncCollection(self._db[name])


@pytest.fixture
def test_db():
    return _MockAsyncDB()


@pytest.fixture
def current_user():
    return {"id": "user_alice", "username": "alice"}


@pytest.fixture
def client(test_db, current_user):
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: current_user

    c = TestClient(app)
    yield c
    app.dependency_overrides = original_overrides


@pytest.fixture
def sample_character(test_db):
    char_doc = {
        "char_id": "test_hero_1",
        "char_name": "Valeros",
        "owner_id": "user_alice",
        "char_class": "Fighter",
        "level": 3,
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        "hp_max": 28,
        "hp_current": 28,
        "conditions": [],
        "active_campaign": "Lost Mine",
        "char_portrait": "/api/v1/portraits/test_hero_1.png",
    }
    test_db["characters"]._coll.insert_one(char_doc)
    return char_doc


def test_delete_character_not_found(client):
    """Deleting a non-existent character ID returns 404."""
    resp = client.delete("/api/v1/characters/non_existent_id")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Character not found"


def test_delete_character_idor_protection(client, test_db):
    """Deleting a character owned by someone else returns 404 and does not delete it."""
    other_char = {
        "char_id": "bob_char_99",
        "char_name": "Bob's Rogue",
        "owner_id": "user_bob",
        "char_class": "Rogue",
        "level": 1,
        "race": "Elf",
        "background": "Criminal",
        "stats": {"STR": 10, "DEX": 16, "CON": 12, "INT": 14, "WIS": 10, "CHA": 12},
        "hp_max": 9,
        "char_portrait": "/api/v1/portraits/bob_char_99.png",
    }
    test_db["characters"]._coll.insert_one(other_char)

    # Bob's portrait on disk
    bob_portrait_path = os.path.join(PORTRAIT_DIR, "bob_char_99.png")
    os.makedirs(PORTRAIT_DIR, exist_ok=True)
    with open(bob_portrait_path, "w") as f:
        f.write("bob portrait data")

    try:
        # Alice tries to delete Bob's character
        resp = client.delete("/api/v1/characters/bob_char_99")
        assert resp.status_code == 404

        # Verify Bob's character was NOT deleted
        found = test_db["characters"]._coll.find_one({"char_id": "bob_char_99"})
        assert found is not None
        assert os.path.exists(bob_portrait_path)
    finally:
        if os.path.exists(bob_portrait_path):
            os.remove(bob_portrait_path)


def test_cascading_cleanup_portrait_on_disk(client, test_db, sample_character):
    """Cascading cleanup deletes local portrait image file from disk."""
    portrait_file = os.path.join(PORTRAIT_DIR, "test_hero_1.png")
    os.makedirs(PORTRAIT_DIR, exist_ok=True)
    with open(portrait_file, "w") as f:
        f.write("image data")

    assert os.path.exists(portrait_file)

    resp = client.delete("/api/v1/characters/test_hero_1")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Character document deleted
    assert test_db["characters"]._coll.find_one({"char_id": "test_hero_1"}) is None

    # Portrait file deleted
    assert not os.path.exists(portrait_file)


def test_cascading_cleanup_versioned_portraits(client, test_db):
    """Cascading cleanup deletes versioned / force-regenerated portraits for the character."""
    char_id = "hero_versioned_123"
    char_doc = {
        "char_id": char_id,
        "char_name": "Versioned Hero",
        "owner_id": "user_alice",
        "char_class": "Wizard",
        "level": 2,
        "race": "Gnome",
        "background": "Sage",
        "stats": {"STR": 8, "DEX": 12, "CON": 12, "INT": 17, "WIS": 13, "CHA": 10},
        "hp_max": 14,
        "char_portrait": f"/api/v1/portraits/{char_id}_1780000000.png",
    }
    test_db["characters"]._coll.insert_one(char_doc)

    file1 = os.path.join(PORTRAIT_DIR, f"{char_id}.png")
    file2 = os.path.join(PORTRAIT_DIR, f"{char_id}_1780000000.png")
    os.makedirs(PORTRAIT_DIR, exist_ok=True)
    for p in (file1, file2):
        with open(p, "w") as f:
            f.write("image data")
        assert os.path.exists(p)

    resp = client.delete(f"/api/v1/characters/{char_id}")
    assert resp.status_code == 200

    assert not os.path.exists(file1)
    assert not os.path.exists(file2)


def test_portrait_default_asset_preserved(client, test_db):
    """Default / template portraits (e.g. default.png, anvil.png) must NOT be deleted from disk."""
    char_id = "hero_with_default"
    char_doc = {
        "char_id": char_id,
        "char_name": "Novice",
        "owner_id": "user_alice",
        "char_class": "Fighter",
        "level": 1,
        "race": "Human",
        "background": "Folk Hero",
        "stats": {"STR": 15, "DEX": 13, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        "hp_max": 12,
        "char_portrait": "/api/v1/portraits/default.png",
    }
    test_db["characters"]._coll.insert_one(char_doc)

    default_file = os.path.join(PORTRAIT_DIR, "default.png")
    os.makedirs(PORTRAIT_DIR, exist_ok=True)
    with open(default_file, "w") as f:
        f.write("default portrait template")

    try:
        resp = client.delete(f"/api/v1/characters/{char_id}")
        assert resp.status_code == 200
        # Default asset is preserved
        assert os.path.exists(default_file)
    finally:
        if os.path.exists(default_file):
            os.remove(default_file)


def test_portrait_shared_asset_preserved(client, test_db):
    """If another character shares the portrait file, it is preserved until the last character is deleted."""
    shared_filename = "shared_paladin_art.png"
    shared_path = os.path.join(PORTRAIT_DIR, shared_filename)
    os.makedirs(PORTRAIT_DIR, exist_ok=True)
    with open(shared_path, "w") as f:
        f.write("shared portrait bytes")

    char1 = {
        "char_id": "shared_hero_1",
        "char_name": "Paladin A",
        "owner_id": "user_alice",
        "char_class": "Paladin",
        "level": 1,
        "race": "Human",
        "background": "Noble",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 14},
        "hp_max": 12,
        "char_portrait": f"/api/v1/portraits/{shared_filename}",
    }
    char2 = {
        "char_id": "shared_hero_2",
        "char_name": "Paladin B",
        "owner_id": "user_alice",
        "char_class": "Paladin",
        "level": 1,
        "race": "Aasimar",
        "background": "Acolyte",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 14},
        "hp_max": 12,
        "char_portrait": f"/api/v1/portraits/{shared_filename}",
    }
    test_db["characters"]._coll.insert_one(char1)
    test_db["characters"]._coll.insert_one(char2)

    try:
        # Delete first character
        resp1 = client.delete("/api/v1/characters/shared_hero_1")
        assert resp1.status_code == 200
        # File is still present because shared_hero_2 references it
        assert os.path.exists(shared_path)

        # Delete second character
        resp2 = client.delete("/api/v1/characters/shared_hero_2")
        assert resp2.status_code == 200
        # File is now deleted
        assert not os.path.exists(shared_path)
    finally:
        if os.path.exists(shared_path):
            os.remove(shared_path)


def test_portrait_external_url_safely_ignored(client, test_db):
    """Character with external pollinations/HTTP portrait does not raise filesystem errors."""
    char_id = "hero_external_url"
    char_doc = {
        "char_id": char_id,
        "char_name": "Sky Hero",
        "owner_id": "user_alice",
        "char_class": "Monk",
        "level": 1,
        "race": "Aarakocra",
        "background": "Hermit",
        "stats": {"STR": 10, "DEX": 16, "CON": 12, "INT": 10, "WIS": 16, "CHA": 8},
        "hp_max": 9,
        "char_portrait": "https://image.pollinations.ai/prompt/monk?seed=12345",
    }
    test_db["characters"]._coll.insert_one(char_doc)

    resp = client.delete(f"/api/v1/characters/{char_id}")
    assert resp.status_code == 200
    assert test_db["characters"]._coll.find_one({"char_id": char_id}) is None


def test_cascading_cleanup_campaign_party_membership(client, test_db, sample_character):
    """Removing character cascades and pulls its identifier from all campaign party arrays."""
    char_id = sample_character["char_id"]

    # Campaign 1: full filename
    camp1 = {
        "campaign_name": "Camp 1",
        "party": [f"valeros_{char_id}.json", "other_hero_456.json"],
    }
    # Campaign 2: char_id.json
    camp2 = {
        "campaign_name": "Camp 2",
        "party": [f"{char_id}.json", "companion.json"],
    }
    # Campaign 3: bare char_id
    camp3 = {
        "campaign_name": "Camp 3",
        "party": [char_id],
    }
    # Campaign 4: partial name that shouldn't match
    camp4 = {
        "campaign_name": "Camp 4",
        "party": [f"other_{char_id}_extra.json"],
    }

    test_db["campaigns"]._coll.insert_one(camp1)
    test_db["campaigns"]._coll.insert_one(camp2)
    test_db["campaigns"]._coll.insert_one(camp3)
    test_db["campaigns"]._coll.insert_one(camp4)

    resp = client.delete(f"/api/v1/characters/{char_id}")
    assert resp.status_code == 200

    c1 = test_db["campaigns"]._coll.find_one({"campaign_name": "Camp 1"})
    assert c1["party"] == ["other_hero_456.json"]

    c2 = test_db["campaigns"]._coll.find_one({"campaign_name": "Camp 2"})
    assert c2["party"] == ["companion.json"]

    c3 = test_db["campaigns"]._coll.find_one({"campaign_name": "Camp 3"})
    assert c3["party"] == []

    c4 = test_db["campaigns"]._coll.find_one({"campaign_name": "Camp 4"})
    assert c4["party"] == [f"other_{char_id}_extra.json"]


def test_cascading_cleanup_campaign_membership_player(client, test_db, sample_character):
    """Player with no other characters in the campaign has their campaign_members record removed."""
    char_id = sample_character["char_id"]
    camp_name = sample_character["active_campaign"]

    test_db["campaigns"]._coll.insert_one(
        {"campaign_name": camp_name, "party": [f"valeros_{char_id}.json"]}
    )

    test_db["campaign_members"]._coll.insert_one(
        {
            "campaign_id": camp_name,
            "user_id": "user_alice",
            "role": "player",
            "character_id": char_id,
        }
    )

    resp = client.delete(f"/api/v1/characters/{char_id}")
    assert resp.status_code == 200

    # campaign_members document should be removed
    member = test_db["campaign_members"]._coll.find_one(
        {
            "campaign_id": camp_name,
            "user_id": "user_alice",
        }
    )
    assert member is None


def test_cascading_cleanup_campaign_membership_multiple_characters(client, test_db):
    """Player with multiple active characters keeps campaign_members and updates character_id."""
    char1_id = "char_hero_alpha"
    char2_id = "char_hero_beta"
    camp_name = "Storm King's Thunder"

    char1 = {
        "char_id": char1_id,
        "char_name": "Hero Alpha",
        "owner_id": "user_alice",
        "char_class": "Fighter",
        "level": 1,
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        "hp_max": 12,
        "active_campaign": camp_name,
    }
    char2 = {
        "char_id": char2_id,
        "char_name": "Hero Beta",
        "owner_id": "user_alice",
        "char_class": "Cleric",
        "level": 1,
        "race": "Dwarf",
        "background": "Acolyte",
        "stats": {"STR": 14, "DEX": 10, "CON": 16, "INT": 10, "WIS": 16, "CHA": 10},
        "hp_max": 11,
        "active_campaign": camp_name,
    }
    test_db["characters"]._coll.insert_one(char1)
    test_db["characters"]._coll.insert_one(char2)

    test_db["campaigns"]._coll.insert_one(
        {
            "campaign_name": camp_name,
            "party": [f"hero_alpha_{char1_id}.json", f"hero_beta_{char2_id}.json"],
        }
    )

    test_db["campaign_members"]._coll.insert_one(
        {
            "campaign_id": camp_name,
            "user_id": "user_alice",
            "role": "player",
            "character_id": char1_id,
        }
    )

    resp = client.delete(f"/api/v1/characters/{char1_id}")
    assert resp.status_code == 200

    # campaign_members document is kept and character_id points to char2_id
    member = test_db["campaign_members"]._coll.find_one(
        {
            "campaign_id": camp_name,
            "user_id": "user_alice",
        }
    )
    assert member is not None
    assert member["character_id"] == char2_id


def test_cascading_cleanup_dm_membership_preserved(client, test_db, sample_character):
    """When a DM deletes their personal character, their DM membership in campaign_members is never deleted."""
    char_id = sample_character["char_id"]
    camp_name = sample_character["active_campaign"]

    test_db["campaigns"]._coll.insert_one(
        {"campaign_name": camp_name, "party": [f"valeros_{char_id}.json"]}
    )

    test_db["campaign_members"]._coll.insert_one(
        {
            "campaign_id": camp_name,
            "user_id": "user_alice",
            "role": "dm",
            "character_id": char_id,
        }
    )

    resp = client.delete(f"/api/v1/characters/{char_id}")
    assert resp.status_code == 200

    member = test_db["campaign_members"]._coll.find_one(
        {
            "campaign_id": camp_name,
            "user_id": "user_alice",
        }
    )
    assert member is not None
    assert member["role"] == "dm"
    assert member.get("character_id") is None


def test_cascading_cleanup_vtt_and_encounters(client, test_db, sample_character):
    """Character deletion cascades to VTT tokens and combatant entries in campaign_encounters."""
    char_id = sample_character["char_id"]
    camp_name = sample_character["active_campaign"]

    test_db["campaigns"]._coll.insert_one(
        {
            "campaign_name": camp_name,
            "party": [char_id],
            "vtt_state": {
                "is_active": True,
                "tokens": [
                    {"id": char_id, "name": "Valeros", "x": 5, "y": 5},
                    {"id": "goblin_1", "name": "Goblin", "x": 6, "y": 6},
                ],
            },
        }
    )

    test_db["campaign_encounters"]._coll.insert_one(
        {
            "campaign_name": camp_name,
            "combatants": [
                {"id": char_id, "char_id": char_id, "name": "Valeros", "hp": 28},
                {"id": "orc_1", "char_id": None, "name": "Orc", "hp": 15},
            ],
        }
    )

    test_db["campaign_roll_requests"]._coll.insert_one(
        {
            "campaign_name": camp_name,
            "char_filename": f"valeros_{char_id}.json",
            "status": "pending",
        }
    )

    resp = client.delete(f"/api/v1/characters/{char_id}")
    assert resp.status_code == 200

    # VTT token removed
    camp = test_db["campaigns"]._coll.find_one({"campaign_name": camp_name})
    tokens = camp["vtt_state"]["tokens"]
    assert len(tokens) == 1
    assert tokens[0]["id"] == "goblin_1"

    # Encounter combatant removed
    enc = test_db["campaign_encounters"]._coll.find_one({"campaign_name": camp_name})
    combatants = enc["combatants"]
    assert len(combatants) == 1
    assert combatants[0]["id"] == "orc_1"

    # Pending roll request removed
    req = test_db["campaign_roll_requests"]._coll.find_one({"campaign_name": camp_name})
    assert req is None


def test_websocket_broadcast_on_cascading_deletion(monkeypatch, client, test_db, sample_character):
    """Deleting a character broadcasts a WebSocket party_update event for affected campaigns."""
    from server.routers import websocket_router

    broadcasts = []

    async def _mock_broadcast(campaign_id, message, **kwargs):
        broadcasts.append((campaign_id, message))

    monkeypatch.setattr(websocket_router.manager, "broadcast", _mock_broadcast)

    char_id = sample_character["char_id"]
    camp_name = sample_character["active_campaign"]

    test_db["campaigns"]._coll.insert_one(
        {
            "campaign_name": camp_name,
            "party": [f"valeros_{char_id}.json"],
        }
    )

    resp = client.delete(f"/api/v1/characters/{char_id}")
    assert resp.status_code == 200

    assert len(broadcasts) >= 1
    matched = [
        b
        for b in broadcasts
        if b[0] == camp_name
        and b[1].get("type") == "party_update"
        and b[1].get("payload", {}).get("action") == "removed"
        and b[1].get("payload", {}).get("char_id") == char_id
    ]
    assert len(matched) == 1
