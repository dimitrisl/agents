from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.dice_service import roll_dice
from backend.services.encounter_service import calculate_danger_indicator
from backend.services.stats_service import calculate_ac, sync_character_stats
from backend.services.validation_service import deterministic_validate_build


def test_unarmored_defense_style_not_applied():
    """Defense Fighting Style (+1 AC) must ONLY apply while wearing armor."""
    # Unarmored Barbarian (base 10 + CON 16 (+3) + DEX 14 (+2) = 15 AC)
    features = [
        {"name": "Unarmored Defense", "description": "Barbarian CON to AC", "source": "Barbarian"},
        {"name": "Fighting Style: Defense", "description": "While wearing armor gain +1 AC"},
    ]
    ac = calculate_ac(dex_score=14, equipment=[], features=features, con_score=16)
    assert ac == 15  # NOT 16!


def test_defense_style_applied_with_armor():
    """Defense Fighting Style applies when armor is equipped."""
    features = [
        {"name": "Fighting Style: Defense", "description": "While wearing armor gain +1 AC"},
    ]
    # Chain Mail base 16, no DEX bonus, +1 Defense style = 17
    equipment = [{"name": "Chain Mail", "equipped": True}]
    ac = calculate_ac(dex_score=14, equipment=equipment, features=features)
    assert ac == 17


def test_multiple_shields_no_stack():
    """Equipping multiple shields must not stack AC bonuses."""
    equipment = [
        {"name": "Leather Armor", "equipped": True},  # Base 11 + DEX 14 (+2) = 13
        {"name": "Shield", "equipped": True, "ac_bonus": 2},
        {"name": "Shield", "equipped": True, "ac_bonus": 2},
    ]
    ac = calculate_ac(dex_score=14, equipment=equipment, features=[])
    assert ac == 15  # 11 + 2 + 2 = 15, NOT 17 (+4)!


def test_retroactive_con_hp_increase():
    """When CON increases, HP max must increase retroactively by (delta * level)."""
    char_data = {
        "char_name": "Torgar",
        "char_class": "Fighter",
        "char_level": 5,
        "base_stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "hp_max": 44,  # Level 1: 10+2=12, L2-5: 4*(6+2)=32 -> Total 44
        "hp_current": 44,
        "dnd_edition": "2014 Edition",
        "equipment": [],
    }
    # Initial sync keeps HP at 44 and records con_mod_applied = 2
    synced = sync_character_stats(char_data)
    assert synced["hp_max"] == 44

    # Now simulate equipping Amulet of Health (sets CON to 19, modifier +4, delta +2)
    synced["equipment"] = [{"name": "Amulet of Health", "equipped": True}]
    synced_after_item = sync_character_stats(synced)
    # Retroactive HP: 44 + (2 delta * 5 levels) = 54 HP
    assert synced_after_item["hp_max"] == 54
    assert synced_after_item["hp_current"] == 54

    # Now simulate level-up ASI: base_stats CON increases from 14 to 16 (+1 modifier delta)
    char_asi = {
        "char_name": "Torgar",
        "char_class": "Fighter",
        "char_level": 5,
        "base_stats": {"STR": 16, "DEX": 10, "CON": 16, "INT": 10, "WIS": 10, "CHA": 10},
        "stats": {"STR": 16, "DEX": 10, "CON": 16, "INT": 10, "WIS": 10, "CHA": 10},
        "hp_max": 44,
        "hp_current": 44,
        "con_mod_applied": 2,  # Previous calculation was at CON 14 (+2)
        "dnd_edition": "2014 Edition",
    }
    synced_asi = sync_character_stats(char_asi)
    assert synced_asi["hp_max"] == 49
    assert synced_asi["hp_current"] == 49


def test_2024_cleric_subclass_min_level():
    """2024 Clerics must not be allowed to choose a subclass before Level 3."""
    char_data = {
        "char_name": "Elowen",
        "char_class": "Cleric",
        "char_level": 1,
        "subclass": "Life Domain",
        "dnd_edition": "2024 Revision (5.5e)",
        "base_stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 16, "CHA": 10},
    }
    corrected, issues = deterministic_validate_build(char_data)
    assert corrected["subclass"] is None
    assert any("requires level 3" in issue for issue in issues)


