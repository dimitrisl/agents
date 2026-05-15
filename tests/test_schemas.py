from backend.core.schemas import (
    StatBlock,
    CharacterSchema,
    SpellList,
    LevelUpAnalysisSchema,
    BuildValidationSchema,
)


# --- StatBlock ---


def test_stat_block_defaults():
    sb = StatBlock()
    assert sb.STR == 10
    assert sb.DEX == 10
    assert sb.CON == 10
    assert sb.INT == 10
    assert sb.WIS == 10
    assert sb.CHA == 10


def test_stat_block_custom():
    sb = StatBlock(STR=18, DEX=14, CON=16, INT=8, WIS=12, CHA=10)
    assert sb.STR == 18
    assert sb.DEX == 14


# --- Equipment & Feature Validators ---


def test_equipment_string_coercion():
    """Passing strings for equipment should auto-convert to EquipmentItem dicts."""
    char = CharacterSchema(
        char_name="Test",
        char_class="Fighter",
        race="Human",
        background="Soldier",
        stats=StatBlock(),
        equipment=["Longsword", "Shield"],
    )
    assert len(char.equipment) == 2
    assert char.equipment[0].name == "Longsword"
    assert char.equipment[1].name == "Shield"
    # Default equipped should be False when not specified
    assert char.equipment[0].equipped is False


def test_equipment_dict_passthrough():
    """Dicts with full fields should pass through unchanged."""
    char = CharacterSchema(
        char_name="Test",
        char_class="Fighter",
        race="Human",
        background="Soldier",
        stats=StatBlock(),
        equipment=[{"name": "Plate Armor", "equipped": True, "ac_bonus": 0}],
    )
    assert char.equipment[0].name == "Plate Armor"
    assert char.equipment[0].equipped is True


def test_features_string_coercion():
    """Passing strings for features should auto-convert to FeatureTrait dicts."""
    char = CharacterSchema(
        char_name="Test",
        char_class="Fighter",
        race="Human",
        background="Soldier",
        stats=StatBlock(),
        features_traits=["Second Wind", "Action Surge"],
    )
    assert len(char.features_traits) == 2
    assert char.features_traits[0].name == "Second Wind"
    assert char.features_traits[0].description == "Imported feature"


def test_features_dict_passthrough():
    """Full feature dicts should pass through."""
    char = CharacterSchema(
        char_name="Test",
        char_class="Fighter",
        race="Human",
        background="Soldier",
        stats=StatBlock(),
        features_traits=[{"name": "Darkvision", "description": "See 60ft in darkness"}],
    )
    assert char.features_traits[0].name == "Darkvision"
    assert "60ft" in char.features_traits[0].description


# --- CharacterSchema Defaults ---


def test_character_schema_defaults():
    char = CharacterSchema(
        char_name="Default Hero",
        char_class="Wizard",
        race="Elf",
        background="Sage",
        stats=StatBlock(),
    )
    assert char.char_level == 1
    assert char.armor_class == 10
    assert char.hp_max == 10
    assert char.speed == 30
    assert char.proficiency_bonus == 2
    assert char.dnd_edition == "2014 Edition"
    assert char.weapons == []
    assert char.equipment == []
    assert char.spells.cantrips == []


def test_character_schema_full_roundtrip():
    """Create a full character, dump to dict, and re-validate."""
    data = {
        "char_name": "Thorin",
        "char_class": "Fighter",
        "char_level": 5,
        "race": "Dwarf",
        "background": "Soldier",
        "stats": {"STR": 18, "DEX": 12, "CON": 16, "INT": 8, "WIS": 10, "CHA": 10},
        "weapons": [{"name": "Battleaxe", "attack_bonus": "+7", "damage": "1d8 + 4"}],
        "equipment": ["Chain Mail", {"name": "Shield", "equipped": True}],
        "features_traits": [
            "Second Wind",
            {"name": "Action Surge", "description": "Extra action once per rest"},
        ],
    }
    char = CharacterSchema(**data)
    dumped = char.model_dump()
    restored = CharacterSchema(**dumped)
    assert restored.char_name == "Thorin"
    assert restored.char_level == 5
    assert restored.equipment[0].name == "Chain Mail"
    assert restored.features_traits[0].name == "Second Wind"


# --- SpellList ---


def test_spell_list_defaults():
    sl = SpellList()
    assert sl.cantrips == []
    assert sl.level_1 == []
    assert sl.level_9 == []


# --- Validation Schemas ---


def test_level_up_analysis_schema():
    data = {
        "automatic_changes": [
            {"name": "Extra Attack", "description": "Attack twice per action"}
        ],
        "hp_increase": 8,
        "new_total_hp": 52,
        "choices_required": [],
    }
    schema = LevelUpAnalysisSchema(**data)
    assert schema.hp_increase == 8
    assert schema.automatic_changes[0].name == "Extra Attack"


def test_build_validation_schema():
    schema = BuildValidationSchema(
        is_valid=False, issues=["No weapon proficiency"], suggestions=["Add a weapon"]
    )
    assert schema.is_valid is False
    assert len(schema.issues) == 1
