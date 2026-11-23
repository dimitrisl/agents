import copy

import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.repositories.rules_repository import RulesRepository
from backend.services.stats_service import calculate_ac, sync_character_stats
from backend.services.validation_service import (
    deterministic_validate_build,
    get_character_weapon_proficiencies,
)
from server.dependencies.auth import get_current_user
from server.main import app


def _base_char(**overrides):
    base = {
        "char_id": "item-test-260",
        "char_name": "Kaelen",
        "char_class": "Wizard",
        "char_level": 5,
        "classes": [{"class_name": "Wizard", "level": 5}],
        "dnd_edition": EDITION_2024,
        "race": "Human",
        "background": "Sage",
        "stats": {"STR": 10, "DEX": 14, "CON": 14, "INT": 18, "WIS": 12, "CHA": 10},
        "saving_throws": ["INT", "WIS"],
        "skill_proficiencies": ["Arcana", "Perception"],
        "spells": {"cantrips": ["Fire Bolt"], "level_1": ["Mage Armor", "Shield"]},
        "equipment": [],
        "weapons": [],
        "features_traits": [],
    }
    base.update(overrides)
    return base


def test_items_catalog_expansion_and_api_endpoint():
    repo = RulesRepository()
    items = repo.get_all_items()
    assert len(items) >= 85

    names = [str(i.get("name") or "") for i in items]
    assert len(names) == len(set(names)), "Duplicate item names detected in items.json"

    required_items = {
        "Plate Armor",
        "Padded Armor",
        "Hide Armor",
        "Elven Chain",
        "Dwarven Plate",
        "Dragon Scale Mail",
        "Shield",
        "Shield +1",
        "Shield +2",
        "Shield +3",
        "Sentinel Shield",
        "Cloak of Protection",
        "Ring of Protection",
        "Gauntlets of Ogre Power",
        "Amulet of Health",
        "Headband of Intellect",
        "Belt of Hill Giant Strength",
        "Belt of Stone Giant Strength",
        "Belt of Frost Giant Strength",
        "Belt of Fire Giant Strength",
        "Belt of Cloud Giant Strength",
        "Belt of Storm Giant Strength",
        "Belt of Dwarvenkind",
        "Bracers of Defense",
        "Bracers of Archery",
        "Stone of Good Luck (Luckstone)",
        "Robe of the Archmagi",
        "Staff of Power",
        "Wand of the War Mage +1",
        "Wand of the War Mage +2",
        "Wand of the War Mage +3",
        "Rod of the Pact Keeper +1",
        "Rod of the Pact Keeper +2",
        "Rod of the Pact Keeper +3",
        "Amulet of the Devout +1",
        "Amulet of the Devout +2",
        "Amulet of the Devout +3",
        "Potion of Healing",
        "Bag of Holding",
    }
    assert required_items.issubset(set(names))

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"id": "item-user", "username": "tester"}
    try:
        client = TestClient(app)
        res = client.get("/api/v1/rules/items")
        assert res.status_code == 200
        api_names = {entry["name"] for entry in res.json()}
        assert len(api_names) >= 85
        assert {"Bracers of Defense", "Stone of Good Luck (Luckstone)", "Bag of Holding"}.issubset(
            api_names
        )
    finally:
        app.dependency_overrides = orig


