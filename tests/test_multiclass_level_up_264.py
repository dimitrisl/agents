"""Tests for Issue #264: Level-Up Multiclassing Wizard, 13+ Prerequisite Enforcement & PHB Proficiencies."""

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.services.forge_service import analyze_level_up
from backend.services.validation_service import (
    ALL_CANONICAL_CLASSES,
    get_character_armor_proficiencies,
    get_multiclass_eligibility,
    get_multiclass_granted_proficiencies,
    validate_multiclass_target,
)
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter


class _AsyncCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor
        self._iter = None

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    async def to_list(self, length=None):
        items = list(self._cursor)
        return items[:length] if length is not None else items

    def __aiter__(self):
        self._iter = iter(list(self._cursor))
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _AsyncColWrapper:
    def __init__(self, col):
        self._col = col

    async def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._col.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def find_one_and_update(self, *args, **kwargs):
        return self._col.find_one_and_update(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._col.delete_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursorWrapper(self._col.find(*args, **kwargs))


class _AsyncDBWrapper:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name):
        return _AsyncColWrapper(self._db[name])

    def __getattr__(self, name):
        return _AsyncColWrapper(getattr(self._db, name))


@pytest.fixture
def raw_db():
    return mongomock.MongoClient().db


@pytest.fixture
def mock_db(raw_db):
    return _AsyncDBWrapper(raw_db)


@pytest.fixture
def auth_client(mock_db):
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-264",
        "username": "thorin",
    }
    yield TestClient(app)
    app.dependency_overrides = orig
    limiter.reset()


def _hero(**overrides):
    doc = {
        "char_id": "char-264",
        "owner_id": "user-264",
        "char_name": "Thorin",
        "char_class": "Fighter",
        "char_level": 4,
        "classes": [{"class_name": "Fighter", "level": 4, "subclass": "Champion"}],
        "dnd_edition": EDITION_2014,
        "race": "Mountain Dwarf",
        "background": "Soldier",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        "hp_max": 36,
        "hp_current": 36,
        "hit_dice": "4d10",
        "saving_throws": ["STR", "CON"],
        "skill_proficiencies": ["Athletics", "Perception", "Stealth"],
        "armor_proficiencies": ["Light Armor", "Medium Armor", "Heavy Armor", "Shields"],
        "weapon_proficiencies": ["Simple Weapons", "Martial Weapons"],
        "tool_proficiencies": ["Smith's Tools"],
        "features_traits": [],
        "weapons": [],
        "equipment": [],
        "active_campaign": "",
        "version": 1,
    }
    doc.update(overrides)
    return doc


def test_multiclass_eligibility_all_13_classes_and_prerequisites():
    fighter = _hero()
    options = get_multiclass_eligibility(fighter)
    assert len(options) == len(ALL_CANONICAL_CLASSES) == 13
    by_name = {o["class_name"]: o for o in options}

    assert by_name["Fighter"]["is_existing"] is True
    assert by_name["Fighter"]["current_level"] == 4
    assert by_name["Fighter"]["target_level"] == 5
    assert by_name["Fighter"]["hit_die"] == 10
    assert by_name["Fighter"]["eligible"] is True

    # Meets STR 13 -> Barbarian eligible; DEX 14 -> Rogue eligible
    assert by_name["Barbarian"]["eligible"] is True
    assert by_name["Rogue"]["eligible"] is True
    assert by_name["Rogue"]["hit_die"] == 8

    # Fails INT 13 -> Wizard & Artificer locked; fails WIS 13 -> Cleric/Druid/Monk/Ranger locked
    assert by_name["Wizard"]["eligible"] is False
    assert "INT 13" in by_name["Wizard"]["missing_prerequisites"][0]
    assert by_name["Ranger"]["eligible"] is False
    assert "WIS 13" in by_name["Ranger"]["missing_prerequisites"][0]
    assert by_name["Paladin"]["eligible"] is False
    assert "CHA 13" in by_name["Paladin"]["missing_prerequisites"][0]


