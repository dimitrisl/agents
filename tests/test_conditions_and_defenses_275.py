"""
Backend verification suite for Ticket #275:
- Condition roll-mode effects (Poisoned, Frightened, Blinded, Restrained, Prone, Invisible 2014 vs 2024)
- Non-destructive Speed 0 condition lock & restoration (player PUT & DM PATCH /state)
- Class, Subclass, Species, and Sense Countermeasures ("Antidotes") across 2014 & 2024
- Damage Resistances, Immunities & Vulnerabilities derivation, normalization & WS party payload
"""

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.core.schemas import CharacterSchema
from backend.services.campaign_service import build_party_update_payload
from backend.services.condition_rules import (
    detect_condition_countermeasures,
    evaluate_condition_roll_mode,
    has_speed_zero_condition,
)
from backend.services.stats_service import sync_character_stats
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter
from server.routers.campaign_router import _roll_in_secret


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
        self._coll = col

    async def find_one(self, *args, **kwargs):
        return self._coll.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._coll.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._coll.update_one(*args, **kwargs)

    async def find_one_and_update(self, *args, **kwargs):
        return self._coll.find_one_and_update(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursorWrapper(self._coll.find(*args, **kwargs))


class _AsyncDbWrapper:
    def __init__(self, mongo_db):
        self._db = mongo_db
        self._colls = {}

    def __getitem__(self, name: str):
        if name not in self._colls:
            self._colls[name] = _AsyncColWrapper(self._db[name])
        return self._colls[name]


@pytest.fixture
def mock_db():
    client = mongomock.MongoClient()
    return _AsyncDbWrapper(client["phyrexian_forge_test_275"])


def _base_char(edition: str = EDITION_2014, **overrides):
    data = {
        "char_id": "cond-hero-275",
        "owner_id": "user-1",
        "char_name": "Kaelen",
        "char_class": "Fighter",
        "char_level": 5,
        "classes": [{"class_name": "Fighter", "level": 5}],
        "dnd_edition": edition,
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        "saving_throws": ["STR", "CON"],
        "speed": 30,
        "hp_max": 44,
        "hp_current": 44,
        "armor_class": 16,
        "features_traits": [],
        "conditions": [],
        "senses": [],
        "damage_resistances": [],
        "damage_immunities": [],
        "damage_vulnerabilities": [],
        "version": 0,
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_condition_speed_zero_is_non_destructive(edition):
    assert has_speed_zero_condition(["Prone"]) is False
    assert has_speed_zero_condition(["Grappled"]) is True
    # 2014 Stunned = can't move; 2024 Stunned = Incapacitated only (no Speed 0)
    assert has_speed_zero_condition(["Stunned"], False) is True
    assert has_speed_zero_condition(["Stunned"], True) is False
    assert has_speed_zero_condition(["Paralyzed"], True) is True

    hero = _base_char(edition, race="Human", conditions=["Grappled"])
    synced_grappled = sync_character_stats(hero)
    assert synced_grappled["speed"] == 0
    assert synced_grappled["base_speed"] == 30

    # Removing Grappled restores full computed speed without loss
    synced_grappled["conditions"] = []
    synced_free = sync_character_stats(synced_grappled)
    assert synced_free["speed"] == 30
    assert synced_free["base_speed"] == 30

    # Prone leaves walking speed intact
    synced_free["conditions"] = ["Prone"]
    synced_prone = sync_character_stats(synced_free)
    assert synced_prone["speed"] == 30


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_condition_roll_mode_matrix_and_cancellation(edition):
    is_2024 = "2024" in edition

    # Poisoned & Frightened -> attack, check, and Initiative DIS in BOTH 2014 & 2024;
    # 2024 Invisible + Poisoned cancels to normal
    poisoned = _base_char(edition, conditions=["Poisoned"])
    assert evaluate_condition_roll_mode(poisoned, "attack") == (False, True, False)
    assert evaluate_condition_roll_mode(poisoned, "check", "STR") == (False, True, False)
    assert evaluate_condition_roll_mode(poisoned, "initiative") == (False, True, False)
    assert evaluate_condition_roll_mode(poisoned, "save", "CON") == (False, False, False)

    # Explicit edition='2014 Edition' overrides stale ruleset_version='2024'
    override_char = _base_char(EDITION_2024, ruleset_version="2024", conditions=["Invisible"])
    assert evaluate_condition_roll_mode(override_char, "initiative", edition=EDITION_2014) == (
        False,
        False,
        False,
    )

    # Restrained -> attack & DEX save DIS; STR save unaffected
    restrained = _base_char(edition, conditions=["Restrained"])
    assert evaluate_condition_roll_mode(restrained, "attack") == (False, True, False)
    assert evaluate_condition_roll_mode(restrained, "save", "DEX") == (False, True, False)
    assert evaluate_condition_roll_mode(restrained, "save", "STR") == (False, False, False)

    # Paralyzed -> Auto-fail STR & DEX saves (short-circuits _roll_in_secret without rolling), NOT WIS
    paralyzed = _base_char(edition, conditions=["Paralyzed"])
    assert evaluate_condition_roll_mode(paralyzed, "save", "STR") == (False, False, True)
    assert evaluate_condition_roll_mode(paralyzed, "save", "DEX") == (False, False, True)
    assert evaluate_condition_roll_mode(paralyzed, "save", "WIS") == (False, False, False)
    secret_str_save = _roll_in_secret(paralyzed, "save", "STR")
    assert secret_str_save["auto_fail"] is True
    assert secret_str_save["total"] == 0
    assert secret_str_save["rolls"] == []
    assert secret_str_save["expression"] == "AUTO-FAIL (Condition)"

    # Incapacitated -> Initiative DIS in 2024 Revision ONLY
    incap = _base_char(edition, conditions=["Incapacitated"])
    assert evaluate_condition_roll_mode(incap, "initiative") == (False, is_2024, False)
    assert evaluate_condition_roll_mode(paralyzed, "initiative") == (False, is_2024, False)
    assert _roll_in_secret(incap, "initiative", "Initiative")["mode"] == (
        "disadvantage" if is_2024 else "normal"
    )

    # Invisible -> Attack ADV in both editions; Initiative ADV strictly in 2024
    invis = _base_char(edition, conditions=["Invisible"])
    assert evaluate_condition_roll_mode(invis, "attack") == (True, False, False)
    assert evaluate_condition_roll_mode(invis, "initiative") == (is_2024, False, False)

    # Secret DM roll combines Invisible ADV + Poisoned DIS cleanly -> normal cancellation
    both = _base_char(edition, conditions=["Invisible", "Poisoned"])
    atk_roll = _roll_in_secret(both, "attack", "STR")
    assert atk_roll["mode"] == "normal"
    init_both_roll = _roll_in_secret(both, "initiative", "Initiative")
    assert init_both_roll["mode"] == ("normal" if is_2024 else "disadvantage")

    init_roll = _roll_in_secret(invis, "initiative", "Initiative")
    assert init_roll["mode"] == ("advantage" if is_2024 else "normal")


def test_2014_vs_2024_antidote_countermeasures_and_monk_purity_split():
    # 2014 Monk L10: Purity of Body grants Poison damage immunity + Poisoned immune antidote;
    # L7 Stillness of Mind grants Action cleanse for Charmed/Frightened
    monk_2014 = sync_character_stats(
        _base_char(
            EDITION_2014,
            char_class="Monk",
            char_level=10,
            classes=[{"class_name": "Monk", "level": 10}],
            features_traits=[
                {"name": "Stillness of Mind", "description": "Action to end Charmed or Frightened"},
                {"name": "Purity of Body", "description": "Immune to disease and poison"},
            ],
        )
    )
    assert "Poison" in monk_2014["damage_immunities"]
    cm_2014 = detect_condition_countermeasures(monk_2014, EDITION_2014)
    assert any(c["condition"] == "Poisoned" and c["kind"] == "immune" for c in cm_2014)
    assert any(c["condition"] == "Frightened" and c["kind"] == "action_end" for c in cm_2014)

    # 2024 Monk L10: Self-Restoration allows Bonus Action cleanse of Charmed/Frightened/Poisoned,
    # WITHOUT passive Poison damage immunity
    monk_2024 = sync_character_stats(
        _base_char(
            EDITION_2024,
            char_class="Monk",
            char_level=10,
            classes=[{"class_name": "Monk", "level": 10}],
            features_traits=[
                {
                    "name": "Self-Restoration",
                    "description": "Bonus Action to end Charmed, Frightened, or Poisoned.",
                }
            ],
        )
    )
    assert "Poison" not in monk_2024["damage_immunities"]
    cm_2024 = detect_condition_countermeasures(monk_2024, EDITION_2024)
    assert any(c["condition"] == "Poisoned" and c["kind"] == "action_end" for c in cm_2024)
    assert any(c["condition"] == "Charmed" and c["kind"] == "action_end" for c in cm_2024)

    # Berserker Mindless Rage, Paladin Aura of Courage, Devotion Aura of Devotion,
    # Elf Fey Ancestry, Halfling Brave, Blind Fighting
    paladin_elf = sync_character_stats(
        _base_char(
            EDITION_2024,
            race="Elf",
            char_class="Paladin",
            subclass="Oath of Devotion",
            char_level=10,
            classes=[{"class_name": "Paladin", "level": 10, "subclass": "Oath of Devotion"}],
            features_traits=[
                {"name": "Mindless Rage", "description": "Immune while raging"},
                {"name": "Blind Fighting", "description": "Blindsight 10 ft."},
            ],
        )
    )
    cm_pal = detect_condition_countermeasures(paladin_elf, EDITION_2024)
    assert any(c["condition"] == "Frightened" and "Aura of Courage" in c["source"] for c in cm_pal)
    assert any(c["condition"] == "Charmed" and "Aura of Devotion" in c["source"] for c in cm_pal)
    assert any(c["condition"] == "Charmed" and "Fey Ancestry" in c["source"] for c in cm_pal)
    assert any(c["condition"] == "Blinded" and c["kind"] == "sense_mitigation" for c in cm_pal)

    halfling = _base_char(EDITION_2014, race="Stout Halfling")
    cm_half = detect_condition_countermeasures(halfling, EDITION_2014)
    assert any(c["condition"] == "Frightened" and "Brave" in c["source"] for c in cm_half)
    assert any(c["condition"] == "Poisoned" and "Stout Resilience" in c["source"] for c in cm_half)

    # 2024 Land Druid L10 Nature's Ward keeps Poisoned condition immunity antidote (NOT Poison damage immunity)
    druid_2024 = sync_character_stats(
        _base_char(
            EDITION_2024,
            char_class="Druid",
            subclass="Circle of the Land",
            char_level=10,
            classes=[{"class_name": "Druid", "level": 10, "subclass": "Circle of the Land"}],
        )
    )
    assert "Poison" not in druid_2024["damage_immunities"]
    cm_druid24 = detect_condition_countermeasures(druid_2024, EDITION_2024)
    assert any(c["condition"] == "Poisoned" and c["source"] == "Nature's Ward" for c in cm_druid24)


def test_legacy_speed_zero_grappled_and_get_hydration():
    from backend.services.stats_service import hydrate_character_spellcasting_and_resources

    # Legacy Grappled sheet without base_speed must NOT latch base_speed = 0
    legacy_grappled = _base_char(
        EDITION_2014,
        race="Human",
        char_class="Monk",
        char_level=10,
        classes=[{"class_name": "Monk", "level": 10}],
        conditions=["Grappled"],
        speed=0,
        base_speed=None,
    )
    hydrated = hydrate_character_spellcasting_and_resources(dict(legacy_grappled))
    assert hydrated["speed"] == 0
    assert hydrated["base_speed"] == 30
    assert "Poison" in hydrated["damage_immunities"]

    synced = sync_character_stats(dict(legacy_grappled))
    assert synced["base_speed"] == 30
    assert synced["speed"] == 0
    synced["conditions"] = []
    restored = sync_character_stats(synced)
    assert restored["speed"] == 50  # 30 base + 20 Monk Unarmored Movement

    # Switching 2014 Monk L10 -> 2024 Revision clears Purity of Body Poison immunity cleanly
    # while keeping user-added Psychic immunity; changing Tiefling -> Human clears Fire while keeping Cold
    monk14 = sync_character_stats(
        _base_char(
            EDITION_2014,
            race="Tiefling",
            char_class="Monk",
            char_level=10,
            classes=[{"class_name": "Monk", "level": 10}],
            damage_resistances=["Cold"],
            damage_immunities=["Psychic"],
        )
    )
    assert "Fire" in monk14["damage_resistances"] and "Cold" in monk14["damage_resistances"]
    assert "Poison" in monk14["damage_immunities"] and "Psychic" in monk14["damage_immunities"]
    monk14["dnd_edition"] = EDITION_2024
    monk14["ruleset_version"] = EDITION_2024
    monk14["race"] = "Human"
    converted = sync_character_stats(monk14)
    assert converted["damage_immunities"] == ["Psychic"]
    assert converted["derived_damage_immunities"] == []
    assert converted["damage_resistances"] == ["Cold"]
    assert converted["derived_damage_resistances"] == []

    # Legacy 2024 Exh L6 zero-speed sheet without base_speed must NOT latch base_speed = 0
    exh6_2024 = _base_char(EDITION_2024, race="Human", exhaustion_level=6, speed=0, base_speed=None)
    synced_exh6 = sync_character_stats(dict(exh6_2024))
    assert synced_exh6["base_speed"] == 30
    assert synced_exh6["speed"] == 0


def test_schema_damage_defenses_and_party_ws_payload():
    hero = CharacterSchema(
        **_base_char(
            EDITION_2024,
            race="Elf",
            senses=["Darkvision 60 ft."],
            damage_resistances=[" Fire ", "fire", "Cold"],
            damage_immunities=["Poison", " poison ", "Psychic"],
            damage_vulnerabilities=["Radiant", "RADIANT"],
        )
    )
    assert hero.damage_resistances == ["Fire", "Cold"]
    assert hero.damage_immunities == ["Poison", "Psychic"]
    assert hero.damage_vulnerabilities == ["Radiant"]

    ws_payload = build_party_update_payload(hero.model_dump(), source="player")
    assert ws_payload["race"] == "Elf"
    assert isinstance(ws_payload["classes"], list)
    assert ws_payload["senses"] == ["Darkvision 60 ft."]
    assert isinstance(ws_payload["features_traits"], list)
    assert ws_payload["damage_resistances"] == ["Fire", "Cold"]
    assert ws_payload["damage_immunities"] == ["Poison", "Psychic"]
    assert ws_payload["damage_vulnerabilities"] == ["Radiant"]


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_routes_sync_condition_speed_and_defenses(mock_db, edition):
    hero = sync_character_stats(
        _base_char(
            edition,
            char_id="hero-route-275",
            owner_id="user-1",
            active_campaign="Frostfell",
            damage_resistances=["Fire"],
            damage_immunities=["Cold"],
            damage_vulnerabilities=["Thunder"],
        )
    )
    mock_db["characters"]._coll.insert_one(hero)
    mock_db["campaigns"]._coll.insert_one(
        {
            "campaign_name": "Frostfell",
            "dm_id": "dm-1",
            "dnd_edition": edition,
            "party": ["hero-route-275"],
        }
    )
    mock_db["campaign_members"]._coll.insert_one(
        {
            "campaign_id": "Frostfell",
            "user_id": "dm-1",
            "role": "dm",
            "character_ids": [],
        }
    )

    orig = app.dependency_overrides.copy()
    try:
        app.dependency_overrides[get_database] = lambda: mock_db

        # 1. DM adds Grappled via PATCH /party/{char_id}/state -> speed drops to 0 non-destructively
        app.dependency_overrides[get_current_user] = lambda: {"id": "dm-1", "username": "dm"}
        client = TestClient(app)
        resp_dm = client.patch(
            "/api/v1/campaigns/Frostfell/party/hero-route-275/state",
            json={"conditions": ["Grappled"]},
        )
        assert resp_dm.status_code == 200, resp_dm.text
        db_after_grapple = mock_db["characters"]._coll.find_one({"char_id": "hero-route-275"})
        assert db_after_grapple["conditions"] == ["Grappled"]
        assert db_after_grapple["speed"] == 0
        assert db_after_grapple["base_speed"] == 30

        # 2. Player clears Grappled via PUT /characters/{id} & preserves custom defenses
        app.dependency_overrides[get_current_user] = lambda: {"id": "user-1", "username": "player"}
        put_payload = {k: v for k, v in db_after_grapple.items() if k != "_id"}
        put_payload["conditions"] = []
        resp_player = client.put("/api/v1/characters/hero-route-275", json=put_payload)
        assert resp_player.status_code == 200, resp_player.text
        body = resp_player.json()
        assert body["speed"] == 30
        assert body["base_speed"] == 30
        assert body["damage_resistances"] == ["Fire"]
        assert body["damage_immunities"] == ["Cold"]
        assert body["damage_vulnerabilities"] == ["Thunder"]

        # 3. GET /campaigns/{name}/party hydrates derived immunities on legacy docs
        mock_db["characters"]._coll.insert_one(
            _base_char(
                EDITION_2014,
                char_id="legacy-monk-party",
                owner_id="user-1",
                active_campaign="Frostfell",
                char_class="Monk",
                char_level=10,
                classes=[{"class_name": "Monk", "level": 10}],
                speed=0,
                base_speed=None,
                conditions=["Grappled"],
            )
        )
        app.dependency_overrides[get_current_user] = lambda: {"id": "dm-1", "username": "dm"}
        party_res = client.get("/api/v1/campaigns/Frostfell/party")
        assert party_res.status_code == 200
        legacy_row = next(r for r in party_res.json() if r["char_id"] == "legacy-monk-party")
        assert "Poison" in legacy_row["damage_immunities"]
        assert legacy_row["speed"] == 0
        assert legacy_row["base_speed"] == 30
    finally:
        app.dependency_overrides = orig
        limiter.reset()
