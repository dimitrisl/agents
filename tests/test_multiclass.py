from backend.services.stats_service import calculate_max_spell_slots, sync_character_stats
from backend.services.validation_service import deterministic_validate_build


def test_multiclass_spell_slots_full_and_half():
    classes = [
        {"class_name": "Paladin", "level": 2, "caster_type": "half"},
        {"class_name": "Sorcerer", "level": 3, "caster_type": "full"},
    ]
    slots = calculate_max_spell_slots("", 0, classes=classes)
    assert slots.get("level_1") == 4
    assert slots.get("level_2") == 3
    assert slots.get("level_3", 0) == 0


def test_multiclass_spell_slots_warlock_pact_magic():
    classes = [
        {"class_name": "Fighter", "level": 3, "caster_type": "none"},
        {"class_name": "Warlock", "level": 3, "caster_type": "pact"},
    ]
    slots = calculate_max_spell_slots("", 0, classes=classes)
    assert slots.get("level_2") == 2
    assert slots.get("level_1", 0) == 0


def test_multiclass_spell_slots_third_caster():
    classes = [
        {
            "class_name": "Fighter",
            "level": 4,
            "subclass": "Eldritch Knight",
            "caster_type": "third",
        },
        {"class_name": "Wizard", "level": 2, "caster_type": "full"},
    ]
    slots = calculate_max_spell_slots("", 0, classes=classes)
    assert slots.get("level_1") == 4
    assert slots.get("level_2") == 2
    assert slots.get("level_3", 0) == 0


def test_multiclass_spell_slots_artificer_rounding():
    classes = [{"class_name": "Artificer", "level": 3, "caster_type": "half"}]
    slots = calculate_max_spell_slots("", 0, classes=classes)
    assert slots.get("level_1") == 3


def test_sync_multiclass_hit_dice():
    char_data = {
        "char_class": "Fighter",
        "char_level": 5,
        "classes": [{"class_name": "Fighter", "level": 3}, {"class_name": "Wizard", "level": 2}],
        "stats": {"STR": 15, "DEX": 10, "CON": 14, "INT": 12, "WIS": 10, "CHA": 10},
    }
    synced = sync_character_stats(char_data)
    assert synced["hit_dice"] == "3d10, 2d6"


def test_multiclass_prerequisites_validation_failure():
    char_data = {
        "char_class": "Fighter",
        "char_level": 4,
        "classes": [{"class_name": "Fighter", "level": 3}, {"class_name": "Wizard", "level": 1}],
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
    }
    corrected, issues = deterministic_validate_build(char_data)
    assert any(
        "does not meet the multiclassing stat prerequisites for Wizard" in issue for issue in issues
    )


def test_multiclass_prerequisites_validation_success():
    char_data = {
        "char_class": "Fighter",
        "char_level": 4,
        "classes": [{"class_name": "Fighter", "level": 3}, {"class_name": "Wizard", "level": 1}],
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 14, "WIS": 10, "CHA": 10},
    }
    corrected, issues = deterministic_validate_build(char_data)
    assert not any(
        "does not meet the multiclassing stat prerequisites" in issue for issue in issues
    )
