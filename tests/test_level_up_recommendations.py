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


def test_level_up_recommendations_level_5_wizard():
    wizard = {
        "char_name": "Elminster",
        "char_class": "Wizard",
        "char_level": 5,
        "subclass": "Evocation",
        "race": "Human",
        "background": "Sage",
        "alignment": "Neutral Good",
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 10, "DEX": 14, "CON": 14, "INT": 18, "WIS": 12, "CHA": 10},
        "hit_dice": "d6",
        "hp_max": 32,
        "features_traits": [],
        "equipment": [{"name": "Staff"}],
        "spells": {"level_1": ["Magic Missile", "Shield"], "level_2": ["Misty Step"]},
    }

    with patch(
        "backend.services.forge_service.generate_ai_json", side_effect=Exception("API down")
    ):
        recs = generate_level_up_build_recommendations(
            wizard, target_class="Wizard", target_level=6
        )
        assert recs["target_level"] == 6
        assert len(recs["builds"]) == 3

        for b in recs["builds"]:
            ms = b["future_milestones"]
            assert len(ms) >= 3
            # Crucial: milestones MUST start at level 6, NOT level 10!
            assert any("Level 6:" in m for m in ms)
            assert any("Level 7:" in m for m in ms)
            assert any("Level 8:" in m for m in ms)
            assert not any("Level 1:" in m for m in ms)
            # Level 8 must be an ASI milestone
            lvl_8_ms = [m for m in ms if "Level 8:" in m]
            assert any("ASI" in m or "Feat" in m for m in lvl_8_ms)


def test_level_up_recommendations_level_17_ranger():
    ranger = {
        "char_name": "Ulad Bhor",
        "char_class": "Ranger",
        "char_level": 17,
        "subclass": "Horizon Walker",
        "race": "Wood Elf",
        "background": "Outlander",
        "alignment": "Chaotic Good",
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 10, "DEX": 20, "CON": 16, "INT": 12, "WIS": 16, "CHA": 8},
        "hit_dice": "d10",
        "hp_max": 145,
        "features_traits": [],
        "equipment": [{"name": "Longbow +1"}],
        "spells": {"level_1": ["Zephyr Strike"], "level_4": ["Freedom of Movement"]},
    }

    with patch(
        "backend.services.forge_service.generate_ai_json", side_effect=Exception("API down")
    ):
        recs = generate_level_up_build_recommendations(
            ranger, target_class="Ranger", target_level=18
        )
        assert recs["target_level"] == 18
        assert len(recs["builds"]) == 3

        for b in recs["builds"]:
            ms = b["future_milestones"]
            assert len(ms) >= 3
            # Crucial: milestones MUST start at level 18, NOT level 10!
            assert any("Level 18:" in m for m in ms)
            assert any("Level 19:" in m for m in ms)
            assert any("Level 20:" in m for m in ms)
            # Must never show level 10 milestones for a level 17/18 character
            assert not any("Level 10:" in m for m in ms)
            assert not any("Level 11:" in m for m in ms)
            # Level 20 must highlight capstone
            lvl_20_ms = [m for m in ms if "Level 20:" in m]
            assert any("Foe Slayer" in m or "Capstone" in m for m in lvl_20_ms)


def test_level_up_planning_custom_target_level():
    ranger = {
        "char_name": "Ulad Bhor",
        "char_class": "Ranger",
        "char_level": 9,
        "subclass": "Horizon Walker",
        "race": "Wood Elf",
        "background": "Outlander",
        "alignment": "Chaotic Good",
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 10, "DEX": 18, "CON": 14, "INT": 12, "WIS": 14, "CHA": 8},
        "hit_dice": "d10",
        "hp_max": 76,
        "features_traits": [],
        "equipment": [{"name": "Longbow +1"}],
        "spells": {},
    }

    # When user uses the planning switcher to jump to Level 12
    with patch(
        "backend.services.forge_service.generate_ai_json", side_effect=Exception("API down")
    ):
        recs = generate_level_up_build_recommendations(
            ranger, target_class="Ranger", target_level=12
        )
        assert recs["target_level"] == 12
        assert len(recs["builds"]) == 3

        for b in recs["builds"]:
            ms = b["future_milestones"]
            # Planning from Level 12 should start at Level 12
            assert any("Level 12:" in m for m in ms)
            assert not any("Level 10:" in m for m in ms)
            lvl_12_ms = [m for m in ms if "Level 12:" in m]
            assert any("ASI" in m or "Feat" in m for m in lvl_12_ms)


def test_ai_prompt_dynamic_parameters():
    ranger = {
        "char_name": "Robin",
        "char_class": "Ranger",
        "char_level": 5,
        "subclass": "Hunter",
        "race": "Human",
        "background": "Folk Hero",
        "alignment": "Neutral Good",
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 12, "DEX": 16, "CON": 14, "INT": 10, "WIS": 14, "CHA": 10},
        "hit_dice": "d10",
        "hp_max": 44,
        "features_traits": [],
        "equipment": [{"name": "Shortbow"}],
        "spells": {},
    }

    captured_prompt = None

    def mock_ai(prompt):
        nonlocal captured_prompt
        captured_prompt = prompt
        return {"builds": []}

    with patch("backend.services.forge_service.generate_ai_json", side_effect=mock_ai):
        recs = generate_level_up_build_recommendations(
            ranger, target_class="Ranger", target_level=6
        )
        assert captured_prompt is not None
        assert "Target Ranger Level: 6" in captured_prompt
        assert "Milestones MUST start at Level 6" in captured_prompt
        assert "Level 8" in captured_prompt  # Upcoming ASI level for lvl 6 ranger
        assert len(recs["builds"]) == 3  # Fallback builds populated cleanly when AI returns empty
