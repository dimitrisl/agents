from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db():
    db = MagicMock()

    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(return_value={"role": "dm", "user_id": "123"})
    db.__getitem__.side_effect = lambda key: (
        mock_members if key == "campaign_members" else MagicMock()
    )

    # Setup mock to_list for find
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[])
    db.session_logs.find.return_value = mock_cursor
    db.campaign_entities.find.return_value = mock_cursor

    db.session_logs.insert_one = AsyncMock(return_value=MagicMock(inserted_id="mock_session_id"))
    db.campaign_entities.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id="mock_entity_id")
    )
    return db


@pytest.fixture
def client(mock_db):
    from server.db_async import get_database
    from server.dependencies.auth import get_current_user
    from server.main import app

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {"username": "testdm", "id": "123"}

    with TestClient(app) as c:
        yield c


def test_generate_prep(client, mock_db):
    # This requires campaign role
    from server.dependencies.campaign import require_campaign_role

    def override_role():
        def _require(campaign_member: dict = None):
            return {"role": "dm"}

        return _require

    client.app.dependency_overrides[require_campaign_role] = override_role()
    client.app.dependency_overrides[require_campaign_role(["dm"])] = override_role()

    # Mock AI directly on the service instance
    from server.routers.session_router import session_service

    original_provider = session_service.ai_provider
    mock_provider_instance = MagicMock()
    mock_provider_instance.client = True
    mock_provider_instance.generate_json.return_value = {
        "strong_start": "Goblins attack!",
        "secrets_clues": ["The mayor is a vampire"],
        "encounters": ["3x Goblins"],
        "key_npcs": ["Mayor Bob"],
    }
    session_service.ai_provider = mock_provider_instance

    try:
        response = client.post(
            "/api/v1/campaigns/TestCamp/sessions/prep", json={"dm_ideas": "I want a dragon"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["strong_start"] == "Goblins attack!"
    finally:
        session_service.ai_provider = original_provider


def test_process_audio_session(client, mock_db):
    from server.dependencies.campaign import require_campaign_role

    def override_role():
        def _require(campaign_member: dict = None):
            return {"role": "dm"}

        return _require

    client.app.dependency_overrides[require_campaign_role] = override_role()

    from server.routers.session_router import session_service

    original_provider = session_service.ai_provider
    mock_provider_instance = MagicMock()
    mock_provider_instance.client = True
    mock_provider_instance.upload_file.return_value = "file_id_123"
    mock_provider_instance.generate_json_from_files.return_value = {
        "title": "The Goblin Cave",
        "summary": "They fought goblins.",
        "extracted_entities": [
            {"name": "Glarg", "type": "npc", "content": "Goblin boss", "tags": []}
        ],
    }
    session_service.ai_provider = mock_provider_instance

    try:
        with open("test_audio.txt", "w") as f:
            f.write("dummy audio content")

        with open("test_audio.txt", "rb") as f:
            response = client.post(
                "/api/v1/campaigns/TestCamp/sessions/audio",
                data={"session_number": 1},
                files={"audio_file": ("test_audio.txt", f, "text/plain")},
            )

        import os

        os.remove("test_audio.txt")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "The Goblin Cave"
        assert len(data["extracted_entities"]) == 1
    finally:
        session_service.ai_provider = original_provider
