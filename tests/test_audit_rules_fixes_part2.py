from backend.services.encounter_service import XP_THRESHOLDS
from backend.services.progression_service import get_level_up_vitals
from backend.services.stats_service import calculate_max_spell_slots, sync_character_stats
from backend.services.validation_service import deterministic_validate_build


def test_sync_idempotency_equipment_bonuses():
    """Verify that sync_character_stats is completely idempotent over multiple calls with equipment."""
    base_char = {
        "char_name": "Idempotent Hero",
        "char_class": "Fighter",
        "char_level": 3,
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "base_stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "speed": 30,
        "classes": [{"class_name": "Fighter", "level": 3}],
        "equipment": [
            {
                "name": "Ring of Health",
                "equipped": True,
                "mod1": "HP",
                "val1": 10,
            },
            {
                "name": "Boots of Speed",
                "equipped": True,
                "mod1": "SPD",
                "val1": 10,
            },
            {
                "name": "Cloak of Protection",
                "equipped": True,
                "mod1": "SAVES",
                "val1": 1,
            },
            {
                "name": "Helm of Awareness",
                "equipped": True,
                "mod1": "INIT",
                "val1": 2,
            },
            {
                "name": "Amulet of Strife",
                "equipped": True,
                "mod1": "ATK",
                "val1": 1,
                "mod2": "DMG",
                "val2": 1,
            },
        ],
        "features_traits": [],
    }

    # Run 1
    run1 = sync_character_stats(base_char)
    # Expected HP: Fighter 3 with CON 14 = 10+2 + (6+2)*2 = 28. Plus 10 equipment = 38.
    assert run1["hp_max"] == 38
    assert run1["speed"] == 40
    assert run1["global_attack_bonus"] == 1
    assert run1["global_damage_bonus"] == 1
    assert run1["initiative_bonus"] == 2
    # DEX 14 (+2) + 2 init bonus = 4
    assert run1["initiative_modifier"] == 4
    # All saves get +1 from cloak
    for stat in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        base_mod = (run1["stats"][stat] - 10) // 2
        prof = run1["proficiency_bonus"] if stat in run1.get("saving_throws", []) else 0
        assert run1["saving_throw_values"][stat] == base_mod + prof + 1

    # Runs 2 through 5: Must match run1 exactly!
    current = run1
    for i in range(2, 6):
        current = sync_character_stats(current)
        assert current["hp_max"] == 38, f"HP drifted on run {i}: {current['hp_max']}"
        assert current["speed"] == 40, f"Speed drifted on run {i}: {current['speed']}"
        assert current["global_attack_bonus"] == 1
        assert current["global_damage_bonus"] == 1
        assert current["initiative_bonus"] == 2
        assert current["initiative_modifier"] == 4


def test_equipment_unequip_returns_to_base():
    """Unequipping items must restore base HP, Speed, and other stats."""
    base_char = {
        "char_name": "Equipper",
        "char_class": "Fighter",
        "char_level": 3,
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "base_stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "speed": 30,
        "classes": [{"class_name": "Fighter", "level": 3}],
        "equipment": [
            {"name": "Ring of Health", "equipped": True, "mod1": "HP", "val1": 15},
            {"name": "Boots of Speed", "equipped": True, "mod1": "SPD", "val1": 10},
        ],
    }

    synced_equipped = sync_character_stats(base_char)
    assert synced_equipped["hp_max"] == 28 + 15
    assert synced_equipped["speed"] == 40

    # Unequip items
    for item in synced_equipped["equipment"]:
        item["equipped"] = False

    synced_unequipped = sync_character_stats(synced_equipped)
    assert synced_unequipped["hp_max"] == 28
    assert synced_unequipped["speed"] == 30


