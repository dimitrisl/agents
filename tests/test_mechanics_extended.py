from backend.services.mechanics_service import (
    calculate_hp,
    calculate_ac,
    calculate_passive_perception,
    calculate_saving_throws,
    calculate_weapon_stats,
    calculate_proficiency_bonus,
    sync_character_stats,
)


# --- calculate_hp edge cases ---


class TestCalculateHp:
    def test_minimum_hp_is_one(self):
        """Even with negative CON mod, HP can't go below 1."""
        # CON 3 -> modifier -4, d6 die -> 6 + (-4) = 2 at level 1
        assert calculate_hp("d6", 1, 3) >= 1

    def test_extreme_negative_con(self):
        """Very low CON should still produce at least 1 HP."""
        assert calculate_hp("d6", 1, 1) >= 1

    def test_existing_hp_preserved(self):
        """When existing_hp is provided and positive, it should be returned as-is."""
        assert calculate_hp("d10", 5, 14, existing_hp=50) == 50

    def test_existing_hp_zero_triggers_recalc(self):
        """existing_hp of 0 should trigger a full recalculation."""
        result = calculate_hp("d10", 1, 14, existing_hp=0)
        assert result == 12  # d10 max (10) + CON mod (2) = 12

    def test_invalid_hit_die_defaults_to_d8(self):
        """Invalid die string should fall back to d8."""
        result = calculate_hp("invalid", 1, 10)
        assert result == 8  # d8 + 0

    def test_hp_scaling_multi_level(self):
        """HP should scale correctly across multiple levels."""
        # d8, CON 10 (mod 0): Level 1 = 8, then (5+0) per level
        assert calculate_hp("d8", 1, 10) == 8
        assert calculate_hp("d8", 3, 10) == 18  # 8 + 5 + 5
        assert calculate_hp("d8", 10, 10) == 53  # 8 + (5 * 9)

    def test_d12_barbarian_hp(self):
        """Barbarian with d12 hit die, high CON."""
        # d12, CON 16 (mod +3): Level 1 = 15
        assert calculate_hp("d12", 1, 16) == 15
        # Level 5: 15 + 4 * (7 + 3) = 15 + 40 = 55
        assert calculate_hp("d12", 5, 16) == 55


# --- calculate_ac edge cases ---


class TestCalculateAc:
    def test_unequipped_items_ignored(self):
        """Items with equipped=False should not affect AC."""
        equipment = [{"name": "Plate Armor", "equipped": False}]
        assert calculate_ac(14, equipment, []) == 12  # base 10 + DEX mod 2

    def test_mixed_equipped_unequipped(self):
        """Only equipped items should contribute to AC."""
        equipment = [
            {"name": "Plate Armor", "equipped": False},
            {"name": "Shield", "equipped": True},
        ]
        # base 10 + DEX 2 + Shield 2 = 14
        assert calculate_ac(14, equipment, []) == 14

    def test_heavy_armor_ignores_dex(self):
        """Heavy armor (dex_limit=0) should not add any DEX bonus."""
        # Plate: base 18, dex_limit 0
        assert calculate_ac(20, [{"name": "Plate Armor", "equipped": True}], []) == 18

    def test_medium_armor_caps_dex(self):
        """Medium armor should cap DEX bonus at +2."""
        # Scale Mail: base 14, dex_limit 2. DEX 20 (+5) should be capped to +2
        assert calculate_ac(20, [{"name": "Scale Mail", "equipped": True}], []) == 16

    def test_light_armor_full_dex(self):
        """Light armor should allow full DEX bonus."""
        # Leather: base 11, dex_limit 10. DEX 20 (+5)
        assert calculate_ac(20, ["Leather Armor"], []) == 16

    def test_empty_equipment_list(self):
        """Empty equipment should give base AC (10 + DEX)."""
        assert calculate_ac(10, [], []) == 10
        assert calculate_ac(16, [], []) == 13  # 10 + 3

    def test_negative_dex_modifier(self):
        """Low DEX should subtract from AC."""
        assert calculate_ac(8, [], []) == 9  # 10 + (-1)

    def test_warforged_integrated_protection(self):
        """Warforged feature should add +1 AC."""
        features = [
            {"name": "Integrated Protection", "description": "Warforged AC bonus"}
        ]
        assert calculate_ac(10, [], features) == 11  # 10 + 0 + 1

    def test_manual_ac_bonus_on_equipment(self):
        """Equipment with ac_bonus field (manual entry) should be applied."""
        equipment = [{"name": "Unknown Armor", "equipped": True, "ac_bonus": 3}]
        assert calculate_ac(10, equipment, []) == 13  # 10 + 0 + 3


# --- calculate_passive_perception ---