def test_multiclass_current_class_gatekeeper_locks_new_classes_only():
    low_str_fighter = _hero(
        stats={"STR": 10, "DEX": 10, "CON": 14, "INT": 16, "WIS": 16, "CHA": 16}
    )
    options = get_multiclass_eligibility(low_str_fighter)
    by_name = {o["class_name"]: o for o in options}

    # Can still advance existing Fighter class despite low STR/DEX
    assert by_name["Fighter"]["eligible"] is True
    fighter_opt = validate_multiclass_target(low_str_fighter, "Fighter")
    assert fighter_opt["is_existing"] is True
    assert fighter_opt["eligible"] is True

    # Cannot multiclass out of Fighter into Wizard even with INT 16
    assert by_name["Wizard"]["eligible"] is False
    with pytest.raises(ValueError) as exc_info:
        validate_multiclass_target(low_str_fighter, "Wizard")
    assert "Current class Fighter requires STR 13 or DEX 13" in str(exc_info.value)

    # Paladin requires BOTH STR 13 & CHA 13 to leave
    low_str_paladin = _hero(
        char_class="Paladin",
        classes=[{"class_name": "Paladin", "level": 3}],
        stats={"STR": 10, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 16},
    )
    with pytest.raises(ValueError) as pal_exc:
        validate_multiclass_target(low_str_paladin, "Sorcerer")
    assert "Current class Paladin requires STR 13" in str(pal_exc.value)


def test_multiclass_granted_proficiencies_2014_vs_2024_parity():
    assert get_multiclass_granted_proficiencies("Druid", EDITION_2014) == [
        "Light Armor",
        "Medium Armor",
        "Shields",
    ]
    assert get_multiclass_granted_proficiencies("Druid", EDITION_2024) == [
        "Light Armor",
        "Shields",
    ]

    assert get_multiclass_granted_proficiencies("Monk", EDITION_2014) == [
        "Simple Weapons",
        "Shortswords",
    ]
    assert get_multiclass_granted_proficiencies("Monk", EDITION_2024) == []

    assert get_multiclass_granted_proficiencies("Warlock", EDITION_2014) == [
        "Light Armor",
        "Simple Weapons",
    ]
    assert get_multiclass_granted_proficiencies("Warlock", EDITION_2024) == ["Light Armor"]

    assert get_multiclass_granted_proficiencies("Rogue", EDITION_2014) == [
        "Light Armor",
        "Thieves' Tools",
        "1 Rogue Skill",
    ]
    assert get_multiclass_granted_proficiencies("Bard", EDITION_2024) == [
        "Light Armor",
        "One Musical Instrument",
        "1 Skill (Any)",
    ]
    assert get_multiclass_granted_proficiencies("Artificer", EDITION_2024) == [
        "Light Armor",
        "Medium Armor",
        "Shields",
        "Thieves' Tools",
        "Tinker's Tools",
    ]


