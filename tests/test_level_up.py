import pytest
from unittest.mock import patch
from backend.services.forge_service import analyze_level_up
from backend.services.mechanics_service import sync_character_stats


@pytest.fixture
def char_at_level_1():
    return {
        "char_name": "Test Hero",
        "char_level": 1,
        "char_class": "Fighter",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "hit_dice": "d10",
        "hp_max": 12,  # 10 + 2
        "proficiency_bonus": 2,
    }


def test_level_up_stat_sync(char_at_level_1):
    # Simulate manual level up to level 2
    char_at_level_1["char_level"] = 2
    # To force recalculation of standard HP, we clear hp_max
    char_at_level_1["hp_max"] = None

    # Re-sync stats
    synced = sync_character_stats(char_at_level_1, class_data={"hit_die": "d10"})

    # Check HP increase: Level 1 was 12. Level 2 adds (6 + 2) = 8. Total 20.
    assert synced["hp_max"] == 20
    assert synced["proficiency_bonus"] == 2  # Still 2 at level 2


def test_level_up_stat_sync_to_level_5(char_at_level_1):
    # Simulate level up to level 5
    char_at_level_1["char_level"] = 5
    char_at_level_1["hp_max"] = None

    # Re-sync stats
    synced = sync_character_stats(char_at_level_1, class_data={"hit_die": "d10"})

    # Proficiency bonus at level 5 should be +3
    assert synced["proficiency_bonus"] == 3

    # HP: Level 1 (12) + 4 levels of (6 + 2) = 12 + 32 = 44
    assert synced["hp_max"] == 44


def test_hp_persistence_during_sync(char_at_level_1):
    # Manually set a non-standard HP
    char_at_level_1["hp_max"] = 100
    char_at_level_1["char_level"] = 2

    synced = sync_character_stats(char_at_level_1)

    # Should NOT have recalculated to 20
    assert synced["hp_max"] == 100


@patch("backend.services.forge_service.generate_ai_json")
def test_analyze_level_up_logic(mock_ai_json, char_at_level_1):
    # Mock AI response for level up analysis
    mock_ai_json.return_value = {
        "automatic_changes": [
            {"name": "Action Surge", "description": "You can take an extra action."}
        ],
        "hp_increase": 8,
        "new_total_hp": 20,
        "choices_required": [],
    }

    result = analyze_level_up(char_at_level_1)

    assert result["hp_increase"] == 8
    assert result["new_total_hp"] == 20
    assert len(result["automatic_changes"]) == 1
    assert result["automatic_changes"][0]["name"] == "Action Surge"