def test_dwarven_toughness_feat_matching():
    """Dwarven Toughness (+1 HP/level) must not trigger the Tough feat (+2 HP/level)."""
    dwarf_char = {
        "char_name": "Thorin",
        "char_class": "Fighter",
        "char_level": 3,
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "base_stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "classes": [{"class_name": "Fighter", "level": 3}],
        "features_traits": [
            {
                "name": "Dwarven Toughness",
                "description": "Your hit point maximum increases by 1, and it increases by 1 every time you gain a level.",
            }
        ],
    }

    synced_dwarf = sync_character_stats(dwarf_char)
    # Base: 28. Dwarven toughness: +3. Total = 31 (NOT 34!).
    assert synced_dwarf["hp_max"] == 31

    vitals = get_level_up_vitals(
        "Fighter", 3, 14, edition="2014 Edition", features=dwarf_char["features_traits"]
    )
    assert vitals["hp_bonus_per_level"] == 1

    # Now verify actual Tough feat gives +2
    tough_char = {
        "char_name": "Bruenor",
        "char_class": "Fighter",
        "char_level": 3,
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "base_stats": {"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "classes": [{"class_name": "Fighter", "level": 3}],
        "features_traits": [
            {
                "name": "Feat: Tough",
                "description": "Your hit point maximum increases by an amount equal to twice your level.",
            }
        ],
    }
    synced_tough = sync_character_stats(tough_char)
    # Base: 28. Tough: +6. Total = 34.
    assert synced_tough["hp_max"] == 34


def test_eldritch_knight_spell_slots():
    """Verify single-class Eldritch Knight spell slots match official PHB progression."""
    # Level 3: 2 1st
    assert calculate_max_spell_slots("Fighter", 3, "Eldritch Knight", "third") == {"level_1": 2}
    # Level 4: 3 1st (previously was 2 due to floor((4+1)/3) = 1)
    assert calculate_max_spell_slots("Fighter", 4, "Eldritch Knight", "third") == {"level_1": 3}
    # Level 7: 4 1st, 2 2nd (previously was missing 2nd level slots)
    assert calculate_max_spell_slots("Fighter", 7, "Eldritch Knight", "third") == {
        "level_1": 4,
        "level_2": 2,
    }
    # Level 10: 4 1st, 3 2nd
    assert calculate_max_spell_slots("Fighter", 10, "Eldritch Knight", "third") == {
        "level_1": 4,
        "level_2": 3,
    }
    # Level 13: 4 1st, 3 2nd, 2 3rd
    assert calculate_max_spell_slots("Fighter", 13, "Eldritch Knight", "third") == {
        "level_1": 4,
        "level_2": 3,
        "level_3": 2,
    }
    # Level 16: 4 1st, 3 2nd, 3 3rd
    assert calculate_max_spell_slots("Fighter", 16, "Eldritch Knight", "third") == {
        "level_1": 4,
        "level_2": 3,
        "level_3": 3,
    }
    # Level 19: 4 1st, 3 2nd, 3 3rd, 1 4th
    assert calculate_max_spell_slots("Fighter", 19, "Eldritch Knight", "third") == {
        "level_1": 4,
        "level_2": 3,
        "level_3": 3,
        "level_4": 1,
    }
    # Level 20: 4 1st, 3 2nd, 3 3rd, 1 4th
    assert calculate_max_spell_slots("Fighter", 20, "Eldritch Knight", "third") == {
        "level_1": 4,
        "level_2": 3,
        "level_3": 3,
        "level_4": 1,
    }


def test_2024_paladin_ranger_level_1_spell_slots():
    """In 2024 (5.5e), Paladin and Ranger gain spell slots at Level 1, while 2014 gains at Level 2."""
    # 2024: Paladin and Ranger get 2 1st-level slots at Level 1
    pal_2024 = calculate_max_spell_slots(
        "Paladin", 1, caster_type="half", edition="2024 Revision (5.5e)"
    )
    assert pal_2024 == {"level_1": 2}

    ran_2024 = calculate_max_spell_slots(
        "Ranger", 1, caster_type="half", edition="2024 Revision (5.5e)"
    )
    assert ran_2024 == {"level_1": 2}

    # 2014: Paladin and Ranger get 0 slots at Level 1
    pal_2014 = calculate_max_spell_slots("Paladin", 1, caster_type="half", edition="2014 Edition")
    assert pal_2014 == {}

    ran_2014 = calculate_max_spell_slots("Ranger", 1, caster_type="half", edition="2014 Edition")
    assert ran_2014 == {}


def test_rogue_sneak_attack_multiclass():
    """Sneak Attack damage dice must scale with Rogue level, not total character level."""
    # Fighter 5 / Rogue 3 (Total level 8): Sneak attack should be 2d6 ((3+1)//2), NOT 4d6 ((8+1)//2)
    multiclass_char = {
        "char_name": "Shadow Knight",
        "char_class": "Fighter",
        "char_level": 8,
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "classes": [
            {"class_name": "Fighter", "level": 5},
            {"class_name": "Rogue", "level": 3},
        ],
        "features_traits": [
            {
                "name": "Sneak Attack",
                "description": "Beginning at 1st level, you know how to strike subtly and exploit a foe's distraction. Once per turn, you can deal an extra 1d6 damage to one creature you hit with an attack...",
            }
        ],
    }

    synced = sync_character_stats(multiclass_char)
    sneak_trait = next(f for f in synced["features_traits"] if f.get("name") == "Sneak Attack")
    assert "extra 2d6 damage" in sneak_trait["description"]
    assert "extra 4d6 damage" not in sneak_trait["description"]


def test_multiclass_subclass_validation():
    """Subclass validation must check class-specific level, not total character level."""
    # Fighter 2 / Wizard 3 (total level 5). Champion requires Fighter level 3.
    invalid_char = {
        "char_name": "Invalid Champion",
        "char_class": "Fighter",
        "subclass": "Champion",
        "char_level": 5,
        "dnd_edition": "2014 Edition",
        "classes": [
            {"class_name": "Fighter", "level": 2, "subclass": "Champion"},
            {"class_name": "Wizard", "level": 3},
        ],
    }

    corrected, issues = deterministic_validate_build(invalid_char)
    assert corrected["subclass"] is None
    assert any("Champion" in issue and "requires level" in issue for issue in issues)

    # Fighter 3 / Wizard 2 (total level 5). Champion on Fighter 3 is valid.
    valid_char = {
        "char_name": "Valid Champion",
        "char_class": "Fighter",
        "subclass": "Champion",
        "char_level": 5,
        "dnd_edition": "2014 Edition",
        "classes": [
            {"class_name": "Fighter", "level": 3, "subclass": "Champion"},
            {"class_name": "Wizard", "level": 2},
        ],
    }
    corrected_valid, issues_valid = deterministic_validate_build(valid_char)
    assert corrected_valid["subclass"] == "Champion"
    assert not any("Champion" in issue for issue in issues_valid)


def test_encounter_level_9_thresholds():
    """XP threshold for level 9 must match official DMG values."""
    assert XP_THRESHOLDS[9]["easy"] == 550
    assert XP_THRESHOLDS[9]["medium"] == 1100
    assert XP_THRESHOLDS[9]["hard"] == 1600
    assert XP_THRESHOLDS[9]["deadly"] == 2400


def test_base_stats_reconciles_manual_and_asi_edits_while_preserving_equipment_idempotency():
    """Editing stats (via ASI or Edit Sheet Modal) must update base_stats without losing equipment idempotency."""
    from backend.core.schemas import CharacterSchema
    from backend.services.forge_service import process_character_update

    char = {
        "char_name": "Growing Fighter",
        "char_class": "Fighter",
        "char_level": 3,
        "race": "Human",
        "background": "Soldier",
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "equipment": [
            {"name": "Gauntlets of Might", "equipped": True, "mod1": "STR", "val1": 2},
        ],
    }

    # Initial sync: base STR = 16, equipped STR = 18
    synced = sync_character_stats(char)
    assert synced["base_stats"]["STR"] == 16
    assert synced["stats"]["STR"] == 18
    assert synced["equip_stat_bonuses"]["STR"] == 2

    # Roundtrip through CharacterSchema
    validated = CharacterSchema.model_validate(synced, strict=False).model_dump()
    assert validated["base_stats"]["STR"] == 16
    assert validated["equip_stat_bonuses"]["STR"] == 2

    # Simulate Edit Sheet Modal or ASI increasing STR by +2 (18 -> 20) and CON by +2 (14 -> 16)
    validated["stats"]["STR"] = 20
    validated["stats"]["CON"] = 16
    updated = process_character_update(validated)
    assert updated["base_stats"]["STR"] == 18
    assert updated["stats"]["STR"] == 20
    assert updated["base_stats"]["CON"] == 16
    assert updated["stats"]["CON"] == 16

    # Unequipping the item drops STR back to new base (18), not old base (16)
    updated["equipment"][0]["equipped"] = False
    unequipped = sync_character_stats(updated)
    assert unequipped["stats"]["STR"] == 18


def test_tough_feat_applies_to_existing_hp_and_2024_farmer_background():
    """Tough feat (+2 HP/lvl) must increase hp_max even when existing_hp > 0, and 2024 Farmer background must apply Tough on first sync."""
    # 1. Existing character at Level 4 with hp_max=36 picks Tough
    char = {
        "char_name": "Brawler",
        "char_class": "Fighter",
        "char_level": 4,
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "hp_max": 36,
        "hp_current": 36,
        "classes": [{"class_name": "Fighter", "level": 4}],
        "features_traits": [{"name": "Feat: Tough", "description": "+2 HP per level"}],
    }
    synced = sync_character_stats(char)
    assert synced["hp_max"] == 36 + 8
    assert synced["hp_current"] == 44
    # Second sync must remain idempotent at 44
    synced_again = sync_character_stats(synced)
    assert synced_again["hp_max"] == 44

    # 2. 2024 Farmer background auto-injects Origin Feat: Tough BEFORE HP calculation
    farmer_2024 = {
        "char_name": "Farmer Hero",
        "char_class": "Fighter",
        "char_level": 1,
        "background": "Farmer",
        "dnd_edition": "2024 Revision (5.5e)",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
        "classes": [{"class_name": "Fighter", "level": 1}],
        "features_traits": [],
    }
    synced_farmer = sync_character_stats(farmer_2024)
    # Fighter 1 with CON 14 = 12 base + 2 from Farmer's Tough = 14 on the VERY FIRST sync!
    assert synced_farmer["hp_max"] == 14


def test_non_caster_fighter_subclasses_get_zero_spell_slots():
    """Champion and Battle Master Fighters must never receive third-caster spell slots."""
    assert calculate_max_spell_slots("Fighter", 5, "Champion") == {}
    assert calculate_max_spell_slots("Fighter", 5, "Battle Master") == {}
    assert (
        calculate_max_spell_slots(
            "Fighter",
            5,
            "Champion",
            classes=[{"class_name": "Fighter", "level": 5, "subclass": "Champion"}],
        )
        == {}
    )
    # Paladin 1 / Wizard 1 in 2014: Paladin 1 contributes 0, Wizard 1 contributes 1 -> 2 1st-level slots
    assert calculate_max_spell_slots(
        "Paladin",
        2,
        classes=[
            {"class_name": "Paladin", "level": 1, "caster_type": "half"},
            {"class_name": "Wizard", "level": 1, "caster_type": "full"},
        ],
        edition="2014 Edition",
    ) == {"level_1": 2}


def test_2024_subclasses_lookup_and_psi_warrior():
    """RulesRepository.get_subclasses must return 2024 subclasses for '2024' and '2024 Revision (5.5e)', including Psi Warrior."""
    from backend.repositories.rules_repository import RulesRepository

    repo = RulesRepository()
    subs_short = repo.get_subclasses("Fighter", "2024")
    subs_full = repo.get_subclasses("Fighter", "2024 Revision (5.5e)")
    assert subs_short == subs_full
    assert "Psi Warrior" in subs_short
    assert "Brawler" not in subs_short
    assert len(subs_short) == 4


def test_ac_breakdown_preserves_higher_unarmored_source():
    """Monk Unarmored Defense (17) must not have its base_source overwritten by lower Mage Armor (16)."""
    from backend.services.stats_service import calculate_ac

    ac, breakdown = calculate_ac(
        dex_score=16,
        wis_score=18,
        con_score=10,
        equipment=[],
        features=[
            {"name": "Unarmored Defense", "description": "10 + DEX + WIS", "source": "Monk"},
            {"name": "Mage Armor", "description": "Base AC becomes 13 + DEX"},
        ],
        return_breakdown=True,
    )
    assert ac == 17
    assert breakdown["base"] == 14
    assert "Unarmored Defense (Monk" in breakdown["base_source"]


def test_multiclass_armor_proficiencies_and_perception_removal():
    """Wizard 1 / Fighter 1 wearing Chain Mail is proficient via Fighter, and removing Perception proficiency sticks."""
    wiz_fighter = {
        "char_name": "Armored Mage",
        "char_class": "Wizard",
        "char_level": 2,
        "dnd_edition": "2014 Edition",
        "stats": {"STR": 14, "DEX": 10, "CON": 14, "INT": 16, "WIS": 12, "CHA": 10},
        "classes": [
            {"class_name": "Wizard", "level": 1},
            {"class_name": "Fighter", "level": 1},
        ],
        "equipment": [{"name": "Chain Mail", "equipped": True}],
        "skill_proficiencies": ["Perception", "Arcana"],
    }
    _, issues = deterministic_validate_build(wiz_fighter)
    assert not any("lacks proficiency for chain mail" in i.lower() for i in issues)

    synced = sync_character_stats(wiz_fighter)
    assert "Perception" in synced["skill_proficiencies"]
    assert synced["passive_perception"] == 13

    # User removes Perception proficiency
    synced["skill_proficiencies"] = ["Arcana"]
    resynced = sync_character_stats(synced)
    assert "Perception" not in resynced["skill_proficiencies"]
    assert resynced["passive_perception"] == 11
