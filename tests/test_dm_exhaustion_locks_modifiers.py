"""
Comprehensive Backend Verification Suite for DM-Only Exhaustion, Locks,
Athas Magic Item Suppression, and Signed DM Modifiers (2014 & 2024 Parity).
"""

import copy
from unittest.mock import patch

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.services.class_resources_service import _load_rules
from backend.services.stats_service import sync_character_stats
from server.db_async import get_database
from server.main import app
from server.rate_limiter import limiter
from server.routers.campaign_router import _roll_in_secret, _sheet_modifier


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

    async def insert_many(self, *args, **kwargs):
        return self._col.insert_many(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def update_many(self, *args, **kwargs):
        return self._col.update_many(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._col.delete_one(*args, **kwargs)

    async def delete_many(self, *args, **kwargs):
        return self._col.delete_many(*args, **kwargs)

    async def find_one_and_update(self, *args, **kwargs):
        return self._col.find_one_and_update(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._col.count_documents(*args, **kwargs)

    async def distinct(self, *args, **kwargs):
        return self._col.distinct(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursorWrapper(self._col.find(*args, **kwargs))


class _AsyncDBWrapper:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name):
        return _AsyncColWrapper(self._db[name])

    def __getattr__(self, name):
        return _AsyncColWrapper(getattr(self._db, name))


def _make_wizard(edition: str) -> dict:
    return {
        "char_id": "wiz_math",
        "char_name": "Kaelith",
        "char_class": "Wizard",
        "char_level": 5,
        "race": "Human",
        "background": "Sage",
        "dnd_edition": edition,
        "ruleset_version": edition,
        "stats": {"STR": 10, "DEX": 14, "CON": 14, "INT": 18, "WIS": 12, "CHA": 8},
        "saving_throws": ["INT", "WIS"],
        "skill_proficiencies": ["Perception", "Arcana"],
        "proficiency_bonus": 3,
        "hp_max": 32,
        "hp_current": 32,
        "speed": 30,
        "base_speed": 30,
        "concentrating_on": "Haste",
        "weapons": [
            {
                "name": "Dagger +1",
                "damage": "1d4",
                "magic_bonus": 1,
                "properties": ["Finesse", "Light", "Thrown"],
            }
        ],
        "equipment": [],
        "exhaustion_level": 0,
        "exhaustion_bypass": False,
        "magic_items_suppressed": False,
        "dm_modifiers": {},
    }


def _make_paladin(edition: str) -> dict:
    return {
        "char_id": "pal_athas",
        "char_name": "Theron",
        "char_class": "Paladin",
        "char_level": 5,
        "race": "Human",
        "background": "Soldier",
        "dnd_edition": edition,
        "ruleset_version": edition,
        "stats": {"STR": 10, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 16},
        "saving_throws": ["WIS", "CHA"],
        "skill_proficiencies": ["Athletics", "Perception"],
        "proficiency_bonus": 3,
        "hp_max": 44,
        "hp_current": 44,
        "speed": 30,
        "base_speed": 30,
        "weapons": [
            {
                "name": "Longsword +2",
                "damage": "1d8",
                "magic_bonus": 2,
                "properties": ["Versatile (1d10)"],
            },
            {
                "name": "Custom Spear",
                "damage": "1d6",
                "magic_bonus": 1,
                "is_custom": True,
                "attack_bonus": "+4",
                "damage_bonus": "+1",
                "properties": ["Thrown"],
            },
        ],
        "equipment": [
            {"name": "+1 Plate Armor", "type": "Heavy Armor", "equipped": True},
            {"name": "+1 Shield", "type": "Shield", "equipped": True},
            {"name": "Cloak of Protection", "type": "Wondrous Item", "equipped": True},
            {"name": "Gauntlets of Ogre Power", "type": "Wondrous Item", "equipped": True},
            {"name": "Amulet of Health", "type": "Wondrous Item", "equipped": True},
            {"name": "Weapon of Warning", "type": "Weapon", "equipped": True},
        ],
        "exhaustion_level": 0,
        "exhaustion_bypass": False,
        "magic_items_suppressed": False,
        "dm_modifiers": {},
    }


def _setup_test_client(db_name: str):
    limiter.reset()
    _load_rules.cache_clear()
    mock_client = mongomock.MongoClient()
    db = _AsyncDBWrapper(mock_client[db_name])
    app.dependency_overrides[get_database] = lambda: db
    client = TestClient(app)

    def register_and_login(uname: str, email: str) -> dict:
        reg = client.post(
            "/api/v1/auth/register",
            json={"username": uname, "email": email, "password": "Password123!"},
        )
        assert reg.status_code == 201
        tok = client.post(
            "/api/v1/auth/login",
            data={"username": uname, "password": "Password123!"},
        )
        assert tok.status_code == 200
        return {"Authorization": f"Bearer {tok.json()['access_token']}"}

    return client, db, register_and_login


# ==============================================================================
# 1 & 2. EXHAUSTION MATH (2014 & 2024) + LEVEL 6 DEATH + BYPASS
# ==============================================================================


@pytest.mark.parametrize("edition", [EDITION_2024, EDITION_2014])
def test_exhaustion_levels_and_bypass_parity(edition):
    base = sync_character_stats(_make_wizard(edition))
    assert base["speed"] == 30
    assert base["passive_perception"] == 14  # 10 + 1 WIS + 3 Perception prof
    assert base["spell_save_dc"] == 15  # 8 + 3 prof + 4 INT
    assert base["spell_attack_bonus"] == "+7"

    # Level 1
    l1 = copy.deepcopy(base)
    l1["exhaustion_level"] = 1
    l1 = sync_character_stats(l1)
    if edition == EDITION_2024:
        assert l1["speed"] == 25
        assert l1["passive_perception"] == 12  # 14 - 2
        # Spell Save DC is NOT a d20 Test in 2024 RAW; spell_attack_bonus IS penalized!
        assert l1["spell_save_dc"] == 15
        assert l1["spell_attack_bonus"] == "+5"  # +7 - 2
        assert l1["initiative_modifier"] == 0  # +2 - 2
        assert l1["weapons"][0]["attack_bonus"] == "+4"  # +2 DEX + 3 prof + 1 magic - 2 exh
    else:
        assert l1["speed"] == 30
        assert l1["passive_perception"] == 9  # 14 - 5 (2014 Disadvantage penalty)
        assert l1["spell_save_dc"] == 15
        assert l1["spell_attack_bonus"] == "+7"

    # Level 2
    l2 = copy.deepcopy(l1)
    l2["exhaustion_level"] = 2
    l2 = sync_character_stats(l2)
    if edition == EDITION_2024:
        assert l2["speed"] == 20
        assert l2["passive_perception"] == 10  # 14 - 4
        assert l2["spell_save_dc"] == 15
        assert l2["spell_attack_bonus"] == "+3"  # +7 - 4
    else:
        assert l2["speed"] == 15  # halved in 2014
        assert l2["hp_max"] == 32

    # Level 4
    l4 = copy.deepcopy(l2)
    l4["exhaustion_level"] = 4
    l4 = sync_character_stats(l4)
    if edition == EDITION_2024:
        assert l4["speed"] == 10
        assert l4["hp_max"] == 32
        assert l4["passive_perception"] == 6
    else:
        assert l4["speed"] == 15
        assert l4["hp_max"] == 16  # halved in 2014
        assert l4["base_hp_max"] == 32
        assert l4["hp_current"] == 16  # clamped cleanly

    # Recovering from Level 4 -> Level 3 restores full HP Max in 2014
    l3_rec = copy.deepcopy(l4)
    l3_rec["exhaustion_level"] = 3
    l3_rec = sync_character_stats(l3_rec)
    if edition == EDITION_2014:
        assert l3_rec["hp_max"] == 32
        assert l3_rec["base_hp_max"] is None

    # Level 5
    l5 = copy.deepcopy(l4)
    l5["exhaustion_level"] = 5
    l5 = sync_character_stats(l5)
    if edition == EDITION_2024:
        assert l5["speed"] == 5
        assert l5["hp_current"] == 32
    else:
        assert l5["speed"] == 0
        assert l5["hp_max"] == 16

    # Level 6 Death (both editions: speed=0, hp_current=0, concentrating_on=None)
    l6 = copy.deepcopy(l5)
    l6["exhaustion_level"] = 6
    l6["concentrating_on"] = "Haste"
    l6 = sync_character_stats(l6)
    assert l6["speed"] == 0
    assert l6["hp_current"] == 0
    assert l6["concentrating_on"] is None

    # Bypass enabled while still at Exhaustion 6: waives penalties & death!
    bypassed = copy.deepcopy(base)
    bypassed["exhaustion_level"] = 6
    bypassed["exhaustion_bypass"] = True
    bypassed["concentrating_on"] = "Haste"
    bypassed = sync_character_stats(bypassed)
    assert bypassed["exhaustion_level"] == 6
    assert bypassed["speed"] == 30
    assert bypassed["hp_max"] == 32
    assert bypassed["hp_current"] == 32
    assert bypassed["passive_perception"] == 14
    assert bypassed["spell_save_dc"] == 15
    assert bypassed["concentrating_on"] == "Haste"

    # Un-waiving bypass immediately enforces Level 6 death
    bypassed["exhaustion_bypass"] = False
    unwaived = sync_character_stats(bypassed)
    assert unwaived["speed"] == 0
    assert unwaived["hp_current"] == 0
    assert unwaived["concentrating_on"] is None


# ==============================================================================
# 3. ATHAS / ANTIMAGIC SUPPRESSION (NON-DESTRUCTIVE + CASCADES)
# ==============================================================================


@pytest.mark.parametrize("edition", [EDITION_2024, EDITION_2014])
def test_magic_items_suppressed_non_destructive_and_cascades(edition):
    pal = sync_character_stats(_make_paladin(edition))

    # Baseline WITH magic items active:
    # Gauntlets set STR 19 (+4), Amulet sets CON 19 (+4)
    # Paladin L5 (hit die d10, avg 6/lvl): base CON 14 (+2) vs Amulet CON 19 (+4):
    # Base CON +4 -> (10+4) + 4*(6+4) = 14 + 40 = 54 HP Max
    # Armor: +1 Plate (18 + 1 = 19) + +1 Shield (2 + 1 = 3) + Cloak (+1) = 23 AC
    assert pal["stats"]["STR"] == 19
    assert pal["stats"]["CON"] == 19
    assert pal["hp_max"] == 54
    assert pal["armor_class"] == 23
    assert pal["speed"] == 30  # STR 19 >= min_str 15 for Plate
    assert pal["initiative_advantage"] is True  # Weapon of Warning
    assert pal["saving_throw_values"]["CHA"] == 7  # +3 mod + 3 prof + 1 Cloak
    # Longsword +2: +4 STR + 3 prof + 2 magic = +9 atk, +4 + 2 = +6 dmg
    ls = pal["weapons"][0]
    assert ls["attack_bonus"] == "+9"
    assert ls["damage_bonus"] == "+6"
    assert ls["magic_bonus"] == 2
    # Custom Spear (+4 atk, +1 dmg initially)
    spear = pal["weapons"][1]
    assert spear["attack_bonus"] == "+4"
    assert spear["damage_bonus"] == "+1"

    # Enable Athas / Antimagic Suppression
    sup_in = copy.deepcopy(pal)
    sup_in["magic_items_suppressed"] = True
    sup = sync_character_stats(sup_in)

    # Stats revert cleanly to innate STR 10 (+0), CON 14 (+2)
    assert sup["stats"]["STR"] == 10
    assert sup["stats"]["CON"] == 14
    assert sup["base_stats"]["STR"] == 10
    assert sup["base_stats"]["CON"] == 14
    # CON +2 HP Max: (10+2) + 4*(6+2) = 12 + 32 = 44
    assert sup["hp_max"] == 44
    assert sup["hp_current"] == 44  # clamped to new max
    # Mundane armor & shield remain! Plate (18) + Shield (2) + Cloak suppressed (0) = 20
    assert sup["armor_class"] == 20
    # Heavy armor STR requirement cascade! Base STR 10 < 15 -> -10 speed -> 20 ft!
    assert sup["speed"] == 20
    # Weapon of Warning suppressed!
    assert sup["initiative_advantage"] is False
    # Cloak +1 saves suppressed! CHA save drops +7 -> +6 (+3 mod + 3 prof)
    assert sup["saving_throw_values"]["CHA"] == 6
    # Longsword +2 retains magic_bonus=2 in sheet, acts as mundane (+0 STR + 3 prof = +3 atk, +0 dmg)!
    sup_ls = sup["weapons"][0]
    assert sup_ls["magic_bonus"] == 2
    assert sup_ls["attack_bonus"] == "+3"
    assert sup_ls["damage_bonus"] == "+0"
    # Custom Spear (magic_bonus=1 suppressed while preserving custom base math)
    sup_spear = sup["weapons"][1]
    assert sup_spear["attack_bonus"] == "+3"
    assert sup_spear["damage_bonus"] == "+0"
    assert sup_spear["magic_bonus_suppressed_applied"] == 1
    # All equipment still present in DB document
    assert len(sup["equipment"]) == 6

    # Re-running sync idempotently preserves exact suppressed values
    sup_again = sync_character_stats(copy.deepcopy(sup))
    assert sup_again["armor_class"] == 20
    assert sup_again["speed"] == 20
    assert sup_again["hp_max"] == 44
    assert sup_again["weapons"][0]["attack_bonus"] == "+3"
    assert sup_again["weapons"][1]["attack_bonus"] == "+3"

    # Lifting suppression restores EVERYTHING seamlessly without losing custom items!
    sup_again["magic_items_suppressed"] = False
    restored = sync_character_stats(sup_again)
    assert restored["stats"]["STR"] == 19
    assert restored["stats"]["CON"] == 19
    assert restored["hp_max"] == 54
    assert restored["armor_class"] == 23
    assert restored["speed"] == 30
    assert restored["initiative_advantage"] is True
    assert restored["saving_throw_values"]["CHA"] == 7
    assert restored["weapons"][0]["attack_bonus"] == "+9"
    assert restored["weapons"][0]["damage_bonus"] == "+6"
    assert restored["weapons"][1]["attack_bonus"] == "+4"
    assert restored["weapons"][1]["damage_bonus"] == "+1"
    assert restored["weapons"][1]["magic_bonus_suppressed_applied"] == 0


# ==============================================================================
# 4. SIGNED DM MODIFIERS (ALL 10 FIELDS + IDEMPOTENCY)
# ==============================================================================


@pytest.mark.parametrize("edition", [EDITION_2024, EDITION_2014])
def test_signed_dm_modifiers_all_fields_idempotent(edition):
    base = sync_character_stats(_make_wizard(edition))
    mods = {
        "attack_bonus": -2,
        "damage_bonus": 3,
        "ac_bonus": -1,
        "speed_bonus": 10,
        "hp_max_bonus": -4,
        "initiative_bonus": 5,
        "saving_throws_bonus": -2,
        "ability_checks_bonus": 3,
        "spell_save_dc_bonus": -2,
        "passive_perception_bonus": 4,
        "note": "Curse of the Dark Sun",
    }

    modded = copy.deepcopy(base)
    modded["dm_modifiers"] = mods
    s1 = sync_character_stats(modded)
    # Run twice more to verify zero double-counting
    s2 = sync_character_stats(copy.deepcopy(s1))
    s3 = sync_character_stats(copy.deepcopy(s2))

    for state in (s1, s2, s3):
        # AC: base 12 -> 11
        assert state["armor_class"] == 11
        # Speed: base 30 + 10 = 40
        assert state["speed"] == 40
        # HP Max: base 32 - 4 = 28, hp_current clamped to 28
        assert state["hp_max"] == 28
        assert state["hp_current"] == 28
        # Initiative: +2 DEX + 5 init + 3 ability_checks_bonus (Init is a Dex check) = +10
        assert state["initiative_modifier"] == 10
        # Weapon: base Dagger +1 (+2 DEX +3 prof +1 = +6 atk, +3 dmg) -> (+4 atk, +6 dmg)
        assert state["weapons"][0]["attack_bonus"] == "+4"
        assert state["weapons"][0]["damage_bonus"] == "+6"
        # Saves: INT base +7 -> +5; DEX base +2 -> +0
        assert state["saving_throw_values"]["INT"] == 5
        assert state["saving_throw_values"]["DEX"] == 0
        # Skills / Checks: Arcana base +7 (+4 INT +3 prof) + 3 = +10; Athletics +0 + 3 = +3
        assert state["skills"]["Arcana"] == 10
        assert state["skills"]["Athletics"] == 3
        # Spell DC: base 15 - 2 = 13; Spell Atk: base +7 - 2 = +5
        assert state["spell_save_dc"] == 13
        assert state["spell_attack_bonus"] == "+5"
        # Passive Perception: 10 + 1 WIS + 3 prof + 3 ability_checks + 4 passive = 21
        assert state["passive_perception"] == 21

    # Clearing DM modifiers restores everything cleanly
    cleared = copy.deepcopy(s3)
    cleared["dm_modifiers"] = {}
    restored = sync_character_stats(cleared)
    assert restored["armor_class"] == 12
    assert restored["speed"] == 30
    assert restored["hp_max"] == 32
    assert restored["initiative_modifier"] == 2
    assert restored["weapons"][0]["attack_bonus"] == "+6"
    assert restored["weapons"][0]["damage_bonus"] == "+3"
    assert restored["saving_throw_values"]["INT"] == 7
    assert restored["skills"]["Arcana"] == 7
    assert restored["spell_save_dc"] == 15
    assert restored["spell_attack_bonus"] == "+7"
    assert restored["passive_perception"] == 14


# ==============================================================================
# 5, 6, 8. HTTP SECURITY LOCKS, 1-SHOT UNLOCKS, SOLO FREEDOM, L6 DEATH, CLEANUP
# ==============================================================================


def test_campaign_locks_1shot_unlocks_solo_freedom_and_detach_cleanup():
    client, db, auth_headers = _setup_test_client("test_dm_locks_db")
    try:
        dm_h = auth_headers("dm_user", "dm@athas.org")
        p1_h = auth_headers("p1_user", "p1@athas.org")
        p2_h = auth_headers("p2_user", "p2@athas.org")

        # 1) Create Solo character first -> verify solo freedom!
        solo_res = client.post(
            "/api/v1/characters",
            json={
                "char_name": "Kael Solo",
                "char_class": "Fighter",
                "char_level": 2,
                "classes": [{"class_name": "Fighter", "level": 2}],
                "race": "Human",
                "background": "Soldier",
                "dnd_edition": EDITION_2024,
                "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
                "hp_max": 20,
                "hp_current": 10,
                "hit_dice_used": 1,
                "exhaustion_level": 0,
            },
            headers=p1_h,
        )
        assert solo_res.status_code == 201
        solo_id = solo_res.json()["char_id"]

        # Solo hero can modify exhaustion directly via PUT and rest freely without DM unlock
        solo_put = client.put(
            f"/api/v1/characters/{solo_id}",
            json={**solo_res.json(), "exhaustion_level": 2},
            headers=p1_h,
        )
        assert solo_put.status_code == 200
        assert solo_put.json()["exhaustion_level"] == 2
        assert solo_put.json()["speed"] == 20

        solo_sr = client.post(
            f"/api/v1/characters/{solo_id}/short-rest",
            json={"dice_to_spend": 1, "hp_healed": 6},
            headers=p1_h,
        )
        assert solo_sr.status_code == 200
        assert solo_sr.json()["hp_current"] == 16

        solo_lr = client.post(
            f"/api/v1/characters/{solo_id}/long-rest",
            json={},
            headers=p1_h,
        )
        assert solo_lr.status_code == 200
        assert solo_lr.json()["exhaustion_level"] == 1
        assert solo_lr.json()["hp_current"] == 20

        # Solo level-up works freely
        solo_lvl = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": solo_id,
                "analysis": {
                    "hp_increase": 8,
                    "new_total_hp": 28,
                    "automatic_changes": [],
                    "choices_required": [],
                },
                "user_choices": {"level_up_class": "Fighter", "hp_method": "fixed"},
            },
            headers=p1_h,
        )
        assert solo_lvl.status_code == 200
        assert solo_lvl.json()["char_level"] == 3

        # 2) Create 2014 campaign & second hero for party tests
        p2_res = client.post(
            "/api/v1/characters",
            json={
                "char_name": "Lira Companion",
                "char_class": "Cleric",
                "char_level": 3,
                "classes": [{"class_name": "Cleric", "level": 3}],
                "race": "Human",
                "background": "Acolyte",
                "dnd_edition": EDITION_2014,
                "stats": {"STR": 12, "DEX": 12, "CON": 14, "INT": 10, "WIS": 16, "CHA": 12},
                "hp_max": 24,
                "hp_current": 12,
                "exhaustion_level": 0,
            },
            headers=p2_h,
        )
        assert p2_res.status_code == 201
        p2_id = p2_res.json()["char_id"]

        assert (
            client.post(
                "/api/v1/campaigns/",
                json={"campaign_name": "Dark Sun Athas", "dnd_edition": EDITION_2014},
                headers=dm_h,
            ).status_code
            == 200
        )
        code = client.post(
            "/api/v1/campaigns/Dark Sun Athas/invite-code",
            headers=dm_h,
        ).json()["invite_code"]

        assert (
            client.post(
                "/api/v1/campaigns/join",
                json={"character_id": solo_id, "invite_code": code},
                headers=p1_h,
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/v1/campaigns/join",
                json={"character_id": p2_id, "invite_code": code},
                headers=p2_h,
            ).status_code
            == 200
        )

        # Verify join cleared prior solo exhaustion/controls on P1? Wait: join clears DM controls (unlocks/bypass/suppression/modifiers); P1 now has active_campaign!
        # 3) Non-DM cannot toggle party state or unlock actions
        assert (
            client.patch(
                f"/api/v1/campaigns/Dark Sun Athas/party/{solo_id}/state",
                json={"exhaustion_level": 0},
                headers=p1_h,
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/campaigns/Dark Sun Athas/party/action-unlock",
                json={"action_type": "short_rest", "unlocked": True, "char_id": solo_id},
                headers=p1_h,
            ).status_code
            == 403
        )

        # 4) Locked Player inside Campaign gets 403 on Short Rest, Long Rest, Level Up
        assert (
            client.post(
                f"/api/v1/characters/{solo_id}/short-rest",
                json={"dice_to_spend": 0, "hp_healed": 0},
                headers=p1_h,
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/characters/{solo_id}/long-rest",
                json={},
                headers=p1_h,
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/forge/level-up-apply",
                json={
                    "character_id": solo_id,
                    "analysis": {
                        "hp_increase": 8,
                        "new_total_hp": 36,
                        "automatic_changes": [],
                        "choices_required": [],
                    },
                    "user_choices": {"level_up_class": "Fighter", "hp_method": "fixed"},
                },
                headers=p1_h,
            ).status_code
            == 403
        )

        # 5) Campaign PUT tamper check: Player tries to override char_level, exhaustion, bypass, suppression, modifiers, unlocks,
        # while legitimately editing hp_current and spending Heroic Inspiration
        dm_set = client.patch(
            f"/api/v1/campaigns/Dark Sun Athas/party/{solo_id}/state",
            json={
                "exhaustion_level": 2,
                "magic_items_suppressed": True,
                "dm_modifiers": {"ac_bonus": -2, "note": "Heatstroke"},
                "inspiration": True,
            },
            headers=dm_h,
        )
        assert dm_set.status_code == 200
        assert dm_set.json()["inspiration"] is True
        assert dm_set.json()["magic_items_suppressed"] is True

        curr_p1 = client.get(f"/api/v1/characters/{solo_id}", headers=p1_h).json()
        tamper_payload = {
            **curr_p1,
            "char_level": 20,
            "exhaustion_level": 0,
            "exhaustion_bypass": True,
            "magic_items_suppressed": False,
            "dm_modifiers": {"ac_bonus": 10},
            "dm_short_rest_unlocked": True,
            "dm_long_rest_unlocked": True,
            "dm_level_up_unlocked": True,
            "hp_current": 15,
            "inspiration": False,  # Player retains spending Heroic Inspiration!
        }
        tamper_res = client.put(f"/api/v1/characters/{solo_id}", json=tamper_payload, headers=p1_h)
        assert tamper_res.status_code == 200
        saved = tamper_res.json()
        assert saved["char_level"] == 3
        assert saved["exhaustion_level"] == 2
        assert saved["exhaustion_bypass"] is False
        assert saved["magic_items_suppressed"] is True
        assert saved["dm_modifiers"]["ac_bonus"] == -2
        assert saved["dm_short_rest_unlocked"] is False
        assert saved["dm_long_rest_unlocked"] is False
        assert saved["dm_level_up_unlocked"] is False
        assert saved["hp_current"] == 15
        assert saved["inspiration"] is False

        # 6) 1-Shot Unlock & Auto-Relock for Short Rest, Long Rest, and Level Up
        for action_type, endpoint, body in [
            (
                "short_rest",
                f"/api/v1/characters/{solo_id}/short-rest",
                {"dice_to_spend": 1, "hp_healed": 5},
            ),
            ("long_rest", f"/api/v1/characters/{solo_id}/long-rest", {}),
        ]:
            ul = client.post(
                "/api/v1/campaigns/Dark Sun Athas/party/action-unlock",
                json={"action_type": action_type, "unlocked": True, "char_id": solo_id},
                headers=dm_h,
            )
            assert ul.status_code == 200
            assert ul.json()["updated_count"] == 1

            first = client.post(endpoint, json=body, headers=p1_h)
            assert first.status_code == 200
            flag_name = f"dm_{action_type}_unlocked"
            assert first.json()[flag_name] is False  # auto-relocked!

            second = client.post(endpoint, json=body, headers=p1_h)
            assert second.status_code == 403  # relock enforced!

        # 1-Shot Level-up unlock + auto-relock
        ul_lvl = client.post(
            "/api/v1/campaigns/Dark Sun Athas/party/action-unlock",
            json={"action_type": "level_up", "unlocked": True, "char_id": solo_id},
            headers=dm_h,
        )
        assert ul_lvl.status_code == 200
        lvl_ok = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": solo_id,
                "analysis": {
                    "hp_increase": 8,
                    "new_total_hp": 36,
                    "automatic_changes": [],
                    "choices_required": [],
                },
                "user_choices": {"level_up_class": "Fighter", "hp_method": "fixed"},
            },
            headers=p1_h,
        )
        assert lvl_ok.status_code == 200
        assert lvl_ok.json()["char_level"] == 4
        assert lvl_ok.json()["dm_level_up_unlocked"] is False
        assert (
            client.post(
                "/api/v1/forge/level-up-apply",
                json={
                    "character_id": solo_id,
                    "analysis": {
                        "hp_increase": 8,
                        "new_total_hp": 44,
                        "automatic_changes": [],
                        "choices_required": [],
                    },
                    "user_choices": {"level_up_class": "Fighter", "hp_method": "fixed"},
                },
                headers=p1_h,
            ).status_code
            == 403
        )

        # Party-wide Athas toggle & party-wide unlock (char_id=None)
        athas_all = client.post(
            "/api/v1/campaigns/Dark Sun Athas/party/action-unlock",
            json={"action_type": "suppress_magic_items", "unlocked": True},
            headers=dm_h,
        )
        assert athas_all.status_code == 200
        assert athas_all.json()["updated_count"] == 2
        assert (
            client.get(f"/api/v1/characters/{p2_id}", headers=p2_h).json()["magic_items_suppressed"]
            is True
        )

        # 7) Level 6 Death Guard + Party Long Rest skipping dead character
        client.patch(
            f"/api/v1/campaigns/Dark Sun Athas/party/{solo_id}/state",
            json={"exhaustion_level": 6},
            headers=dm_h,
        )
        client.patch(
            f"/api/v1/campaigns/Dark Sun Athas/party/{p2_id}/state",
            json={"exhaustion_level": 3, "hp_current": 5},
            headers=dm_h,
        )
        # Unlock long rest & level up for dead character -> still 400 Bad Request!
        client.post(
            "/api/v1/campaigns/Dark Sun Athas/party/action-unlock",
            json={"action_type": "long_rest", "unlocked": True, "char_id": solo_id},
            headers=dm_h,
        )
        client.post(
            "/api/v1/campaigns/Dark Sun Athas/party/action-unlock",
            json={"action_type": "level_up", "unlocked": True, "char_id": solo_id},
            headers=dm_h,
        )
        assert (
            client.post(
                f"/api/v1/characters/{solo_id}/long-rest", json={}, headers=p1_h
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/v1/forge/level-up-apply",
                json={
                    "character_id": solo_id,
                    "analysis": {
                        "hp_increase": 8,
                        "new_total_hp": 44,
                        "automatic_changes": [],
                        "choices_required": [],
                    },
                    "user_choices": {"level_up_class": "Fighter", "hp_method": "fixed"},
                },
                headers=p1_h,
            ).status_code
            == 400
        )

        # Party-wide DM Long Rest restores Lira (EXH 3 -> 2, full HP) and SKIPS dead Kael (EXH 6, HP 0)
        party_lr = client.post("/api/v1/campaigns/Dark Sun Athas/party/long-rest", headers=dm_h)
        assert party_lr.status_code == 200
        k_after = client.get(f"/api/v1/characters/{solo_id}", headers=p1_h).json()
        l_after = client.get(f"/api/v1/characters/{p2_id}", headers=p2_h).json()
        assert k_after["exhaustion_level"] == 6
        assert k_after["hp_current"] == 0
        assert k_after["speed"] == 0
        assert l_after["exhaustion_level"] == 2
        assert l_after["hp_current"] == l_after["hp_max"]

        # 8) Campaign Detach Cleanup (DELETE member) + Cascade Cleanup (DELETE campaign)
        rem_res = client.delete(f"/api/v1/campaigns/Dark Sun Athas/party/{solo_id}", headers=dm_h)
        assert rem_res.status_code == 200
        k_detached = client.get(f"/api/v1/characters/{solo_id}", headers=p1_h).json()
        assert k_detached.get("active_campaign") in (None, "")
        assert k_detached["magic_items_suppressed"] is False
        assert k_detached["exhaustion_bypass"] is False
        assert k_detached["dm_modifiers"]["ac_bonus"] == 0
        assert k_detached["dm_short_rest_unlocked"] is False
        assert k_detached["dm_long_rest_unlocked"] is False
        assert k_detached["dm_level_up_unlocked"] is False

        del_camp = client.delete("/api/v1/campaigns/Dark Sun Athas", headers=dm_h)
        assert del_camp.status_code == 200
        l_detached = client.get(f"/api/v1/characters/{p2_id}", headers=p2_h).json()
        assert l_detached.get("active_campaign") in (None, "")
        assert l_detached["magic_items_suppressed"] is False
        assert l_detached["dm_modifiers"]["note"] == ""
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 7. DM SECRET ROLLS (_roll_in_secret + _sheet_modifier) ACROSS 2014 & 2024
# ==============================================================================


