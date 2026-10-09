import mongomock
import pytest
from fastapi.testclient import TestClient

from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app


class _AsyncCollection:
    """Minimal async facade over a mongomock collection."""

    def __init__(self, coll):
        self._coll = coll

    async def find_one(self, query):
        return self._coll.find_one(query)

    async def update_one(self, query, update, upsert=False):
        class Result:
            def __init__(self, res):
                self.modified_count = res.modified_count
                self.matched_count = res.matched_count
                self.upserted_id = res.upserted_id

        res = self._coll.update_one(query, update, upsert=upsert)
        return Result(res)

    async def delete_one(self, query):
        class Result:
            def __init__(self, res):
                self.deleted_count = res.deleted_count

        res = self._coll.delete_one(query)
        return Result(res)

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

    def find(self, query):
        return self._AsyncCursor(self._coll.find(query))

    async def count_documents(self, query):
        return self._coll.count_documents(query)


class _AsyncDB:
    def __init__(self):
        self._db = mongomock.MongoClient().db
        self.characters = _AsyncCollection(self._db.characters)
        self.homebrew_content = _AsyncCollection(self._db.homebrew_content)
        self.users = _AsyncCollection(self._db.users)

    def __getitem__(self, name):
        if name == "characters":
            return self.characters
        elif name == "homebrew_content":
            return self.homebrew_content
        elif name == "users":
            return self.users
        return _AsyncCollection(self._db[name])


@pytest.fixture
def test_client():
    # Intentionally not using 'with TestClient' to avoid triggering the real mongo lifespan logic
    client = TestClient(app)
    return client


@pytest.fixture
def mock_db():
    db = _AsyncDB()
    return db


@pytest.fixture(autouse=True)
def setup_mocks(mock_db):
    original_overrides = app.dependency_overrides.copy()

    app.dependency_overrides[get_current_user] = lambda: {"id": "user_1", "username": "tester"}
    app.dependency_overrides[get_database] = lambda: mock_db

    yield mock_db

    app.dependency_overrides = original_overrides


