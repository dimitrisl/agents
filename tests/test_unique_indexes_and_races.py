from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from server.db_async import INDEX_DEFINITIONS, get_database, init_indexes
from server.dependencies.auth import get_current_user
from server.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_index_definitions_completeness():
    """Verify that all required unique and query performance indexes are defined."""
    defined_specs = {coll: [] for coll, _, _ in INDEX_DEFINITIONS}
    for coll, keys, kwargs in INDEX_DEFINITIONS:
        defined_specs[coll].append((keys, kwargs))

    # 1. users: unique username and unique id
    user_specs = defined_specs.get("users", [])
    assert any(
        keys == [("username", 1)] and kwargs.get("unique") is True for keys, kwargs in user_specs
    )
    assert any(keys == [("id", 1)] and kwargs.get("unique") is True for keys, kwargs in user_specs)

    # 2. campaigns: unique campaign_name
    camp_specs = defined_specs.get("campaigns", [])
    assert any(
        keys == [("campaign_name", 1)] and kwargs.get("unique") is True
        for keys, kwargs in camp_specs
    )

    # 3. campaign_members: compound unique (campaign_id, user_id)
    member_specs = defined_specs.get("campaign_members", [])
    assert any(
        keys == [("campaign_id", 1), ("user_id", 1)] and kwargs.get("unique") is True
        for keys, kwargs in member_specs
    )

    # 4. characters: unique char_id, query indexes on owner_id, active_campaign, (char_id, owner_id)
    char_specs = defined_specs.get("characters", [])
    assert any(
        keys == [("char_id", 1)] and kwargs.get("unique") is True for keys, kwargs in char_specs
    )
    assert any(keys == [("owner_id", 1)] for keys, kwargs in char_specs)
    assert any(keys == [("active_campaign", 1)] for keys, kwargs in char_specs)
    assert any(keys == [("char_id", 1), ("owner_id", 1)] for keys, kwargs in char_specs)

    # 5. campaign_entities: query index on campaign_name
    entity_specs = defined_specs.get("campaign_entities", [])
    assert any(keys == [("campaign_name", 1)] for keys, kwargs in entity_specs)

    # 6. session_logs: compound query index on (campaign_name ASC, session_number DESC)
    session_specs = defined_specs.get("session_logs", [])
    assert any(
        keys == [("campaign_name", 1), ("session_number", -1)] for keys, kwargs in session_specs
    )


@pytest.mark.anyio
async def test_init_indexes_defensive_error_handling():
    """Verify that if one index creation fails, it is caught and does not crash the server startup."""
    mock_db = MagicMock()
    mock_coll = MagicMock()

    # Fail on first call (e.g. duplicate key in pre-existing data), succeed on subsequent calls
    mock_coll.create_index = AsyncMock(
        side_effect=[
            Exception("E11000 duplicate key error collection"),
            None,
        ]
        + [None] * (len(INDEX_DEFINITIONS) - 2)
    )
    mock_db.__getitem__.return_value = mock_coll

    # Must complete without throwing an unhandled exception
    await init_indexes(mock_db)
    assert mock_coll.create_index.call_count == len(INDEX_DEFINITIONS)


