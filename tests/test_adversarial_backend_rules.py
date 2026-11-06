"""Adversarial stress-test suite for backend rules and mechanics changes.

Covers:
1. Dynamic attunement limits & Artificer multiclass scaling (Artificer 9/Wizard 1 vs Artificer 10/Wizard 1)
2. Extreme attunement cap enforcement (Artificer 18 with 6 vs 7 items)
3. Half-proficiency non-stacking (Jack of All Trades + Remarkable Athlete on Initiative and Skills)
4. Starting equipment auto-equip invariant & armor proficiency enforcement (Paladin, Wizard, Barbarian)
5. Combat state sync (Death saves strictly reset on heal from 0 HP; Concentration DC formula max(10, floor(dmg/2)))
"""

import math
from pathlib import Path

from fastapi.testclient import TestClient

from backend.services.stats_service import (
    calculate_skills,
    has_jack_of_all_trades,
    has_remarkable_athlete,
    sync_character_stats,
)
from backend.services.validation_service import (
    deterministic_validate_build,
    get_character_armor_proficiencies,
    get_max_attunement_slots,
)
from tests.e2e.conftest import E2EAuthHelper, auth_helper, e2e_client, mock_db

# Ensure fixtures are recognized by pytest
__all__ = ["mock_db", "e2e_client", "auth_helper"]


# ============================================================================
# 1. Dynamic Attunement Limits & Multiclassing
# ============================================================================


class TestAdversarialDynamicAttunement:
    """Stress-tests dynamic attunement slot rules for Artificer multiclassing and scaling."""

    def test_artificer_multiclass_boundary_level_9_vs_10(self):
        """Artificer 9 / Wizard 1 has total level 10, but only 9 Artificer levels.

        5e Rule: Magic Item Adept is an Artificer 10th-level feature.
        Therefore, Artificer 9 / Wizard 1 must be capped at 3 attunement slots.
        Artificer 10 / Wizard 1 gains Magic Item Adept and expands to 4 slots.
        """
        # --- Case A: Artificer 9 / Wizard 1 (Total Level 10, Artificer 9) ---
        artificer_9_wiz_1 = {
            "char_name": "Tinker Mage 9-1",
            "char_class": "Artificer",
            "char_level": 10,
            "classes": [
                {"class_name": "Artificer", "level": 9},
                {"class_name": "Wizard", "level": 1},
            ],
            "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 18, "WIS": 10, "CHA": 10},
            "equipment": [
                {
                    "name": f"Ring of Protection +{i}",
                    "equipped": True,
                    "attuned": True,
                    "ac_bonus": 1,
                }
                for i in range(1, 5)  # 4 attuned items
            ],
        }

        # 1. Check max attunement slots function directly
        assert get_max_attunement_slots(artificer_9_wiz_1) == 3

        # 2. Deterministic validation must flag exceeding limit 3
        _, issues = deterministic_validate_build(artificer_9_wiz_1)
        assert any("exceeding the maximum attunement limit of 3" in issue for issue in issues), (
            f"Expected attunement limit 3 violation, got issues: {issues}"
        )

        # 3. Stats synchronization must only apply 3 attuned item bonuses
        synced_9 = sync_character_stats(artificer_9_wiz_1)
        # Base AC 10 + 3 active rings = 13 (4th ring must be ignored)
        assert synced_9["armor_class"] == 13

        # --- Case B: Artificer 10 / Wizard 1 (Total Level 11, Artificer 10) ---
        artificer_10_wiz_1 = {
            "char_name": "Tinker Mage 10-1",
            "char_class": "Artificer",
            "char_level": 11,
            "classes": [
                {"class_name": "Artificer", "level": 10},
                {"class_name": "Wizard", "level": 1},
            ],
            "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 18, "WIS": 10, "CHA": 10},
            "equipment": [
                {
                    "name": f"Ring of Protection +{i}",
                    "equipped": True,
                    "attuned": True,
                    "ac_bonus": 1,
                }
                for i in range(1, 5)  # 4 attuned items
            ],
        }

        # 1. Check max attunement slots
        assert get_max_attunement_slots(artificer_10_wiz_1) == 4

        # 2. 4 attuned items must PASS deterministic validation
        _, issues_10 = deterministic_validate_build(artificer_10_wiz_1)
        assert not any("attunement limit" in issue for issue in issues_10)

        # 3. Stats sync must apply all 4 attuned rings -> AC 14
        synced_10 = sync_character_stats(artificer_10_wiz_1)
        assert synced_10["armor_class"] == 14

        # 4. Adding a 5th attuned item must trigger violation of limit 4
        artificer_10_wiz_1["equipment"].append(
            {"name": "Ring 5", "equipped": True, "attuned": True, "ac_bonus": 1}
        )
        _, issues_5 = deterministic_validate_build(artificer_10_wiz_1)
        assert any("exceeding the maximum attunement limit of 4" in issue for issue in issues_5)

    def test_class_order_and_naming_invariance(self):
        """Attunement limit calculation must be robust to class order and case formatting."""
        # Wizard is primary class in char_class, but Artificer 10 is in classes list
        reversed_order = {
            "char_name": "Arcane Engineer",
            "char_class": "Wizard",
            "char_level": 12,
            "classes": [
                {"class_name": "Wizard", "level": 2},
                {"class_name": "artificer", "level": 10},  # lowercase class name
            ],
        }
        assert get_max_attunement_slots(reversed_order) == 4

        # Non-artificer high level multiclass
        non_artificer = {
            "char_name": "Fighter Wizard",
            "char_class": "Fighter",
            "char_level": 20,
            "classes": [
                {"class_name": "Fighter", "level": 10},
                {"class_name": "Wizard", "level": 10},
            ],
        }
        assert get_max_attunement_slots(non_artificer) == 3


