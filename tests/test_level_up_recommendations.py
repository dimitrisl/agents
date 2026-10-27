from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014
from backend.services.forge_service import generate_level_up_build_recommendations
from server.main import app


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def sample_fighter():
    return {
        "char_name": "Valeros",
        "char_class": "Fighter",
        "char_level": 3,
        "race": "Human",
        "background": "Soldier",
        "alignment": "Neutral Good",
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        "hit_dice": "d10",
        "hp_max": 28,
        "proficiency_bonus": 2,
        "features_traits": [],
        "equipment": [{"name": "Longsword"}],
        "spells": {"cantrips": []},
    }


def test_generate_level_up_build_recommendations_fallback(sample_fighter):
    with patch(
        "backend.services.forge_service.generate_ai_json", side_effect=Exception("API down")
    ):
        recs = generate_level_up_build_recommendations(
            sample_fighter, target_class="Fighter", target_level=4
        )
        assert recs["character_name"] == "Valeros"
        assert recs["target_class"] == "Fighter"
        assert recs["target_level"] == 4
        assert len(recs["builds"]) == 3

        for b in recs["builds"]:
            assert "build_name" in b
            assert "theme" in b
            assert "playstyle_summary" in b
            assert len(b["pros"]) > 0
            assert len(b["cons"]) > 0
            assert b["recommended_feat_or_asi"] is not None  # Level 4 has ASI
            assert (
                b["recommended_subclass"] is not None
            )  # Subclass needed for lvl 4 fighter without one


def test_generate_level_up_build_recommendations_with_ai(sample_fighter):
    mock_ai_json = {
        "builds": [
            {
                "build_name": "Champion of the Forge",
                "theme": "Crit-fishing bruiser",
                "playstyle_summary": "Charge into battle and take advantage of expanded crit range.",
                "pros": ["High critical hit chance", "Simple and effective"],
                "cons": ["Limited tactical utility"],
                "recommended_subclass": "Champion",
                "recommended_feat_or_asi": "Great Weapon Master",
                "recommended_spells": [],
                "key_tactics": ["Flank enemies for advantage"],
            }
        ]
    }

    with patch("backend.services.forge_service.generate_ai_json", return_value=mock_ai_json):
        recs = generate_level_up_build_recommendations(
            sample_fighter, target_class="Fighter", target_level=4
        )
        assert len(recs["builds"]) == 1
        assert recs["builds"][0]["build_name"] == "Champion of the Forge"
        assert recs["builds"][0]["recommended_subclass"] == "Champion"
        assert recs["builds"][0]["recommended_feat_or_asi"] == "Great Weapon Master"


def test_level_up_recommendations_endpoint(test_client, sample_fighter):
    from server.dependencies.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test_user_id",
        "username": "testuser",
    }

    with patch(
        "backend.services.forge_service.generate_ai_json", side_effect=Exception("Fast fallback")
    ):
        try:
            response = test_client.post(
                "/api/v1/forge/level-up-recommendations",
                json={
                    "character": sample_fighter,
                    "target_class": "Fighter",
                    "target_level": 4,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["character_name"] == "Valeros"
            assert data["target_level"] == 4
            assert len(data["builds"]) == 3
        finally:
            app.dependency_overrides.pop(get_current_user, None)
