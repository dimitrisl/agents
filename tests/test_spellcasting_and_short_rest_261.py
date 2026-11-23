"""Tests for Issue #261: Prepared Spells Cap, Always-Prepared Split, Rituals & Short-Rest Slot Recovery."""

import copy

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.repositories.rules_repository import RulesRepository
from backend.services.class_resources_service import rules_pools
from backend.services.rest_service import apply_short_rest
from backend.services.stats_service import (
    calculate_max_prepared_spells,
    collect_always_prepared_spells,
    sync_character_stats,
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
def mock_db():
    return _AsyncDBWrapper(mongomock.MongoClient().db)


@pytest.fixture
def auth_client(mock_db):
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-261",
        "username": "elara",
    }
    yield TestClient(app)
    app.dependency_overrides = orig
    limiter.reset()


def _base_char(**overrides):
    doc = {
        "char_id": "char-261",
        "owner_id": "user-261",
        "char_name": "Elara",
        "char_class": "Wizard",
        "char_level": 5,
        "classes": [{"class_name": "Wizard", "level": 5}],
        "dnd_edition": EDITION_2014,
        "race": "Human",
        "background": "Sage",
        "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 18, "WIS": 12, "CHA": 10},
        "hp_max": 32,
        "hp_current": 20,
        "hit_dice_used": 0,
        "spells": {
            "cantrips": ["Fire Bolt", "Mage Hand"],
            "level_1": ["Detect Magic", "Mage Armor", "Shield"],
            "level_2": ["Misty Step", "Hold Person"],
            "level_3": ["Fireball"],
        },
        "prepared_spells": ["Mage Armor", "Shield", "Misty Step", "Fireball"],
        "features_traits": [],
        "weapons": [],
        "equipment": [],
        "active_campaign": "Frostmarch",
        "dm_short_rest_unlocked": True,
        "version": 1,
    }
    doc.update(overrides)
    return doc


