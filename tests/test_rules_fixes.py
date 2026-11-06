from backend.services.stats_service import (
    has_jack_of_all_trades,
    has_remarkable_athlete,
    sync_character_stats,
)
from backend.services.validation_service import (
    deterministic_validate_build,
    get_max_attunement_slots,
)


class TestArtificerAttunementLimits:
    """Tests for dynamic attunement slot expansion for Artificers and static limit for others."""

    def test_get_max_attunement_slots_progression(self):
        # Non-artificer
        wizard = {"char_class": "Wizard", "char_level": 20}
        assert get_max_attunement_slots(wizard) == 3

        # Artificer levels 1-9
        artificer_lvl9 = {"char_class": "Artificer", "char_level": 9}
        assert get_max_attunement_slots(artificer_lvl9) == 3

        # Artificer level 10-13 (Magic Item Adept) -> 4
        artificer_lvl10 = {"char_class": "Artificer", "char_level": 10}
        assert get_max_attunement_slots(artificer_lvl10) == 4

        # Artificer level 14-17 (Magic Item Savant) -> 5
        artificer_lvl14 = {"char_class": "Artificer", "char_level": 14}
        assert get_max_attunement_slots(artificer_lvl14) == 5

        # Artificer level 18-20 (Magic Item Master) -> 6
        artificer_lvl18 = {"char_class": "Artificer", "char_level": 18}
        assert get_max_attunement_slots(artificer_lvl18) == 6

    def test_get_max_attunement_slots_multiclass_and_features(self):
        # Multiclass character with Artificer 14 / Wizard 2
        multiclass = {
            "char_class": "Artificer",
            "classes": [
                {"class_name": "Wizard", "level": 2},
                {"class_name": "Artificer", "level": 14},
            ],
        }
        assert get_max_attunement_slots(multiclass) == 5

        # Character with explicit feature trait
        feat_char = {
            "char_class": "Homebrew",
            "features_traits": [
                {"name": "Magic Item Master", "description": "Attune up to 6 items"}
            ],
        }
        assert get_max_attunement_slots(feat_char) == 6

    def test_validation_service_artificer_attunement(self):
        # Level 10 Artificer with 4 attuned items -> 0 issues
        artificer_10 = {
            "char_name": "Tinkerer",
            "char_class": "Artificer",
            "char_level": 10,
            "classes": [{"class_name": "Artificer", "level": 10}],
            "equipment": [
                {"name": f"Item {i}", "equipped": True, "attuned": True} for i in range(1, 5)
            ],
        }
        _, issues = deterministic_validate_build(artificer_10)
        assert not any("attunement limit" in issue for issue in issues)

        # Level 10 Artificer with 5 attuned items -> issue with limit 4
        artificer_10["equipment"].append({"name": "Item 5", "equipped": True, "attuned": True})
        _, issues = deterministic_validate_build(artificer_10)
        assert any("exceeding the maximum attunement limit of 4" in issue for issue in issues)

        # Level 18 Artificer with 6 attuned items -> valid
        artificer_18 = {
            "char_name": "Master Artificer",
            "char_class": "Artificer",
            "char_level": 18,
            "classes": [{"class_name": "Artificer", "level": 18}],
            "equipment": [
                {"name": f"Item {i}", "equipped": True, "attuned": True} for i in range(1, 7)
            ],
        }
        _, issues = deterministic_validate_build(artificer_18)
        assert not any("attunement limit" in issue for issue in issues)

        # Level 18 Artificer with 7 attuned items -> rejected with limit 6
        artificer_18["equipment"].append({"name": "Item 7", "equipped": True, "attuned": True})
        _, issues = deterministic_validate_build(artificer_18)
        assert any("exceeding the maximum attunement limit of 6" in issue for issue in issues)

    def test_stats_service_attunement_bonuses_scaled_for_artificer(self):
        # Level 14 Artificer (attunement limit 5) with 5 attuned AC items
        artificer = {
            "char_name": "Automa",
            "char_class": "Artificer",
            "char_level": 14,
            "classes": [{"class_name": "Artificer", "level": 14}],
            "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 18, "WIS": 10, "CHA": 10},
            "equipment": [
                {
                    "name": f"Ring of Protection {i}",
                    "equipped": True,
                    "attuned": True,
                    "ac_bonus": 1,
                }
                for i in range(1, 6)
            ],
        }
        synced = sync_character_stats(artificer)
        # Base 10 + 5 attuned items = 15
        assert synced["armor_class"] == 15

        # Standard Wizard (limit 3) with 5 attuned items -> only 3 apply
        wizard = {
            "char_name": "Mage",
            "char_class": "Wizard",
            "char_level": 14,
            "classes": [{"class_name": "Wizard", "level": 14}],
            "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 18, "WIS": 10, "CHA": 10},
            "equipment": [
                {
                    "name": f"Ring of Protection {i}",
                    "equipped": True,
                    "attuned": True,
                    "ac_bonus": 1,
                }
                for i in range(1, 6)
            ],
        }
        wizard_synced = sync_character_stats(wizard)
        # Base 10 + 3 attuned items = 13 (4th and 5th ignored)
        assert wizard_synced["armor_class"] == 13