def test_2024_weapon_masteries_count():
    """Verify 2024 Weapon Masteries count per class at level 4."""
    # Fighter level 4 gets 4 masteries
    fighter_data = {
        "char_name": "Valeros",
        "char_class": "Fighter",
        "char_level": 4,
        "dnd_edition": "2024 Revision (5.5e)",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "weapons": [{"name": "Longsword"}],
    }
    synced_fighter = sync_character_stats(fighter_data)
    assert len(synced_fighter["weapon_masteries"]) == 4

    # Paladin level 4 stays at 2 masteries (does NOT scale to 3)
    paladin_data = {
        "char_name": "Seelah",
        "char_class": "Paladin",
        "char_level": 4,
        "dnd_edition": "2024 Revision (5.5e)",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 14},
        "weapons": [{"name": "Longsword"}],
    }
    synced_paladin = sync_character_stats(paladin_data)
    assert len(synced_paladin["weapon_masteries"]) == 2

    # Rogue level 4 stays at 2 masteries
    rogue_data = {
        "char_name": "Merisiel",
        "char_class": "Rogue",
        "char_level": 4,
        "dnd_edition": "2024 Revision (5.5e)",
        "stats": {"STR": 10, "DEX": 18, "CON": 14, "INT": 12, "WIS": 10, "CHA": 10},
        "weapons": [{"name": "Dagger"}],
    }
    synced_rogue = sync_character_stats(rogue_data)
    assert len(synced_rogue["weapon_masteries"]) == 2


def test_dice_nat20_guard_and_compound():
    """Multi-dice totaling 20 should not trigger Natural 20, and compound formulas should sum correctly."""
    # Compound dice
    res = roll_dice("2d6 + 1d4 + 3")
    assert res["num_dice"] == 3
    assert res["modifier"] == 3
    assert 6 <= res["total"] <= 19
    assert len(res["rolls"]) == 3
    # Multiple dice can never be Nat 20 or Nat 1
    assert res["is_nat20"] is False
    assert res["is_nat1"] is False


@pytest.mark.anyio
async def test_danger_indicator_explicit_cr_and_2024():
    """Verify danger indicator reads explicit CR and omits multipliers for 2024."""
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    # 4 level 5 heroes (Hard threshold: 4 * 750 = 3000 XP)
    mock_cursor.to_list = AsyncMock(
        return_value=[{"char_id": f"hero{i}", "char_level": 5} for i in range(1, 5)]
    )
    mock_db.__getitem__.return_value.find.return_value = mock_cursor

    # 1 Archmage with explicit CR 12 (8400 XP) -> Deadly
    combatants = [{"char_id": f"hero{i}", "is_player": True} for i in range(1, 5)] + [
        {"name": "Archmage", "is_player": False, "max_hp": 99, "cr": "12"}
    ]

    danger_2014 = await calculate_danger_indicator(combatants, mock_db, edition="2014 Edition")
    assert danger_2014 == "Deadly"

    danger_2024 = await calculate_danger_indicator(
        combatants, mock_db, edition="2024 Revision (5.5e)"
    )
    assert danger_2024 == "Deadly"


def test_ac_breakdown_transparency():
    """Verify that calculate_ac produces a rich breakdown with formula text."""
    # Armored fighter with Chain Mail, Shield, and Defense Fighting Style
    equipment = [
        {"name": "Chain Mail", "equipped": True},
        {"name": "Shield", "equipped": True},
    ]
    features = [
        {"name": "Fighting Style: Defense", "description": "+1 bonus to AC while wearing armor"}
    ]
    total_ac, breakdown = calculate_ac(
        dex_score=14,  # +2 mod, but Chain Mail (Heavy) should ignore DEX
        equipment=equipment,
        features=features,
        return_breakdown=True,
    )

    assert total_ac == 19
    assert breakdown["base"] == 16
    assert "Chain Mail" in breakdown["base_source"]
    assert breakdown["dex_applied"] == 0
    assert breakdown["shield_bonus"] == 2
    assert breakdown["defense_bonus"] == 1
    assert "Chain Mail (16)" in breakdown["formula_text"]
    assert "Shield (+2)" in breakdown["formula_text"]
    assert "Defense Style (+1)" in breakdown["formula_text"]
    assert "= 19" in breakdown["formula_text"]

    # Verify sync_character_stats also injects ac_breakdown
    char_data = {
        "char_name": "Karn",
        "char_class": "Fighter",
        "char_level": 3,
        "stats": {"STR": 16, "DEX": 14, "CON": 16, "INT": 10, "WIS": 12, "CHA": 8},
        "equipment": equipment,
        "features_traits": features,
    }
    synced = sync_character_stats(char_data)
    assert synced["armor_class"] == 19
    assert "ac_breakdown" in synced
    assert synced["ac_breakdown"]["formula_text"] == breakdown["formula_text"]