def test_prepared_spells_cap_2014_vs_2024_and_multiclass():
    stats = {"STR": 10, "DEX": 14, "CON": 14, "INT": 18, "WIS": 16, "CHA": 16}

    # 2014 Edition: Prepared casters use Level + Mod (or floor(Level/2) + Mod), Known casters -> None
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Wizard", "level": 5}], "Wizard", None, 5, stats, EDITION_2014
        )
        == 9
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Cleric", "level": 5}], "Cleric", "Life Domain", 5, stats, EDITION_2014
        )
        == 8
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Druid", "level": 1}],
            "Druid",
            None,
            1,
            {"WIS": 8},
            EDITION_2014,
        )
        == 1
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Paladin", "level": 1}], "Paladin", None, 1, stats, EDITION_2014
        )
        is None
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Paladin", "level": 2}], "Paladin", None, 2, stats, EDITION_2014
        )
        == 4
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Artificer", "level": 5}], "Artificer", None, 5, stats, EDITION_2014
        )
        == 6
    )
    for known_cls in ("Bard", "Sorcerer", "Warlock", "Ranger"):
        assert (
            calculate_max_prepared_spells(
                [{"class_name": known_cls, "level": 5}], known_cls, None, 5, stats, EDITION_2014
            )
            is None
        )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Fighter", "subclass": "Eldritch Knight", "level": 5}],
            "Fighter",
            "Eldritch Knight",
            5,
            stats,
            EDITION_2014,
        )
        is None
    )

    # 2024 Revision: All spellcasters use fixed prepared spell tables (except Artificer formula)
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Wizard", "level": 5}], "Wizard", None, 5, stats, EDITION_2024
        )
        == 9
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Cleric", "level": 5}], "Cleric", None, 5, stats, EDITION_2024
        )
        == 9
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Bard", "level": 5}], "Bard", None, 5, stats, EDITION_2024
        )
        == 9
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Sorcerer", "level": 5}], "Sorcerer", None, 5, stats, EDITION_2024
        )
        == 9
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Warlock", "level": 5}], "Warlock", None, 5, stats, EDITION_2024
        )
        == 6
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Paladin", "level": 1}], "Paladin", None, 1, stats, EDITION_2024
        )
        == 2
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Ranger", "level": 1}], "Ranger", None, 1, stats, EDITION_2024
        )
        == 2
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Fighter", "subclass": "Eldritch Knight", "level": 3}],
            "Fighter",
            "Eldritch Knight",
            3,
            stats,
            EDITION_2024,
        )
        == 3
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Rogue", "subclass": "Arcane Trickster", "level": 3}],
            "Rogue",
            "Arcane Trickster",
            3,
            stats,
            EDITION_2024,
        )
        == 3
    )
    assert (
        calculate_max_prepared_spells(
            [{"class_name": "Artificer", "level": 5}], "Artificer", None, 5, stats, EDITION_2024
        )
        == 6
    )

    # Multiclass sums prepared caps across prepared classes
    synced_mc_2014 = sync_character_stats(
        _base_char(
            char_class="Cleric",
            char_level=5,
            classes=[
                {"class_name": "Cleric", "subclass": "Life Domain", "level": 3},
                {"class_name": "Wizard", "level": 2},
            ],
            stats=stats,
            dnd_edition=EDITION_2014,
        )
    )
    assert synced_mc_2014["max_prepared_spells"] == 12  # (3+3) + (2+4)

    synced_mc_2024 = sync_character_stats(
        _base_char(
            char_class="Cleric",
            char_level=5,
            classes=[
                {"class_name": "Cleric", "subclass": "Life Domain", "level": 3},
                {"class_name": "Wizard", "level": 2},
            ],
            stats=stats,
            dnd_edition=EDITION_2024,
        )
    )
    assert synced_mc_2024["max_prepared_spells"] == 11  # L3 Cleric (6) + L2 Wizard (5)


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_always_prepared_spells_extraction_and_split_preservation(edition):
    repo = RulesRepository()
    cleric = sync_character_stats(
        _base_char(
            char_class="Cleric",
            subclass="Life Domain",
            char_level=3,
            classes=[{"class_name": "Cleric", "subclass": "Life Domain", "level": 3}],
            dnd_edition=edition,
            race="Tiefling",
            stats={"STR": 14, "DEX": 10, "CON": 14, "INT": 10, "WIS": 16, "CHA": 12},
            spells={
                "cantrips": ["Sacred Flame", "Thaumaturgy"],
                "level_1": ["Bless", "Cure Wounds", "Guiding Bolt"],
                "level_2": [
                    "Lesser Restoration",
                    "Aid" if "2024" in edition else "Spiritual Weapon",
                    "Prayer of Healing",
                ],
            },
            prepared_spells=["Guiding Bolt", "Prayer of Healing"],
        )
    )
    always = set(cleric["always_prepared_spells"])
    expected_domain_l2 = "Aid" if "2024" in edition else "Spiritual Weapon"
    assert {
        "Bless",
        "Cure Wounds",
        "Lesser Restoration",
        expected_domain_l2,
        "Hellish Rebuke",
    }.issubset(always)
    # Cantrips must never be listed in always_prepared_spells
    assert "Thaumaturgy" not in always
    # User's manual prepared_spells list stays separated from always_prepared_spells
    assert cleric["prepared_spells"] == ["Guiding Bolt", "Prayer of Healing"]
    assert cleric["max_prepared_spells"] == 6

    # Known caster in 2014 with Horizon Walker bonus spells keeps empty prepared_spells untouched
    if edition == EDITION_2014:
        ranger = sync_character_stats(
            _base_char(
                char_class="Ranger",
                subclass="Horizon Walker",
                char_level=5,
                classes=[{"class_name": "Ranger", "subclass": "Horizon Walker", "level": 5}],
                dnd_edition=EDITION_2014,
                prepared_spells=[],
            )
        )
        assert ranger["max_prepared_spells"] is None
        assert ranger["prepared_spells"] == []
        expected_hw = repo.get_subclass_entry("Ranger", "Horizon Walker", EDITION_2014)[
            "bonus_spells"
        ]
        assert "Protection from Evil and Good" in expected_hw["3"]
        assert {"Protection from Evil and Good", "Misty Step"}.issubset(
            set(ranger["always_prepared_spells"])
        )

    always_drow = collect_always_prepared_spells(
        {"race": "Dark Elf (Drow)", "char_level": 5},
        [{"class_name": "Fighter", "level": 5}],
        "Fighter",
        None,
        5,
        edition,
        repo,
    )
    assert "Faerie Fire" in always_drow
    assert "Darkness" in always_drow
    assert "Dancing Lights" not in always_drow


def test_ritual_flag_data_accuracy_2014_and_2024():
    repo = RulesRepository()
    for edition in (EDITION_2014, EDITION_2024):
        by_name = {sp["name"]: sp for sp in repo.get_all_spells(edition)}
        assert by_name["Purify Food and Drink"].get("ritual") is True
        assert by_name["Detect Magic"].get("ritual") is True
        assert by_name["Hold Person"].get("ritual") is False
        assert by_name["Fireball"].get("ritual") is False