class TestPassivePerception:
    def test_proficient_in_perception(self):
        """WIS 14 (+2), prof +2, proficient -> 10 + 2 + 2 = 14."""
        assert calculate_passive_perception(14, 2, ["Perception"]) == 14

    def test_not_proficient(self):
        """WIS 14 (+2), prof +2, not proficient -> 10 + 2 = 12."""
        assert calculate_passive_perception(14, 2, ["Athletics"]) == 12

    def test_low_wisdom(self):
        """WIS 8 (-1), no proficiency -> 10 + (-1) = 9."""
        assert calculate_passive_perception(8, 2, []) == 9

    def test_high_level_proficiency(self):
        """WIS 20 (+5), prof +6, proficient -> 10 + 5 + 6 = 21."""
        assert calculate_passive_perception(20, 6, ["Perception"]) == 21


# --- calculate_saving_throws ---


class TestSavingThrows:
    def test_basic_saves(self):
        stats = {"STR": 16, "DEX": 14, "CON": 12, "INT": 10, "WIS": 8, "CHA": 10}
        saves = calculate_saving_throws(stats, 2, ["STR", "CON"])

        assert saves["STR"] == 5  # +3 + 2 (prof)
        assert saves["DEX"] == 2  # +2 + 0
        assert saves["CON"] == 3  # +1 + 2 (prof)
        assert saves["INT"] == 0  # +0 + 0
        assert saves["WIS"] == -1  # -1 + 0
        assert saves["CHA"] == 0  # +0 + 0

    def test_no_proficient_saves(self):
        stats = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
        saves = calculate_saving_throws(stats, 3, [])
        for val in saves.values():
            assert val == 0

    def test_all_proficient_saves(self):
        stats = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
        all_stats = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
        saves = calculate_saving_throws(stats, 4, all_stats)
        for val in saves.values():
            assert val == 4  # mod 0 + prof 4

    def test_missing_stat_defaults_to_10(self):
        """Missing stats should default to 10 (modifier 0)."""
        saves = calculate_saving_throws({}, 2, [])
        for val in saves.values():
            assert val == 0


# --- calculate_weapon_stats edge cases ---


class TestWeaponStats:
    def test_finesse_weapon_uses_higher_mod(self):
        """Finesse weapons should use the higher of STR or DEX."""
        stats = {"STR": 10, "DEX": 18}  # STR +0, DEX +4
        weapon = {"name": "Rapier", "damage": "1d8"}
        result = calculate_weapon_stats(weapon, stats, 2)
        assert result["attack_bonus"] == "+6"  # DEX +4 + prof 2
        assert result["damage"] == "1d8 + 4"

    def test_finesse_weapon_str_higher(self):
        """Finesse with higher STR should use STR."""
        stats = {"STR": 20, "DEX": 10}  # STR +5, DEX +0
        weapon = {"name": "Dagger", "damage": "1d4"}
        result = calculate_weapon_stats(weapon, stats, 2)
        assert result["attack_bonus"] == "+7"  # STR +5 + prof 2
        assert result["damage"] == "1d4 + 5"

    def test_ranged_weapon_uses_dex(self):
        stats = {"STR": 18, "DEX": 14}  # STR +4, DEX +2
        weapon = {"name": "Shortbow", "damage": "1d6"}
        result = calculate_weapon_stats(weapon, stats, 2)
        assert result["attack_bonus"] == "+4"  # DEX +2 + prof 2
        assert result["damage"] == "1d6 + 2"

    def test_zero_modifier_no_damage_suffix(self):
        """With 0 modifier, damage string should be just the dice."""
        stats = {"STR": 10, "DEX": 10}
        weapon = {"name": "Club", "damage": "1d4"}
        result = calculate_weapon_stats(weapon, stats, 2)
        assert result["attack_bonus"] == "+2"
        assert result["damage"] == "1d4"

    def test_negative_modifier(self):
        stats = {"STR": 6, "DEX": 10}  # STR -2
        weapon = {"name": "Greataxe", "damage": "1d12"}
        result = calculate_weapon_stats(weapon, stats, 2)
        assert result["attack_bonus"] == "+0"  # -2 + 2 = 0
        assert result["damage"] == "1d12 - 2"

    def test_existing_modifier_stripped(self):
        """Old modifier in stored damage string should be stripped cleanly."""
        stats = {"STR": 16, "DEX": 10}  # STR +3
        weapon = {"name": "Longsword", "damage": "1d8 + 5"}  # stale stored value
        result = calculate_weapon_stats(weapon, stats, 2)
        assert result["damage"] == "1d8 + 3"


# --- calculate_proficiency_bonus ---


