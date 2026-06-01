from unittest.mock import patch
from backend.services.forge_service import forge_character_manual
from backend.core.constants import EDITION_2014


@patch("backend.services.forge_service.generate_ai_json")
def test_forge_character_manual_success(mock_ai_json):
    # Mock return value from AI enrich step
    mock_ai_json.return_value = {
        "backstory": "A brave warrior of the forge.",
        "features_traits": [
            {
                "name": "Stonecunning",
                "description": "Whenever you make an Intelligence (History) check related to the origin of stonework...",
                "source": "Race",
            }
        ],
        "weapons": [
            {
                "name": "Greataxe",
                "attack_bonus": "+5",
                "damage_dice": "1d12",
                "damage_bonus": "+3",
            }
        ],
        "equipment": [
            {"name": "Chain mail", "equipped": True},
            {"name": "Explorer's Pack", "equipped": False},
        ],
        "spells": {"cantrips": [], "level_1": []},
        "languages": ["Common", "Dwarvish"],
        "personality_traits": "Hardworking and gruff.",
        "ideals": "Clans and family first.",
        "bonds": "My smithy tools.",
        "flaws": "I never admit I'm wrong.",
    }

    base_stats = {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8}

    char = forge_character_manual(
        target_level=1,
        race="Dwarf",
        char_class="Fighter",
        background="Soldier",
        subclass="None",
        alignment="Lawful Good",
        gender="Male",
        name="Thorgar Ironbreaker",
        base_stats=base_stats,
        skill_proficiencies=["Athletics", "Intimidation"],
        saving_throws=["STR", "CON"],
        spell_ability=None,
        concept="Dwarven fighter searching for ancient blueprints.",
        edition=EDITION_2014,
    )

    assert char["char_name"] == "Thorgar Ironbreaker"
    assert char["race"] == "Dwarf"
    assert char["char_class"] == "Fighter"
    assert char["stats"]["STR"] == 16
    assert char["stats"]["CHA"] == 8
    assert char["backstory"] == "A brave warrior of the forge."
    assert "Athletics" in char["skill_proficiencies"]
    assert "Intimidation" in char["skill_proficiencies"]
    assert "STR" in char["saving_throws"]
    assert "CON" in char["saving_throws"]
    assert len(char["weapons"]) == 1
    assert char["weapons"][0]["name"] == "Greataxe"
    assert len(char["equipment"]) == 2
