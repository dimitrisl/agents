from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app

# Setup our mock database dictionary
fake_db_data = {
    "characters": {},
    "users": {"test_user": {"id": "test_user", "username": "tester"}},
    "homebrew_content": {},
}


async def mock_find_one(collection_name, query):
    if collection_name == "characters":
        char_id = query.get("char_id")
        owner_id = query.get("owner_id")
        for char in fake_db_data["characters"].values():
            if char.get("char_id") == char_id and char.get("owner_id") == owner_id:
                return dict(char)
    elif collection_name == "users":
        return fake_db_data["users"].get("test_user")
    return None


class MockCursor:
    def __init__(self, collection_name, query):
        self.items = []
        if collection_name == "characters":
            owner_id = query.get("owner_id")
            for char in fake_db_data["characters"].values():
                if char.get("owner_id") == owner_id:
                    self.items.append(dict(char))
        elif collection_name == "homebrew_content":
            campaign_id = query.get("campaign_id")
            for item in fake_db_data["homebrew_content"].values():
                if item.get("campaign_id") == campaign_id:
                    self.items.append(dict(item))
        self.idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.idx < len(self.items):
            item = self.items[self.idx]
            self.idx += 1
            return item
        raise StopAsyncIteration


def mock_find(collection_name, query):
    return MockCursor(collection_name, query)


async def mock_update_one(collection_name, query, update, upsert=False):
    if collection_name == "characters":
        char_id = query.get("char_id") or update.get("$set", {}).get("char_id")
        if char_id in fake_db_data["characters"]:
            fake_db_data["characters"][char_id].update(update.get("$set", {}))
            mock_res = MagicMock()
            mock_res.modified_count = 1
            mock_res.matched_count = 1
            return mock_res
        elif upsert:
            fake_db_data["characters"][char_id] = update.get("$set", {})
            mock_res = MagicMock()
            mock_res.modified_count = 0
            mock_res.matched_count = 0
            return mock_res
    mock_res = MagicMock()
    mock_res.modified_count = 0
    mock_res.matched_count = 0
    return mock_res


async def mock_delete_one(collection_name, query):
    if collection_name == "characters":
        char_id = query.get("char_id")
        if char_id in fake_db_data["characters"]:
            del fake_db_data["characters"][char_id]
            mock_res = MagicMock()
            mock_res.deleted_count = 1
            return mock_res
    mock_res = MagicMock()
    mock_res.deleted_count = 0
    return mock_res


class MockCollection:
    def __init__(self, name):
        self.name = name

    async def find_one(self, query):
        return await mock_find_one(self.name, query)

    def find(self, query):
        return mock_find(self.name, query)

    async def update_one(self, query, update, upsert=False):
        return await mock_update_one(self.name, query, update, upsert)

    async def delete_one(self, query):
        return await mock_delete_one(self.name, query)


class MockDatabase:
    def __getitem__(self, name):
        return MockCollection(name)


@pytest.fixture
def test_client():
    client = TestClient(app)
    return client


@pytest.fixture(autouse=True)
def setup_mocks():
    fake_db_data["characters"].clear()

    app.dependency_overrides[get_current_user] = lambda: {"id": "test_user", "username": "tester"}
    app.dependency_overrides[get_database] = lambda: MockDatabase()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_database, None)


def test_root_endpoint(test_client):
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_docs_endpoint_exists(test_client):
    response = test_client.get("/docs")
    assert response.status_code == 200


def test_character_lifecycle(test_client):
    # Create character
    new_char = {
        "char_name": "Grog Strongjaw",
        "char_class": "Barbarian",
        "level": 1,
        "race": "Goliath",
        "background": "Outlander",
        "stats": {"str": 18, "dex": 14, "con": 16, "int": 8, "wis": 10, "cha": 12},
        "hp_max": 15,
        "hp_current": 15,
    }
    create_resp = test_client.post("/api/v1/characters", json=new_char)
    assert create_resp.status_code == 201, create_resp.json()
    char_data = create_resp.json()
    assert char_data["char_name"] == "Grog Strongjaw"
    assert "char_id" in char_data

    char_id = char_data["char_id"]

    # Get character
    get_resp = test_client.get(f"/api/v1/characters/{char_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["char_name"] == "Grog Strongjaw"

    # List characters
    list_resp = test_client.get("/api/v1/characters")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["characters"]) == 1

    # Delete character
    del_resp = test_client.delete(f"/api/v1/characters/{char_id}")
    assert del_resp.status_code == 200

    # Verify deletion
    get_resp_after = test_client.get(f"/api/v1/characters/{char_id}")
    assert get_resp_after.status_code == 404