class TestProficiencyBonus:
    def test_all_standard_breakpoints(self):
        """Check every standard proficiency bonus breakpoint."""
        assert calculate_proficiency_bonus(1) == 2
        assert calculate_proficiency_bonus(4) == 2
        assert calculate_proficiency_bonus(5) == 3
        assert calculate_proficiency_bonus(8) == 3
        assert calculate_proficiency_bonus(9) == 4
        assert calculate_proficiency_bonus(12) == 4
        assert calculate_proficiency_bonus(13) == 5
        assert calculate_proficiency_bonus(16) == 5
        assert calculate_proficiency_bonus(17) == 6
        assert calculate_proficiency_bonus(20) == 6

    def test_with_class_data_override(self):
        """If class_data provides proficiency_bonus at a level, use it."""
        class_data = {
            "progression": {
                "1": {"proficiency_bonus": 2},
                "5": {"proficiency_bonus": 3},
            }
        }
        assert calculate_proficiency_bonus(1, class_data) == 2
        assert calculate_proficiency_bonus(5, class_data) == 3

    def test_class_data_missing_level_falls_back(self):
        """If class_data doesn't have the level, fall back to formula."""
        class_data = {"progression": {"1": {"proficiency_bonus": 2}}}
        assert calculate_proficiency_bonus(9, class_data) == 4  # formula fallback


# --- sync_character_stats edge cases ---


class TestSyncCharacterStats:
    def test_sync_with_string_equipment(self):
        """sync_character_stats should handle string-based equipment."""
        char = {
            "char_level": 1,
            "char_class": "Fighter",
            "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        }
        synced = sync_character_stats(char, {"hit_die": "d10"})
        assert synced["hp_max"] == 10  # d10 + 0 CON
        assert synced["armor_class"] == 10  # base, no armor

    def test_sync_with_pydantic_stat_block(self):
        """sync should handle Pydantic StatBlock objects in addition to dicts."""
        from backend.core.schemas import StatBlock

        char = {
            "char_level": 3,
            "char_class": "Wizard",
            "stats": StatBlock(STR=8, DEX=14, CON=12, INT=18, WIS=10, CHA=10),
        }
        synced = sync_character_stats(char, {"hit_die": "d6"})
        assert synced["proficiency_bonus"] == 2
        # d6+1 at level 1, then 2*(4+1)=10 -> 7 + 10 = 17
        assert synced["hp_max"] == 17  # d6(6) + 1 CON + 2*(4+1)

    def test_sync_initiative_with_alert_feat(self):
        """Alert feat should add +5 to initiative."""
        char = {
            "char_level": 1,
            "char_class": "Rogue",
            "stats": {"STR": 10, "DEX": 16, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
            "features_traits": [
                {"name": "Alert", "description": "You gain +5 to initiative."}
            ],
        }
        synced = sync_character_stats(char, {"hit_die": "d8"})
        # DEX mod (+3) + Alert (+5) = +8
        assert synced["initiative_modifier"] == 8

    def test_sync_without_alert(self):
        """Without Alert, initiative should equal DEX modifier."""
        char = {
            "char_level": 1,
            "char_class": "Fighter",
            "stats": {"STR": 10, "DEX": 14, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        }
        synced = sync_character_stats(char, {"hit_die": "d10"})
        assert synced["initiative_modifier"] == 2  # DEX mod only

    def test_sync_hit_die_with_1d_prefix(self):
        """class_data with '1d10' format should work same as 'd10'."""
        char = {
            "char_level": 1,
            "char_class": "Fighter",
            "stats": {"STR": 10, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        }
        synced = sync_character_stats(char, {"hit_die": "1d10"})
        assert synced["hp_max"] == 12  # 10 + 2 CON

    def test_sync_tough_feat_bonus(self):
        """Tough feat should add +2 HP per level."""
        char = {
            "char_level": 5,
            "char_class": "Fighter",
            "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
            "features_traits": [
                {"name": "Tough", "description": "Your HP increases by +2 per level."}
            ],
        }
        synced = sync_character_stats(char, {"hit_die": "d10"})
        # Base HP: 10 + 4*(6+0) = 34. Tough: +2*5 = 10. Total = 44
        assert synced["hp_max"] == 44

    def test_sync_saving_throws(self):
        """Saving throws should include proficiency for proficient saves."""
        char = {
            "char_level": 1,
            "char_class": "Fighter",
            "stats": {"STR": 16, "DEX": 14, "CON": 12, "INT": 10, "WIS": 8, "CHA": 10},
            "saving_throws": ["STR", "CON"],
        }
        synced = sync_character_stats(char, {"hit_die": "d10"})
        assert synced["saving_throw_values"]["STR"] == 5  # +3 + 2
        assert synced["saving_throw_values"]["CON"] == 3  # +1 + 2
        assert synced["saving_throw_values"]["DEX"] == 2  # +2 + 0
        assert synced["saving_throw_values"]["WIS"] == -1  # -1 + 0

    def test_sync_hit_dice_string_format(self):
        """hit_dice field should be formatted as '{level}{die}' e.g. '5d10'."""
        char = {
            "char_level": 5,
            "char_class": "Fighter",
            "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
        }
        synced = sync_character_stats(char, {"hit_die": "d10"})
        assert synced["hit_dice"] == "5d10"