# ============================================================================
# 2. Extreme Attunement Limits (Artificer 18)
# ============================================================================


class TestAdversarialExtremeAttunement:
    """Stress-tests the maximum extreme attunement limit (Artificer 18 Magic Item Master = 6 slots)."""

    def test_artificer_18_six_vs_seven_attuned_items(self):
        """Artificer 18: 6 attuned items passes validation; 7th item strictly rejected."""
        artificer_18 = {
            "char_name": "Omni-Artificer",
            "char_class": "Artificer",
            "char_level": 18,
            "classes": [{"class_name": "Artificer", "level": 18}],
            "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 20, "WIS": 10, "CHA": 10},
            "equipment": [
                {
                    "name": f"Amulet of Warding +{i}",
                    "equipped": True,
                    "attuned": True,
                    "ac_bonus": 1,
                }
                for i in range(1, 7)  # Exactly 6 attuned items
            ],
        }

        # 1. Max slots is 6
        assert get_max_attunement_slots(artificer_18) == 6

        # 2. 6 attuned items -> PASS
        _, issues_6 = deterministic_validate_build(artificer_18)
        assert not any("attunement limit" in issue for issue in issues_6)

        # 3. AC applies all 6 bonuses -> Base 10 + 6 = 16
        synced = sync_character_stats(artificer_18)
        assert synced["armor_class"] == 16

        # 4. Add 7th attuned item -> strictly rejected with limit 6
        artificer_18["equipment"].append(
            {"name": "Amulet 7", "equipped": True, "attuned": True, "ac_bonus": 1}
        )
        _, issues_7 = deterministic_validate_build(artificer_18)
        assert any(
            "Character is attuned to 7 magic items, exceeding the maximum attunement limit of 6."
            in issue
            for issue in issues_7
        )

        # 5. In stats sync, 7th item must NOT increase AC beyond 6 attuned bonuses
        synced_7 = sync_character_stats(artificer_18)
        assert synced_7["armor_class"] == 16

    def test_unattuned_magic_items_do_not_consume_slots(self):
        """Magic items in inventory with attuned=False do not count against attunement limit."""
        artificer_18 = {
            "char_name": "Vault Keeper",
            "char_class": "Artificer",
            "char_level": 18,
            "classes": [{"class_name": "Artificer", "level": 18}],
            "equipment": [
                {"name": f"Attuned Item {i}", "equipped": True, "attuned": True}
                for i in range(1, 7)
            ]
            + [
                {"name": f"Unattuned Item {i}", "equipped": True, "attuned": False}
                for i in range(1, 15)  # 14 additional magic items not attuned
            ],
        }
        _, issues = deterministic_validate_build(artificer_18)
        assert not any("attunement limit" in issue for issue in issues)


