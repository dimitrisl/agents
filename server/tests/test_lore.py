from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app

client = TestClient(app)


@pytest.fixture
def mock_db():
    db = MagicMock()
    # Mock collections
    db["campaigns"].find_one = AsyncMock(return_value={"campaign_name": "test_camp", "party": []})
    db["campaign_entities"].insert_one = AsyncMock(
        return_value=MagicMock(inserted_id="60a8b9f7a73a3c20c0341234")
    )

    # Setup mock to_list for find
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(
        return_value=[
            {
                "_id": "60a8b9f7a73a3c20c0341234",
                "campaign_name": "test_camp",
                "name": "Bbeg",
                "type": "villain",
                "content": "Evil guy",
                "tags": [],
            }
        ]
    )
    db["campaign_entities"].find.return_value = mock_cursor
    db["campaign_members"].find_one = AsyncMock(
        return_value={"campaign_id": "test_camp", "user_id": "dm_id", "role": "dm"}
    )

    app.dependency_overrides[get_database] = lambda: db

    # Mock auth overrides
    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_id", "username": "dm_user"}

    yield db

    app.dependency_overrides.clear()


def test_get_campaign_entities(mock_db):
    response = client.get("/api/v1/campaigns/test_camp/entities")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Bbeg"
    assert data[0]["id"] == "60a8b9f7a73a3c20c0341234"


def test_create_campaign_entity(mock_db):
    response = client.post(
        "/api/v1/campaigns/test_camp/entities",
        json={
            "campaign_name": "test_camp",
            "name": "Bbeg",
            "type": "villain",
            "content": "Evil guy",
            "tags": [],
            "stats": {},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Bbeg"
    assert data["id"] == "60a8b9f7a73a3c20c0341234"


def test_extract_campaign_entity(mock_db, mocker):
    mocker.patch(
        "backend.services.lore_service.generate_ai_json",
        return_value={
            "name": "Goblin Chief",
            "type": "npc",
            "content": "He rules the cave.",
            "tags": ["goblin", "boss"],
            "stats": {"hp": 50, "ac": 16},
        },
    )

    response = client.post(
        "/api/v1/campaigns/test_camp/entities/extract",
        json={"raw_text": "Goblin chief with 50 hp and 16 ac. He rules the cave."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Goblin Chief"
    assert data["type"] == "npc"
    assert data["tags"] == ["goblin", "boss"]
