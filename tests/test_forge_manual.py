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


@patch("backend.services.forge_service.generate_ai_json")
def test_forge_character_weapon_properties_as_list(mock_ai_json):
    mock_ai_json.return_value = {
        "backstory": "A mighty warrior.",
        "weapons": [
            {
                "name": "Longsword",
                "attack_bonus": "+5",
                "damage_dice": "1d8",
                "damage_bonus": "+3",
                "properties": ["versatile (1d10)"],
                "range": ["5 ft"],
            }
        ],
    }

    base_stats = {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8}

    char = forge_character_manual(
        target_level=1,
        race="Human",
        char_class="Fighter",
        background="Soldier",
        subclass="None",
        alignment="Lawful Good",
        gender="Male",
        name="Warrior",
        base_stats=base_stats,
        skill_proficiencies=["Athletics"],
        saving_throws=["STR", "CON"],
        spell_ability=None,
        concept="Warrior",
        edition=EDITION_2014,
    )

    assert len(char["weapons"]) == 1
    assert char["weapons"][0]["properties"] == "versatile (1d10)"
    assert char["weapons"][0]["range"] == "5 ft"


@patch("backend.services.forge_service.generate_ai_json", return_value=None)
def test_forge_character_manual_deterministic_mandatory_grants_elf_rogue_criminal(mock_ai_json):
    """Even when AI returns None and user omits background skills/feats/gear, all mandatory Class, Species, and Background grants must be injected."""
    char = forge_character_manual(
        target_level=1,
        race="Elf",
        char_class="Rogue",
        background="Criminal",
        subclass="None",
        alignment="Chaotic Neutral",
        gender="Female",
        name="Lyra Nightwhisper",
        base_stats={"STR": 8, "DEX": 17, "CON": 14, "INT": 14, "WIS": 12, "CHA": 10},
        skill_proficiencies=["Acrobatics", "Investigation"],
        saving_throws=[],
        spell_ability=None,
        concept="Shadow operative.",
        edition="2024 Revision (5.5e)",
        chosen_feats=None,
        chosen_spells=None,
        chosen_equipment=None,
    )

    # 1. Class + Background + Species Skill Proficiencies
    skills = set(char["skill_proficiencies"])
    assert {"Acrobatics", "Investigation"}.issubset(skills)  # User chosen class skills
    assert {"Sleight of Hand", "Stealth"}.issubset(skills)  # Criminal background mandatory skills
    assert "Perception" in skills  # Elf Keen Senses mandatory racial skill

    # 2. Species Traits (Elf 2024) + Class Features (Rogue Lvl 1) + Background Origin Feat (Criminal -> Alert) + Tools
    trait_names = {f["name"].lower() for f in char["features_traits"]}
    assert "darkvision" in trait_names
    assert "fey ancestry" in trait_names
    assert "keen senses" in trait_names
    assert "trance" in trait_names
    assert "sneak attack" in trait_names
    assert "expertise" in trait_names
    assert "thieves' cant" in trait_names
    assert "weapon mastery" in trait_names
    assert any("alert" in n for n in trait_names)
    assert any("tool proficiency" in n for n in trait_names)

    # 3. Saving Throws, Starting Gear, Weapons & 2024 Masteries
    assert set(char["saving_throws"]) == {"DEX", "INT"}
    assert len(char["weapons"]) >= 2
    assert len(char["equipment"]) >= 2
    assert len(char["weapon_masteries"]) == 2


@patch("backend.services.forge_service.generate_ai_json", return_value=None)
def test_forge_character_manual_deterministic_mandatory_grants_dwarf_cleric_acolyte(mock_ai_json):
    """Dwarf Cleric (Acolyte, 2024) must automatically receive Acolyte skills, Dwarven Toughness (+1 HP/lvl), Magic Initiate (Cleric), and starting Cleric spells/gear."""
    char = forge_character_manual(
        target_level=1,
        race="Dwarf",
        char_class="Cleric",
        background="Acolyte",
        subclass="None",
        alignment="Lawful Good",
        gender="Male",
        name="Bram Ironprayer",
        base_stats={"STR": 14, "DEX": 10, "CON": 16, "INT": 8, "WIS": 17, "CHA": 12},
        skill_proficiencies=["History", "Medicine"],
        saving_throws=[],
        spell_ability=None,
        concept="Temple guardian.",
        edition="2024 Revision (5.5e)",
        chosen_feats=None,
        chosen_spells=None,
        chosen_equipment=None,
    )

    # 1. Skills: Class (History, Medicine) + Acolyte Background (Insight, Religion)
    skills = set(char["skill_proficiencies"])
    assert {"History", "Medicine", "Insight", "Religion"}.issubset(skills)

    # 2. Dwarf Traits + Dwarven Toughness (+1 HP/lvl -> 8 base + 3 CON + 1 Dwarf = 12 HP)
    trait_names = {f["name"].lower() for f in char["features_traits"]}
    assert "dwarven resilience" in trait_names
    assert "dwarven toughness" in trait_names
    assert "stonecunning" in trait_names
    assert char["hp_max"] == 12

    # 3. Acolyte Origin Feat (Magic Initiate (Cleric)) & Cleric Features
    assert any("magic initiate" in n for n in trait_names)
    assert "spellcasting" in trait_names
    assert "divine order" in trait_names

    # 4. Auto-populated Starting Spells & Gear
    assert len(char["spells"].get("cantrips", [])) >= 2
    assert len(char["spells"].get("level_1", [])) >= 2
    assert len(char["prepared_spells"]) >= 4
    assert set(char["saving_throws"]) == {"WIS", "CHA"}
    assert char["armor_class"] >= 15  # Chain Shirt (13) + Shield (+2) = 15


@patch("backend.services.forge_service.generate_ai_json", return_value=None)
def test_forge_character_manual_deterministic_mandatory_grants_2014_edition(mock_ai_json):
    """In 2014 Edition, Half-Orc Barbarian (Outlander) receives 2014 racial traits/skill (Menacing -> Intimidation), Outlander skills (Athletics, Survival), and 2014 Background Feature (Wanderer) instead of a 2024 Origin Feat."""
    char = forge_character_manual(
        target_level=1,
        race="Half-Orc",
        char_class="Barbarian",
        background="Outlander",
        subclass="None",
        alignment="Chaotic Good",
        gender="Female",
        name="Grommash",
        base_stats={"STR": 16, "DEX": 14, "CON": 16, "INT": 8, "WIS": 12, "CHA": 10},
        skill_proficiencies=["Perception"],
        saving_throws=[],
        spell_ability=None,
        concept="Tribal exile.",
        edition="5e (2014)",
        chosen_feats=None,
        chosen_spells=None,
        chosen_equipment=None,
    )

    skills = set(char["skill_proficiencies"])
    assert "Perception" in skills  # User chosen class skill
    assert {"Athletics", "Survival"}.issubset(skills)  # Outlander background skills
    assert "Intimidation" in skills  # 2014 Half-Orc Menacing racial skill

    trait_names = {f["name"].lower() for f in char["features_traits"]}
    assert "relentless endurance" in trait_names
    assert "savage attacks" in trait_names
    assert "menacing" in trait_names
    assert "rage" in trait_names
    assert "unarmored defense" in trait_names
    assert "wanderer" in trait_names  # 2014 Outlander narrative background feature
    assert not any("origin feat" in n for n in trait_names)  # No 2024 Origin Feat in 2014 edition