def test_bracers_of_defense_and_robe_of_the_archmagi_unarmored_ac_2014_and_2024():
    for edition in (EDITION_2014, EDITION_2024):
        # 1. Bracers of Defense: +2 AC ONLY when wearing no armor and no shield
        unarmored = _base_char(
            dnd_edition=edition,
            equipment=[{"name": "Bracers of Defense", "equipped": True, "attuned": True}],
        )
        synced = sync_character_stats(copy.deepcopy(unarmored))
        assert synced["armor_class"] == 14  # 10 + 2 DEX + 2 Bracers

        # Holding a Shield disables Bracers of Defense (+2 Shield only -> 10 + 2 DEX + 2 Shield = 14, not 16)
        with_shield = _base_char(
            dnd_edition=edition,
            equipment=[
                {"name": "Bracers of Defense", "equipped": True, "attuned": True},
                {"name": "Shield", "equipped": True},
            ],
        )
        assert calculate_ac(14, with_shield["equipment"], edition=edition) == 14

        # Wearing Light Armor disables Bracers of Defense (12 Studded + 2 DEX = 14, not 16)
        with_armor = _base_char(
            dnd_edition=edition,
            equipment=[
                {"name": "Bracers of Defense", "equipped": True, "attuned": True},
                {"name": "Studded Leather", "equipped": True},
            ],
        )
        assert calculate_ac(14, with_armor["equipment"], edition=edition) == 14

        # Robe of the Archmagi sets unarmored base AC to 15 + DEX, stacks with Bracers of Defense,
        # adds +2 Spell Attack & +2 Spell Save DC, and does NOT block Monk Unarmored Movement
        monk_wiz = _base_char(
            char_class="Monk",
            char_level=5,
            classes=[{"class_name": "Monk", "level": 2}, {"class_name": "Wizard", "level": 3}],
            dnd_edition=edition,
            stats={"STR": 10, "DEX": 16, "CON": 12, "INT": 16, "WIS": 12, "CHA": 10},
            spell_ability="INT",
            equipment=[
                {"name": "Robe of the Archmagi", "equipped": True, "attuned": True},
                {"name": "Bracers of Defense", "equipped": True, "attuned": True},
            ],
        )
        synced_mw = sync_character_stats(copy.deepcopy(monk_wiz))
        # Base 15 (Robe) + 3 (DEX) + 2 (Bracers) = 20
        assert synced_mw["armor_class"] == 20
        # Monk L2 +10 ft Unarmored Movement still applies because Robe is not armor
        assert synced_mw["speed"] == 40
        # Spellcasting: 8 + 3 PB + 3 INT + 2 Robe = 16 DC; +3 PB + 3 INT + 2 Robe = +8 Atk
        assert synced_mw["spell_save_dc"] == 16
        assert synced_mw["spell_attack_bonus"] == "+8"

        # Athas / Antimagic suppresses both Robe of the Archmagi and Bracers of Defense
        suppressed_mw = sync_character_stats({**monk_wiz, "magic_items_suppressed": True})
        assert suppressed_mw["armor_class"] == 14  # Monk 10 + 1 WIS + 3 DEX
        assert suppressed_mw["spell_save_dc"] == 14
        assert suppressed_mw["spell_attack_bonus"] == "+6"