def test_character_lifecycle(test_client):
    # 1. Create character
    new_char = {
        "char_name": "Grog Strongjaw",
        "char_class": "Barbarian",
        "level": 1,
        "race": "Goliath",
        "background": "Outlander",
        "stats": {"STR": 18, "DEX": 14, "CON": 16, "INT": 8, "WIS": 10, "CHA": 12},
        "hp_max": 15,
        "hp_current": 15,
    }
    create_resp = test_client.post("/api/v1/characters", json=new_char)
    assert create_resp.status_code == 201, create_resp.json()
    char_data = create_resp.json()
    assert char_data["char_name"] == "Grog Strongjaw"
    assert "char_id" in char_data
    # Verify stats were parsed correctly and generated a +4 STR modifier (if that logic applies)
    assert char_data["stats"]["STR"] == 18

    char_id = char_data["char_id"]

    # 2. Get character
    get_resp = test_client.get(f"/api/v1/characters/{char_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["char_name"] == "Grog Strongjaw"
    assert get_resp.json()["version"] == 0

    # 3. Update character (PUT)
    update_payload = dict(char_data)
    update_payload["char_name"] = "Grog Updated"
    update_resp = test_client.put(f"/api/v1/characters/{char_id}", json=update_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["char_name"] == "Grog Updated"
    assert update_resp.json()["version"] == 1

    # 4. List characters
    list_resp = test_client.get("/api/v1/characters")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["characters"]) == 1

    # 5. Delete character
    del_resp = test_client.delete(f"/api/v1/characters/{char_id}")
    assert del_resp.status_code == 200

    # 6. Verify deletion
    get_resp_after = test_client.get(f"/api/v1/characters/{char_id}")
    assert get_resp_after.status_code == 404


def test_character_update_conflict(test_client):
    new_char = {
        "char_name": "Conflict Hero",
        "char_class": "Fighter",
        "level": 1,
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
    }
    create_resp = test_client.post("/api/v1/characters", json=new_char)
    assert create_resp.status_code == 201
    char_data = create_resp.json()
    char_id = char_data["char_id"]

    # Attempt to update with a stale version (client sends version 0, but DB has version 1)
    # Wait, the newly created char is version 0.
    # Let's update it once to bump version to 1.
    valid_update_resp = test_client.put(f"/api/v1/characters/{char_id}", json=char_data)
    assert valid_update_resp.status_code == 200
    assert valid_update_resp.json()["version"] == 1

    # Now attempt to update again using the ORIGINAL payload (version 0)
    conflict_resp = test_client.put(f"/api/v1/characters/{char_id}", json=char_data)
    assert conflict_resp.status_code == 409
    assert "Conflict" in conflict_resp.json()["detail"]


def test_cross_user_isolation(test_client):
    # Create char as user_1
    new_char = {
        "char_name": "User 1 Hero",
        "char_class": "Fighter",
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
    }
    create_resp = test_client.post("/api/v1/characters", json=new_char)
    char_id = create_resp.json()["char_id"]

    # Switch identity to user_2
    app.dependency_overrides[get_current_user] = lambda: {"id": "user_2", "username": "evil_tester"}

    # Attempt GET
    get_resp = test_client.get(f"/api/v1/characters/{char_id}")
    assert get_resp.status_code == 404

    # Attempt PUT
    put_resp = test_client.put(f"/api/v1/characters/{char_id}", json=create_resp.json())
    assert put_resp.status_code == 404

    # Attempt DELETE
    del_resp = test_client.delete(f"/api/v1/characters/{char_id}")
    assert del_resp.status_code == 404

    # Attempt IDOR POST (Takeover)
    idor_payload = dict(create_resp.json())
    idor_payload["char_name"] = "Hacked Hero"
    idor_resp = test_client.post("/api/v1/characters", json=idor_payload)
    assert idor_resp.status_code == 403


def test_validation_error_on_bad_payload(test_client):
    bad_char = {
        "char_name": "Bad Payload",
        # missing race, background, stats
    }
    create_resp = test_client.post("/api/v1/characters", json=bad_char)
    assert create_resp.status_code == 422


def _hero(char_id, owner_id, name="Hero", **extra):
    return {
        "char_id": char_id,
        "owner_id": owner_id,
        "char_name": name,
        "char_class": "Fighter",
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "version": 0,
        **extra,
    }


def test_takeover_is_refused_even_when_the_precheck_loses_the_race(test_client, mock_db):
    """The find_one pre-check is not atomic. The owner-scoped upsert plus the unique index
    on char_id is what actually stops two requests from claiming the same id."""
    mock_db._db.characters.create_index("char_id", unique=True)
    mock_db._db.characters.insert_one(_hero("victim_1", "user_2", name="Victim's Hero"))

    async def _blind(query):
        return None  # as if the victim's document did not exist yet at check time

    mock_db.characters.find_one = _blind

    payload = _hero("victim_1", "user_1", name="Hacked Hero")
    payload.pop("owner_id")
    resp = test_client.post("/api/v1/characters", json=payload)

    assert resp.status_code == 403
    stored = mock_db._db.characters.find_one({"char_id": "victim_1"})
    assert stored["owner_id"] == "user_2"
    assert stored["char_name"] == "Victim's Hero"


@pytest.fixture
def two_tables(mock_db, monkeypatch):
    """user_1 is DM of 'Table A'. A hero from 'Table B' (someone else's table) exists too."""
    from server.routers import websocket_router

    async def _silent(*args, **kwargs):
        pass

    monkeypatch.setattr(websocket_router.manager, "broadcast", _silent)

    db = mock_db._db
    db.campaigns.insert_one({"campaign_name": "Table A", "party": []})
    db.campaigns.insert_one({"campaign_name": "Table B", "party": []})
    db.campaign_members.insert_one({"campaign_id": "Table A", "user_id": "user_1", "role": "dm"})
    db.campaign_members.insert_one({"campaign_id": "Table B", "user_id": "user_3", "role": "dm"})
    db.characters.insert_one(_hero("in_a", "user_4", "Alice", active_campaign="Table A"))
    db.characters.insert_one(_hero("in_b", "user_5", "Bob", active_campaign="Table B"))
    db.campaign_members.insert_one(
        {"campaign_id": "Table A", "user_id": "user_4", "role": "player"}
    )
    return db


def test_a_dm_cannot_evict_a_hero_from_another_table(test_client, two_tables):
    resp = test_client.delete("/api/v1/campaigns/Table A/party/in_b")

    assert resp.status_code == 403
    assert two_tables.characters.find_one({"char_id": "in_b"})["active_campaign"] == "Table B"


def test_a_dm_cannot_write_hit_points_of_a_hero_from_another_table(test_client, two_tables):
    resp = test_client.patch("/api/v1/campaigns/Table A/party/in_b/state", json={"hp_current": 1})

    assert resp.status_code == 403
    assert "hp_current" not in two_tables.characters.find_one({"char_id": "in_b"})


def test_a_dm_can_still_remove_their_own_hero(test_client, two_tables):
    resp = test_client.delete("/api/v1/campaigns/Table A/party/in_a")

    assert resp.status_code == 200
    assert "active_campaign" not in two_tables.characters.find_one({"char_id": "in_a"})
    assert (
        two_tables.campaign_members.find_one({"campaign_id": "Table A", "user_id": "user_4"})
        is None
    )
