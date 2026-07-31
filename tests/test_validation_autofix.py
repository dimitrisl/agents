from unittest.mock import patch

from backend.services.rules_service import autofix_character_build, validate_character_build


def test_validate_character_build_mock():
    mock_char = {
        "char_name": "Test Hero",
        "char_class": "Paladin",
        "race": "Human",
        "background": "Noble",
        "char_level": 5,
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 14},
        "hp_max": 44,
        "armor_class": 18,
    }

    mock_validation_response = {
        "is_valid": False,
        "issues": ["Armor class miscalculated"],
        "suggestions": ["Re-check shield bonus"],
        "corrections": {"armor_class": 16},
    }

    with patch(
        "backend.services.rules_service.generate_ai_json", return_value=mock_validation_response
    ):
        res = validate_character_build(mock_char)
        assert res["is_valid"] is False
        assert "Armor class miscalculated" in res["issues"]


def test_autofix_character_build_mock():
    mock_char = {
        "char_name": "Broken Hero",
        "char_class": "Fighter",
        "race": "Human",
        "background": "Soldier",
        "char_level": 3,
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8},
        "hp_max": 10,  # Intentional error: Level 3 fighter HP should be higher
        "armor_class": 10,
    }

    mock_validation_response = {
        "is_valid": False,
        "issues": ["Low HP for level 3 fighter"],
        "suggestions": ["Recalculate HP"],
        "corrections": {"hp_max": 28},
    }

    with patch(
        "backend.services.rules_service.generate_ai_json", return_value=mock_validation_response
    ):
        res = autofix_character_build(mock_char)
        assert "validation_result" in res
        assert "character" in res
        # Check that mechanics resync ran and auto-calculated stats
        assert res["character"]["proficiency_bonus"] == 2
        assert res["character"]["char_name"] == "Broken Hero"


def test_autofix_edition_2024_subclass_rule():
    # In 2024 Edition, a level 1 Paladin cannot have a subclass yet
    mock_2024_char = {
        "char_name": "Young Paladin",
        "char_class": "Paladin",
        "subclass": "Devotion",  # Invalid at level 1 in 2024 Edition!
        "race": "Human",
        "background": "Noble",
        "char_level": 1,
        "dnd_edition": "2024 Edition",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 14},
        "hp_max": 12,
        "armor_class": 16,
    }

    mock_validation_response = {
        "is_valid": False,
        "issues": ["Subclasses in 2024 Edition are gained at Level 3"],
        "suggestions": ["Remove subclass until Level 3"],
        "corrections": {"subclass": ""},
    }

    with patch(
        "backend.services.rules_service.generate_ai_json", return_value=mock_validation_response
    ):
        res = autofix_character_build(mock_2024_char)
        assert res["character"]["subclass"] == ""
        assert res["character"]["dnd_edition"] == "2024 Edition"


def test_2024_fighter_autofix_comprehensive():
    # Test Fighter Level 5 2024 Edition with Guard background, INT 15 (+2), WIS 12 (+1)
    mock_fighter = {
        "char_name": "Feric Custos",
        "char_class": "Fighter",
        "subclass": "Eldritch Knight",
        "char_level": 5,
        "race": "Human",
        "background": "Guard",
        "dnd_edition": "2024 Revision (5.5e)",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 15, "WIS": 12, "CHA": 10},
        "weapons": [
            {"name": "Longsword", "attack_bonus": "+6", "damage_dice": "1d8", "damage_bonus": "+3"},
            {
                "name": "Light Crossbow",
                "attack_bonus": "+5",
                "damage_dice": "1d8",
                "damage_bonus": "+2",
            },
        ],
        "spells": {"level_1": ["Shield"]},
        "passive_perception": 14,  # Indicates WIS +1 + Prof +3 = 14
        "skill_proficiencies": ["Athletics"],  # Perception missing initially!
    }

    mock_validation = {
        "is_valid": False,
        "issues": [
            "Missing Spell DC",
            "Perception proficiency unchecked",
            "Missing Origin Feat Alert",
            "Missing 2024 Fighter features",
        ],
        "suggestions": ["Fix calculations"],
        "corrections": {},
    }

    with patch("backend.services.rules_service.generate_ai_json", return_value=mock_validation):
        res = autofix_character_build(mock_fighter)
        char = res["character"]

        # 1. Spell DC & Attack Bonus (INT 15 => +2, Prof => +3 => DC 13, Atk +5)
        assert char["spell_save_dc"] == 13
        assert char["spell_attack_bonus"] == "+5"
        assert char["spell_ability"] == "INT"

        # 2. Perception skill proficiencies synchronization
        assert "Perception" in char["skill_proficiencies"]
        assert char["passive_perception"] == 14

        # 3. 2024 Weapon Masteries
        assert len(char["weapon_masteries"]) >= 2
        assert any("Sap" in m for m in char["weapon_masteries"])

        # 4. Background Guard -> Origin Feat: Alert
        ft_names = [f.get("name", "") for f in char["features_traits"]]
        # 5. 2024 Fighter Class Features: Tactical Mind & Tactical Shift
        assert any("Tactical Mind" in n for n in ft_names)
        assert any("Tactical Shift" in n for n in ft_names)

        # 6. Third Caster Spell Slots for Eldritch Knight Level 5 (3 Level 1 slots)
        assert char["spell_slots"]["level_1"]["max"] == 3


