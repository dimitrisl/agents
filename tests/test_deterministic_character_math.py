"""Comprehensive tests proving 100% deterministic character math across Forge, Level-Up, PDF Import, and Encounters."""

from unittest.mock import patch

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.repositories.rules_repository import RulesRepository
from backend.services.dm_service import generate_random_encounter
from backend.services.forge_service import (
    analyze_level_up,
    forge_character,
    forge_character_manual,
)
from backend.services.rules_service import parse_character_from_text
from backend.services.stats_service import calculate_hp, get_modifier
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app


class _AsyncCursor:
    def __init__(self, items):
        self._items = list(items)
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item

    async def to_list(self, length=None):
        return self._items[:length] if length is not None else self._items


class _AsyncCollection:
    def __init__(self, col):
        self._col = col

    async def find_one(self, query, *args, **kwargs):
        return self._col.find_one(query, *args, **kwargs)

    def find(self, query=None, *args, **kwargs):
        return _AsyncCursor(self._col.find(query or {}, *args, **kwargs))

    async def update_one(self, filt, update, *args, **kwargs):
        return self._col.update_one(filt, update, *args, **kwargs)


class _AsyncDB:
    def __init__(self):
        self._db = mongomock.MongoClient().db

    def __getitem__(self, name):
        return _AsyncCollection(self._db[name])


def _hallucinating_weak_llm_payload(char_class: str, level: int) -> dict:
    """Simulates a weak/free LLM trying to inject bad math and derived numbers."""
    return {
        "char_name": f"WeakLLM {char_class} L{level}",
        "gender": "Female",
        "char_class": char_class,
        "char_level": level,
        "race": "Human",
        "background": "Soldier",
        "alignment": "Neutral Good",
        "backstory": "Forged under a hallucinating weak model.",
        # Deliberately wrong math:
        "hp_max": 999,
        "hp_current": 1,
        "armor_class": 99,
        "speed": 120,
        "proficiency_bonus": 9,
        "passive_perception": 45,
        "spell_save_dc": 30,
        "spell_attack_bonus": "+19",
        "hit_dice": "99d12",
        "stats": {"STR": 20, "DEX": 20, "CON": 20, "INT": 20, "WIS": 20, "CHA": 20},
        "skills": {"Athletics": 99, "Perception": 99, "Arcana": 99},
        "skill_proficiencies": ["Athletics", "Perception"]
        if char_class == "Fighter"
        else ["Arcana"],
        "weapons": [
            {
                "name": "Longsword" if char_class == "Fighter" else "Dagger",
                "damage_dice": "1d8" if char_class == "Fighter" else "1d4",
                "attack_bonus": "+99",
                "damage_bonus": "+99",
                "is_custom": True,
            }
        ],
        "equipment": [],
        "advancements": [],
    }


def _expected_deterministic_hp(char: dict, hit_die_size: int) -> int:
    level = char["char_level"]
    con_mod = get_modifier(char["stats"]["CON"])
    base_hp = calculate_hp(f"1d{hit_die_size}", level, char["stats"]["CON"])
    bonus_per_level = 0
    feat_blob = " ".join(
        f"{f.get('name', '')} {f.get('description', '')}".lower()
        for f in char.get("features_traits", [])
        if isinstance(f, dict)
    )
    if "dwarven toughness" in feat_blob:
        bonus_per_level += 1
    if "draconic resilience" in feat_blob or (
        char["char_class"].lower() == "sorcerer"
        and "draconic" in str(char.get("subclass") or "").lower()
    ):
        bonus_per_level += 1
    repo = RulesRepository()
    feat_lib = {f["name"].lower(): f for f in repo.get_all_feats(char["dnd_edition"])}
    for f in char.get("features_traits", []):
        if not isinstance(f, dict):
            continue
        clean = f.get("name", "").lower().replace("origin feat: ", "").replace("feat: ", "").strip()
        if clean in feat_lib and feat_lib[clean].get("hp_bonus_per_level", 0) > 0:
            bonus_per_level += feat_lib[clean]["hp_bonus_per_level"]
    expected = base_hp + (bonus_per_level * level)
    assert con_mod is not None
    return expected