def test_analyze_level_up_multiclass_endpoint_and_rejection(auth_client):
    fighter = _hero()

    # Single-class Fighter L5 analysis includes all 13 multiclass_options
    resp = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": fighter, "user_choices": {"level_up_class": "Fighter"}},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["multiclass_options"]) == 13

    # Ineligible target Wizard (INT 10 < 13) -> HTTP 400
    bad_resp = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": fighter, "user_choices": {"level_up_class": "Wizard"}},
    )
    assert bad_resp.status_code == 400
    assert "INT 13" in bad_resp.json()["detail"]

    # Eligible target Rogue L1 (DEX 14 >= 13) -> d8 HP (+5 + 2 CON = +7), proficiencies notice, filtered bonus skill pick
    rogue_resp = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": fighter, "user_choices": {"level_up_class": "Rogue"}},
    )
    assert rogue_resp.status_code == 200, rogue_resp.text
    rogue_data = rogue_resp.json()
    assert rogue_data["hp_increase"] == 7
    assert any(
        isinstance(chg, dict)
        and "Multiclass Proficiencies (Rogue)" in chg.get("name", "")
        and "Thieves' Tools" in chg.get("description", "")
        for chg in rogue_data["automatic_changes"]
    )
    skill_choices = [c for c in rogue_data["choices_required"] if c["type"] == "skill"]
    assert len(skill_choices) == 1
    # Athletics & Stealth already known by Thorin so excluded from Rogue bonus skill options
    assert "Stealth" not in skill_choices[0]["options"]
    assert "Athletics" not in skill_choices[0]["options"]
    assert "Acrobatics" in skill_choices[0]["options"]

    # Bard multiclassing exposes any non-proficient skill
    bard_char = _hero(stats={"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 14})
    bard_analysis = analyze_level_up(bard_char, {"level_up_class": "Bard"})
    bard_skill = [c for c in bard_analysis["choices_required"] if c["type"] == "skill"][0]
    assert "Arcana" in bard_skill["options"]
    assert "Stealth" not in bard_skill["options"]


def test_apply_level_up_enforces_prereqs_skill_choice_and_persists_phb_grants(auth_client, raw_db):
    fighter = _hero()
    raw_db["characters"].insert_one(fighter.copy())

    dummy_analysis = {
        "hp_increase": 6,
        "new_total_hp": 42,
        "automatic_changes": [],
        "choices_required": [],
    }

    # 1. Reject ineligible target Wizard (INT 10 < 13) even with forged payload
    res_bad = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": fighter["char_id"],
            "analysis": dummy_analysis,
            "user_choices": {"level_up_class": "Wizard", "hp_method": "average"},
        },
    )
    assert res_bad.status_code == 400
    assert "INT 13" in res_bad.json()["detail"]

    rogue_analysis = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": fighter, "user_choices": {"level_up_class": "Rogue"}},
    ).json()
    choices = rogue_analysis["choices_required"]
    skill_idx = next(i for i, c in enumerate(choices) if c["type"] == "skill")
    exp_indices = [i for i, c in enumerate(choices) if c["type"] == "expertise"]

    # 2. Reject missing Rogue +1 bonus skill pick
    res_missing_skill = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": fighter["char_id"],
            "analysis": rogue_analysis,
            "user_choices": {"level_up_class": "Rogue", "hp_method": "average"},
        },
    )
    assert res_missing_skill.status_code == 400
    assert "bonus skill" in res_missing_skill.json()["detail"].lower()

    # 3. Reject non-Rogue skill ('Arcana') or already-proficient skill ('Stealth')
    res_invalid_skill = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": fighter["char_id"],
            "analysis": rogue_analysis,
            "user_choices": {
                "level_up_class": "Rogue",
                "hp_method": "average",
                f"skill_{skill_idx}": "Arcana",
            },
        },
    )
    assert res_invalid_skill.status_code == 400

    res_dup_skill = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": fighter["char_id"],
            "analysis": rogue_analysis,
            "user_choices": {
                "level_up_class": "Rogue",
                "hp_method": "average",
                f"skill_{skill_idx}": "Stealth",
            },
        },
    )
    assert res_dup_skill.status_code == 400

    # 4. Valid Fighter 4 -> Fighter 4 / Rogue 1 with Acrobatics bonus skill + Expertise
    ok_choices = {
        "level_up_class": "Rogue",
        "hp_method": "average",
        f"skill_{skill_idx}": "Acrobatics",
    }
    if len(exp_indices) >= 2:
        ok_choices[f"expertise_{exp_indices[0]}"] = "Athletics"
        ok_choices[f"expertise_{exp_indices[1]}"] = "Stealth"

    res_ok = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": fighter["char_id"],
            "analysis": rogue_analysis,
            "user_choices": ok_choices,
        },
    )
    assert res_ok.status_code == 200, res_ok.text
    updated = res_ok.json()
    assert updated["char_level"] == 5
    assert updated["hit_dice"] == "4d10, 1d8"
    assert updated["saving_throws"] == ["STR", "CON"]  # Starting saves preserved
    assert "Thieves' Tools" in updated["tool_proficiencies"]
    assert "light armor" in get_character_armor_proficiencies(updated, {})
    assert "Acrobatics" in updated["skill_proficiencies"]
    assert updated["skill_proficiencies"].count("Stealth") == 1
    if len(exp_indices) >= 2:
        assert set(updated["skill_expertise"]) >= {"Athletics", "Stealth"}


