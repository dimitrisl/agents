"""Regression suite for consolidated board tickets (#201, #202, #221, #232-#234, #236-#238)."""

from unittest.mock import AsyncMock, patch

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.core.schemas import LevelUpAnalysisSchema, LevelUpChoice
from backend.services.rules_service import parse_character_from_text
from backend.services.stats_service import (
    calculate_max_spell_slots,
    calculate_weapon_stats,
    sync_character_stats,
)
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter
from server.routers.campaign_router import (
    CampaignSchema,
    _compute_health_status,
    _redact_encounter_for_player,
)


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
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _AsyncColWrapper:
    def __init__(self, col):
        self._col = col

    async def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._col.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._col.delete_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._col.count_documents(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursorWrapper(self._col.find(*args, **kwargs))


class _AsyncDBWrapper:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name):
        return _AsyncColWrapper(self._db[name])

    def __getattr__(self, name):
        return _AsyncColWrapper(getattr(self._db, name))


# ---------------------------------------------------------------------------
# #201: Encounter Monster Redaction & Health Status
# ---------------------------------------------------------------------------


def test_encounter_redaction_strips_monster_secrets_and_preserves_health_status():
    assert _compute_health_status(50, 80) == "healthy"
    assert _compute_health_status(40, 80) == "bloodied"
    assert _compute_health_status(0, 80) == "down"

    enc = {
        "round": 2,
        "activeCombatantId": "m_1",
        "combatants": [
            {
                "id": "p_1",
                "name": "Elara",
                "is_player": True,
                "hp": 32,
                "max_hp": 40,
                "ac": 18,
            },
            {
                "id": "m_1",
                "name": "Beholder",
                "is_player": False,
                "hp": 45,
                "max_hp": 100,
                "ac": 18,
                "cr": "13",
                "xp": 10000,
                "statblock": "Secret statblock",
                "stats": {"STR": 10},
                "traits": [{"name": "Antimagic Cone"}],
                "actions": [{"name": "Bite"}],
                "legendary_actions": [{"name": "Eye Ray"}],
            },
        ],
    }

    redacted = _redact_encounter_for_player(enc)
    hero, monster = redacted["combatants"]

    assert hero["hp"] == 32
    assert hero["ac"] == 18
    assert hero["health_status"] == "healthy"

    assert monster["health_status"] == "bloodied"
    for secret_key in (
        "hp",
        "max_hp",
        "ac",
        "cr",
        "xp",
        "statblock",
        "stats",
        "traits",
        "actions",
        "legendary_actions",
    ):
        assert monster[secret_key] is None


# ---------------------------------------------------------------------------
# #202: Exhaustion Mechanics & Party Long Rest
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_exhaustion_penalties_affect_skills_saves_attacks_dc_and_speed(edition):
    base_char = {
        "char_name": "Kaelen",
        "char_class": "Wizard",
        "char_level": 5,
        "dnd_edition": edition,
        "base_speed": 30,
        "stats": {"STR": 10, "DEX": 14, "CON": 14, "INT": 18, "WIS": 12, "CHA": 10},
        "skill_proficiencies": ["Arcana"],
        "weapons": [{"name": "Dagger", "damage": "1d4 piercing"}],
        "exhaustion_level": 0,
    }
    fresh = sync_character_stats(base_char)
    exh_2 = sync_character_stats({**base_char, "exhaustion_level": 2})
    exh_6 = sync_character_stats({**base_char, "exhaustion_level": 6})

    assert exh_2["speed"] == fresh["speed"] - 10
    assert exh_2["skills"]["Arcana"] == fresh["skills"]["Arcana"] - 4
    assert exh_2["saving_throw_values"]["INT"] == fresh["saving_throw_values"]["INT"] - 4
    assert exh_2["spell_save_dc"] == fresh["spell_save_dc"] - 4

    fresh_spell_atk = int(str(fresh["spell_attack_bonus"]).replace("+", ""))
    exh2_spell_atk = int(str(exh_2["spell_attack_bonus"]).replace("+", ""))
    assert exh2_spell_atk == fresh_spell_atk - 4

    fresh_wpn_atk = int(str(fresh["weapons"][0]["attack_bonus"]).replace("+", ""))
    exh2_wpn_atk = int(str(exh_2["weapons"][0]["attack_bonus"]).replace("+", ""))
    assert exh2_wpn_atk == fresh_wpn_atk - 4

    assert exh_6["speed"] == 0