def test_natural_recovery_pool_edition_gating():
    land_2014_l1 = rules_pools(
        [{"class_name": "Druid", "subclass": "Circle of the Land", "level": 1}],
        {"WIS": 16},
        EDITION_2014,
    )
    assert not any(p["name"] == "Natural Recovery" for p in land_2014_l1)

    land_2014_l2 = rules_pools(
        [{"class_name": "Druid", "subclass": "Circle of the Land", "level": 2}],
        {"WIS": 16},
        EDITION_2014,
    )
    assert any(p["name"] == "Natural Recovery" and p["max"] == 1 for p in land_2014_l2)

    land_2024_l5 = rules_pools(
        [{"class_name": "Druid", "subclass": "Circle of the Land", "level": 5}],
        {"WIS": 18},
        EDITION_2024,
    )
    assert not any(p["name"] == "Natural Recovery" for p in land_2024_l5)

    land_2024_l6 = rules_pools(
        [{"class_name": "Druid", "subclass": "Circle of the Land", "level": 6}],
        {"WIS": 18},
        EDITION_2024,
    )
    assert any(p["name"] == "Natural Recovery" and p["max"] == 1 for p in land_2024_l6)

    moon_l6 = rules_pools(
        [{"class_name": "Druid", "subclass": "Circle of the Moon", "level": 6}],
        {"WIS": 18},
        EDITION_2014,
    )
    assert not any(p["name"] == "Natural Recovery" for p in moon_l6)


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_arcane_recovery_short_rest_and_errors(auth_client, mock_db, edition):
    wiz = sync_character_stats(
        _base_char(
            char_id=f"wiz-{edition[:4]}",
            char_class="Wizard",
            char_level=5,
            classes=[{"class_name": "Wizard", "level": 5}],
            dnd_edition=edition,
        )
    )
    wiz["spell_slots"]["level_1"]["used"] = 2
    wiz["spell_slots"]["level_2"]["used"] = 2
    wiz["spell_slots"]["level_3"]["used"] = 1

    # Budget for Wizard L5 = ceil(5/2) = 3: 1x L1 + 1x L2 = 3 succeeds (0 Hit Dice spent!)
    rested = apply_short_rest(wiz, dice_to_spend=0, arcane_recovery_slots={"1": 1, "2": 1})
    assert rested["spell_slots"]["level_1"]["used"] == 1
    assert rested["spell_slots"]["level_2"]["used"] == 1
    assert rested["dm_short_rest_unlocked"] is False
    ar_pool = next(r for r in rested["class_resources"] if r["name"] == "Arcane Recovery")
    assert ar_pool["current"] == 0

    # Validation errors on service layer
    with pytest.raises(ValueError, match="budget exceeded"):
        apply_short_rest(wiz, dice_to_spend=0, arcane_recovery_slots={"2": 2})

    wiz_high = copy.deepcopy(wiz)
    wiz_high["char_level"] = 11
    wiz_high["classes"] = [{"class_name": "Wizard", "level": 11}]
    wiz_high["spell_slots"]["level_6"] = {"max": 1, "used": 1}
    with pytest.raises(ValueError, match="6th level"):
        apply_short_rest(wiz_high, dice_to_spend=0, arcane_recovery_slots={"6": 1})

    wiz_unexpended = copy.deepcopy(wiz)
    wiz_unexpended["spell_slots"]["level_1"]["used"] = 0
    with pytest.raises(ValueError, match="expended"):
        apply_short_rest(wiz_unexpended, dice_to_spend=0, arcane_recovery_slots={"1": 1})

    # Re-trying via REST endpoint succeeds once, then rejects when Arcane Recovery == 0
    mock_db["characters"]._col.insert_one(copy.deepcopy(wiz))
    res_ok = auth_client.post(
        f"/api/v1/characters/{wiz['char_id']}/short-rest",
        json={
            "dice_to_spend": 0,
            "arcane_recovery_slots": {"3": 1},
            "expected_version": wiz["version"],
        },
    )
    assert res_ok.status_code == 200, res_ok.text
    body = res_ok.json()
    assert body["spell_slots"]["level_3"]["used"] == 0
    assert (
        next(r for r in body["class_resources"] if r["name"] == "Arcane Recovery")["current"] == 0
    )

    # Re-unlock DM short rest and attempt second Arcane Recovery without Long Rest -> 400
    mock_db["characters"]._col.update_one(
        {"char_id": wiz["char_id"]}, {"$set": {"dm_short_rest_unlocked": True}}
    )
    res_dup = auth_client.post(
        f"/api/v1/characters/{wiz['char_id']}/short-rest",
        json={"dice_to_spend": 0, "arcane_recovery_slots": {"1": 1}},
    )
    assert res_dup.status_code == 400


