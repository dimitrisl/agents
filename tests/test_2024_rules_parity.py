"""Comprehensive tests for Ticket #259: 2024 Rules & Subclass Parity (alongside 2014 parity)."""

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.repositories.rules_repository import RulesRepository
from backend.services.forge_service import (
    analyze_level_up,
    apply_level_up_spell_swap,
    forge_character_manual,
)
from backend.services.rules_service import grant_subclass_bonus_spells
from backend.services.stats_service import sync_character_stats
from backend.services.validation_service import (
    get_character_armor_proficiencies,
    get_character_weapon_proficiencies,
)
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter

DATA_RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rules")


@pytest.fixture
def rules_client():
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u_rules_2024",
        "username": "arbiter",
        "is_admin": False,
    }
    yield TestClient(app)
    app.dependency_overrides = orig
    limiter.reset()


def test_all_13_classes_have_2014_and_2024_subclass_mechanics_and_valid_bonus_spells():
    repo = RulesRepository()
    subclasses_master = json.load(open(os.path.join(DATA_RULES_DIR, "subclasses.json")))
    spells_2024 = {
        s["name"].strip().lower()
        for s in json.load(open(os.path.join(DATA_RULES_DIR, "spells_2024.json")))
    }

    for edition_key, edition_const in [
        ("2014 Edition", EDITION_2014),
        ("2024 Edition", EDITION_2024),
    ]:
        class_map = subclasses_master[edition_key]
        assert len(class_map) == 13
        for cls_name, sub_list in class_map.items():
            mech = repo.get_subclass_mechanics(cls_name, edition_const)
            assert mech and isinstance(mech.get("subclasses"), dict), (
                f"Missing subclass mechanics JSON for {edition_key} {cls_name}"
            )
            for sub_name in sub_list:
                entry = repo.get_subclass_entry(cls_name, sub_name, edition_const)
                assert entry is not None, (
                    f"Subclass '{sub_name}' missing from {edition_key} {cls_name} JSON"
                )
                if edition_const == EDITION_2024:
                    assert entry.get("features"), (
                        f"2024 {cls_name}/{sub_name} must declare progression features"
                    )
                    for req_lvl, sp_list in (entry.get("bonus_spells") or {}).items():
                        for sp_name in sp_list:
                            assert sp_name.strip().lower() in spells_2024, (
                                f"2024 {cls_name}/{sub_name} L{req_lvl} bonus spell '{sp_name}' missing from spells_2024.json"
                            )