def test_secret_roll_2014_disadvantage_adv_cancel_bypass_and_dm_modifiers():
    pal_2014 = sync_character_stats(_make_paladin(EDITION_2014))
    pal_2014["exhaustion_level"] = 1
    pal_2014["dm_modifiers"] = {
        "saving_throws_bonus": 2,
        "ability_checks_bonus": -1,
        "initiative_bonus": 4,
    }
    pal_2014 = sync_character_stats(pal_2014)

    with patch("server.routers.campaign_router.roll_dice") as mock_roll:
        mock_roll.return_value = {"total": 12, "raw_result": 10, "rolls": [10, 15]}

        # 2014 L1 Skill check: automatic Disadvantage!
        res_skill = _roll_in_secret(pal_2014, "skill", "Perception")
        assert mock_roll.call_args.kwargs["disadvantage"] is True
        assert mock_roll.call_args.kwargs["advantage"] is False
        assert res_skill["mode"] == "disadvantage"

        # 2014 L1 Save: NO Disadvantage yet (only starts at L3!) + +2 DM save bonus included in modifier!
        res_save_l1 = _roll_in_secret(pal_2014, "save", "WIS")
        assert mock_roll.call_args.kwargs["disadvantage"] is False
        assert res_save_l1["mode"] == "normal"
        # WIS: +1 mod + 3 prof + 1 Cloak + 2 DM mod = +7
        assert _sheet_modifier(pal_2014, "save", "WIS") == 7

        # 2014 L1 Initiative WITH Weapon of Warning (adv) + L1 Exhaustion (dis) => Adv/Dis cancel to normal!
        res_init_warn = _roll_in_secret(pal_2014, "initiative", "Initiative")
        assert mock_roll.call_args.kwargs["advantage"] is True
        assert mock_roll.call_args.kwargs["disadvantage"] is True
        assert res_init_warn["mode"] == "normal"
        assert (
            _sheet_modifier(pal_2014, "initiative", "Initiative") == 4
        )  # +1 DEX + 4 DM init - 1 DM checks

        # Athas suppresses Weapon of Warning -> initiative_advantage=False -> L1 Disadvantage applies!
        pal_sup = sync_character_stats({**copy.deepcopy(pal_2014), "magic_items_suppressed": True})
        res_init_sup = _roll_in_secret(pal_sup, "initiative", "Initiative")
        assert mock_roll.call_args.kwargs["advantage"] is False
        assert mock_roll.call_args.kwargs["disadvantage"] is True
        assert res_init_sup["mode"] == "disadvantage"

        # 2014 L3 Exhaustion: Save gets Disadvantage too!
        pal_l3 = sync_character_stats({**copy.deepcopy(pal_2014), "exhaustion_level": 3})
        res_save_l3 = _roll_in_secret(pal_l3, "save", "WIS")
        assert mock_roll.call_args.kwargs["disadvantage"] is True
        assert res_save_l3["mode"] == "disadvantage"

        # Exhaustion bypass waives L3 Disadvantage!
        pal_waived = sync_character_stats({**copy.deepcopy(pal_l3), "exhaustion_bypass": True})
        res_save_waived = _roll_in_secret(pal_waived, "save", "WIS")
        assert mock_roll.call_args.kwargs["disadvantage"] is False
        assert res_save_waived["mode"] == "normal"

    # 2024 Exhaustion: no automatic Disadvantage, flat -2*lvl already synced into sheet modifier
    wiz_2024 = sync_character_stats({**_make_wizard(EDITION_2024), "exhaustion_level": 3})
    with patch("server.routers.campaign_router.roll_dice") as mock_roll:
        mock_roll.return_value = {"total": 10, "raw_result": 10, "rolls": [10]}
        res_2024 = _roll_in_secret(wiz_2024, "save", "INT")
        assert mock_roll.call_args.kwargs["disadvantage"] is False
        assert res_2024["mode"] == "normal"
        # INT save: +4 mod + 3 prof - 6 exhaustion = +1
        assert res_2024["modifier"] == 1
