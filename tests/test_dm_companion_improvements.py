from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from backend.core.homebrew_schemas import HomebrewEntity, HomebrewMonster
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------
# Feature 1: Fix Campaign Join Character ID Extraction
# ---------------------------------------------------------


def test_campaign_join_with_underscore_character_id_explicit(client):
    """Verify join succeeds when explicit character_id contains underscores."""
    mock_campaigns = MagicMock()
    mock_campaigns.find_one = AsyncMock(
        return_value={"campaign_name": "Underdark_Quest", "invite_code": "INVITE123"}
    )
    mock_campaigns.update_one = AsyncMock()

    mock_characters = MagicMock()
    mock_characters.find_one = AsyncMock(
        return_value={"char_id": "warrior_sub_999", "owner_id": "player_1"}
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
            json={
                "invite_code": "INVITE123",
                "char_filename": "thorin_warrior_sub_999.json",
                "character_id": "warrior_sub_999",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        mock_members.insert_one.assert_called_once()
        inserted_member = mock_members.insert_one.call_args[0][0]
        assert inserted_member["character_id"] == "warrior_sub_999"
        assert inserted_member["campaign_id"] == "Underdark_Quest"
    finally:
        app.dependency_overrides.clear()


def test_campaign_join_resolves_underscore_character_id_from_db(client):
    """Verify join safely resolves character ID with underscores when character_id is omitted."""
    mock_campaigns = MagicMock()
    mock_campaigns.find_one = AsyncMock(
        return_value={"campaign_name": "Underdark_Quest", "invite_code": "INVITE123"}
    )
    mock_campaigns.update_one = AsyncMock()

    async def mock_find_char(query):
        # query might be {"char_id": "...", "owner_id": "player_1"}
        if query.get("char_id") == "warrior_sub_999":
            return {"char_id": "warrior_sub_999", "owner_id": "player_1"}
        return None

    mock_characters = MagicMock()
    mock_characters.find_one = AsyncMock(side_effect=mock_find_char)
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
            json={
                "invite_code": "INVITE123",
                "char_filename": "thorin_oakenshield_warrior_sub_999.json",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        mock_members.insert_one.assert_called_once()
        inserted_member = mock_members.insert_one.call_args[0][0]
        assert inserted_member["character_id"] == "warrior_sub_999"
    finally:
        app.dependency_overrides.clear()


def test_add_party_member_with_explicit_character_id(client):
    """Verify DM adding character with explicit character_id containing underscores."""
    mock_campaigns = MagicMock()
    mock_campaigns.find_one = AsyncMock(return_value={"campaign_name": "MyCampaign"})
    mock_campaigns.update_one = AsyncMock()

    mock_characters = MagicMock()
    mock_characters.find_one = AsyncMock(
        return_value={"char_id": "npc_guard_captain_1", "owner_id": "dm_user"}
    )
    mock_characters.update_one = AsyncMock()

    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(
        return_value={"campaign_id": "MyCampaign", "user_id": "dm_user", "role": "dm"}
    )

    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_user", "username": "dm"}
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_campaigns,
        "characters": mock_characters,
        "campaign_members": mock_members,
    }

    try:
        response = client.post(
            "/api/v1/campaigns/MyCampaign/party/members",
            json={
                "char_filename": "guard_npc_guard_captain_1.json",
                "character_id": "npc_guard_captain_1",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_characters.update_one.assert_called_once()
        assert mock_characters.update_one.call_args[0][0]["char_id"] == "npc_guard_captain_1"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------
# Feature 3: Homebrew Monster Support
# ---------------------------------------------------------


def test_homebrew_monster_schema_validation():
    """Verify HomebrewMonster schema and polymorphic HomebrewEntity validation."""
    monster_data = {
        "campaign_id": "CurseOfStrahd",
        "creator_dm_id": "dm_123",
        "name": "Barovian Shadow Wolf",
        "homebrew_type": "monster",
        "size": "Large",
        "type": "beast",
        "alignment": "neutral evil",
        "cr": "3",
        "ac": 14,
        "hp": 45,
        "speed": "40 ft.",
        "stats": {"str": 16, "dex": 14, "con": 15, "int": 6, "wis": 12, "cha": 8},
        "traits": [
            {
                "name": "Pack Tactics",
                "description": "Advantage on attack rolls if ally within 5 ft.",
            }
        ],
        "actions": [{"name": "Bite", "description": "+5 to hit, 2d6+3 piercing damage."}],
        "senses": "Darkvision 60 ft., passive Perception 13",
        "languages": "Understands Abyssal but cannot speak",
        "description": "A terrifying wolf shrouded in necrotic fog.",
    }

    monster = HomebrewMonster(**monster_data)
    assert monster.name == "Barovian Shadow Wolf"
    assert monster.homebrew_type == "monster"
    assert monster.stats["str"] == 16
    assert monster.ac == 14
    assert len(monster.actions) == 1

    # Discriminated union validation
    entity = TypeAdapter(HomebrewEntity).validate_python(monster_data)
    assert isinstance(entity, HomebrewMonster)


def test_homebrew_monster_creation_endpoint(client):
    """Verify creating a monster homebrew via the API router."""
    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(
        return_value={"campaign_id": "CurseOfStrahd", "user_id": "dm_1", "role": "dm"}
    )
    mock_homebrew = MagicMock()
    mock_homebrew.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id=ObjectId("507f1f77bcf86cd799439011"))
    )

    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_1", "username": "dm"}
    app.dependency_overrides[get_database] = lambda: {
        "campaign_members": mock_members,
        "homebrew_content": mock_homebrew,
    }

    try:
        response = client.post(
            "/api/v1/campaigns/CurseOfStrahd/homebrew",
            json={
                "type": "monster",
                "data": {
                    "name": "Barovian Gargoyle",
                    "size": "Medium",
                    "type": "elemental",
                    "cr": 2,
                    "ac": 15,
                    "hp": 52,
                    "speed": "30 ft., fly 60 ft.",
                    "stats": {"str": 15, "dex": 11, "con": 16, "int": 6, "wis": 11, "cha": 7},
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_homebrew.insert_one.assert_called_once()
        inserted_doc = mock_homebrew.insert_one.call_args[0][0]
        assert inserted_doc["homebrew_type"] == "monster"
        assert inserted_doc["name"] == "Barovian Gargoyle"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------
# Feature 4: Direct DM Loot & Currency Award Endpoint
# ---------------------------------------------------------


def test_distribute_loot_forbidden_for_players(client):
    """Verify loot distribution is forbidden for non-DM members."""
    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(
        return_value={"campaign_id": "DragonHeist", "user_id": "player_1", "role": "player"}
    )

    app.dependency_overrides[get_current_user] = lambda: {"id": "player_1", "username": "player"}
    app.dependency_overrides[get_database] = lambda: {
        "campaign_members": mock_members,
    }

    try:
        response = client.post(
            "/api/v1/campaigns/DragonHeist/loot/distribute",
            json={
                "character_ids": ["hero_1"],
                "currency": {"gp": 100},
            },
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_distribute_loot_currency_and_items(client):
    """Verify DM distributing currency and equipment to characters."""
    mock_camp = MagicMock()
    mock_camp.find_one = AsyncMock(return_value={"campaign_name": "DragonHeist"})

    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(
        return_value={"campaign_id": "DragonHeist", "user_id": "dm_1", "role": "dm"}
    )

    mock_chars = MagicMock()
    # Characters exist
    char_docs = {
        "char_1": {
            "char_id": "char_1",
            "char_name": "Fighter",
            "active_campaign": "DragonHeist",
            "currency": {"cp": 0, "sp": 0, "ep": 0, "gp": 50, "pp": 0},
            "equipment": [],
            "weapons": [],
            "version": 1,
        },
        "char_2": {
            "char_id": "char_2",
            "char_name": "Rogue",
            "active_campaign": "DragonHeist",
            "currency": {"cp": 10, "sp": 5, "ep": 0, "gp": 20, "pp": 1},
            "equipment": [],
            "weapons": [],
            "version": 1,
        },
    }

    async def mock_find_one(query):
        cid = query.get("char_id")
        return char_docs.get(cid)

    mock_chars.find_one = AsyncMock(side_effect=mock_find_one)
    mock_chars.update_one = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_1", "username": "dm"}
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_camp,
        "campaign_members": mock_members,
        "characters": mock_chars,
    }

    try:
        response = client.post(
            "/api/v1/campaigns/DragonHeist/loot/distribute",
            json={
                "character_ids": ["char_1", "char_2"],
                "currency": {"gp": 100, "pp": 2},
                "split_currency": True,
                "items": [
                    {"name": "Potion of Healing", "type": "item", "description": "Heals 2d4+2 HP"}
                ],
                "reason": "Defeated the Goblin Boss",
            },
        )
        assert response.status_code == 200
        res = response.json()
        assert res["success"] is True
        assert res["currency_awarded"] == {"pp": 1, "gp": 50, "ep": 0, "sp": 0, "cp": 0}
        assert "Potion of Healing" in res["items_awarded"]

        # Verify update_one was called for both characters
        assert mock_chars.update_one.call_count == 2
        calls = mock_chars.update_one.call_args_list

        for call in calls:
            update_op = call[0][1]
            assert "$inc" in update_op
            assert update_op["$inc"]["currency.gp"] == 50
            assert update_op["$inc"]["currency.pp"] == 1
            assert update_op["$inc"]["version"] == 1
            assert "$push" in update_op
            assert "equipment" in update_op["$push"]
    finally:
        app.dependency_overrides.clear()


def test_distribute_loot_rejects_empty_recipients(client):
    """Verify endpoint rejects distribution with empty character list."""
    mock_camp = MagicMock()
    mock_camp.find_one = AsyncMock(return_value={"campaign_name": "DragonHeist"})
    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(
        return_value={"campaign_id": "DragonHeist", "user_id": "dm_1", "role": "dm"}
    )

    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_1", "username": "dm"}
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_camp,
        "campaign_members": mock_members,
    }

    try:
        response = client.post(
            "/api/v1/campaigns/DragonHeist/loot/distribute",
            json={
                "character_ids": [],
                "currency": {"gp": 50},
            },
        )
        assert response.status_code == 400
        assert "At least one character" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_campaign_join_with_character_id_only(client):
    """Verify campaign join works when char_filename is omitted and character_id is provided."""
    mock_camp = MagicMock()
    mock_camp.find_one = AsyncMock(
        return_value={"campaign_name": "DragonHeist", "invite_code": "CODE123"}
    )
    mock_camp.update_one = AsyncMock()

    mock_chars = MagicMock()
    mock_chars.find_one = AsyncMock(
        return_value={"char_id": "hero_und_123", "char_name": "Gimli", "owner_id": "player_1"}
    )
    mock_chars.update_one = AsyncMock()

    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(return_value=None)
    mock_members.insert_one = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: {"id": "player_1", "username": "player"}
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_camp,
        "characters": mock_chars,
        "campaign_members": mock_members,
    }

    try:
        response = client.post(
            "/api/v1/campaigns/join",
            json={
                "invite_code": "CODE123",
                "character_id": "hero_und_123",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Check party was populated with a valid string filename, not None!
        mock_camp.update_one.assert_called_once()
        party_add = mock_camp.update_one.call_args[0][1]["$addToSet"]["party"]
        assert party_add == "gimli_hero_und_123.json"
    finally:
        app.dependency_overrides.clear()


def test_character_id_precedence_prioritizes_longer_suffix_over_short(client):
    """Verify that when a user owns both 'archer' and 'elven_archer', 'legolas_elven_archer.json' matches 'elven_archer'."""
    mock_camp = MagicMock()
    mock_camp.find_one = AsyncMock(
        return_value={"campaign_name": "DragonHeist", "invite_code": "ELVEN123"}
    )
    mock_camp.update_one = AsyncMock()

    owned_characters = {
        "archer": {"char_id": "archer", "char_name": "Basic Archer", "owner_id": "p1"},
        "elven_archer": {"char_id": "elven_archer", "char_name": "Legolas", "owner_id": "p1"},
    }

    async def mock_find_char(query):
        cid = query.get("char_id")
        return owned_characters.get(cid)

    mock_chars = MagicMock()
    mock_chars.find_one = AsyncMock(side_effect=mock_find_char)
    mock_chars.update_one = AsyncMock()

    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(return_value=None)
    mock_members.insert_one = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: {"id": "p1", "username": "player"}
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_camp,
        "characters": mock_chars,
        "campaign_members": mock_members,
    }

    try:
        response = client.post(
            "/api/v1/campaigns/join",
            json={
                "invite_code": "ELVEN123",
                "char_filename": "legolas_elven_archer.json",
            },
        )
        assert response.status_code == 200
        mock_members.insert_one.assert_called_once()
        assert mock_members.insert_one.call_args[0][0]["character_id"] == "elven_archer"
    finally:
        app.dependency_overrides.clear()


def test_distribute_loot_rejects_empty_loot(client):
    """Verify endpoint rejects distribution when both currency and items are empty."""
    mock_camp = MagicMock()
    mock_camp.find_one = AsyncMock(return_value={"campaign_name": "DragonHeist"})
    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(
        return_value={"campaign_id": "DragonHeist", "user_id": "dm_1", "role": "dm"}
    )

    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_1", "username": "dm"}
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_camp,
        "campaign_members": mock_members,
    }

    try:
        response = client.post(
            "/api/v1/campaigns/DragonHeist/loot/distribute",
            json={
                "character_ids": ["hero_1"],
                "currency": {"gp": 0, "sp": 0},
                "items": [],
            },
        )
        assert response.status_code == 400
        assert "At least one currency amount or item" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_distribute_loot_cross_campaign_isolation(client):
    """Verify characters belonging to other campaigns do not receive loot."""
    mock_camp = MagicMock()
    mock_camp.find_one = AsyncMock(return_value={"campaign_name": "DragonHeist"})
    mock_members = MagicMock()
    mock_members.find_one = AsyncMock(
        return_value={"campaign_id": "DragonHeist", "user_id": "dm_1", "role": "dm"}
    )

    # hero_other belongs to StrahdCampaign, not DragonHeist
    mock_chars = MagicMock()
    mock_chars.find_one = AsyncMock(
        return_value={
            "char_id": "hero_other",
            "char_name": "Lost Paladin",
            "active_campaign": "StrahdCampaign",
            "currency": {"gp": 10},
        }
    )
    mock_chars.update_one = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: {"id": "dm_1", "username": "dm"}
    app.dependency_overrides[get_database] = lambda: {
        "campaigns": mock_camp,
        "campaign_members": mock_members,
        "characters": mock_chars,
    }

    try:
        response = client.post(
            "/api/v1/campaigns/DragonHeist/loot/distribute",
            json={
                "character_ids": ["hero_other"],
                "currency": {"gp": 50},
            },
        )
        assert response.status_code == 200
        # Character did not receive loot because it is in a different campaign
        assert response.json()["recipients"] == []
        mock_chars.update_one.assert_not_called()
    finally:
        app.dependency_overrides.clear()
