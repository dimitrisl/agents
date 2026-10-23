import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services.character_import_service import (
    CharacterImportService,
    DndBeyondImportError,
)
from backend.utils.import_utils import FoundryImportError, import_vtt_character
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.rate_limiter import limiter
from server.routers.character_router import router

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def mock_db():
    db = MagicMock()
    db["characters"] = MagicMock()
    db["characters"].insert_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    db["characters"].update_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    db["characters"].replace_one = AsyncMock(return_value=MagicMock(acknowledged=True))
    db["characters"].find_one = AsyncMock(return_value=None)
    db["campaigns"] = MagicMock()
    db["campaigns"].find_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def test_client(mock_db):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "import_user_456",
        "username": "importer",
        "is_admin": False,
    }

    client = TestClient(app)
    return client


# ==============================================================
# D&D Beyond URL Extraction & Fetch Tests
# ==============================================================
def test_extract_ddb_character_id():
    # Plain numeric ID
    assert CharacterImportService.extract_dndbeyond_character_id("12345678") == "12345678"
    # Standard URL
    assert (
        CharacterImportService.extract_dndbeyond_character_id(
            "https://www.dndbeyond.com/characters/98765432"
        )
        == "98765432"
    )
    # URL with trailing slash or query
    assert (
        CharacterImportService.extract_dndbeyond_character_id(
            "https://dndbeyond.com/characters/11223344/"
        )
        == "11223344"
    )
    # Invalid URL
    with pytest.raises(DndBeyondImportError):
        CharacterImportService.extract_dndbeyond_character_id("https://evil.com/characters/12345")


