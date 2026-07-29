from unittest.mock import patch

from backend.core.constants import EDITION_2014
from backend.services.forge_service import forge_character_manual


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


@patch("backend.services.forge_service.generate_ai_json")
def test_forge_character_manual_with_custom_preferences(mock_ai_json):
    mock_ai_json.return_value = {
        "backstory": "Archmage of the High Tower.",
        "features_traits": [{"name": "Feat: War Caster", "description": "Advantage on CON saves"}],
        "weapons": [{"name": "Quarterstaff", "attack_bonus": "+2", "damage_dice": "1d6"}],
        "equipment": [{"name": "Robes", "equipped": True}],
        "spells": {
            "cantrips": ["Fire Bolt"],
            "level_1": ["Shield"],
            "level_3": ["Fireball", "Counterspell"],
        },
        "advancements": [
            {
                "level": 4,
                "type": "Feat",
                "name": "War Caster",
                "description": "Advantage",
            }
        ],
        "languages": ["Common", "Elvish"],
    }

    base_stats = {"STR": 8, "DEX": 14, "CON": 14, "INT": 18, "WIS": 12, "CHA": 10}

    char = forge_character_manual(
        target_level=8,
        race="Elf",
        char_class="Wizard",
        background="Sage",
        subclass="Evocation",
        alignment="Neutral Good",
        gender="Female",
        name="Elindra",
        base_stats=base_stats,
        skill_proficiencies=["Arcana", "History"],
        saving_throws=["INT", "WIS"],
        spell_ability="INT",
        concept="High level elementalist.",
        edition=EDITION_2014,
        custom_preferences="Feat: War Caster at level 4. Spells: Fireball, Counterspell.",
    )

    assert char["char_level"] == 8
    assert mock_ai_json.called
    # Check that custom_preferences instruction was injected into prompt sent to AI
    prompt_sent = mock_ai_json.call_args[0][0]
    assert "USER CUSTOM BUILD PREFERENCES" in prompt_sent
    assert "War Caster" in prompt_sent


@patch("backend.services.forge_service.generate_ai_json")
def test_forge_character_manual_disable_auto_spells_and_feats(mock_ai_json):
    mock_ai_json.return_value = {
        "backstory": "Archmage who picks their own spells and feats.",
        "features_traits": [
            {"name": "Spellcasting", "description": "Class spellcasting ability"},
            {"name": "Feat: War Caster", "description": "Advantage on CON saves"},
        ],
        "spells": {"cantrips": ["Fire Bolt"], "level_1": ["Shield"]},
        "prepared_spells": ["Shield"],
        "advancements": [{"level": 4, "type": "Feat", "name": "War Caster"}],
    }

    base_stats = {"STR": 8, "DEX": 14, "CON": 14, "INT": 18, "WIS": 12, "CHA": 10}

    char = forge_character_manual(
        target_level=8,
        race="Elf",
        char_class="Wizard",
        background="Sage",
        subclass="Evocation",
        alignment="Neutral Good",
        gender="Female",
        name="Elindra Manual",
        base_stats=base_stats,
        skill_proficiencies=["Arcana", "History"],
        saving_throws=["INT", "WIS"],
        spell_ability="INT",
        concept="High level elementalist.",
        edition=EDITION_2014,
        auto_spells=False,
        auto_feats=False,
    )

    assert not any(char["spells"].values())
    assert char["prepared_spells"] == []
    assert char["advancements"] == []
    feat_names = [f["name"] for f in char["features_traits"]]
    assert "Feat: War Caster" not in feat_names
    assert "Spellcasting" in feat_names