def test_apply_level_up_respects_2014_vs_2024_monk_and_druid_grants(auth_client, raw_db):
    base_stats = {"STR": 10, "DEX": 14, "CON": 14, "INT": 16, "WIS": 14, "CHA": 10}

    # Human Wizard isolates PHB multiclass grants (starts with no armor and no simple/martial profs)
    hero_2014 = _hero(
        char_id="char-monk-2014",
        char_name="Merlin14",
        race="Human",
        char_class="Wizard",
        classes=[{"class_name": "Wizard", "level": 4, "subclass": "Evocation"}],
        dnd_edition=EDITION_2014,
        stats=base_stats,
        hit_dice="4d6",
        saving_throws=["INT", "WIS"],
        skill_proficiencies=["Arcana", "History"],
        weapon_proficiencies=[],
        tool_proficiencies=[],
    )
    hero_2024 = _hero(
        char_id="char-monk-2024",
        char_name="Merlin24",
        race="Human",
        char_class="Wizard",
        classes=[{"class_name": "Wizard", "level": 4, "subclass": "Evoker"}],
        dnd_edition=EDITION_2024,
        stats=base_stats,
        hit_dice="4d6",
        saving_throws=["INT", "WIS"],
        skill_proficiencies=["Arcana", "History"],
        weapon_proficiencies=[],
        tool_proficiencies=[],
    )
    druid_2014 = _hero(
        char_id="char-druid-2014",
        char_name="Sylva14",
        race="Human",
        char_class="Wizard",
        classes=[{"class_name": "Wizard", "level": 4, "subclass": "Evocation"}],
        dnd_edition=EDITION_2014,
        stats=base_stats,
        hit_dice="4d6",
        saving_throws=["INT", "WIS"],
        skill_proficiencies=["Arcana", "History"],
        weapon_proficiencies=[],
        tool_proficiencies=[],
    )
    druid_2024 = _hero(
        char_id="char-druid-2024",
        char_name="Sylva24",
        race="Human",
        char_class="Wizard",
        classes=[{"class_name": "Wizard", "level": 4, "subclass": "Evoker"}],
        dnd_edition=EDITION_2024,
        stats=base_stats,
        hit_dice="4d6",
        saving_throws=["INT", "WIS"],
        skill_proficiencies=["Arcana", "History"],
        weapon_proficiencies=[],
        tool_proficiencies=[],
    )
    raw_db["characters"].insert_one(hero_2014.copy())
    raw_db["characters"].insert_one(hero_2024.copy())
    raw_db["characters"].insert_one(druid_2014.copy())
    raw_db["characters"].insert_one(druid_2024.copy())

    a14 = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": hero_2014, "user_choices": {"level_up_class": "Monk"}},
    ).json()
    r14 = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": hero_2014["char_id"],
            "analysis": a14,
            "user_choices": {"level_up_class": "Monk", "hp_method": "average"},
        },
    )
    assert r14.status_code == 200, r14.text
    assert "shortswords" in r14.json()["weapon_proficiencies"]
    assert "simple weapons" in r14.json()["weapon_proficiencies"]

    a24 = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": hero_2024, "user_choices": {"level_up_class": "Monk"}},
    ).json()
    r24 = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": hero_2024["char_id"],
            "analysis": a24,
            "user_choices": {"level_up_class": "Monk", "hp_method": "average"},
        },
    )
    assert r24.status_code == 200, r24.text
    assert "shortswords" not in r24.json()["weapon_proficiencies"]
    assert r24.json()["saving_throws"] == ["INT", "WIS"]

    ad14 = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": druid_2014, "user_choices": {"level_up_class": "Druid"}},
    ).json()
    d14 = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": druid_2014["char_id"],
            "analysis": ad14,
            "user_choices": {"level_up_class": "Druid", "hp_method": "average"},
        },
    )
    assert d14.status_code == 200, d14.text
    armor14 = get_character_armor_proficiencies(d14.json(), {})
    assert {"light armor", "medium armor", "shields"}.issubset(armor14)

    ad24 = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": druid_2024, "user_choices": {"level_up_class": "Druid"}},
    ).json()
    d24 = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": druid_2024["char_id"],
            "analysis": ad24,
            "user_choices": {"level_up_class": "Druid", "hp_method": "average"},
        },
    )
    assert d24.status_code == 200, d24.text
    # 2024 Druid multiclassing grants Light Armor + Shields (NOT Medium Armor)
    armor24 = get_character_armor_proficiencies(d24.json(), {})
    assert "light armor" in armor24
    assert "shields" in armor24
    assert "medium armor" not in armor24

    # ruleset_version alone (without dnd_edition) also triggers 2024 parity
    ruleset_only_druid = _hero(
        char_id="char-ruleset-2024",
        char_name="SylvaRuleset",
        race="Human",
        char_class="Wizard",
        classes=[{"class_name": "Wizard", "level": 4, "subclass": "Evoker"}],
        stats=base_stats,
        hit_dice="4d6",
        saving_throws=["INT", "WIS"],
        skill_proficiencies=["Arcana", "History"],
        weapon_proficiencies=[],
        tool_proficiencies=[],
    )
    ruleset_only_druid.pop("dnd_edition", None)
    ruleset_only_druid["ruleset_version"] = EDITION_2024
    armor_ruleset = get_character_armor_proficiencies(
        {
            **ruleset_only_druid,
            "classes": [*ruleset_only_druid["classes"], {"class_name": "Druid", "level": 1}],
        },
        {},
    )
    assert "light armor" in armor_ruleset
    assert "medium armor" not in armor_ruleset


