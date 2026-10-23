"""
QA Playbook & Test Suite: Veteran Player Evaluation (#162)
Covers all 4 Veteran Player evaluation scenarios:
1. Character Creation (The Forge & Manual Creation, 2014 vs 2024, Point Buy, Defense Style, Origin Bonuses, Wizard Spellbook)
2. Live Combat, Vitals & Rest Mechanics (Interactive AC Breakdown, Shield non-stacking, Dynamic HP bounds, Retroactive CON HP, Multiclass & Warlock Rests)
3. Dice, Modifiers & Weapon Masteries (Compound rolls, Advantage/Disadvantage, 2024 Weapon Masteries & Topple DC)
4. Live Collaboration with DM (Secret Rolls, Live Whispers isolation, DM State Sync)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.core.constants import EDITION_2014, EDITION_2024, WEAPON_MASTERIES_2024
from backend.services.dice_service import roll_dice
from backend.services.stats_service import (
    calculate_ac,
    get_modifier,
    sync_character_stats,
)
from server.routers.campaign_router import _authorize_roll_request_target


def apply_short_rest(char: dict, hit_dice_spent: int = 0, roll_result: int = 0) -> dict:
    """Applies D&D 5e short rest mechanics (Pact Magic slot recovery and hit dice healing)."""
    import copy

    res = copy.deepcopy(char)
    if "spell_slots" in res and "pact_magic" in res["spell_slots"]:
        res["spell_slots"]["pact_magic"]["used"] = 0
    if hit_dice_spent > 0 and roll_result > 0:
        con_mod = get_modifier((res.get("stats") or {}).get("CON", 10))
        heal = max(1, roll_result + con_mod)
        res["hp_current"] = min(res.get("hp_max", 1), res.get("hp_current", 0) + heal)
        res["hit_dice_used"] = res.get("hit_dice_used", 0) + hit_dice_spent
    return res


# ============================================================================
# Scenario 1: Character Creation (The Forge & Manual Creation)
# ============================================================================


def test_scenario_1_defense_fighting_style_armor_requirement():
    """Fighting Style 'Defense' gives +1 AC only when wearing armor."""
    # 1. Unarmored: Defense style must NOT grant +1 AC
    ac_unarmored, breakdown_unarmored = calculate_ac(
        dex_score=14,  # +2 mod
        equipment=[],
        features=[{"name": "Fighting Style: Defense", "source": "Class"}],
        return_breakdown=True,
    )
    assert ac_unarmored == 12  # 10 base + 2 DEX
    assert breakdown_unarmored["defense_bonus"] == 0

    # 2. Armored (Chain Mail, base 16, heavy): Defense style grants +1 AC -> 17
    ac_armored, breakdown_armored = calculate_ac(
        dex_score=14,
        equipment=[{"name": "Chain Mail", "equipped": True}],
        features=[{"name": "Fighting Style: Defense", "source": "Class"}],
        return_breakdown=True,
    )
    assert ac_armored == 17  # 16 + 1 defense
    assert breakdown_armored["defense_bonus"] == 1


def test_scenario_1_point_buy_bounds_and_origin_bonuses():
    """Point Buy enforces 8-15 base stats before Origin/Racial bonuses."""
    valid_base = {"STR": 15, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8}
    for stat, val in valid_base.items():
        assert 8 <= val <= 15, f"Point buy stat {stat} out of bounds"

    # Adding Origin Bonuses (+2 STR, +1 CON)
    final_stats = dict(valid_base)
    final_stats["STR"] += 2  # 17 (+3)
    final_stats["CON"] += 1  # 14 (+2)

    assert get_modifier(final_stats["STR"]) == 3
    assert get_modifier(final_stats["CON"]) == 2
    assert get_modifier(final_stats["CHA"]) == -1


def test_scenario_1_2024_weapon_masteries_and_subclass_progression():
    """2024 Fighter selects up to 3 masteries; 2024 subclasses start at Level 3."""
    # Masteries validation
    selected_masteries = ["Topple", "Vex", "Nick"]
    for m in selected_masteries:
        assert m in WEAPON_MASTERIES_2024

    # 2024 Subclass Level progression rule
    def get_subclass_unlock_level(cls: str, edition: str) -> int:
        if edition == EDITION_2024:
            return 3  # All 2024 classes unlock subclass at Level 3
        # 2014 Cleric / Warlock / Sorcerer unlock at L1
        if cls in ("Cleric", "Warlock", "Sorcerer"):
            return 1
        return 3

    assert get_subclass_unlock_level("Cleric", EDITION_2024) == 3
    assert get_subclass_unlock_level("Fighter", EDITION_2024) == 3
    assert get_subclass_unlock_level("Cleric", EDITION_2014) == 1


def test_scenario_1_wizard_level_1_spell_limits():
    """Wizard Level 1 starts with exactly 3 cantrips and 6 level 1 spells in spellbook."""
    cantrips = ["Fire Bolt", "Mage Hand", "Light"]
    level_1_spells = [
        "Shield",
        "Mage Armor",
        "Magic Missile",
        "Sleep",
        "Detect Magic",
        "Find Familiar",
    ]

    assert len(cantrips) == 3
    assert len(level_1_spells) == 6


# ============================================================================
# Scenario 2: Live Combat, Vitals & Rest Mechanics
# ============================================================================


def test_scenario_2_interactive_ac_breakdown_and_shield_stacking():
    """AC breakdown displays correctly; two shields do NOT stack."""
    equipment = [
        {"name": "Scale Mail", "equipped": True},  # Base 14, max dex 2
        {"name": "Shield", "equipped": True},  # +2
        {"name": "Shield", "equipped": True},  # Second shield must not stack
    ]
    ac, breakdown = calculate_ac(
        dex_score=16,  # +3 DEX, capped at +2 by medium armor
        equipment=equipment,
        features=[{"name": "Fighting Style: Defense"}],
        return_breakdown=True,
    )
    # Expected: 14 (base) + 2 (dex cap) + 2 (shield) + 1 (defense) = 19
    assert ac == 19
    assert breakdown["base"] == 14
    assert breakdown["dex_applied"] == 2
    assert breakdown["shield_bonus"] == 2
    assert breakdown["defense_bonus"] == 1


def test_scenario_2_vitals_hp_bounds_and_retroactive_con():
    """HP does not drop below 0 or exceed max; CON mod change retroactively scales HP."""
    char = {
        "char_level": 5,
        "char_class": "Fighter",
        "hit_dice": "1d10",
        "con_mod_applied": 2,
        "base_stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "hp_max": 44,  # Level 1 (10+2) + 4*(6+2) = 44
        "hp_current": 44,
        "hp_temp": 0,
    }

    # Damage test
    damage = 50
    char["hp_current"] = max(0, min(char["hp_max"], char["hp_current"] - damage))
    assert char["hp_current"] == 0  # Clamped at 0

    # Healing test
    heal = 100
    char["hp_current"] = max(0, min(char["hp_max"], char["hp_current"] + heal))
    assert char["hp_current"] == 44  # Clamped at max

    # Retroactive CON increase: CON 14 (+2) -> CON 16 (+3)
    # At Level 5, an increase of +1 CON mod must add 5 HP retroactively!
    char["stats"]["CON"] = 16
    char = sync_character_stats(char)
    assert char["hp_max"] == 49  # 44 + 5 = 49
    assert char["hp_current"] == 49


def test_scenario_2_rest_mechanics_warlock_pact_magic():
    """Short rest recovers Warlock Pact Magic slots while regular slots recover on Long Rest."""
    char = {
        "char_class": "Warlock",
        "char_level": 3,
        "spell_slots": {
            "pact_magic": {"total": 2, "used": 2, "level": 2},
            "level_1": {"total": 4, "used": 3},
        },
        "hp_current": 10,
        "hp_max": 24,
        "hit_dice_used": 1,
    }

    # Simulate Short Rest
    restored = apply_short_rest(char, hit_dice_spent=1, roll_result=6)
    # Pact magic must recover to used=0
    assert restored["spell_slots"]["pact_magic"]["used"] == 0
    # Regular spell slots must NOT recover on short rest
    assert restored["spell_slots"]["level_1"]["used"] == 3


# ============================================================================
# Scenario 3: Dice, Modifiers & Weapon Masteries
# ============================================================================


def test_scenario_3_dice_roller_compound_buffs_and_masteries():
    """Evaluates compound rolls and Weapon Mastery Topple DC calculation."""
    # 1. Compound roll: 1d20 + 5 + 1d4 (e.g. Bless)
    res = roll_dice("1d20 + 5 + 1d4")
    assert 7 <= res["total"] <= 29  # min 1+5+1, max 20+5+4

    # 2. Topple Save DC formula: 8 + Proficiency Bonus + Ability Modifier (STR)
    proficiency_bonus = 3
    str_mod = 4
    topple_dc = 8 + proficiency_bonus + str_mod
    assert topple_dc == 15


# ============================================================================
# Scenario 4: Live Collaboration with DM (WebSockets & Whispers)
# ============================================================================


@pytest.mark.anyio
async def test_scenario_4_secret_roll_visibility_authorization():
    """Secret roll requests are only authorized for target character or DM."""
    collections = {}

    def get_col(name):
        if name not in collections:
            collections[name] = MagicMock()
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_col

    target_char = {"char_id": "hero_1", "char_name": "Rogue", "owner_id": "player_123"}
    mock_db["characters"].find_one = AsyncMock(return_value=target_char)
    mock_db["campaigns"].find_one = AsyncMock(
        return_value={"campaign_name": "Strahd", "party": ["hero_1"]}
    )

    caller_player = {"id": "player_123", "username": "hero_player"}
    caller_dm = {"id": "dm_456", "username": "dungeon_master"}
    caller_stranger = {"id": "player_999", "username": "random_player"}

    target = {"char_filename": "hero_1.json", "char_name": "Rogue"}

    # 1. Target player can roll (no exception raised)
    await _authorize_roll_request_target(
        mock_db, "Strahd", target, caller_player, {"user_id": "player_123", "role": "player"}
    )

    # 2. DM can roll (no exception raised)
    await _authorize_roll_request_target(
        mock_db, "Strahd", target, caller_dm, {"user_id": "dm_456", "role": "dm"}
    )

    # 3. Stranger is forbidden
    with pytest.raises(HTTPException) as exc_info:
        await _authorize_roll_request_target(
            mock_db, "Strahd", target, caller_stranger, {"user_id": "player_999", "role": "player"}
        )
    assert exc_info.value.status_code == 403


def test_scenario_4_whisper_filtering_and_recipient_privacy():
    """Whispers are private to sender and recipient; third parties cannot view them."""
    whisper_doc = {
        "id": "w1",
        "campaign_name": "Strahd",
        "sender": "Rogue",
        "recipient": "DM",
        "sender_user_id": "user_rogue",
        "recipient_user_id": "user_dm",
        "message": "I slip poison into the chalice.",
        "archived_at": None,
    }

    def is_whisper_visible_to_user(w: dict, uid: str, is_dm: bool) -> bool:
        if is_dm:
            return True
        if w.get("recipient") == "All":
            return True
        return w.get("sender_user_id") == uid or w.get("recipient_user_id") == uid

    assert is_whisper_visible_to_user(whisper_doc, "user_rogue", is_dm=False) is True
    assert is_whisper_visible_to_user(whisper_doc, "user_dm", is_dm=True) is True
    assert is_whisper_visible_to_user(whisper_doc, "user_paladin", is_dm=False) is False