@pytest.mark.parametrize(
    "char_class,subclass,hit_die",
    [
        ("Fighter", "Champion", 10),
        ("Wizard", "Evocation", 6),
        ("Rogue", "Thief", 8),
        ("Sorcerer", "Draconic Sorcery", 6),
    ],
)
@pytest.mark.parametrize("target_level", [3, 8])
@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_forge_character_deterministic_math_4_classes_lvl3_and_lvl8(
    char_class, subclass, hit_die, target_level, edition
):
    """Weak LLM math hallucinations (HP 999, AC 99, 20x6 stats, PB 9) are completely overwritten."""
    # Map 2014 Wizard subclass name vs 2024 Evoker
    sub_arg = subclass
    if char_class == "Wizard" and "2024" in edition:
        sub_arg = "Evoker"
    if char_class == "Sorcerer" and "2014" in edition:
        sub_arg = "Draconic Bloodline"

    fake_llm = _hallucinating_weak_llm_payload(char_class, target_level)

    with patch("backend.services.forge_service.generate_ai_json", return_value=fake_llm):
        char = forge_character(
            target_level=target_level,
            forge_race="Human",
            forge_class=char_class,
            forge_background="Soldier" if char_class == "Fighter" else "Sage",
            concept="Deterministic validation test",
            name=f"Det {char_class}",
            stats_mode="standard",
            edition=edition,
            subclass=sub_arg,
        )

    expected_pb = 2 if target_level == 3 else 3
    assert char["char_level"] == target_level
    assert char["proficiency_bonus"] == expected_pb

    # Must NEVER keep LLM's 20x6 stats, hp_max=999, hp_current=1, or armor_class=99
    assert not all(v == 20 for v in char["stats"].values())
    for stat_val in char["stats"].values():
        assert 8 <= stat_val <= 20

    expected_hp = _expected_deterministic_hp(char, hit_die)
    assert char["hp_max"] == expected_hp
    assert char["hp_current"] == expected_hp
    assert char["hp_max"] != 999
    assert char["armor_class"] != 99
    assert char["speed"] == 30
    assert char["hit_dice"] == f"{target_level}d{hit_die}"

    # Weapons must recompute attack_bonus/damage_bonus instead of +99
    for w in char["weapons"]:
        assert w["attack_bonus"] != "+99"
        assert "+99" not in w.get("damage", "")

    # Caster checks
    if char_class in ("Wizard", "Sorcerer"):
        ability = "INT" if char_class == "Wizard" else "CHA"
        mod = get_modifier(char["stats"][ability])
        assert char["spell_save_dc"] == 8 + expected_pb + mod
        assert char["spell_attack_bonus"] == f"+{expected_pb + mod}"
        expected_slot_1 = 4
        assert char["spell_slots"]["level_1"]["max"] == expected_slot_1
        if target_level == 3:
            assert char["spell_slots"]["level_2"]["max"] == 2
        else:
            assert char["spell_slots"]["level_4"]["max"] == 2

    # Rogue Sneak Attack scaling check (2d6 at lvl 3, 4d6 at lvl 8)
    if char_class == "Rogue":
        sa = next(f for f in char["features_traits"] if f.get("name") == "Sneak Attack")
        expected_dice = "2d6" if target_level == 3 else "4d6"
        assert expected_dice in sa["description"]


@pytest.mark.parametrize("char_class,hit_die", [("Fighter", 10), ("Wizard", 6), ("Rogue", 8)])
@pytest.mark.parametrize("target_level", [3, 8])
@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_forge_character_llm_outage_fallback_is_valid_at_lvl3_and_lvl8(
    char_class, hit_die, target_level, edition
):
    """Even when the AI provider returns None, level 3 and 8 characters compute full deterministic mechanics."""
    with patch("backend.services.forge_service.generate_ai_json", return_value=None):
        char = forge_character(
            target_level=target_level,
            forge_race="Dwarf",
            forge_class=char_class,
            forge_background="Criminal",
            concept="Offline fallback hero",
            stats_mode="point_buy",
            edition=edition,
        )

    assert char["char_level"] == target_level
    assert char["proficiency_bonus"] == (2 if target_level == 3 else 3)
    assert char["hit_dice"] == f"{target_level}d{hit_die}"
    assert char["hp_max"] == _expected_deterministic_hp(char, hit_die)
    assert char["hp_current"] == char["hp_max"]
    assert char["hp_max"] > 10
    assert char["subclass"]  # Unlocked by level 3 in both editions


@pytest.mark.parametrize("char_class,hit_die", [("Fighter", 10), ("Wizard", 6), ("Rogue", 8)])
@pytest.mark.parametrize("target_level", [3, 8])
def test_forge_character_manual_ignores_hallucinated_llm_math_lvl3_and_lvl8(
    char_class, hit_die, target_level
):
    """Manual Forge preserves user base_stats while discarding any hallucinated HP/AC/weapon bonuses from AI."""
    base_stats = {"STR": 16, "DEX": 14, "CON": 14, "INT": 16, "WIS": 12, "CHA": 10}
    malicious_enrich = {
        "backstory": "Manual hero",
        "hp_max": 500,
        "armor_class": 42,
        "proficiency_bonus": 8,
        "weapons": [{"name": "Dagger", "damage_dice": "1d4", "attack_bonus": "+42"}],
        "equipment": [{"name": "Leather Armor", "equipped": True}],
    }
    with patch("backend.services.forge_service.generate_ai_json", return_value=malicious_enrich):
        char = forge_character_manual(
            target_level=target_level,
            race="Human",
            char_class=char_class,
            background="Soldier",
            subclass="None",
            alignment="Neutral",
            gender="Male",
            name=f"Manual {char_class}",
            base_stats=base_stats,
            skill_proficiencies=["Athletics"],
            saving_throws=[],
            spell_ability="INT" if char_class == "Wizard" else None,
            concept="Manual test",
            edition=EDITION_2024,
        )

    expected_hp = _expected_deterministic_hp(char, hit_die)
    assert char["hp_max"] == expected_hp
    assert char["hp_current"] == expected_hp
    assert char["armor_class"] != 42
    assert char["proficiency_bonus"] == (2 if target_level == 3 else 3)
    assert char["weapons"][0]["attack_bonus"] != "+42"