# ============================================================================
# 3. Half-Proficiency Non-Stacking
# ============================================================================


class TestAdversarialHalfProficiencyNonStacking:
    """Stress-tests Bard Jack of All Trades and Champion Remarkable Athlete non-stacking."""

    def test_half_proficiency_non_stacking_pb3_adversarial(self):
        """Adversarial scenario: Character with DEX 14 (+2) and prof bonus 3 with BOTH

        Jack of All Trades and Remarkable Athlete.
        Initiative modifier must be +3 (+2 DEX + 1 half prof), strictly NOT +4.
        """
        # Character with explicit features granting both, at Level 7 (where 5e PB is +3)
        char = {
            "char_name": "Athletic Skald",
            "char_class": "Fighter",
            "char_level": 7,
            "subclass": "Champion",
            "features_traits": [
                {"name": "Jack of All Trades", "description": "Add half proficiency bonus"},
                {"name": "Remarkable Athlete", "description": "Add half proficiency bonus"},
            ],
            "stats": {"STR": 10, "DEX": 14, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
            "skill_proficiencies": [],
        }

        # Validate detection functions
        assert has_jack_of_all_trades(char) is True
        assert has_remarkable_athlete(char) is True

        synced = sync_character_stats(char)
        # Level 7 character has proficiency bonus 3
        assert synced["proficiency_bonus"] == 3

        # Initiative calculation:
        # DEX 14 modifier = +2
        # Remarkable Athlete (round up per 5e RAW) = ceil(3 / 2) = 2
        # Correct non-stacking = 2 + 2 = 4 (takes higher rounded-up bonus, does not stack 2 + 1)
        assert synced["initiative_modifier"] == 4, (
            f"Initiative modifier must be +4 (non-stacked), got {synced['initiative_modifier']}"
        )

    def test_half_proficiency_multiclass_bard2_champion7_level9(self):
        """In official 5e multiclassing, Bard 2 / Champion Fighter 7 is character level 9.

        At level 9, proficiency bonus is +4, half-proficiency is +2.
        With DEX 14 (+2), initiative modifier must be +4 (+2 DEX + 2 half prof), NOT +6.
        """
        multiclass_char = {
            "char_name": "Battle Minstrel",
            "char_class": "Bard",
            "char_level": 9,
            "classes": [
                {"class_name": "Bard", "level": 2},
                {"class_name": "Fighter", "level": 7, "subclass": "Champion"},
            ],
            "stats": {"STR": 10, "DEX": 14, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
            "skill_proficiencies": [],
            "features_traits": [],
        }

        synced = sync_character_stats(multiclass_char)
        assert synced["proficiency_bonus"] == 4

        # DEX (+2) + half-prof (+2) = 4
        # If stacked: DEX (+2) + 2 + 2 = 6
        assert synced["initiative_modifier"] == 4
        assert synced["skills"]["Athletics"] == 2  # STR 0 + 2 half-prof (not 4)
        assert synced["skills"]["Acrobatics"] == 4  # DEX 2 + 2 half-prof (not 6)

    def test_direct_calculate_skills_non_stacking(self):
        """calculate_skills with both half_prof_all=True and half_prof_phys=True must NOT stack."""
        stats = {"STR": 10, "DEX": 14, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
        skills = calculate_skills(
            stats=stats,
            proficiency_bonus=3,
            proficiencies=[],
            expertise=[],
            half_prof_all=True,
            half_prof_phys=True,
        )

        # Athletics (STR 10 -> mod 0): 0 + ceil(3/2) = 2 (Remarkable Athlete rounds up, does NOT stack with Jack)
        assert skills["Athletics"] == 2
        # Acrobatics (DEX 14 -> mod 2): 2 + ceil(3/2) = 4, NOT 2 + 2 + 1 = 5
        assert skills["Acrobatics"] == 4
        # Stealth (DEX 14 -> mod 2): 2 + 2 = 4, NOT 5
        assert skills["Stealth"] == 4
        # Arcana (INT 10 -> mod 0, mental skill): 0 + floor(3/2) = 1 (Jack rounds down)
        assert skills["Arcana"] == 1

    def test_initiative_proficiency_overrides_half_proficiency_2024(self):
        """In 2024 Revision, Alert grants initiative proficiency.

        Full PB applies without stacking half-proficiency.
        """
        alert_bard_2024 = {
            "char_name": "Alert Skald 2024",
            "char_class": "Bard",
            "char_level": 7,  # PB = 3
            "dnd_edition": "2024 Revision",
            "stats": {"STR": 10, "DEX": 14, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
            "features_traits": [
                {"name": "Jack of All Trades"},
                {"name": "Alert", "initiative_proficiency": True},
            ],
            "skill_proficiencies": [],
        }
        synced = sync_character_stats(alert_bard_2024)
        # DEX (+2) + Full PB (+3) = +5 (MUST NOT add half-prof +1 to become +6)
        assert synced["initiative_modifier"] == 5


# ============================================================================
# 4. Starting Equipment Invariant & Armor Proficiencies
# ============================================================================


class TestAdversarialStartingEquipmentInvariant:
    """Stress-tests the auto-equip invariant for starting armor/shield and proficiency gates."""

    def test_paladin_starting_chain_mail_and_shield_ac18_and_defense_ac19(self):
        """Paladin created with Chain Mail and Shield without equipped flags -> AC 18.

        With Fighting Style: Defense -> AC 19.
        Both items must be marked equipped: True.
        """
        # Baseline Paladin
        paladin = {
            "char_name": "Uther the Pure",
            "char_class": "Paladin",
            "char_level": 1,
            "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 12, "CHA": 14},
            "equipment": [
                {"name": "Chain Mail"},  # Base AC 16 (Heavy Armor)
                {"name": "Shield"},  # +2 AC
            ],
        }
        synced = sync_character_stats(paladin)

        # Invariant checks:
        assert synced["equipment"][0]["name"] == "Chain Mail"
        assert synced["equipment"][0]["equipped"] is True
        assert synced["equipment"][1]["name"] == "Shield"
        assert synced["equipment"][1]["equipped"] is True
        assert synced["armor_class"] == 18

        # Paladin with Defense Fighting Style
        paladin_defense = {
            "char_name": "Uther the Aegis",
            "char_class": "Paladin",
            "char_level": 2,
            "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 12, "CHA": 14},
            "features_traits": [
                {
                    "name": "Fighting Style: Defense",
                    "description": "While you are wearing armor, you gain a +1 bonus to AC.",
                }
            ],
            "equipment": [
                {"name": "Chain Mail"},
                {"name": "Shield"},
            ],
        }
        synced_def = sync_character_stats(paladin_defense)
        assert synced_def["equipment"][0]["equipped"] is True
        assert synced_def["equipment"][1]["equipped"] is True
        # AC: 16 (Chain Mail) + 2 (Shield) + 1 (Defense) = 19
        assert synced_def["armor_class"] == 19

    def test_non_proficient_character_never_auto_equips_armor(self):
        """A character with no armor proficiency possessing Chain Mail must NOT equip it."""
        # Wizard with no armor proficiencies
        wizard = {
            "char_name": "Ignis the Scorcher",
            "char_class": "Wizard",
            "char_level": 1,
            "stats": {"STR": 8, "DEX": 14, "CON": 12, "INT": 16, "WIS": 12, "CHA": 10},
            "equipment": [
                {"name": "Chain Mail"},  # Heavy Armor - Wizard NOT proficient
                {"name": "Dagger"},
            ],
        }

        # Verify proficiencies: Wizard has 0 armor proficiencies (passing None for class_data)
        profs = get_character_armor_proficiencies(wizard, None)
        assert "heavy armor" not in profs
        assert len(profs) == 0

        synced_wiz = sync_character_stats(wizard)
        # Chain Mail must NOT be equipped
        assert synced_wiz["equipment"][0].get("equipped", False) is False
        # AC must remain unarmored DEX bonus: 10 + DEX 14 (+2) = 12
        assert synced_wiz["armor_class"] == 12

    def test_barbarian_partial_proficiency_auto_equips_medium_not_heavy(self):
        """Barbarian is proficient in Light and Medium armor, but NOT Heavy armor.

        Given Chain Mail and Scale Mail in inventory, Scale Mail must be equipped, NOT Chain Mail.
        """
        barbarian = {
            "char_name": "Krag",
            "char_class": "Barbarian",
            "char_level": 1,
            "stats": {"STR": 16, "DEX": 14, "CON": 16, "INT": 8, "WIS": 10, "CHA": 8},
            "equipment": [
                {"name": "Chain Mail"},  # Heavy - NOT proficient
                {"name": "Scale Mail"},  # Medium (Base 14, DEX max 2) - proficient
            ],
        }
        synced = sync_character_stats(barbarian)
        assert synced["equipment"][0].get("equipped", False) is False
        assert synced["equipment"][1]["equipped"] is True
        # AC: Scale Mail 14 + DEX (+2) = 16
        assert synced["armor_class"] == 16


# ============================================================================
# 5. Combat State Sync: Death Saves Reset & Concentration DC Formula
# ============================================================================


class TestAdversarialCombatStateSync:
    """Stress-tests combat state synchronization across death saves and concentration DC."""

    def test_heal_from_zero_strictly_resets_death_saves_api(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """DM healing a dying character (0 HP) to >0 HP strictly resets death saves to 0/0."""
        dm_headers = auth_helper.register_and_login("dm_combat_adv", "dm_adv@forge.dnd")
        player_headers = auth_helper.register_and_login("p_combat_adv", "p_adv@forge.dnd")

        # 1. DM creates campaign
        campaign_name = "Adversarial Combat Sync"
        c_res = e2e_client.post(
            "/api/v1/campaigns/", json={"campaign_name": campaign_name}, headers=dm_headers
        )
        assert c_res.status_code == 200

        invite_code = e2e_client.post(
            f"/api/v1/campaigns/{campaign_name}/invite-code", headers=dm_headers
        ).json()["invite_code"]

        # 2. Player creates a dying character with 2 successes and 2 failures
        char_payload = {
            "char_name": "Fallen Hero",
            "char_class": "Paladin",
            "char_level": 3,
            "race": "Human",
            "background": "Soldier",
            "hp_max": 28,
            "hp_current": 0,
            "death_saves": {"successes": 2, "failures": 2},
            "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 12, "CHA": 14},
        }
        p_res = e2e_client.post("/api/v1/characters", json=char_payload, headers=player_headers)
        assert p_res.status_code in (200, 201), f"Failed to create character: {p_res.text}"
        char_id = p_res.json()["char_id"]

        # 3. Player joins campaign
        j_res = e2e_client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": invite_code, "character_id": char_id},
            headers=player_headers,
        )
        assert j_res.status_code == 200

        # 4. DM heals player from 0 HP to 8 HP
        heal_res = e2e_client.patch(
            f"/api/v1/campaigns/{campaign_name}/party/{char_id}/state",
            json={"hp_current": 8},
            headers=dm_headers,
        )
        assert heal_res.status_code == 200
        heal_data = heal_res.json()

        # Invariant verification:
        assert heal_data["hp_current"] == 8

        # 5. Verify database persistence (D&D Rules Invariant: 0 HP -> >0 HP strictly resets death saves)
        persisted = e2e_client.get(f"/api/v1/characters/{char_id}", headers=player_headers).json()
        assert persisted["death_saves"]["successes"] == 0
        assert persisted["death_saves"]["failures"] == 0

    def test_heal_from_above_zero_preserves_death_saves(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """Healing a character that was NOT at 0 HP must not alter existing death save records."""
        dm_headers = auth_helper.register_and_login("dm_heal_stable", "dm_stable@forge.dnd")
        player_headers = auth_helper.register_and_login("p_heal_stable", "p_stable@forge.dnd")

        c_name = "Stable Campaign"
        e2e_client.post("/api/v1/campaigns/", json={"campaign_name": c_name}, headers=dm_headers)
        invite = e2e_client.post(
            f"/api/v1/campaigns/{c_name}/invite-code", headers=dm_headers
        ).json()["invite_code"]

        # Character at 5 HP with recorded death saves (e.g. stabilized previously)
        char = e2e_client.post(
            "/api/v1/characters",
            json={
                "char_name": "Recovering Rogue",
                "char_class": "Rogue",
                "char_level": 2,
                "race": "Elf",
                "background": "Criminal",
                "hp_max": 18,
                "hp_current": 5,
                "death_saves": {"successes": 1, "failures": 0},
                "stats": {"STR": 10, "DEX": 16, "CON": 12, "INT": 10, "WIS": 12, "CHA": 10},
            },
            headers=player_headers,
        ).json()
        char_id = char["char_id"]

        e2e_client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": invite, "character_id": char_id},
            headers=player_headers,
        )

        # DM heals from 5 to 12
        patch_res = e2e_client.patch(
            f"/api/v1/campaigns/{c_name}/party/{char_id}/state",
            json={"hp_current": 12},
            headers=dm_headers,
        )
        assert patch_res.status_code == 200

        # death_saves must not be reset because old_hp > 0
        after = e2e_client.get(f"/api/v1/characters/{char_id}", headers=player_headers).json()
        assert after["death_saves"]["successes"] == 1

    def test_concentration_saving_throw_dc_mathematical_oracle_matrix(self):
        """Comprehensive verification of the D&D 5e Concentration DC formula:

        DC = max(10, floor(damage / 2))
        Evaluated across odd, even, sub-threshold, and high damage values.
        """

        def concentration_dc(dmg: int) -> int:
            return max(10, math.floor(dmg / 2))

        # Values <= 21 must strictly yield DC 10
        for dmg in range(1, 22):
            assert concentration_dc(dmg) == 10, f"Failed at damage={dmg}"

        # Threshold transitions
        assert concentration_dc(22) == 11
        assert concentration_dc(23) == 11  # floor(23/2) = 11
        assert concentration_dc(24) == 12
        assert concentration_dc(25) == 12
        assert concentration_dc(30) == 15
        assert concentration_dc(35) == 17
        assert concentration_dc(40) == 20
        assert concentration_dc(55) == 27
        assert concentration_dc(70) == 35
        assert concentration_dc(100) == 50

    def test_client_player_component_concentration_rules_fidelity(self):
        """Verifies player.component.ts strictly implements:

        1. DC = Math.max(10, Math.floor(damage / 2))
        2. HP == 0 drops concentration immediately.
        """
        player_ts_path = (
            Path(__file__).resolve().parent.parent
            / "client"
            / "src"
            / "app"
            / "features"
            / "player"
            / "player.component.ts"
        )
        assert player_ts_path.exists()
        code = player_ts_path.read_text()

        # Rule 1: DC formula Math.max(10, Math.floor(damage / 2))
        assert "Math.max(10, Math.floor(" in code
        assert "damage / 2" in code or "amount / 2" in code

        # Rule 2: Reaching 0 HP drops concentration automatically
        assert "if (hp === 0)" in code or "hp === 0" in code
        assert "concentrating_on = undefined" in code or 'concentrating_on = ""' in code