def test_2014_fighter_autofix_no_2024_bleed():
    # Verify that a 2014 Edition Fighter does NOT get 2024 features auto-injected
    mock_2014_char = {
        "char_name": "Old School Fighter",
        "char_class": "Fighter",
        "char_level": 5,
        "race": "Human",
        "background": "Soldier",
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8},
        "hp_max": 44,
        "armor_class": 16,
    }

    mock_validation = {"is_valid": True, "issues": [], "suggestions": [], "corrections": {}}

    with patch("backend.services.rules_service.generate_ai_json", return_value=mock_validation):
        res = autofix_character_build(mock_2014_char)
        char = res["character"]
        # Ensure 2024-specific fields/features are NOT added to 2014 Edition character
        assert len(char.get("weapon_masteries", [])) == 0
        ft_names = [f.get("name", "") for f in char.get("features_traits", [])]
        assert not any("Tactical Mind" in n for n in ft_names)
        assert not any("Origin Feat" in n for n in ft_names)


def test_autofix_spell_slots_int_format_handling():
    # Test character where spell_slots is initialized as integers e.g. {"level_1": 3}
    char_with_int_slots = {
        "char_name": "Eldritch Knight Integer Slots",
        "char_class": "Fighter",
        "subclass": "Eldritch Knight",
        "char_level": 5,
        "race": "Human",
        "background": "Soldier",
        "dnd_edition": "2024 Revision (5.5e)",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 14, "WIS": 10, "CHA": 8},
        "spell_slots": {"level_1": 3},  # Integer value instead of dict!
    }

    mock_validation = {"is_valid": True, "issues": [], "suggestions": [], "corrections": {}}

    with patch("backend.services.rules_service.generate_ai_json", return_value=mock_validation):
        res = autofix_character_build(char_with_int_slots)
        char = res["character"]
        # Ensure spell_slots was safely converted into a dictionary without raising TypeError
        assert isinstance(char["spell_slots"]["level_1"], dict)
        assert char["spell_slots"]["level_1"]["max"] == 3


def test_autofix_weapon_properties_none_handling():
    char_with_none_weapon_props = {
        "char_name": "Fighter None Weapon Props",
        "char_class": "Fighter",
        "char_level": 5,
        "race": "Human",
        "background": "Soldier",
        "dnd_edition": "2024 Revision (5.5e)",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8},
        "weapons": [
            {"name": "Longsword", "attack_bonus": "+6", "damage_dice": "1d8+3", "properties": None}
        ],
    }

    mock_validation = {"is_valid": True, "issues": [], "suggestions": [], "corrections": {}}

    with patch("backend.services.rules_service.generate_ai_json", return_value=mock_validation):
        res = autofix_character_build(char_with_none_weapon_props)
        char = res["character"]
        assert char["weapons"][0]["properties"] is not None
        assert "Mastery: Sap" in char["weapons"][0]["properties"]


def test_2014_edition_isolation():
    """Verify that 2014 Edition characters retain 2014 background features and do not receive 2024 Masteries."""
    from backend.services.stats_service import sync_character_stats

    char_2014 = {
        "char_name": "Valeros 2014",
        "char_class": "Fighter",
        "char_level": 5,
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8},
        "background": "Guard",
        "features_traits": [{"name": "Stand Your Ground", "description": "2014 Guard Feature"}],
        "weapons": [{"name": "Longsword", "attack_bonus": "+6", "damage_dice": "1d8+3", "properties": "Versatile"}],
    }

    synced = sync_character_stats(char_2014, {})
    # 2014 background feature preserved
    trait_names = [f["name"] for f in synced["features_traits"]]
    assert "Stand Your Ground" in trait_names
    # No 2024 Origin Feat added
    assert not any("Origin Feat" in name for name in trait_names)
    # Weapon Masteries list remains empty
    assert len(synced.get("weapon_masteries", [])) == 0
    assert "Mastery" not in synced["weapons"][0]["properties"]