@pytest.mark.parametrize(
    "char_class,subclass,hit_die",
    [
        ("Fighter", "Champion", 10),
        ("Wizard", "Evoker", 6),
        ("Rogue", "Thief", 8),
        ("Sorcerer", "Draconic Sorcery", 6),
    ],
)
@pytest.mark.parametrize("current_level", [2, 7])
@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_level_up_analysis_and_apply_deterministic_lvl3_and_lvl8(
    char_class, subclass, hit_die, current_level, edition
):
    """Leveling 2->3 and 7->8 computes deterministic HP, spell slots, and rejects client HP spoofing."""
    target_level = current_level + 1
    is_2024 = "2024" in edition
    con_score = 14  # +2 CON mod
    # In 2014 Edition Sorcerer unlocks subclass (Draconic Resilience) at Level 1; in 2024 at Level 3
    has_draconic_before = char_class == "Sorcerer" and (not is_2024 or current_level >= 3)
    has_draconic_after = char_class == "Sorcerer"
    pre_lvl_bonus = 1 if has_draconic_before else 0
    starting_hp = (hit_die + 2 + pre_lvl_bonus) + (current_level - 1) * (
        hit_die // 2 + 1 + 2 + pre_lvl_bonus
    )

    char_doc = {
        "char_id": f"{char_class}_{current_level}",
        "owner_id": "u_det",
        "char_name": f"Hero {char_class}",
        "char_class": char_class,
        "subclass": subclass
        if (current_level >= 3 or (not is_2024 and char_class == "Sorcerer"))
        else None,
        "char_level": current_level,
        "classes": [
            {
                "class_name": char_class,
                "level": current_level,
                "subclass": subclass
                if (current_level >= 3 or (not is_2024 and char_class == "Sorcerer"))
                else None,
            }
        ],
        "race": "Human",
        "background": "Sage",
        "dnd_edition": edition,
        "stats": {"STR": 14, "DEX": 14, "CON": con_score, "INT": 16, "WIS": 12, "CHA": 16},
        "base_stats": {"STR": 14, "DEX": 14, "CON": con_score, "INT": 16, "WIS": 12, "CHA": 16},
        "hp_max": starting_hp,
        "hp_current": starting_hp,
        "features_traits": (
            [{"name": "Draconic Resilience", "description": "+1 HP per level"}]
            if has_draconic_before
            else []
        ),
        "version": 1,
    }

    analysis = analyze_level_up(
        char_doc,
        user_choices={"subclass": subclass}
        if (current_level == 2 and not char_doc["subclass"])
        else {},
    )

    expected_analysis_gain = (hit_die // 2 + 1) + 2 + (1 if has_draconic_after else 0)
    assert analysis["hp_increase"] == expected_analysis_gain
    assert analysis["new_total_hp"] == starting_hp + expected_analysis_gain
    assert analysis["updated_proficiency_bonus"] == (2 if target_level == 3 else 3)

    if char_class in ("Wizard", "Sorcerer"):
        if target_level == 3:
            assert analysis["updated_spell_slots"] == {"level_1": 4, "level_2": 2}
        else:
            assert analysis["updated_spell_slots"] == {
                "level_1": 4,
                "level_2": 3,
                "level_3": 3,
                "level_4": 2,
            }

    # Verify /forge/level-up-apply rejects spoofed new_total_hp=9999 and computes exact HP across all levels
    async_db = _AsyncDB()
    async_db._db["characters"].insert_one(dict(char_doc))

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: async_db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_det", "username": "det"}
    try:
        client = TestClient(app)
        spoofed_analysis = dict(analysis)
        spoofed_analysis["new_total_hp"] = 9999

        user_choices = {"level_up_class": char_class}
        if not char_doc["subclass"]:
            user_choices["subclass_0"] = subclass

        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": char_doc["char_id"],
                "analysis": spoofed_analysis,
                "user_choices": user_choices,
            },
        )
        assert resp.status_code == 200
        res = resp.json()
        expected_final_hp = (hit_die + 2 + (1 if has_draconic_after else 0)) + (
            target_level - 1
        ) * (hit_die // 2 + 1 + 2 + (1 if has_draconic_after else 0))
        assert res["char_level"] == target_level
        assert res["hp_max"] == expected_final_hp
        assert res["hp_current"] == res["hp_max"]
        assert res["proficiency_bonus"] == (2 if target_level == 3 else 3)
    finally:
        app.dependency_overrides = orig


@pytest.mark.parametrize("char_class,hit_die", [("Fighter", 10), ("Wizard", 6), ("Rogue", 8)])
@pytest.mark.parametrize("level", [3, 8])
def test_pdf_import_rejects_impossible_hp_and_recomputes_derived_stats(char_class, hit_die, level):
    """PDF import replaces out-of-bounds HP and always recomputes PB, AC, skills, and spell DC."""
    step1 = {
        "char_name": f"PDF {char_class}",
        "char_class": char_class,
        "char_level": level,
        "race": "Human",
        "background": "Soldier",
        "hp_max": 9999,  # Impossible HP for level 3 or 8
        "armor_class": 88,
        "proficiency_bonus": 9,
        "passive_perception": 50,
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 16, "WIS": 12, "CHA": 10},
        "skill_proficiencies": ["Athletics"],
    }
    step2 = {"weapons": [], "equipment": [], "spells": {}}

    with patch("backend.services.rules_service.generate_ai_json", side_effect=[step1, step2]):
        parsed = parse_character_from_text("Sheet text", edition=EDITION_2024)

    expected_hp = calculate_hp(f"1d{hit_die}", level, 14)
    assert parsed["hp_max"] == expected_hp
    assert parsed["hp_current"] == expected_hp
    assert parsed["proficiency_bonus"] == (2 if level == 3 else 3)
    assert parsed["armor_class"] != 88
    assert "Perception" not in parsed["skill_proficiencies"]


