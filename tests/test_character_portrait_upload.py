import io
import os

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.utils.image_utils import PORTRAIT_DIR
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app


class _AsyncCollection:
    def __init__(self, coll):
        self._coll = coll

    async def find_one(self, query=None, *args, **kwargs):
        return self._coll.find_one(query or {}, *args, **kwargs)

    async def update_one(self, query, update, upsert=False):
        class Result:
            def __init__(self, res):
                self.modified_count = res.modified_count
                self.matched_count = res.matched_count

        res = self._coll.update_one(query, update, upsert=upsert)
        return Result(res)

    async def count_documents(self, query=None):
        return self._coll.count_documents(query or {})


class _AsyncDatabase:
    def __init__(self, client):
        self._client = client
        self._db = client["dnd_test_db"]

    def __getitem__(self, name: str):
        return _AsyncCollection(self._db[name])


@pytest.fixture
def mock_db():
    client = mongomock.MongoClient()
    return _AsyncDatabase(client)


@pytest.fixture
def test_client(mock_db):
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user_123",
        "username": "tester",
    }
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_upload_character_portrait_success(test_client, mock_db):
    # Insert test character
    mock_db["characters"]._coll.insert_one(
        {
            "char_id": "char_hero_1",
            "owner_id": "user_123",
            "char_name": "Valeros",
            "version": 1,
            "char_portrait": None,
        }
    )

    image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    files = {"file": ("hero_portrait.png", io.BytesIO(image_bytes), "image/png")}

    response = test_client.post("/api/v1/characters/char_hero_1/portrait-upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "/api/v1/portraits/" in data["portrait_url"]
    assert data["version"] == 2

    # Check database updated
    doc = mock_db["characters"]._coll.find_one({"char_id": "char_hero_1"})
    assert doc["char_portrait"] == data["portrait_url"]
    assert doc["version"] == 2

    # Clean up file on disk
    filename = os.path.basename(data["portrait_url"])
    disk_path = os.path.join(PORTRAIT_DIR, filename)
    if os.path.exists(disk_path):
        os.remove(disk_path)


def test_upload_character_portrait_rejects_non_image(test_client, mock_db):
    mock_db["characters"]._coll.insert_one(
        {
            "char_id": "char_hero_2",
            "owner_id": "user_123",
            "char_name": "Valeros",
        }
    )

    files = {"file": ("malicious.exe", io.BytesIO(b"NOT_AN_IMAGE"), "application/octet-stream")}
    response = test_client.post("/api/v1/characters/char_hero_2/portrait-upload", files=files)
    assert response.status_code == 400
    assert "image" in response.json()["detail"].lower()


def test_upload_character_portrait_not_found(test_client):
    files = {"file": ("hero.png", io.BytesIO(b"PNGDATA"), "image/png")}
    response = test_client.post("/api/v1/characters/non_existent/portrait-upload", files=files)
    assert response.status_code == 404