def test_2024_subclass_bonus_spells_granted_and_protected_from_level_up_spell_swap():
    repo = RulesRepository()
    # 2024 Warlock (Fiend Patron) L5 gets Fiend Patron always-prepared bonus spells
    char = {
        "char_name": "Kaelen",
        "char_class": "Warlock",
        "subclass": "Fiend Patron",
        "char_level": 5,
        "classes": [{"class_name": "Warlock", "level": 5, "subclass": "Fiend Patron"}],
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 18},
        "spells": {"cantrips": ["Eldritch Blast"], "level_1": ["Hex"], "level_3": ["Counterspell"]},
        "prepared_spells": ["Eldritch Blast", "Hex", "Counterspell"],
        "features_traits": [],
    }
    grant_subclass_bonus_spells(char, "Warlock", "Fiend Patron", 5, EDITION_2024, repo=repo)
    assert "Burning Hands" in char["spells"].get("level_1", [])
    assert "Scorching Ray" in char["spells"].get("level_2", [])
    assert "Fireball" in char["spells"].get("level_3", [])
    assert "Fireball" in char["prepared_spells"]

    # Fireball (Fiend Patron bonus spell) must NOT be replaceable via Level-Up Spell Swap
    analysis = analyze_level_up(char)
    assert "Fireball" not in analysis["replaceable_spells"]
    assert "Burning Hands" not in analysis["replaceable_spells"]
    assert "Hex" in analysis["replaceable_spells"]

    with pytest.raises(ValueError, match="cannot be replaced"):
        apply_level_up_spell_swap(
            char_doc=char,
            pre_level_spells=char["spells"],
            target_class="Warlock",
            chosen_subclass="Fiend Patron",
            new_class_level=6,
            swap_out="Fireball",
            swap_in="Fly",
            selected_spells_in_payload=set(),
            edition=EDITION_2024,
            rules_repo=repo,
            pre_total_level=5,
        )

    # 2024 Paladin (Oath of Vengeance) L9 grants Haste & Protection from Energy in level_3
    pal = {
        "char_name": "Vex",
        "char_class": "Paladin",
        "subclass": "Oath of Vengeance",
        "char_level": 9,
        "dnd_edition": EDITION_2024,
        "spells": {},
        "prepared_spells": [],
    }
    grant_subclass_bonus_spells(pal, "Paladin", "Oath of Vengeance", 9, EDITION_2024, repo=repo)
    assert "Hunter's Mark" in pal["spells"].get("level_1", [])
    assert "Misty Step" in pal["spells"].get("level_2", [])
    assert "Haste" in pal["spells"].get("level_3", [])

    # 2024 Artificer (Battle Smith) L9 grants Aura of Vitality & Conjure Barrage in level_3 (NOT level_5)
    art = {
        "char_name": "Tinker",
        "char_class": "Artificer",
        "subclass": "Battle Smith",
        "char_level": 9,
        "dnd_edition": EDITION_2024,
        "spells": {},
        "prepared_spells": [],
    }
    grant_subclass_bonus_spells(art, "Artificer", "Battle Smith", 9, EDITION_2024, repo=repo)
    assert "Shield" in art["spells"].get("level_1", [])
    assert "Shining Smite" in art["spells"].get("level_2", [])
    assert "Aura of Vitality" in art["spells"].get("level_3", [])
    assert "Conjure Barrage" in art["spells"].get("level_3", [])
    assert "Aura of Vitality" not in art["spells"].get("level_5", [])