def test_stone_of_good_luck_skills_saves_passives_and_initiative():
    for edition in (EDITION_2014, EDITION_2024):
        base = _base_char(dnd_edition=edition)
        plain = sync_character_stats(copy.deepcopy(base))

        with_luck = sync_character_stats(
            _base_char(
                dnd_edition=edition,
                equipment=[
                    {"name": "Stone of Good Luck (Luckstone)", "equipped": True, "attuned": True}
                ],
            )
        )
        # +1 to every saving throw
        for stat in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
            assert with_luck["saving_throw_values"][stat] == plain["saving_throw_values"][stat] + 1
        # +1 to every skill, passive perception, and initiative
        for sk_name in with_luck["skills"]:
            assert with_luck["skills"][sk_name] == plain["skills"][sk_name] + 1
        assert with_luck["passive_perception"] == plain["passive_perception"] + 1
        assert with_luck["initiative_modifier"] == plain["initiative_modifier"] + 1

        # Also works when entered by short alias "Luckstone"
        short_alias = sync_character_stats(
            _base_char(
                dnd_edition=edition,
                equipment=[{"name": "Luckstone", "equipped": True, "attuned": True}],
            )
        )
        assert short_alias["skills"]["Arcana"] == plain["skills"]["Arcana"] + 1
        assert short_alias["saving_throw_values"]["CON"] == plain["saving_throw_values"]["CON"] + 1

        # Athas suppresses Luckstone bonuses non-destructively
        suppressed = sync_character_stats(
            _base_char(
                dnd_edition=edition,
                magic_items_suppressed=True,
                equipment=[
                    {"name": "Stone of Good Luck (Luckstone)", "equipped": True, "attuned": True}
                ],
            )
        )
        assert suppressed["saving_throw_values"] == plain["saving_throw_values"]
        assert suppressed["skills"] == plain["skills"]
        assert suppressed["passive_perception"] == plain["passive_perception"]
        assert suppressed["initiative_modifier"] == plain["initiative_modifier"]


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_caster_focus_items_staff_of_power_and_athas_suppression(edition: str):
    # Wand of the War Mage +2 (test both "+2" and "(+2)" parenthetical lookup!)
    for wand_name in ("Wand of the War Mage +2", "Wand of the War Mage (+2)"):
        wiz = sync_character_stats(
            _base_char(
                dnd_edition=edition,
                equipment=[{"name": wand_name, "equipped": True, "attuned": True}],
            )
        )
        # L5 (+3 PB) + INT 18 (+4) = +7 base; +2 Wand = +9 attack, DC unchanged (15)
        assert wiz["spell_attack_bonus"] == "+9"
        assert wiz["spell_save_dc"] == 15

    # Rod of the Pact Keeper +3 boosts BOTH Spell Attack and Spell Save DC
    warlock = sync_character_stats(
        _base_char(
            dnd_edition=edition,
            char_class="Warlock",
            classes=[{"class_name": "Warlock", "level": 9}],
            char_level=9,
            stats={"STR": 8, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 20},
            spell_ability="CHA",
            equipment=[{"name": "Rod of the Pact Keeper +3", "equipped": True, "attuned": True}],
        )
    )
    # L9 (+4 PB) + CHA 20 (+5) + 3 Rod = 20 DC & +12 Spell Atk
    assert warlock["spell_save_dc"] == 20
    assert warlock["spell_attack_bonus"] == "+12"

    # Amulet of the Devout +1 boosts Cleric DC & Attack
    cleric = sync_character_stats(
        _base_char(
            dnd_edition=edition,
            char_class="Cleric",
            classes=[{"class_name": "Cleric", "level": 5}],
            char_level=5,
            stats={"STR": 14, "DEX": 10, "CON": 14, "INT": 10, "WIS": 18, "CHA": 10},
            spell_ability="WIS",
            equipment=[{"name": "Amulet of the Devout +1", "equipped": True, "attuned": True}],
        )
    )
    assert cleric["spell_save_dc"] == 16
    assert cleric["spell_attack_bonus"] == "+8"

    # Staff of Power grants +2 AC, +2 Saves, +2 Spell Atk (not +2 Spell DC)
    staff_wiz = sync_character_stats(
        _base_char(
            dnd_edition=edition,
            equipment=[{"name": "Staff of Power", "equipped": True, "attuned": True}],
        )
    )
    assert staff_wiz["armor_class"] == 14  # 10 + 2 DEX + 2 Staff
    assert staff_wiz["saving_throw_values"]["CON"] == 4  # +2 CON + 2 Staff
    assert staff_wiz["spell_attack_bonus"] == "+9"
    assert staff_wiz["spell_save_dc"] == 15

    # Athas suppresses all focus/staff bonuses
    suppressed_lock = sync_character_stats(
        _base_char(
            dnd_edition=edition,
            char_class="Warlock",
            classes=[{"class_name": "Warlock", "level": 9}],
            char_level=9,
            stats={"STR": 8, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 20},
            spell_ability="CHA",
            magic_items_suppressed=True,
            equipment=[{"name": "Rod of the Pact Keeper +3", "equipped": True, "attuned": True}],
        )
    )
    assert suppressed_lock["spell_save_dc"] == 17
    assert suppressed_lock["spell_attack_bonus"] == "+9"


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_stat_items_sentinel_shield_magic_armors_and_bracers_of_archery(edition: str):
    # 1. Headband of Intellect, Belts of Giant Strength, Belt of Dwarvenkind, Ioun Stone
    fighter = sync_character_stats(
        _base_char(
            dnd_edition=edition,
            char_class="Fighter",
            classes=[{"class_name": "Fighter", "level": 5}],
            stats={"STR": 12, "DEX": 14, "CON": 14, "INT": 8, "WIS": 10, "CHA": 10},
            saving_throws=["STR", "CON"],
            equipment=[
                {"name": "Headband of Intellect", "equipped": True, "attuned": True},
                {"name": "Belt of Fire Giant Strength", "equipped": True, "attuned": True},
                {"name": "Ioun Stone of Insight", "equipped": True, "attuned": True},
                # 4th attuned item exceeds 3-slot cap and must be ignored
                {"name": "Belt of Dwarvenkind", "equipped": True, "attuned": True},
            ],
        )
    )
    assert fighter["stats"]["INT"] == 19
    assert fighter["stats"]["STR"] == 25
    assert fighter["stats"]["WIS"] == 12
    assert fighter["stats"]["CON"] == 14  # 4th attuned item ignored

    # 2. Sentinel Shield grants +2 AC and Initiative Advantage; Athas preserves +2 physical AC while losing Initiative Advantage
    sent = sync_character_stats(
        _base_char(
            dnd_edition=edition,
            char_class="Cleric",
            classes=[{"class_name": "Cleric", "level": 5}],
            equipment=[{"name": "Sentinel Shield", "equipped": True}],
        )
    )
    assert sent["armor_class"] == 14
    assert sent["initiative_advantage"] is True

    sent_athas = sync_character_stats(
        _base_char(
            dnd_edition=edition,
            char_class="Cleric",
            classes=[{"class_name": "Cleric", "level": 5}],
            magic_items_suppressed=True,
            equipment=[{"name": "Sentinel Shield", "equipped": True}],
        )
    )
    assert sent_athas["armor_class"] == 14
    assert sent_athas["initiative_advantage"] is False

    # 3. Shield +2, Elven Chain, Dwarven Plate without double counting
    assert calculate_ac(14, [{"name": "Shield +2", "equipped": True}]) == 16  # 10 + 2 DEX + 4
    assert (
        calculate_ac(14, [{"name": "Shield +2", "equipped": True}], suppress_magic_items=True) == 14
    )
    assert calculate_ac(16, [{"name": "Elven Chain", "equipped": True}]) == 16  # 13 + 2 DEX + 1
    assert calculate_ac(10, [{"name": "Dwarven Plate", "equipped": True}]) == 20  # 18 + 2

    # 4. Bracers of Archery: grants Longbow & Shortbow proficiency +2 bow damage on a Wizard
    bow_wiz = _base_char(
        dnd_edition=edition,
        stats={"STR": 10, "DEX": 16, "CON": 12, "INT": 16, "WIS": 10, "CHA": 10},
        equipment=[{"name": "Bracers of Archery", "equipped": True, "attuned": True}],
        weapons=[
            {"name": "Longbow", "damage_dice": "1d8 piercing"},
            {"name": "Light Crossbow", "damage_dice": "1d8 piercing"},
        ],
    )
    profs = get_character_weapon_proficiencies(bow_wiz)
    assert "longbows" in profs and "shortbows" in profs

    synced_bow = sync_character_stats(copy.deepcopy(bow_wiz))
    longbow = next(w for w in synced_bow["weapons"] if w["name"] == "Longbow")
    crossbow = next(w for w in synced_bow["weapons"] if w["name"] == "Light Crossbow")
    assert longbow["proficient"] is True
    assert longbow["attack_bonus"] == "+6"  # +3 DEX + 3 PB
    assert longbow["damage_bonus"] == "+5"  # +3 DEX + 2 Bracers
    assert crossbow["damage_bonus"] == "+3"  # Bracers apply only to bows

    # Under Athas, Bracers of Archery prof & damage bonus are suppressed
    assert "longbows" not in get_character_weapon_proficiencies(
        {**bow_wiz, "magic_items_suppressed": True}
    )
    suppressed_bow = sync_character_stats({**bow_wiz, "magic_items_suppressed": True})
    supp_lb = next(w for w in suppressed_bow["weapons"] if w["name"] == "Longbow")
    assert supp_lb["proficient"] is False
    assert supp_lb["attack_bonus"] == "+3"
    assert supp_lb["damage_bonus"] == "+3"


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_magic_item_caps_order_independence_armor_and_duplicate_guards(edition: str):
    # 1. Ioun Stone & Belt of Dwarvenkind respect stat_max: 20 and never reduce >= 20,
    #    while Manuals/Tomes raise stats past 20 up to 30.
    capped_hero = sync_character_stats(
        _base_char(
            dnd_edition=edition,
            stats={"STR": 20, "DEX": 12, "CON": 20, "INT": 14, "WIS": 10, "CHA": 10},
            equipment=[
                {"name": "Ioun Stone of Strength", "equipped": True, "attuned": True},
                {"name": "Belt of Dwarvenkind", "equipped": True, "attuned": True},
            ],
        )
    )
    assert capped_hero["stats"]["STR"] == 20
    assert capped_hero["stats"]["CON"] == 20

    barb_20 = sync_character_stats(
        _base_char(
            dnd_edition=edition,
            char_class="Barbarian",
            char_level=20,
            classes=[{"class_name": "Barbarian", "level": 20}],
            stats={"STR": 24, "DEX": 14, "CON": 24, "INT": 8, "WIS": 10, "CHA": 10},
            saving_throws=["STR", "CON"],
            equipment=[
                {"name": "Ioun Stone of Strength", "equipped": True, "attuned": True},
            ],
        )
    )
    assert barb_20["stats"]["STR"] == 24

    manual_hero = sync_character_stats(
        _base_char(
            dnd_edition=edition,
            stats={"STR": 20, "DEX": 12, "CON": 14, "INT": 14, "WIS": 10, "CHA": 10},
            equipment=[{"name": "Manual of Gainful Exercise", "equipped": True}],
        )
    )
    assert manual_hero["stats"]["STR"] == 22

    # 2. Order-independence between stat_set (Gauntlets of Ogre Power -> 19) and stat_bonus (Ioun Stone +2)
    gauntlets = {"name": "Gauntlets of Ogre Power", "equipped": True, "attuned": True}
    ioun_str = {"name": "Ioun Stone of Strength", "equipped": True, "attuned": True}
    order_a = sync_character_stats(
        _base_char(
            dnd_edition=edition, equipment=[copy.deepcopy(gauntlets), copy.deepcopy(ioun_str)]
        )
    )
    order_b = sync_character_stats(
        _base_char(
            dnd_edition=edition, equipment=[copy.deepcopy(ioun_str), copy.deepcopy(gauntlets)]
        )
    )
    assert order_a["stats"]["STR"] == 19
    assert order_b["stats"]["STR"] == 19

    # 3. Elven Chain works even for Wizards without Medium Armor proficiency
    elven_wiz = _base_char(
        dnd_edition=edition,
        equipment=[{"name": "Elven Chain", "equipped": True}],
    )
    _, issues = deterministic_validate_build(copy.deepcopy(elven_wiz))
    assert issues == [], f"Unexpected validation errors for Elven Chain: {issues}"
    synced_elven = sync_character_stats(elven_wiz)
    assert synced_elven["armor_class"] == 16  # 13 + 2 DEX + 1 magic

    # 4. Generic Armor +1 / Armor (+1) lookup & custom ac_bonus preservation
    assert calculate_ac(14, [{"name": "Armor +1", "equipped": True, "ac_bonus": 16}]) == 19
    assert calculate_ac(14, [{"name": "Armor (+1)", "equipped": True}]) == 13

    # 5. Bracers of Archery parenthetical "(Attuned)" proficiency and non-stacking duplicates
    parenthetical_wiz = _base_char(
        dnd_edition=edition,
        stats={"STR": 10, "DEX": 16, "CON": 12, "INT": 16, "WIS": 10, "CHA": 10},
        equipment=[
            {"name": "Bracers of Archery (Attuned)", "equipped": True, "attuned": True},
            {"name": "Bracers of Archery", "equipped": True, "attuned": True},
        ],
        weapons=[{"name": "Longbow", "damage_dice": "1d8 piercing"}],
    )
    assert "longbows" in get_character_weapon_proficiencies(parenthetical_wiz)
    synced_dup = sync_character_stats(parenthetical_wiz)
    lb = next(w for w in synced_dup["weapons"] if w["name"] == "Longbow")
    assert lb["proficient"] is True
    assert lb["damage_bonus"] == "+5"  # +3 DEX + 2 (must not stack to +4)
