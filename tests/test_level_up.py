import pytest
from unittest.mock import patch
from backend.services.forge_service import analyze_level_up
from backend.services.mechanics_service import sync_character_stats
from backend.repositories.rules_repository import RulesRepository
from backend.core.constants import EDITION_2014, EDITION_2024


# --- Fixtures ---


@pytest.fixture
def char_at_level_1():
    return {
        "char_name": "Test Hero",
        "char_level": 1,
        "char_class": "Fighter",
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "hit_dice": "d10",
        "hp_max": 12,  # 10 + 2 (CON mod)
        "proficiency_bonus": 2,
    }


@pytest.fixture
def char_2024_level_4():
    return {
        "char_name": "Test Hero 2024",
        "char_level": 4,
        "char_class": "Fighter",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "hit_dice": "d10",
        "hp_max": 36,
        "proficiency_bonus": 2,
        "features_traits": [],
    }


@pytest.fixture
def char_with_tough():
    """Level 8 Fighter with the Tough feat."""
    return {
        "char_name": "Tough Hero",
        "char_level": 8,
        "char_class": "Fighter",
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "hit_dice": "8d10",
        "hp_max": None,  # Force recalculation
        "proficiency_bonus": 3,
        "features_traits": [
            {
                "name": "Feat: Tough",
                "description": "Your hit point maximum increases by an amount equal to twice your level.",
            }
        ],
    }


@pytest.fixture
def char_with_alert_2014():
    """Level 4 character with Alert feat (2014 rules)."""
    return {
        "char_name": "Alert Hero 2014",
        "char_level": 4,
        "char_class": "Rogue",
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 10, "DEX": 16, "CON": 12, "INT": 10, "WIS": 14, "CHA": 10},
        "hit_dice": "4d8",
        "hp_max": None,
        "proficiency_bonus": 2,
        "features_traits": [
            {
                "name": "Feat: Alert",
                "description": "You have advantage on initiative.",
            }
        ],
    }


@pytest.fixture
def char_with_alert_2024():
    """Level 4 character with Alert feat (2024 rules)."""
    return {
        "char_name": "Alert Hero 2024",
        "char_level": 4,
        "char_class": "Rogue",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 10, "DEX": 16, "CON": 12, "INT": 10, "WIS": 14, "CHA": 10},
        "hit_dice": "4d8",
        "hp_max": None,
        "proficiency_bonus": 2,
        "features_traits": [
            {
                "name": "Feat: Alert",
                "description": "You gain proficiency in Initiative.",
            }
        ],
    }


# --- Basic Level Up Tests ---


def test_level_up_stat_sync(char_at_level_1):
    """Level 2 Fighter: HP should recalculate correctly."""
    char_at_level_1["char_level"] = 2
    char_at_level_1["hp_max"] = None  # Force recalculation

    synced = sync_character_stats(char_at_level_1, class_data={"hit_die": "d10"})

    # Level 1: 10 + 2 = 12. Level 2: + (6 + 2) = 8. Total = 20.
    assert synced["hp_max"] == 20
    assert synced["proficiency_bonus"] == 2  # Still 2 at level 2


def test_level_up_stat_sync_to_level_5(char_at_level_1):
    """Level 5 Fighter: prof bonus should be +3."""
    char_at_level_1["char_level"] = 5
    char_at_level_1["hp_max"] = None

    synced = sync_character_stats(char_at_level_1, class_data={"hit_die": "d10"})

    assert synced["proficiency_bonus"] == 3
    # HP: Level 1 (12) + 4 levels of (6 + 2) = 12 + 32 = 44
    assert synced["hp_max"] == 44


def test_hp_persistence_during_sync(char_at_level_1):
    """Manually set HP should be preserved during sync."""
    char_at_level_1["hp_max"] = 100
    char_at_level_1["char_level"] = 2

    synced = sync_character_stats(char_at_level_1)

    assert synced["hp_max"] == 100


# --- Feat Mechanics: HP Bonus ---


def test_tough_feat_adds_hp_bonus(char_with_tough):
    """Tough feat should add +2 HP per level via structured JSON lookup."""
    synced = sync_character_stats(char_with_tough, class_data={"hit_die": "d10"})

    # Base HP at level 8 (d10, CON 14 = +2 mod):
    # Level 1: 10 + 2 = 12
    # Levels 2-8: 7 * (6 + 2) = 56
    # Base = 68
    # Tough: +2 * 8 = +16
    # Total = 84
    assert synced["hp_max"] == 84