def test_2024_divine_order_and_primal_order_proficiencies_and_skill_bonuses():
    # 1. Generic "Divine Order" placeholder prose must NOT grant Heavy Armor / Martial Weapons
    base_cleric = {
        "char_name": "Generic Cleric",
        "char_class": "Cleric",
        "char_level": 1,
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 10, "DEX": 12, "CON": 14, "INT": 10, "WIS": 16, "CHA": 10},
        "skill_proficiencies": [],
        "features_traits": [
            {
                "name": "Divine Order",
                "description": "You choose Protector (gain proficiency with Heavy Armor and Martial Weapons) or Thaumaturge.",
                "source": "Class",
            }
        ],
    }
    assert "heavy armor" not in get_character_armor_proficiencies(base_cleric, None)
    assert "martial weapons" not in get_character_weapon_proficiencies(base_cleric)
    synced_generic = sync_character_stats(dict(base_cleric))
    assert synced_generic["skills"]["Arcana"] == 0
    assert synced_generic["skills"]["Religion"] == 0

    # 2. Divine Order: Protector grants Heavy Armor + Martial Weapons, no Thaumaturge skill bonus
    protector = dict(base_cleric)
    protector["features_traits"] = list(base_cleric["features_traits"]) + [
        {
            "name": "Divine Order: Protector",
            "description": "Trained for battle, you gain proficiency with Martial weapons and training with Heavy armor.",
            "source": "Class",
        }
    ]
    assert "heavy armor" in get_character_armor_proficiencies(protector, None)
    assert "martial weapons" in get_character_weapon_proficiencies(protector)
    synced_prot = sync_character_stats(dict(protector))
    assert synced_prot["skills"]["Arcana"] == 0
    assert synced_prot["skills"]["Religion"] == 0

    # 3. Divine Order: Thaumaturge adds +max(1, WIS mod) to Arcana & Religion (2024 ONLY)
    thaum = dict(base_cleric)
    thaum["features_traits"] = list(base_cleric["features_traits"]) + [
        {
            "name": "Divine Order: Thaumaturge",
            "description": "Bonus to Arcana & Religion equal to WIS modifier (minimum +1).",
            "source": "Class",
        }
    ]
    assert "heavy armor" not in get_character_armor_proficiencies(thaum, None)
    assert "martial weapons" not in get_character_weapon_proficiencies(thaum)
    synced_thaum = sync_character_stats(dict(thaum))
    assert synced_thaum["skills"]["Arcana"] == 3  # INT 0 + WIS +3
    assert synced_thaum["skills"]["Religion"] == 3
    assert synced_thaum["skills"]["Nature"] == 0
    # Re-syncing must stay idempotent (must NOT infer Arcana proficiency!)
    resynced_thaum = sync_character_stats(dict(synced_thaum))
    assert resynced_thaum["skills"]["Arcana"] == 3
    assert "Arcana" not in resynced_thaum["skill_proficiencies"]

    # Minimum +1 floor when WIS mod <= 0
    low_wis_thaum = dict(thaum)
    low_wis_thaum["stats"] = {"STR": 10, "DEX": 12, "CON": 14, "INT": 10, "WIS": 8, "CHA": 10}
    synced_low = sync_character_stats(low_wis_thaum)
    assert synced_low["skills"]["Arcana"] == 1
    assert synced_low["skills"]["Religion"] == 1

    # 2014 Edition must NOT apply 2024 Thaumaturge bonus
    thaum_2014 = dict(thaum)
    thaum_2014["dnd_edition"] = EDITION_2014
    synced_2014 = sync_character_stats(thaum_2014)
    assert synced_2014["skills"]["Arcana"] == 0

    # 4. Druid Primal Order: Warden (Medium Armor + Martial Weapons) vs Magician (+WIS to Arcana & Nature)
    base_druid = {
        "char_name": "Sylvia",
        "char_class": "Druid",
        "char_level": 1,
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 10, "DEX": 14, "CON": 12, "INT": 10, "WIS": 18, "CHA": 10},
        "skill_proficiencies": [],
        "features_traits": [
            {
                "name": "Primal Order",
                "description": "Magician or Warden (gain proficiency with Martial Weapons and Medium Armor).",
                "source": "Class",
            }
        ],
    }
    assert "medium armor" not in get_character_armor_proficiencies(base_druid, None)
    assert "martial weapons" not in get_character_weapon_proficiencies(base_druid)

    warden = dict(base_druid)
    warden["features_traits"] = list(base_druid["features_traits"]) + [
        {
            "name": "Primal Order: Warden",
            "description": "Medium armor & Martial weapons.",
            "source": "Class",
        }
    ]
    assert "medium armor" in get_character_armor_proficiencies(warden, None)
    assert "martial weapons" in get_character_weapon_proficiencies(warden)

    magician = dict(base_druid)
    magician["features_traits"] = list(base_druid["features_traits"]) + [
        {
            "name": "Primal Order: Magician",
            "description": "+WIS to Arcana & Nature.",
            "source": "Class",
        }
    ]
    assert "medium armor" not in get_character_armor_proficiencies(magician, None)
    synced_mag = sync_character_stats(magician)
    assert synced_mag["skills"]["Arcana"] == 4  # INT 0 + WIS +4
    assert synced_mag["skills"]["Nature"] == 4
    assert synced_mag["skills"]["Religion"] == 0


def test_2024_bard_college_of_dance_and_valor_mechanics():
    # College of Dance (2024): unarmored AC = 10 + DEX + CHA (no shield)
    dancer = {
        "char_name": "Lyra",
        "char_class": "Bard",
        "subclass": "College of Dance",
        "char_level": 3,
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 8, "DEX": 16, "CON": 12, "INT": 10, "WIS": 10, "CHA": 18},
        "equipment": [],
        "features_traits": [],
    }
    synced = sync_character_stats(dict(dancer))
    assert synced["armor_class"] == 17  # 10 + 3 DEX + 4 CHA

    # Wearing a shield disables Dazzling Footwork unarmored AC
    dancer_shield = dict(dancer)
    dancer_shield["equipment"] = [{"name": "Shield", "ac_bonus": 2, "equipped": True}]
    synced_shield = sync_character_stats(dancer_shield)
    assert synced_shield["armor_class"] == 15  # Base 10 + 3 DEX + 2 Shield (not 19!)

    # College of Valor (2024): Medium armor, Shields, Martial weapons
    valor = {
        "char_name": "Skald",
        "char_class": "Bard",
        "subclass": "College of Valor",
        "char_level": 3,
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 14, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 16},
        "features_traits": [],
    }
    assert "medium armor" in get_character_armor_proficiencies(valor, None)
    assert "shields" in get_character_armor_proficiencies(valor, None)
    assert "martial weapons" in get_character_weapon_proficiencies(valor)