class TestJackOfAllTradesAndRemarkableAthlete:
    """Tests for Bard Jack of All Trades and Champion Remarkable Athlete half-proficiency."""

    def test_has_jack_and_remarkable_detection(self):
        bard_lvl1 = {"char_class": "Bard", "char_level": 1}
        bard_lvl2 = {"char_class": "Bard", "char_level": 2}
        assert not has_jack_of_all_trades(bard_lvl1)
        assert has_jack_of_all_trades(bard_lvl2)

        fighter_lvl6 = {"char_class": "Fighter", "subclass": "Champion", "char_level": 6}
        fighter_lvl7 = {"char_class": "Fighter", "subclass": "Champion", "char_level": 7}
        assert not has_remarkable_athlete(fighter_lvl6)
        assert has_remarkable_athlete(fighter_lvl7)

    def test_bard_jack_of_all_trades_skills_and_initiative(self):
        # Level 2 Bard: PB +2 -> half-prof = 1
        bard = {
            "char_name": "Minstrel",
            "char_class": "Bard",
            "char_level": 2,
            "stats": {"STR": 10, "DEX": 14, "CON": 12, "INT": 12, "WIS": 10, "CHA": 16},
            "skill_proficiencies": ["Performance", "Persuasion"],
            "features_traits": [],
        }
        synced = sync_character_stats(bard)

        # Performance (trained, CHA +3): 3 + 2 (PB) = 5
        assert synced["skills"]["Performance"] == 5
        # Athletics (untrained, STR +0): 0 + 1 (half-prof) = 1
        assert synced["skills"]["Athletics"] == 1
        # Stealth (untrained, DEX +2): 2 + 1 (half-prof) = 3
        assert synced["skills"]["Stealth"] == 3
        # History (untrained, INT +1): 1 + 1 (half-prof) = 2
        assert synced["skills"]["History"] == 2
        # Initiative: DEX (+2) + half-prof (1) = 3
        assert synced["initiative_modifier"] == 3
        # Passive Perception: WIS 10 (+0) + half-prof 1 = 11
        assert synced["passive_perception"] == 11

    def test_champion_remarkable_athlete_skills_and_initiative(self):
        # Level 7 Champion Fighter: PB +3 -> half-prof = 1
        champ = {
            "char_name": "Gladiator",
            "char_class": "Fighter",
            "subclass": "Champion",
            "char_level": 7,
            "stats": {"STR": 18, "DEX": 14, "CON": 16, "INT": 10, "WIS": 12, "CHA": 8},
            "skill_proficiencies": ["Athletics"],
            "features_traits": [],
        }
        synced = sync_character_stats(champ)

        # Athletics (trained, STR +4): 4 + 3 (PB) = 7
        assert synced["skills"]["Athletics"] == 7
        # Acrobatics (untrained, DEX +2, physical): 2 + 1 = 3
        assert synced["skills"]["Acrobatics"] == 3
        # Stealth (untrained, DEX +2, physical): 2 + 1 = 3
        assert synced["skills"]["Stealth"] == 3
        # Arcana (untrained, INT +0, mental): 0 (Remarkable Athlete only affects STR/DEX/CON)
        assert synced["skills"]["Arcana"] == 0
        # Insight (untrained, WIS +1, mental): 1
        assert synced["skills"]["Insight"] == 1
        # Initiative (DEX check): DEX (+2) + half-prof (1) = 3
        assert synced["initiative_modifier"] == 3

    def test_jack_and_remarkable_non_stacking(self):
        # Multiclass Bard 2 / Champion 7 (PB +4 -> half-prof = 2)
        multiclass = {
            "char_name": "Bardic Champion",
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
        synced = sync_character_stats(multiclass)

        # Untrained physical skill: STR 10 (+0), bonus is +2 (half-prof), NOT +4 (stacked)
        assert synced["skills"]["Athletics"] == 2
        # Initiative: DEX (+2) + half-prof (2) = 4, NOT 6
        assert synced["initiative_modifier"] == 4

    def test_initiative_proficiency_prevents_half_proficiency(self):
        # Feat with initiative proficiency (e.g., Alert 2024)
        bard = {
            "char_name": "Alert Bard",
            "char_class": "Bard",
            "char_level": 4,
            "dnd_edition": "2024 Revision",
            "stats": {"STR": 10, "DEX": 14, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
            "features_traits": [{"name": "Alert", "initiative_proficiency": True}],
            "skill_proficiencies": [],
        }
        synced = sync_character_stats(bard)
        # DEX (+2) + full PB (+2) = 4 (does NOT also add half-prof)
        assert synced["initiative_modifier"] == 4


class TestStartingEquipmentAutoEquipInvariant:
    """Tests for GitHub Issue #210: Starting armor & shield default to equipped for valid AC."""

    def test_paladin_starting_chain_mail_and_shield(self):
        # Paladin Level 2 with starting gear submitted with default equipped=False
        paladin = {
            "char_name": "Kaelen Vane",
            "char_class": "Paladin",
            "char_level": 2,
            "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 12, "CHA": 14},
            "equipment": [
                {"name": "Chain Mail"},  # Base AC 16
                {"name": "Shield"},  # +2 AC
            ],
        }
        synced = sync_character_stats(paladin)

        # Invariant: Both are auto-equipped
        assert synced["equipment"][0]["equipped"] is True
        assert synced["equipment"][1]["equipped"] is True
        # AC: 16 (Chain Mail) + 2 (Shield) = 18
        assert synced["armor_class"] == 18

    def test_auto_equip_chooses_highest_proficient_armor(self):
        # Fighter has Leather Armor (11) and Chain Mail (16)
        fighter = {
            "char_name": "Fighter",
            "char_class": "Fighter",
            "char_level": 1,
            "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
            "equipment": [
                {"name": "Leather Armor"},
                {"name": "Chain Mail"},
            ],
        }
        synced = sync_character_stats(fighter)
        assert synced["equipment"][0].get("equipped", False) is False
        assert synced["equipment"][1]["equipped"] is True
        assert synced["armor_class"] == 16

    def test_auto_equip_respects_armor_proficiencies(self):
        # Rogue is proficient in Light Armor, but NOT Heavy Armor
        rogue = {
            "char_name": "Sneak",
            "char_class": "Rogue",
            "char_level": 1,
            "stats": {"STR": 10, "DEX": 16, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10},
            "equipment": [
                {"name": "Plate Armor"},  # Heavy - not proficient
                {"name": "Leather Armor"},  # Light - proficient (11 + DEX 3 = 14)
            ],
        }
        synced = sync_character_stats(rogue)
        assert synced["equipment"][0].get("equipped", False) is False
        assert synced["equipment"][1]["equipped"] is True
        assert synced["armor_class"] == 14

    def test_manual_equipped_item_prevents_auto_equip_override(self):
        # If user explicitly marked even one item as equipped, do not override
        character = {
            "char_name": "Custom",
            "char_class": "Fighter",
            "char_level": 1,
            "stats": {"STR": 16, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
            "equipment": [
                {"name": "Common Clothes", "equipped": True},
                {"name": "Plate Armor", "equipped": False},
            ],
        }
        synced = sync_character_stats(character)
        # Does not override user choice
        assert synced["equipment"][1].get("equipped", False) is False
        assert synced["armor_class"] == 10
