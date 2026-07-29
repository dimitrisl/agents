from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
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