def test_2024_vs_2014_structured_level_up_choices():
    # 2024 Sorcerer gets 2 Metamagic choices at Level 2 (whereas 2014 gets them at Level 3)
    sorc_2024 = {
        "char_name": "Ignis",
        "char_class": "Sorcerer",
        "char_level": 1,
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 16},
        "features_traits": [],
    }
    analysis_2024_l2 = analyze_level_up(sorc_2024)
    mm_2024 = [c for c in analysis_2024_l2["choices_required"] if c["type"] == "metamagic"]
    assert len(mm_2024) == 2
    assert "Metamagic: Seeking Spell" in mm_2024[0]["options"]

    sorc_2014 = dict(sorc_2024, dnd_edition=EDITION_2014)
    analysis_2014_l2 = analyze_level_up(sorc_2014)
    assert not [c for c in analysis_2014_l2["choices_required"] if c["type"] == "metamagic"]

    # 2024 Warlock L2 -> gains 2 Eldritch Invocations (with L2 options like Agonizing Blast);
    # 2024 Warlock L3 -> NO separate pact_boon picker (Pact Boons are L1 Invocations in 2024)
    lock_2024_l1 = {
        "char_name": "Malakor",
        "char_class": "Warlock",
        "char_level": 1,
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 16},
        "features_traits": [{"name": "Pact of the Blade", "description": "Pact weapon"}],
    }
    analysis_lock_l2 = analyze_level_up(lock_2024_l1)
    inv_l2 = [c for c in analysis_lock_l2["choices_required"] if c["type"] == "eldritch_invocation"]
    assert len(inv_l2) == 2
    assert "Agonizing Blast" in inv_l2[0]["options"]
    assert "Pact of the Blade" not in inv_l2[0]["options"]

    lock_2024_l2 = dict(lock_2024_l1, char_level=2)
    analysis_lock_l3 = analyze_level_up(lock_2024_l2)
    assert not [c for c in analysis_lock_l3["choices_required"] if c["type"] == "pact_boon"]

    # 2014 Warlock L3 STILL offers Pact Boon
    lock_2014_l2 = {
        "char_name": "OldLock",
        "char_class": "Warlock",
        "char_level": 2,
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 16},
        "features_traits": [],
    }
    analysis_2014_lock_l3 = analyze_level_up(lock_2014_l2)
    assert (
        len([c for c in analysis_2014_lock_l3["choices_required"] if c["type"] == "pact_boon"]) == 1
    )

    # 2024 Champion Fighter gets Additional Fighting Style at Level 7 (2014 gets it at Level 10)
    champ_2024_l6 = {
        "char_name": "Garrick",
        "char_class": "Fighter",
        "subclass": "Champion",
        "char_level": 6,
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 18, "DEX": 14, "CON": 16, "INT": 10, "WIS": 10, "CHA": 10},
        "features_traits": [{"name": "Fighting Style: Defense", "description": "+1 AC"}],
    }
    analysis_champ_l7 = analyze_level_up(champ_2024_l6)
    fs_l7 = [c for c in analysis_champ_l7["choices_required"] if c["type"] == "fighting_style"]
    assert len(fs_l7) == 1
    assert "Fighting Style: Defense" not in fs_l7[0]["options"]
    assert "Fighting Style: Dueling" in fs_l7[0]["options"]