def test_dm_encounter_hydrates_srd_stats_and_falls_back_deterministically():
    """Encounter monsters match SRD HP/AC/DEX over LLM guesses, and fallback builds without AI."""
    hallucinated = {
        "encounter_text": "Goblin ambush!",
        "monsters": [{"name": "Goblin", "hp": 999, "ac": 30, "dex": 2, "quantity": 2}],
    }
    with patch("backend.services.dm_service.generate_ai_json", return_value=hallucinated):
        enc = generate_random_encounter(4, 3, "Forest", edition=EDITION_2014, difficulty="Medium")

    assert enc is not None
    assert enc["monsters"][0]["hp"] != 999
    assert enc["monsters"][0]["ac"] != 30
    assert enc["monsters"][0]["hp"] == 7
    assert enc["monsters"][0]["ac"] == 15

    with patch("backend.services.dm_service.generate_ai_json", return_value=None):
        fallback_enc = generate_random_encounter(
            4, 8, "Dungeon", edition=EDITION_2024, difficulty="Hard"
        )
    assert fallback_enc is not None
    assert len(fallback_enc["monsters"]) >= 1
    assert fallback_enc["monsters"][0]["hp"] > 0


def test_level_up_apply_clamps_rolled_hp_and_recomputes_con_asi_at_lvl8():
    """Level 7 -> 8 Fighter with custom_hp_increase=500 and +2 CON ASI enforces max d10+CON and adds +8 retroactive CON HP."""
    char_doc = {
        "char_id": "fighter_lvl7",
        "owner_id": "u_det",
        "char_name": "Kaelen",
        "char_class": "Fighter",
        "subclass": "Champion",
        "char_level": 7,
        "classes": [{"class_name": "Fighter", "level": 7, "subclass": "Champion"}],
        "race": "Human",
        "background": "Soldier",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 18, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        "base_stats": {"STR": 18, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        "hp_max": 60,  # (10+2) + 6*(6+2) = 12 + 48 = 60
        "hp_current": 60,
        "features_traits": [],
        "version": 1,
    }
    analysis = analyze_level_up(char_doc)
    async_db = _AsyncDB()
    async_db._db["characters"].insert_one(dict(char_doc))

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: async_db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_det", "username": "det"}
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": "fighter_lvl7",
                "analysis": analysis,
                "user_choices": {
                    "level_up_class": "Fighter",
                    "hp_method": "roll",
                    "custom_hp_increase": "500",
                    "feat_0": "+2 to one Stat",
                    "feat_stat1_0": "CON",
                },
            },
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["char_level"] == 8
        assert res["stats"]["CON"] == 16  # +3 mod
        # Level 8 roll clamped to max(10 + 2 old CON = 12) => 60 + 12 = 72, plus +1 CON mod * 8 levels = 80
        assert res["hp_max"] == 80
        assert res["hp_current"] == 80
    finally:
        app.dependency_overrides = orig