def test_party_long_rest_restores_party_and_reduces_exhaustion(monkeypatch):
    limiter.reset()
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["test_long_rest_db"]
    db = _AsyncDBWrapper(raw_db)

    campaign = "Citadel"
    raw_db["campaigns"].insert_one({"campaign_name": campaign, "owner_id": "dm_1"})
    raw_db["campaign_members"].insert_many(
        [
            {"campaign_id": campaign, "user_id": "dm_1", "role": "dm"},
            {"campaign_id": campaign, "user_id": "p_1", "role": "player"},
        ]
    )
    raw_db["characters"].insert_one(
        {
            "char_id": "hero_1",
            "char_name": "Elesh",
            "active_campaign": campaign,
            "hp_current": 11,
            "hp_max": 45,
            "hp_temp": 6,
            "hit_dice_used": 3,
            "concentrating_on": "Bless",
            "death_saves": {"successes": 2, "failures": 1},
            "exhaustion_level": 3,
            "spell_slots": {"level_1": {"max": 4, "used": 3}},
            "version": 4,
        }
    )

    broadcasts = []
    from server.routers import websocket_router

    monkeypatch.setattr(
        websocket_router.manager,
        "broadcast",
        AsyncMock(side_effect=lambda *a, **kw: broadcasts.append(a)),
    )

    current_user = {"id": "dm_1", "username": "dm"}
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    try:
        client = TestClient(app)

        resp = client.post(f"/api/v1/campaigns/{campaign}/party/long-rest")
        assert resp.status_code == 200

        updated = raw_db["characters"].find_one({"char_id": "hero_1"})
        assert updated["hp_current"] == 45
        assert updated["hp_temp"] == 0
        assert updated["hit_dice_used"] == 0
        assert updated["concentrating_on"] is None
        assert updated["death_saves"] == {"successes": 0, "failures": 0}
        assert updated["exhaustion_level"] == 2
        assert updated["spell_slots"]["level_1"]["used"] == 0
        assert updated["version"] == 5
        assert broadcasts[0][1]["payload"]["action"] == "long_rest"

        # Player cannot invoke DM Long Rest
        current_user["id"] = "p_1"
        resp_forbidden = client.post(f"/api/v1/campaigns/{campaign}/party/long-rest")
        assert resp_forbidden.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# #221: Omitted HP Derivation on Character Creation (2014 & 2024)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "edition,char_class",
    [
        (EDITION_2014, "Barbarian"),
        (EDITION_2024, "Fighter"),
    ],
)
def test_create_character_derives_hp_when_omitted(edition, char_class):
    limiter.reset()
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["test_hp_create_db"]
    db = _AsyncDBWrapper(raw_db)

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_1", "username": "hero"}
    try:
        client = TestClient(app)
        payload = {
            "char_name": "Durgan",
            "char_class": char_class,
            "race": "Human",
            "background": "Soldier",
            "char_level": 5,
            "dnd_edition": edition,
            "stats": {"STR": 16, "DEX": 12, "CON": 16, "INT": 8, "WIS": 10, "CHA": 10},
        }
        resp = client.post("/api/v1/characters", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["hp_max"] > 10
        assert data["hp_current"] == data["hp_max"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# #232 / #233 / #234: Security, Validation, Invite Rotate, Report Dedupe
# ---------------------------------------------------------------------------


def test_campaign_name_validation_and_membership_guards_and_reports():
    for bad_name in ("Test/Camp", "Bad\\Name", "Percent%1"):
        with pytest.raises(ValueError):
            CampaignSchema(campaign_name=bad_name)

    limiter.reset()
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["test_security_db"]
    db = _AsyncDBWrapper(raw_db)

    campaign = "SafeKeep"
    raw_db["campaigns"].insert_one(
        {"campaign_name": campaign, "owner_id": "dm_1", "invite_code": "OLD_CODE"}
    )
    raw_db["campaign_members"].insert_many(
        [
            {"campaign_id": campaign, "user_id": "dm_1", "role": "dm"},
            {"campaign_id": campaign, "user_id": "p_1", "role": "player"},
        ]
    )
    raw_db["campaign_whispers"].insert_one(
        {
            "campaign_name": campaign,
            "id": "w_1",
            "sender": "dm",
            "sender_user_id": "dm_1",
            "recipient": "All",
            "message": "Watch out",
        }
    )

    current_user = {"id": "outsider", "username": "outsider"}
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    try:
        client = TestClient(app)

        # #233: Non-member cannot attach character to campaign via active_campaign
        char_resp = client.post(
            "/api/v1/characters",
            json={
                "char_name": "Intruder",
                "char_class": "Fighter",
                "race": "Human",
                "background": "Criminal",
                "char_level": 1,
                "stats": {"STR": 14, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 10},
                "active_campaign": campaign,
            },
        )
        assert char_resp.status_code == 201
        assert char_resp.json()["active_campaign"] is None

        # #234: DM can rotate invite code, player cannot
        current_user["id"] = "p_1"
        assert client.post(f"/api/v1/campaigns/{campaign}/invite-code/rotate").status_code == 403
        current_user["id"] = "dm_1"
        rot = client.post(f"/api/v1/campaigns/{campaign}/invite-code/rotate")
        assert rot.status_code == 200
        assert rot.json()["invite_code"] != "OLD_CODE"

        # #234: Whisper report deduplicates open reports per user
        current_user["id"] = "p_1"
        r1 = client.post(
            f"/api/v1/campaigns/{campaign}/whispers/w_1/report",
            json={"reason": "Spam"},
        )
        r2 = client.post(
            f"/api/v1/campaigns/{campaign}/whispers/w_1/report",
            json={"reason": "Spam again"},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert "already reported" in r2.json()["message"].lower()
        assert raw_db["whisper_reports"].count_documents({"whisper_id": "w_1"}) == 1
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# #236: Epic Boon ASI Cap 30 in 2024 vs 20 in 2014
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "edition,expected_str",
    [
        (EDITION_2024, 22),
        (EDITION_2014, 20),
    ],
)
def test_level_19_epic_boon_stat_cap_by_edition(edition, expected_str):
    limiter.reset()
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["test_epic_boon_db"]
    db = _AsyncDBWrapper(raw_db)

    raw_db["characters"].insert_one(
        {
            "char_id": "epic_1",
            "owner_id": "u_1",
            "char_name": "Aurelia",
            "char_class": "Fighter",
            "race": "Human",
            "background": "Soldier",
            "char_level": 18,
            "classes": [{"class_name": "Fighter", "level": 18, "subclass": "Champion"}],
            "dnd_edition": edition,
            "stats": {"STR": 20, "DEX": 14, "CON": 16, "INT": 10, "WIS": 12, "CHA": 10},
            "base_stats": {"STR": 20, "DEX": 14, "CON": 16, "INT": 10, "WIS": 12, "CHA": 10},
            "hp_max": 180,
            "hp_current": 180,
            "version": 1,
        }
    )

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_1", "username": "player"}
    try:
        client = TestClient(app)
        analysis = LevelUpAnalysisSchema(
            hp_increase=10,
            new_total_hp=190,
            choices_required=[
                LevelUpChoice(type="feat", label="Choose a Feat or ASI", options=["+2 to one Stat"])
            ],
        ).model_dump()
        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": "epic_1",
                "analysis": analysis,
                "user_choices": {"feat_0": "+2 to one Stat", "feat_stat1_0": "STR"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["stats"]["STR"] == expected_str
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# #237: Armor Classification, Weapon Rules, Multiclass Caster Clamp
# ---------------------------------------------------------------------------


def test_armor_classification_weapon_modifiers_and_multiclass_clamp():
    for armor_name in ("Half Plate", "Breastplate"):
        synced = sync_character_stats(
            {
                "char_name": "Vanguard",
                "char_class": "Cleric",
                "char_level": 3,
                "dnd_edition": EDITION_2014,
                "stats": {"STR": 10, "DEX": 14, "CON": 12, "INT": 10, "WIS": 16, "CHA": 10},
                "equipment": [{"name": armor_name, "equipped": True}],
            }
        )
        # 15 + 2 DEX (Half Plate) or 14 + 2 DEX (Breastplate) -> clearly above unarmored 12
        assert synced["armor_class"] >= 16

    stats = {"STR": 16, "DEX": 8, "CON": 12, "INT": 10, "WIS": 10, "CHA": 10}
    features = [{"name": "Fighting Style: Archery"}, {"name": "Fighting Style: Dueling"}]

    # Explicit ability_modifier=DEX, negative DEX mod, Archery +2 to ranged, NO Dueling bonus on ranged
    longbow = calculate_weapon_stats(
        {"name": "Longbow", "ability_modifier": "DEX", "damage_dice": "1d8 piercing"},
        stats,
        proficiency_bonus=2,
        features_traits=features,
    )
    assert longbow["attack_bonus"] == "+3"  # -1 DEX + 2 prof + 2 Archery
    assert longbow["damage"] == "1d8 - 1 piercing"

    # Melee 1H gets Dueling +2 damage, NO Archery +2 attack
    longsword = calculate_weapon_stats(
        {"name": "Longsword", "damage_dice": "1d8 slashing"},
        stats,
        proficiency_bonus=2,
        features_traits=features,
    )
    assert longsword["attack_bonus"] == "+5"  # +3 STR + 2 prof
    assert longsword["damage"] == "1d8 + 5 slashing"  # +3 STR + 2 Dueling

    # Multiclass total caster level > 20 clamps at level 20 full-caster progression
    over_slots = calculate_max_spell_slots(
        "Wizard",
        level=25,
        classes=[
            {"class_name": "Wizard", "level": 15, "caster_type": "full"},
            {"class_name": "Cleric", "level": 10, "caster_type": "full"},
        ],
        edition=EDITION_2024,
    )
    lvl20_slots = calculate_max_spell_slots("Wizard", level=20, edition=EDITION_2024)
    assert over_slots == lvl20_slots
    assert over_slots["level_9"] == 1


# ---------------------------------------------------------------------------
# #238: PDF Import 2024 Auto-Detection
# ---------------------------------------------------------------------------


def test_pdf_import_detects_2024_edition_markers():
    captured_prompts = []

    def _fake_ai(prompt: str):
        captured_prompts.append(prompt)
        if len(captured_prompts) == 1:
            return {"char_name": "Mastery Hero", "char_class": "Fighter", "char_level": 1}
        return {"weapons": [], "equipment": [], "spells": {}}

    with patch("backend.services.rules_service.generate_ai_json", side_effect=_fake_ai):
        result = parse_character_from_text(
            "Level 1 Fighter with Weapon Mastery (Sap) and Origin Feat: Tough",
            edition=EDITION_2014,
        )

    assert result is not None
    assert "2024 Edition" in captured_prompts[0]
