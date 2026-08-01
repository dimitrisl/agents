from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from server.dependencies.auth import get_current_user
from server.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "Phyrexian Forge API" in data["system"]


def test_auth_registration_and_login(mocker):
    # Create AsyncMock for Motor's coroutine methods
    mock_users_col = MagicMock()
    mock_users_col.find_one = AsyncMock(return_value=None)
    mock_users_col.insert_one = AsyncMock(return_value=MagicMock())

    mock_db = {"users": mock_users_col}
    mocker.patch("server.routers.auth_router.get_database", return_value=mock_db)

    # Test Registration
    reg_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_adventurer",
            "password": "securepassword123",
            "email": "test@example.com",
            "name": "Test Hero",
        },
    )
    assert reg_response.status_code == 201
    user_data = reg_response.json()
    assert user_data["username"] == "test_adventurer"
    assert "id" in user_data

    # Test Demo Login
    demo_response = client.post(
        "/api/v1/auth/demo",
        json={"demo_type": "mitsos"},
    )
    assert demo_response.status_code == 200
    assert "access_token" in demo_response.json()


def test_character_routes(mocker):
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user_123",
        "username": "hero",
    }

    try:
        mock_chars_col = MagicMock()

        # Async cursor for list_characters
        class AsyncCursor:
            def __init__(self, data):
                self.data = data
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index < len(self.data):
                    item = self.data[self.index]
                    self.index += 1
                    return item
                else:
                    raise StopAsyncIteration

        sample_char = {
            "char_id": "test_123",
            "owner_id": "user_123",
            "char_name": "Test Paladin",
            "char_class": "Paladin",
            "char_level": 5,
            "race": "Human",
            "background": "Soldier",
            "armor_class": 18,
            "hp_max": 44,
            "speed": 30,
            "proficiency_bonus": 3,
            "stats": {"STR": 18, "DEX": 12, "CON": 15, "INT": 10, "WIS": 14, "CHA": 16},
        }

        mock_chars_col.find.return_value = AsyncCursor([sample_char])
        mock_chars_col.find_one = AsyncMock(return_value=sample_char.copy())
        mock_chars_col.update_one = AsyncMock(return_value=MagicMock())
        mock_chars_col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))

        mock_db = {"characters": mock_chars_col}
        mocker.patch("server.routers.character_router.get_database", return_value=mock_db)

        # 1. List characters
        response = client.get("/api/v1/characters/")
        assert response.status_code == 200
        chars = response.json()
        assert len(chars) == 1
        assert chars[0]["char_name"] == "Test Paladin"

        # 2. Get single character
        response = client.get("/api/v1/characters/test_123")
        assert response.status_code == 200
        assert response.json()["char_id"] == "test_123"

        # 3. Delete character
        response = client.delete("/api/v1/characters/test_123")
        assert response.status_code == 200
        assert response.json()["success"] is True
    finally:
        app.dependency_overrides.clear()


def test_rules_router(mocker):
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user_123",
        "username": "hero",
    }

    try:
        mocker.patch(
            "server.routers.rules_router.query_rules",
            return_value="Grappling requires an Athletics check vs Athletics/Acrobatics.",
        )
        mocker.patch(
            "server.routers.rules_router.compare_rules",
            return_value="2024 Revision simplifies Grappling to a Saving Throw.",
        )
        mocker.patch(
            "server.routers.rules_router.deterministic_validate_build",
            return_value={"valid": True, "errors": []},
        )

        # 1. Oracle query
        response = client.post(
            "/api/v1/rules/query",
            json={"query": "How to grapple?", "edition": "2014 Edition"},
        )
        assert response.status_code == 200
        assert "Athletics check" in response.json()["answer_markdown"]

        # 2. Rules comparison
        response = client.post("/api/v1/rules/compare", json={"query": "Grapple rules"})
        assert response.status_code == 200
        assert "Saving Throw" in response.json()["comparison_markdown"]

        # 3. Rules validation
        response = client.post(
            "/api/v1/rules/validate", json={"character": {"char_name": "Valeros"}}
        )
        assert response.status_code == 200
        assert response.json()["validation_result"]["is_valid"] is True
    finally:
        app.dependency_overrides.clear()


def test_dm_router(mocker):
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user_123",
        "username": "dm",
    }

    try:
        mocker.patch(
            "server.routers.dm_router.generate_npc",
            return_value="### Sir Tristan\nValiant Knight",
        )
        mocker.patch(
            "server.routers.dm_router.generate_riddle",
            return_value="What speaks without a mouth?",
        )

        # 1. NPC Generation
        response = client.post(
            "/api/v1/dm/npc",
            json={"npc_concept": "Paladin Knight", "edition": "2014 Edition"},
        )
        assert response.status_code == 200
        assert "Sir Tristan" in response.json()["npc_markdown"]

        # 2. Riddle Generation
        response = client.post(
            "/api/v1/dm/riddle", json={"location": "Crypt", "edition": "2014 Edition"}
        )
        assert response.status_code == 200
        assert "speaks without a mouth" in response.json()["riddle_markdown"]
    finally:
        app.dependency_overrides.clear()