# ==============================================================
# D&D Beyond Parsing Fixture Tests
# ==============================================================
def test_parse_dndbeyond_martial_fixture():
    path = os.path.join(FIXTURES_DIR, "dndbeyond", "martial_2014.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    char, warnings = CharacterImportService.parse_dndbeyond_character(data)
    assert char["char_name"] == "Krag the Barbarian"
    assert char["race"] == "Half-Orc"
    assert char["char_level"] == 5
    assert char["char_class"] == "Barbarian"
    assert len(char["classes"]) == 1
    assert char["classes"][0]["subclass"] == "Path of the Berserker"
    assert char["stats"]["STR"] == 16
    assert char["stats"]["DEX"] == 14
    assert char["stats"]["CON"] == 16
    assert "Athletics" in char["skill_proficiencies"]
    assert "Greataxe" in [w["name"] for w in char["weapons"]]


def test_parse_dndbeyond_caster_fixture():
    path = os.path.join(FIXTURES_DIR, "dndbeyond", "caster_2024.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    char, warnings = CharacterImportService.parse_dndbeyond_character(data)
    assert char["char_name"] == "Eldrin Moonshadow"
    assert char["char_class"] == "Wizard"
    assert char["char_level"] == 3
    assert "cantrips" in char["spells"]
    assert "Fire Bolt" in char["spells"]["cantrips"]
    assert "level_1" in char["spells"]
    assert "Magic Missile" in char["spells"]["level_1"]
    assert "Shield" in char["spells"]["level_1"]
    assert "level_2" in char["spells"]
    assert "Misty Step" in char["spells"]["level_2"]


def test_parse_dndbeyond_multiclass_fixture():
    path = os.path.join(FIXTURES_DIR, "dndbeyond", "multiclass.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    char, warnings = CharacterImportService.parse_dndbeyond_character(data)
    assert char["char_name"] == "Valen Shadowblade"
    assert char["char_level"] == 5
    assert len(char["classes"]) == 2
    class_names = [c["class_name"] for c in char["classes"]]
    assert "Rogue" in class_names
    assert "Fighter" in class_names
    assert "Stealth" in char["skill_expertise"]


# ==============================================================
# Foundry VTT Parsing Fixture Tests
# ==============================================================
def test_parse_foundry_v2_fixture():
    path = os.path.join(FIXTURES_DIR, "foundry", "actor_v2.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    char, warnings = import_vtt_character(data)
    assert char["char_name"] == "Thorne Ironbreaker"
    assert char["race"] == "Mountain Dwarf"
    assert char["char_level"] == 4
    assert len(char["classes"]) == 1
    assert char["classes"][0]["class_name"] == "Fighter"
    assert char["classes"][0]["subclass"] == "Battle Master"
    assert char["stats"]["STR"] == 18
    assert len(char["weapons"]) >= 1
    assert char["weapons"][0]["name"] == "Warhammer"


def test_parse_foundry_v3_multiclass_fixture():
    path = os.path.join(FIXTURES_DIR, "foundry", "actor_v3.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    char, warnings = import_vtt_character(data)
    assert char["char_name"] == "Lyra Whisperwind"
    assert char["race"] == "Wood Elf"
    assert char["background"] == "Entertainer"
    assert char["char_level"] == 4
    assert len(char["classes"]) == 2
    c_map = {c["class_name"]: c for c in char["classes"]}
    assert "Bard" in c_map and c_map["Bard"]["level"] == 3
    assert c_map["Bard"]["subclass"] == "College of Lore"
    assert "Sorcerer" in c_map and c_map["Sorcerer"]["level"] == 1
    assert "Performance" in char["skill_expertise"]
    assert "Vicious Mockery" in char["spells"]["cantrips"]
    assert "Invisibility" in char["spells"]["level_2"]


def test_parse_foundry_invalid_json():
    with pytest.raises(FoundryImportError):
        import_vtt_character("not a dict")  # type: ignore


# ==============================================================
# Endpoints Integration Tests
# ==============================================================
@patch.object(CharacterImportService, "fetch_dndbeyond_character")
def test_import_dndbeyond_endpoint(mock_fetch, test_client):
    path = os.path.join(FIXTURES_DIR, "dndbeyond", "martial_2014.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    mock_fetch.return_value = data

    res = test_client.post(
        "/characters/import-dndbeyond",
        json={"url_or_id": "https://www.dndbeyond.com/characters/1001"},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["char_name"] == "Krag the Barbarian"
    assert res_data["owner_id"] == "import_user_456"
    assert res_data["char_id"] is not None
    assert "warnings" in res_data
    # Check weapon damage auto-calculated
    assert any(w["name"] == "Greataxe" for w in res_data.get("weapons", []))


def test_import_foundry_endpoint(test_client):
    path = os.path.join(FIXTURES_DIR, "foundry", "actor_v3.json")
    with open(path, "rb") as f:
        file_bytes = f.read()

    res = test_client.post(
        "/characters/import-foundry",
        files={"file": ("actor.json", file_bytes, "application/json")},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["char_name"] == "Lyra Whisperwind"
    assert res_data["owner_id"] == "import_user_456"
    assert res_data["char_level"] == 4
    assert len(res_data["classes"]) == 2


def test_import_foundry_endpoint_rejects_non_json(test_client):
    res = test_client.post(
        "/characters/import-foundry",
        files={"file": ("actor.txt", b"plain text", "text/plain")},
    )
    assert res.status_code == 400
    assert "must be a JSON file" in res.json()["detail"]


def test_import_foundry_endpoint_rejects_corrupted_json(test_client):
    res = test_client.post(
        "/characters/import-foundry",
        files={"file": ("actor.json", b"{invalid json string...", "application/json")},
    )
    assert res.status_code == 400
    assert "invalid JSON" in res.json()["detail"]


def test_import_dndbeyond_rejects_invalid_url_and_ssrf(test_client):
    # Non-D&D Beyond domain (SSRF attempt)
    res = test_client.post(
        "/characters/import-dndbeyond",
        json={"url_or_id": "https://evil.com/characters/12345"},
    )
    assert res.status_code == 400
    assert "Invalid D&D Beyond character URL" in res.json()["detail"]

    # Localhost attempt
    res = test_client.post(
        "/characters/import-dndbeyond",
        json={"url_or_id": "http://localhost:8000/characters/12345"},
    )
    assert res.status_code == 400

    # Malformed URL
    res = test_client.post(
        "/characters/import-dndbeyond",
        json={"url_or_id": "not_a_valid_url_or_id"},
    )
    assert res.status_code == 400


def test_extract_ddb_character_id_profile_url():
    # Supports D&D Beyond profile URLs
    url = "https://www.dndbeyond.com/profile/CriticalRole/characters/99887766"
    assert CharacterImportService.extract_dndbeyond_character_id(url) == "99887766"


@patch.object(CharacterImportService, "fetch_dndbeyond_character")
def test_import_dndbeyond_returns_403_for_private_character(mock_fetch, test_client):
    from backend.services.character_import_service import DndBeyondPrivateError

    mock_fetch.side_effect = DndBeyondPrivateError("Character is Private on D&D Beyond.")
    res = test_client.post(
        "/characters/import-dndbeyond",
        json={"url_or_id": "https://www.dndbeyond.com/characters/12345"},
    )
    assert res.status_code == 403
    assert "Private" in res.json()["detail"]


@patch.object(CharacterImportService, "fetch_dndbeyond_character")
def test_import_dndbeyond_returns_404_for_not_found(mock_fetch, test_client):
    from backend.services.character_import_service import DndBeyondNotFoundError

    mock_fetch.side_effect = DndBeyondNotFoundError("Character not found on D&D Beyond.")
    res = test_client.post(
        "/characters/import-dndbeyond",
        json={"url_or_id": "https://www.dndbeyond.com/characters/99999999"},
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


@patch.object(CharacterImportService, "fetch_dndbeyond_character")
def test_import_dndbeyond_returns_502_for_upstream_error(mock_fetch, test_client):
    from backend.services.character_import_service import DndBeyondUpstreamError

    mock_fetch.side_effect = DndBeyondUpstreamError("D&D Beyond service error (HTTP 500).")
    res = test_client.post(
        "/characters/import-dndbeyond",
        json={"url_or_id": "https://www.dndbeyond.com/characters/12345"},
    )
    assert res.status_code == 502
    assert "service error" in res.json()["detail"].lower()