def test_auth_registration_duplicate_key_error_handled(client):
    """Verify that DuplicateKeyError during user registration returns HTTP 400, not 500."""
    mock_users = MagicMock()
    # find_one returns None (simulating race where pre-check didn't catch the collision)
    mock_users.find_one = AsyncMock(return_value=None)
    mock_users.insert_one = AsyncMock(
        side_effect=DuplicateKeyError("E11000 duplicate key error on users.username")
    )

    app.dependency_overrides[get_database] = lambda: {"users": mock_users}
    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "collision_user",
                "password": "Password123!",
                "email": "collision@example.com",
            },
        )
        assert response.status_code == 400
        assert "Username already registered." in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_campaign_creation_duplicate_key_error_handled(client):
    """Verify that DuplicateKeyError during campaign creation returns HTTP 409 Conflict, not 500."""
    mock_campaigns = MagicMock()
    mock_campaigns.find_one = AsyncMock(return_value=None)
    mock_campaigns.insert_one = AsyncMock(
        side_effect=DuplicateKeyError("E11000 duplicate key error on campaigns.campaign_name")
    )
    mock_members = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "dm_user_1",
        "username": "dm_user",
    }
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_campaigns,
        "campaign_members": mock_members,
    }
    try:
        response = client.post(
            "/api/v1/campaigns/",
            json={"campaign_name": "Phyrexian Invasion", "notes": "Dark campaign"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_campaign_join_existing_member_handled(client):
    """Verify that joining an already-joined campaign returns HTTP 409 Conflict, not 500."""
    mock_campaigns = MagicMock()
    mock_campaigns.find_one = AsyncMock(
        return_value={"campaign_name": "Phyrexian Invasion", "invite_code": "CODE123"}
    )
    mock_characters = MagicMock()
    mock_characters.find_one = AsyncMock(
        return_value={"char_id": "char_999", "owner_id": "player_1"}
    )
    mock_members = MagicMock()
    # Member is already in campaign
    mock_members.find_one = AsyncMock(
        return_value={"campaign_id": "Phyrexian Invasion", "user_id": "player_1"}
    )

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "player_1",
        "username": "player_one",
    }
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_campaigns,
        "characters": mock_characters,
        "campaign_members": mock_members,
    }
    try:
        response = client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": "CODE123", "char_filename": "hero_char_999.json"},
        )
        assert response.status_code == 409
        assert "already a member" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_campaign_join_duplicate_key_error_handled(client):
    """Verify that DuplicateKeyError during join (race condition) returns HTTP 409 Conflict, not 500."""
    mock_campaigns = MagicMock()
    mock_campaigns.find_one = AsyncMock(
        return_value={"campaign_name": "Phyrexian Invasion", "invite_code": "CODE123"}
    )
    mock_campaigns.update_one = AsyncMock()
    mock_characters = MagicMock()
    mock_characters.find_one = AsyncMock(
        return_value={"char_id": "char_999", "owner_id": "player_1"}
    )
    mock_characters.update_one = AsyncMock()
    mock_members = MagicMock()
    # Pre-check didn't see member yet
    mock_members.find_one = AsyncMock(return_value=None)
    # Concurrent insert raises DuplicateKeyError
    mock_members.insert_one = AsyncMock(
        side_effect=DuplicateKeyError(
            "E11000 duplicate key error on campaign_members compound index"
        )
    )

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "player_1",
        "username": "player_one",
    }
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_campaigns,
        "characters": mock_characters,
        "campaign_members": mock_members,
    }
    try:
        response = client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": "CODE123", "char_filename": "hero_char_999.json"},
        )
        assert response.status_code == 409
        assert "already a member" in response.json()["detail"]
        # Verify no database state pollution occurred: party and character were untouched
        mock_campaigns.update_one.assert_not_called()
        mock_characters.update_one.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_campaign_join_success_updates_party_and_character(client):
    """Verify that a successful join updates campaign party, character active_campaign, and creates member."""
    mock_campaigns = MagicMock()
    mock_campaigns.find_one = AsyncMock(
        return_value={"campaign_name": "Phyrexian Invasion", "invite_code": "CODE123"}
    )
    mock_campaigns.update_one = AsyncMock()
    mock_characters = MagicMock()
    mock_characters.find_one = AsyncMock(
        return_value={"char_id": "char_999", "owner_id": "player_1"}
    )
    mock_characters.update_one = AsyncMock()
    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(return_value=None)
    mock_members.insert_one = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "player_1",
        "username": "player_one",
    }
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_campaigns,
        "characters": mock_characters,
        "campaign_members": mock_members,
    }
    try:
        response = client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": "CODE123", "char_filename": "hero_char_999.json"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify membership was created
        mock_members.insert_one.assert_called_once()
        inserted_member = mock_members.insert_one.call_args[0][0]
        assert inserted_member["campaign_id"] == "Phyrexian Invasion"
        assert inserted_member["user_id"] == "player_1"
        assert inserted_member["role"] == "player"
        assert inserted_member["character_id"] in ("char_999", "999")

        # Verify party and character active_campaign were updated
        mock_campaigns.update_one.assert_called_once()
        mock_characters.update_one.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_demo_login_race_duplicate_key_error_handled(client, monkeypatch):
    """Verify that DuplicateKeyError during demo user creation does not break the login flow."""
    from server.config import settings

    monkeypatch.setattr(settings, "DEBUG_MODE", True)

    mock_users = MagicMock()
    # User does not exist initially
    mock_users.find_one = AsyncMock(return_value=None)
    # Concurrent insert by another worker raises DuplicateKeyError
    mock_users.insert_one = AsyncMock(
        side_effect=DuplicateKeyError("E11000 duplicate key error on users.id")
    )

    app.dependency_overrides[get_database] = lambda: {"users": mock_users}
    try:
        response = client.post(
            "/api/v1/auth/demo",
            json={"demo_type": "mitsos"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["username"] == "mitsos"
    finally:
        app.dependency_overrides.clear()


def test_campaign_creation_member_collision_fallback(client):
    """Verify that if campaign_members.insert_one raises DuplicateKeyError (stale member doc), it updates role to dm."""
    mock_campaigns = MagicMock()
    mock_campaigns.find_one = AsyncMock(return_value=None)
    mock_campaigns.insert_one = AsyncMock()
    mock_members = MagicMock()
    # Member insert collides
    mock_members.insert_one = AsyncMock(
        side_effect=DuplicateKeyError("E11000 duplicate key on campaign_members")
    )
    mock_members.update_one = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "dm_user_1",
        "username": "dm_user",
    }
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_campaigns,
        "campaign_members": mock_members,
    }
    try:
        response = client.post(
            "/api/v1/campaigns/",
            json={"campaign_name": "Phyrexian Invasion", "notes": "Dark campaign"},
        )
        assert response.status_code == 200
        mock_campaigns.insert_one.assert_called_once()
        # Fallback update to role 'dm' was invoked
        mock_members.update_one.assert_called_once_with(
            {"campaign_id": "Phyrexian Invasion", "user_id": "dm_user_1"},
            {"$set": {"role": "dm"}},
        )
    finally:
        app.dependency_overrides.clear()