def test_manual_forge_injects_chosen_2024_divine_order():
    with patch("backend.services.forge_service.generate_ai_json", return_value=None):
        hero = forge_character_manual(
            target_level=1,
            race="Human",
            char_class="Cleric",
            background="Acolyte",
            subclass="",
            alignment="Lawful Good",
            gender="Female",
            name="Seraphina",
            base_stats={"STR": 10, "DEX": 12, "CON": 14, "INT": 10, "WIS": 16, "CHA": 12},
            skill_proficiencies=["Insight", "Religion"],
            saving_throws=["WIS", "CHA"],
            spell_ability="WIS",
            concept="Scholarly divine mystic",
            edition=EDITION_2024,
            chosen_class_choices=["Divine Order: Thaumaturge"],
        )
    ft_names = [f["name"] for f in hero["features_traits"]]
    assert "Divine Order: Thaumaturge" in ft_names
    assert hero["skills"]["Arcana"] == 3  # INT 0 + Thaumaturge WIS +3
    assert hero["skills"]["Religion"] == 5  # INT 0 + PB +2 + Thaumaturge WIS +3


def test_rules_endpoints_weapon_masteries_class_choices_and_2024_combat_profile(rules_client):
    # 1. GET /api/v1/rules/weapon-masteries
    res_wm = rules_client.get("/api/v1/rules/weapon-masteries")
    assert res_wm.status_code == 200
    masteries = res_wm.json()
    assert len(masteries) == 8
    assert {m["name"] for m in masteries} == {
        "Cleave",
        "Graze",
        "Nick",
        "Push",
        "Sap",
        "Slow",
        "Topple",
        "Vex",
    }

    res_wm_bad = rules_client.get("/api/v1/rules/weapon-masteries?edition=invalid")
    assert res_wm_bad.status_code == 400

    # 2. GET /api/v1/rules/class-choices for 2024 vs 2014
    res_cc_2024 = rules_client.get("/api/v1/rules/class-choices?edition=2024")
    assert res_cc_2024.status_code == 200
    cc_2024 = res_cc_2024.json()
    assert "divine_orders" in cc_2024
    assert "primal_orders" in cc_2024
    assert "cunning_strikes" in cc_2024
    assert any(
        o["name"] == "Pact of the Blade" and o["min_level"] == 1
        for o in cc_2024["eldritch_invocations"]
    )

    res_cc_2014 = rules_client.get("/api/v1/rules/class-choices?edition=2014")
    assert res_cc_2014.status_code == 200
    cc_2014 = res_cc_2014.json()
    assert "pact_boons" in cc_2014
    assert "divine_orders" not in cc_2014

    # 3. POST /api/v1/rules/combat-profile resolves new 2024 subclass scaling & base Cleric L7 Blessed Strikes
    res_stars = rules_client.post(
        "/api/v1/rules/combat-profile",
        json={
            "classes": [{"class_name": "Druid", "level": 10, "subclass": "circle of the stars"}],
            "edition": "2024 Edition",
        },
    )
    assert res_stars.status_code == 200
    star_actions = {a["id"]: a for a in res_stars.json()["actions"]}
    assert star_actions["starry-form-archer"]["notation"] == "2d8"

    res_cleric = rules_client.post(
        "/api/v1/rules/combat-profile",
        json={
            "classes": [{"class_name": "Cleric", "level": 7, "subclass": "Life Domain"}],
            "edition": "2024 Edition",
        },
    )
    assert res_cleric.status_code == 200
    cleric_actions = {a["id"]: a for a in res_cleric.json()["actions"]}
    # 2024 Cleric Blessed Strikes unlocks at Level 7 (no longer overwritten by stale 2014 L8 subclass override!)
    assert cleric_actions["divine-strike"]["notation"] == "1d8"

    res_bs = rules_client.post(
        "/api/v1/rules/combat-profile",
        json={
            "classes": [{"class_name": "Artificer", "level": 14, "subclass": "Battle Smith"}],
            "edition": "2024 Edition",
        },
    )
    assert res_bs.status_code == 200
    bs_actions = {a["id"]: a for a in res_bs.json()["actions"]}
    assert bs_actions["arcane-jolt"]["notation"] == "4d6"