def test_multiclass_edge_cases_subclass_isolation_skill_abuse_and_legacy_slots(auth_client, raw_db):
    # 1. Primary class subclass ('Champion') MUST NOT bleed into a newly entered multiclass (2024 Cleric L1)
    champion = _hero(
        char_id="char-champ-cleric",
        dnd_edition=EDITION_2024,
        stats={"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 14, "CHA": 8},
        subclass="Champion",
        classes=[{"class_name": "Fighter", "level": 4, "subclass": "Champion"}],
    )
    raw_db["characters"].insert_one(champion.copy())

    cleric_analysis = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": champion, "user_choices": {"level_up_class": "Cleric"}},
    ).json()
    divine_idx = next(
        i for i, c in enumerate(cleric_analysis["choices_required"]) if c["type"] == "divine_order"
    )
    res_cleric = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": champion["char_id"],
            "analysis": cleric_analysis,
            "user_choices": {
                "level_up_class": "Cleric",
                "hp_method": "average",
                f"divine_order_{divine_idx}": "Divine Order: Protector",
            },
        },
    )
    assert res_cleric.status_code == 200, res_cleric.text
    cleric_updated = res_cleric.json()
    feat_names = [f["name"] for f in cleric_updated["features_traits"]]
    assert not any("Champion Subclass Feature" in name for name in feat_names)
    cleric_entry = next(c for c in cleric_updated["classes"] if c["class_name"] == "Cleric")
    assert cleric_entry.get("subclass") in (None, "")

    # 2. Crafted duplicate skill_* keys during Rogue multiclass OR skill_0 on Fighter level-up return HTTP 400
    rogue_hero = _hero(char_id="char-skill-abuse")
    raw_db["characters"].insert_one(rogue_hero.copy())
    rogue_analysis = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": rogue_hero, "user_choices": {"level_up_class": "Rogue"}},
    ).json()
    skill_idx = next(
        i for i, c in enumerate(rogue_analysis["choices_required"]) if c["type"] == "skill"
    )
    dup_skill_resp = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": rogue_hero["char_id"],
            "analysis": rogue_analysis,
            "user_choices": {
                "level_up_class": "Rogue",
                "hp_method": "average",
                f"skill_{skill_idx}": "Acrobatics",
                "skill_99": "Investigation",
            },
        },
    )
    assert dup_skill_resp.status_code == 400

    fighter_analysis = auth_client.post(
        "/api/v1/forge/level-up-analysis",
        json={"character": rogue_hero, "user_choices": {"level_up_class": "Fighter"}},
    ).json()
    arbitrary_skill_resp = auth_client.post(
        "/api/v1/forge/level-up-apply",
        json={
            "character_id": rogue_hero["char_id"],
            "analysis": fighter_analysis,
            "user_choices": {
                "level_up_class": "Fighter",
                "hp_method": "average",
                "skill_0": "Arcana",
            },
        },
    )
    assert arbitrary_skill_resp.status_code == 400

    # 3. Legacy character without `classes` array computes Level 1 Wizard slots (not Level 5 slots)
    legacy_fighter = _hero(
        char_id="char-legacy-noclasses",
        classes=[],
        stats={"STR": 16, "DEX": 12, "CON": 14, "INT": 14, "WIS": 10, "CHA": 8},
    )
    legacy_analysis = analyze_level_up(legacy_fighter, {"level_up_class": "Wizard"})
    slots = legacy_analysis["updated_spell_slots"]
    assert slots.get("level_1") == 2
    assert slots.get("level_2", 0) == 0
    assert slots.get("level_3", 0) == 0