def test_natural_recovery_short_rest_2014_vs_2024(auth_client, mock_db):
    druid_14 = sync_character_stats(
        _base_char(
            char_id="druid-14",
            char_class="Druid",
            subclass="Circle of the Land",
            char_level=4,
            classes=[{"class_name": "Druid", "subclass": "Circle of the Land", "level": 4}],
            dnd_edition=EDITION_2014,
            stats={"STR": 10, "DEX": 14, "CON": 14, "INT": 12, "WIS": 18, "CHA": 10},
        )
    )
    druid_14["spell_slots"]["level_2"]["used"] = 2
    mock_db["characters"]._col.insert_one(druid_14)

    res14 = auth_client.post(
        "/api/v1/characters/druid-14/short-rest",
        json={"dice_to_spend": 0, "natural_recovery_slots": {"2": 1}},
    )
    assert res14.status_code == 200, res14.text
    assert res14.json()["spell_slots"]["level_2"]["used"] == 1
    assert (
        next(r for r in res14.json()["class_resources"] if r["name"] == "Natural Recovery")[
            "current"
        ]
        == 0
    )

    druid_24_low = sync_character_stats(
        _base_char(
            char_id="druid-24-l4",
            char_class="Druid",
            subclass="Circle of the Land",
            char_level=4,
            classes=[{"class_name": "Druid", "subclass": "Circle of the Land", "level": 4}],
            dnd_edition=EDITION_2024,
            stats={"STR": 10, "DEX": 14, "CON": 14, "INT": 12, "WIS": 18, "CHA": 10},
        )
    )
    druid_24_low["spell_slots"]["level_2"]["used"] = 1
    with pytest.raises(ValueError, match="Level 6+"):
        apply_short_rest(druid_24_low, dice_to_spend=0, natural_recovery_slots={"2": 1})

    druid_24_l6 = sync_character_stats(
        _base_char(
            char_id="druid-24-l6",
            char_class="Druid",
            subclass="Circle of the Land",
            char_level=6,
            classes=[{"class_name": "Druid", "subclass": "Circle of the Land", "level": 6}],
            dnd_edition=EDITION_2024,
            stats={"STR": 10, "DEX": 14, "CON": 14, "INT": 12, "WIS": 18, "CHA": 10},
        )
    )
    druid_24_l6["spell_slots"]["level_3"]["used"] = 1
    rested_24 = apply_short_rest(druid_24_l6, dice_to_spend=0, natural_recovery_slots={"3": 1})
    assert rested_24["spell_slots"]["level_3"]["used"] == 0
    assert (
        next(r for r in rested_24["class_resources"] if r["name"] == "Natural Recovery")["current"]
        == 0
    )


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_harness_divine_power_short_rest_2014_and_2024(auth_client, mock_db, edition):
    cleric = sync_character_stats(
        _base_char(
            char_id=f"cleric-hdp-{edition[:4]}",
            char_class="Cleric",
            subclass="Life Domain",
            char_level=5,
            classes=[{"class_name": "Cleric", "subclass": "Life Domain", "level": 5}],
            dnd_edition=edition,
            stats={"STR": 14, "DEX": 10, "CON": 14, "INT": 10, "WIS": 18, "CHA": 12},
        )
    )
    cleric["spell_slots"]["level_2"]["used"] = 2
    cleric["spell_slots"]["level_3"]["used"] = 1

    # L5 PB = 3 -> ceil(3/2) = 2 max slot level; level_3 must be rejected
    with pytest.raises(ValueError, match="up to level 2"):
        apply_short_rest(cleric, dice_to_spend=0, harness_divine_power_slot=3)

    # Pre-check blocks Harness Divine Power when Channel Divinity started at 0 before the rest
    no_cd = copy.deepcopy(cleric)
    for r in no_cd["class_resources"]:
        if r["name"] == "Channel Divinity":
            r["current"] = 0
    with pytest.raises(ValueError, match="No Channel Divinity"):
        apply_short_rest(no_cd, dice_to_spend=0, harness_divine_power_slot=2)

    # With Channel Divinity >= 1 before short rest: recovers Level 2 slot & ends with CD spent
    mock_db["characters"]._col.insert_one(copy.deepcopy(cleric))
    res = auth_client.post(
        f"/api/v1/characters/{cleric['char_id']}/short-rest",
        json={"dice_to_spend": 0, "harness_divine_power_slot": 2},
    )
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["spell_slots"]["level_2"]["used"] == 1
    cd_out = next(r for r in out["class_resources"] if r["name"] == "Channel Divinity")
    assert cd_out["current"] == cd_out["max"] - 1

    # Paladin L3+ also eligible for Harness Divine Power (L3 PB=2 -> max slot level 1)
    paladin = sync_character_stats(
        _base_char(
            char_id=f"pal-hdp-{edition[:4]}",
            char_class="Paladin",
            subclass="Oath of Devotion",
            char_level=3,
            classes=[{"class_name": "Paladin", "subclass": "Oath of Devotion", "level": 3}],
            dnd_edition=edition,
            stats={"STR": 16, "DEX": 10, "CON": 14, "INT": 10, "WIS": 12, "CHA": 16},
        )
    )
    paladin["spell_slots"]["level_1"]["used"] = 1
    rested_pal = apply_short_rest(paladin, dice_to_spend=0, harness_divine_power_slot=1)
    assert rested_pal["spell_slots"]["level_1"]["used"] == 0
