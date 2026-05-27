from backend.services.mechanics_service import (
    get_modifier,
    calculate_proficiency_bonus,
    calculate_hp,
    calculate_ac,
    calculate_weapon_stats,
    sync_character_stats,
)


def test_get_modifier():
    assert get_modifier(10) == 0
    assert get_modifier(11) == 0
    assert get_modifier(12) == 1
    assert get_modifier(8) == -1
    assert get_modifier(20) == 5
    assert get_modifier(1) == -5


def test_calculate_proficiency_bonus():
    assert calculate_proficiency_bonus(1) == 2
    assert calculate_proficiency_bonus(4) == 2
    assert calculate_proficiency_bonus(5) == 3
    assert calculate_proficiency_bonus(9) == 4
    assert calculate_proficiency_bonus(13) == 5
    assert calculate_proficiency_bonus(17) == 6
    assert calculate_proficiency_bonus(20) == 6


def test_calculate_hp():
    # Fighter level 1, CON 14 (+2)
    assert calculate_hp("d10", 1, 14) == 12
    # Fighter level 2, CON 14 (+2) -> 12 + (6 + 2) = 20
    assert calculate_hp("d10", 2, 14) == 20
    # Wizard level 1, CON 10 (0) -> 6 + 0 = 6
    assert calculate_hp("d6", 1, 10) == 6


def test_calculate_ac_unarmored():
    # DEX 14 (+2), No armor
    assert calculate_ac(14, [], []) == 12
    # DEX 10 (0), No armor
    assert calculate_ac(10, [], []) == 10


def test_calculate_ac_with_armor():
    # DEX 14 (+2), Leather Armor (11 + DEX)
    assert calculate_ac(14, ["Leather Armor"], []) == 13
    # DEX 14 (+2), Studded Leather (12 + DEX) + Shield (+2)
    assert calculate_ac(14, ["Studded Leather", "Shield"], []) == 16
    # Plate (18, ignores DEX)
    assert calculate_ac(14, ["Plate Armor"], []) == 18


def test_calculate_weapon_stats():
    stats = {"STR": 16, "DEX": 12}  # STR +3, DEX +1
    prof = 2

    # Melee (STR)
    weapon = {"name": "Longsword", "damage": "1d8"}
    updated = calculate_weapon_stats(weapon, stats, prof)
    assert updated["attack_bonus"] == "+5"
    assert updated["damage"] == "1d8 + 3"  # STR modifier added to damage

    # Ranged (DEX)
    weapon = {"name": "Longbow", "damage": "1d8"}
    updated = calculate_weapon_stats(weapon, stats, prof)
    assert updated["attack_bonus"] == "+3"
    assert updated["damage"] == "1d8 + 1"

    # Negative Modifier (now floored to 0 for damage, as per user request)
    neg_stats = {"STR": 8, "DEX": 8}  # STR -1, DEX -1
    weapon = {"name": "Longsword", "damage": "1d8"}
    updated = calculate_weapon_stats(weapon, neg_stats, prof)
    assert updated["damage"] == "1d8"

    # Repeated Sync should NOT duplicate anything
    updated_again = calculate_weapon_stats(updated, neg_stats, prof)
    assert updated_again["damage"] == "1d8"

    # Suffix preservation — strip old modifier, keep damage type
    weapon_with_suffix = {"name": "Dagger", "damage": "1d4 piercing"}
    updated_suffix = calculate_weapon_stats(weapon_with_suffix, neg_stats, prof)
    assert updated_suffix["damage"] == "1d4 piercing"


def test_sync_character_stats():
    char_data = {
        "char_level": 1,
        "char_class": "Fighter",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        "skill_proficiencies": ["Perception"],
        "weapons": [{"name": "Longsword", "damage": "1d8"}],
        "equipment": [
            {"name": "Chain Shirt", "equipped": True},
            {"name": "Shield", "equipped": True},
        ],  # 13 + DEX (max 2) + Shield (2) = 17
    }
    class_data = {"hit_die": "d10"}

    synced = sync_character_stats(char_data, class_data)

    assert synced["proficiency_bonus"] == 2
    assert synced["hp_max"] == 12
    assert synced["armor_class"] == 17
    assert synced["passive_perception"] == 13  # 10 + 1 (WIS) + 2 (Prof)
    assert synced["weapons"][0]["attack_bonus"] == "+5"


def test_sync_character_stats_weapons_add_delete():
    char_data = {
        "char_level": 1,
        "char_class": "Fighter",
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "weapons": [
            {"name": "Dagger", "damage": "1d4", "attack_bonus": "+2"},
            {"name": "Longsword", "damage": "1d8", "attack_bonus": "+2"},
        ],
    }
    class_data = {"hit_die": "d10"}

    # Deleting Longsword (index 1) and adding Shortbow
    weapon_deltas = {
        "deleted_rows": [1],
        "added_rows": [
            {
                "name": "Shortbow",
                "damage_dice": "1d6 piercing",
                "attack_bonus": "+2",
                "range": "80/320",
                "properties": "Two-Handed",
            }
        ],
    }

    synced = sync_character_stats(char_data, class_data, weapon_deltas=weapon_deltas)

    assert len(synced["weapons"]) == 2
    assert synced["weapons"][0]["name"] == "Dagger"
    assert synced["weapons"][1]["name"] == "Shortbow"
    assert synced["weapons"][1]["range"] == "80/320"
    assert synced["weapons"][1]["properties"] == "Two-Handed"


def test_sync_character_stats_weapon_damage_edit():
    char_data = {
        "char_level": 1,
        "char_class": "Fighter",
        "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        "weapons": [
            {
                "name": "Dagger",
                "damage": "1d4 piercing",
                "attack_bonus": "+2",
                "is_custom": False,
            }
        ],
    }
    class_data = {"hit_die": "d10"}

    # Simulate user editing the "damage" column to "2d6 + 5 fire"
    weapon_deltas = {"edited_rows": {"0": {"damage": "2d6 + 5 fire"}}}

    synced = sync_character_stats(char_data, class_data, weapon_deltas=weapon_deltas)

    weapon = synced["weapons"][0]
    assert weapon["is_custom"] is True
    assert weapon["damage"] == "2d6 + 5 fire"
    assert weapon["damage_dice"] == "2d6 fire"
    assert weapon["damage_bonus"] == "+5"