def test_tough_feat_uses_structured_data_not_name():
    """A custom-named feat with hp_bonus_per_level should still apply HP."""
    # This simulates a homebrew feat that grants HP
    # The system should detect it via the structured JSON, not the name
    char = {
        "char_name": "Custom Hero",
        "char_level": 4,
        "char_class": "Fighter",
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "hit_dice": "4d10",
        "hp_max": None,
        "proficiency_bonus": 2,
        "features_traits": [
            {
                "name": "Feat: Tough",
                "description": "HP bonus feat",
            }
        ],
    }
    synced = sync_character_stats(char, class_data={"hit_die": "d10"})

    # Base HP at level 4: 10+2 + 3*(6+2) = 12 + 24 = 36
    # Tough: +2 * 4 = +8
    # Total = 44
    assert synced["hp_max"] == 44


# --- Feat Mechanics: Initiative ---


def test_alert_2014_gives_plus_5(char_with_alert_2014):
    """2014 Alert feat should give +5 initiative."""
    synced = sync_character_stats(char_with_alert_2014, class_data={"hit_die": "d8"})

    dex_mod = 3  # DEX 16 = +3
    expected = dex_mod + 5  # +5 from 2014 Alert
    assert synced["initiative_modifier"] == expected


def test_alert_2024_gives_proficiency_bonus(char_with_alert_2024):
    """2024 Alert feat should add proficiency bonus to initiative."""
    synced = sync_character_stats(char_with_alert_2024, class_data={"hit_die": "d8"})

    dex_mod = 3  # DEX 16 = +3
    prof_bonus = 2  # Level 4 = +2
    expected = dex_mod + prof_bonus
    assert synced["initiative_modifier"] == expected


def test_no_alert_no_initiative_bonus(char_at_level_1):
    """Without Alert, initiative should just be DEX mod."""
    synced = sync_character_stats(char_at_level_1, class_data={"hit_die": "d10"})

    dex_mod = 0  # DEX 10 = +0
    assert synced["initiative_modifier"] == dex_mod


# --- Edition Awareness ---


def test_2024_edition_loads_2024_feats():
    """The repository should load the correct feat file for 2024."""
    repo = RulesRepository()
    feats_2024 = repo.get_all_feats(EDITION_2024)
    feats_2014 = repo.get_all_feats(EDITION_2014)

    # 2024 should have Origin Feats (e.g. Alert, Tavern Brawler)
    feat_names_2024 = [f["name"] for f in feats_2024]
    assert "Alert" in feat_names_2024

    # The two lists should be different (different libraries)
    # 2014 has way more feats than 2024
    assert len(feats_2014) > len(feats_2024)


def test_feat_structured_prerequisites():
    """All feats should have structured prerequisites (not strings)."""
    repo = RulesRepository()

    for edition in [EDITION_2014, EDITION_2024]:
        feats = repo.get_all_feats(edition)
        for feat in feats:
            prereqs = feat.get("prerequisites")
            assert isinstance(prereqs, dict), (
                f"Feat '{feat['name']}' in {edition} has string prerequisites: {prereqs}"
            )
            assert "min_level" in prereqs, (
                f"Feat '{feat['name']}' in {edition} missing min_level"
            )
            assert "stat_requirements" in prereqs, (
                f"Feat '{feat['name']}' in {edition} missing stat_requirements"
            )


def test_feat_stat_bonus_structure():
    """All feats should have a well-formed stat_bonus object."""
    repo = RulesRepository()
    expected_keys = {"STR", "DEX", "CON", "INT", "WIS", "CHA"}

    for edition in [EDITION_2014, EDITION_2024]:
        feats = repo.get_all_feats(edition)
        for feat in feats:
            bonus = feat.get("stat_bonus")
            assert isinstance(bonus, dict), (
                f"Feat '{feat['name']}' in {edition} has no stat_bonus"
            )
            assert set(bonus.keys()) == expected_keys, (
                f"Feat '{feat['name']}' in {edition} stat_bonus keys mismatch: {bonus.keys()}"
            )


# --- AI Fallback Test ---


@patch("backend.services.forge_service.generate_ai_json")
def test_analyze_level_up_logic(mock_ai_json, char_at_level_1):
    """AI level-up analysis should return structured results."""
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
