"""Regression suite for consolidated board tickets (#201, #202, #221, #232-#234, #236-#238)."""

from unittest.mock import AsyncMock, patch

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.core.schemas import (
    LevelUpAnalysisSchema,
    LevelUpChoice,
    VTTGridSchema,
    VTTStateSchema,
    VTTTokenSchema,
)
from backend.services.rules_service import parse_character_from_text
from backend.services.stats_service import (
    calculate_max_spell_slots,
    calculate_weapon_stats,
    sync_character_stats,
)
from backend.services.vtt_service import VTTService
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter
from server.routers.campaign_router import (
    CampaignSchema,
    _compute_health_status,
    _redact_encounter_for_player,
    _sheet_modifier,
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

    async def find_one_and_update(self, *args, **kwargs):
        return self._col.find_one_and_update(*args, **kwargs)

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
        "hp_max": 30,
        "hp_current": 30,
        "stats": {"STR": 10, "DEX": 14, "CON": 14, "INT": 18, "WIS": 12, "CHA": 10},
        "skill_proficiencies": ["Arcana"],
        "weapons": [
            {"name": "Dagger", "damage": "1d4 piercing"},
            {
                "name": "Custom Wand-Blade",
                "damage": "1d6 piercing",
                "attack_bonus": "+7",
                "is_custom": True,
            },
        ],
        "exhaustion_level": 0,
    }
    fresh = sync_character_stats(base_char)
    exh_2 = sync_character_stats({**base_char, "exhaustion_level": 2})

    # Per both 2014 & 2024 rules, exhaustion never penalizes caster's spell save DC
    assert exh_2["spell_save_dc"] == fresh["spell_save_dc"]

    fresh_spell_atk = int(str(fresh["spell_attack_bonus"]).replace("+", ""))
    exh2_spell_atk = int(str(exh_2["spell_attack_bonus"]).replace("+", ""))
    fresh_wpn_atk = int(str(fresh["weapons"][0]["attack_bonus"]).replace("+", ""))
    exh2_wpn_atk = int(str(exh_2["weapons"][0]["attack_bonus"]).replace("+", ""))

    if edition == EDITION_2024:
        assert exh_2["speed"] == fresh["speed"] - 10
        assert exh_2["skills"]["Arcana"] == fresh["skills"]["Arcana"] - 4
        assert exh_2["saving_throw_values"]["INT"] == fresh["saving_throw_values"]["INT"] - 4
        assert exh_2["initiative_modifier"] == fresh["initiative_modifier"] - 4
        assert exh2_spell_atk == fresh_spell_atk - 4
        assert exh2_wpn_atk == fresh_wpn_atk - 4

        # Custom weapons must apply -4 exactly once across repeated saves (no compound decay)
        custom_after_1 = sync_character_stats({**base_char, "exhaustion_level": 2})
        custom_after_2 = sync_character_stats(custom_after_1)
        custom_after_3 = sync_character_stats(custom_after_2)
        assert custom_after_1["weapons"][1]["attack_bonus"] == "+3"
        assert custom_after_2["weapons"][1]["attack_bonus"] == "+3"
        assert custom_after_3["weapons"][1]["attack_bonus"] == "+3"
        # Clearing exhaustion restores the custom weapon attack bonus to +7
        restored = sync_character_stats({**custom_after_3, "exhaustion_level": 0})
        assert restored["weapons"][1]["attack_bonus"] == "+7"

        exh_6 = sync_character_stats({**base_char, "exhaustion_level": 6})
        assert exh_6["speed"] == 0
    else:
        # 2014 PHB exhaustion: speed halved at L2, speed 0 at L5, HP max halved at L4, no -2/lvl D20 penalty
        assert exh_2["speed"] == fresh["speed"] // 2
        assert exh_2["skills"]["Arcana"] == fresh["skills"]["Arcana"]
        assert exh_2["saving_throw_values"]["INT"] == fresh["saving_throw_values"]["INT"]
        assert exh_2["initiative_modifier"] == fresh["initiative_modifier"]
        assert exh2_spell_atk == fresh_spell_atk
        assert exh2_wpn_atk == fresh_wpn_atk

        exh_4 = sync_character_stats({**base_char, "exhaustion_level": 4})
        assert exh_4["hp_max"] == 15
        assert exh_4["base_hp_max"] == 30
        exh_4_repeat = sync_character_stats(exh_4)
        assert exh_4_repeat["hp_max"] == 15
        restored_hp = sync_character_stats({**exh_4_repeat, "exhaustion_level": 3})
        assert restored_hp["hp_max"] == 30

        exh_5 = sync_character_stats({**base_char, "exhaustion_level": 5})
        assert exh_5["speed"] == 0


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
    raw_db["characters"].insert_many(
        [
            {
                "char_id": "hero_1",
                "char_name": "Elesh",
                "char_class": "Cleric",
                "char_level": 5,
                "dnd_edition": EDITION_2014,
                "active_campaign": campaign,
                "hp_current": 11,
                "hp_max": 22,
                "base_hp_max": 45,
                "hp_temp": 6,
                "hit_dice_used": 4,
                "concentrating_on": "Bless",
                "death_saves": {"successes": 2, "failures": 1},
                "exhaustion_level": 4,
                "spell_slots": {"level_1": {"max": 4, "used": 3}},
                "class_resources": [{"name": "Channel Divinity", "max": 2, "current": 0}],
                "version": 4,
            },
            {
                "char_id": "hero_2",
                "char_name": "Vael",
                "char_class": "Warlock",
                "char_level": 5,
                "dnd_edition": EDITION_2024,
                "active_campaign": campaign,
                "base_speed": 30,
                "speed": 20,
                "stats": {"STR": 10, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 18},
                "base_stats": {"STR": 10, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 18},
                "hp_current": 10,
                "hp_max": 40,
                "hp_temp": 0,
                "hit_dice_used": 4,
                "concentrating_on": None,
                "death_saves": {"successes": 0, "failures": 0},
                "exhaustion_level": 2,
                "spell_slots": {
                    "pact": {"max": 2, "used": 2, "level": 3},
                    "level_1": {"max": 4, "used": 1},
                },
                "version": 2,
            },
        ]
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

        updated_2014 = raw_db["characters"].find_one({"char_id": "hero_1"})
        assert updated_2014["exhaustion_level"] == 3
        assert updated_2014["hp_max"] == 45
        assert updated_2014["hp_current"] == 45
        assert updated_2014["hp_temp"] == 0
        # 2014 PHB: recover up to half total Hit Dice (max(1, 5 // 2) = 2), so 4 -> 2
        assert updated_2014["hit_dice_used"] == 2
        assert updated_2014["concentrating_on"] is None
        assert updated_2014["death_saves"] == {"successes": 0, "failures": 0}
        assert updated_2014["spell_slots"]["level_1"]["used"] == 0
        assert updated_2014["class_resources"][0]["current"] == 2
        assert updated_2014["version"] == 5

        updated_2024 = raw_db["characters"].find_one({"char_id": "hero_2"})
        assert updated_2024["exhaustion_level"] == 1
        assert updated_2024["speed"] == 25
        # 2024 PHB: regain all spent Hit Dice on a Long Rest
        assert updated_2024["hit_dice_used"] == 0
        assert updated_2024["spell_slots"]["pact"]["used"] == 0
        assert updated_2024["spell_slots"]["level_1"]["used"] == 0
        assert updated_2024["version"] == 3

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
    assert EDITION_2024 in captured_prompts[0]


# ---------------------------------------------------------------------------
# QA Consolidation Regression Tests (VTT Redaction, Encounter, Journey, Assets, Invite Code)
# ---------------------------------------------------------------------------


def test_vtt_redact_for_player_strips_enemy_hp_and_max_hp():
    state = VTTStateSchema(
        campaign_name="Citadel",
        grid=VTTGridSchema(width=20, height=20, cell_size=50),
        tokens=[
            VTTTokenSchema(id="hero_tok", name="Elesh", x=0, y=0, hp=34, max_hp=40, is_enemy=False),
            VTTTokenSchema(
                id="goblin_tok", name="Goblin", x=50, y=50, hp=5, max_hp=7, is_enemy=True
            ),
            VTTTokenSchema(
                id="hidden_tok",
                name="Assassin",
                x=100,
                y=100,
                hp=45,
                max_hp=78,
                is_enemy=True,
                is_hidden=True,
            ),
        ],
    )
    redacted = VTTService.redact_for_player(state, player_character_name="Elesh")
    token_map = {t.id: t for t in redacted.tokens}

    assert "hidden_tok" not in token_map
    assert token_map["hero_tok"].hp == 34
    assert token_map["hero_tok"].max_hp == 40
    assert token_map["goblin_tok"].hp is None
    assert token_map["goblin_tok"].max_hp is None


def test_post_encounter_returns_danger_indicator_and_redacts_player_view(monkeypatch):
    limiter.reset()
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["test_encounter_qa_db"]
    db = _AsyncDBWrapper(raw_db)

    campaign = "Citadel"
    raw_db["campaigns"].insert_one(
        {"campaign_name": campaign, "owner_id": "dm_1", "dnd_edition": EDITION_2024}
    )
    raw_db["campaign_members"].insert_many(
        [
            {"campaign_id": campaign, "user_id": "dm_1", "role": "dm"},
            {"campaign_id": campaign, "user_id": "p_1", "role": "player"},
        ]
    )

    from server.routers import websocket_router

    monkeypatch.setattr(websocket_router.manager, "broadcast", AsyncMock())

    current_user = {"id": "dm_1", "username": "dm"}
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    try:
        client = TestClient(app)
        resp = client.post(
            f"/api/v1/campaigns/{campaign}/encounter",
            json={
                "round": 1,
                "activeCombatantId": "m1",
                "combatants": [
                    {
                        "id": "m1",
                        "name": "Hobgoblin",
                        "hp": 5,
                        "max_hp": 11,
                        "ac": 18,
                        "initiative": 12,
                        "dex": 12,
                        "is_player": False,
                        "cr": "1/2",
                    }
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "danger_indicator" in body

        dm_get = client.get(f"/api/v1/campaigns/{campaign}/encounter")
        assert dm_get.status_code == 200
        assert dm_get.json()["combatants"][0]["hp"] == 5

        current_user["id"] = "p_1"
        player_get = client.get(f"/api/v1/campaigns/{campaign}/encounter")
        assert player_get.status_code == 200
        redacted_monster = player_get.json()["combatants"][0]
        assert redacted_monster["hp"] is None
        assert redacted_monster["max_hp"] is None
        assert redacted_monster["ac"] is None
        assert redacted_monster["cr"] is None
        assert redacted_monster["health_status"] == "bloodied"
    finally:
        app.dependency_overrides.clear()


def test_generate_journey_filters_unrevealed_sessions_for_players():
    limiter.reset()
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["test_journey_qa_db"]
    db = _AsyncDBWrapper(raw_db)

    campaign = "Citadel"
    raw_db["campaigns"].insert_one({"campaign_name": campaign, "owner_id": "dm_1"})
    raw_db["campaign_members"].insert_many(
        [
            {"campaign_id": campaign, "user_id": "dm_1", "role": "dm"},
            {"campaign_id": campaign, "user_id": "p_1", "role": "player"},
        ]
    )
    raw_db["session_logs"].insert_many(
        [
            {
                "campaign_name": campaign,
                "session_number": 1,
                "title": "Public Tavern",
                "summary": "Met the guild.",
                "is_revealed": True,
            },
            {
                "campaign_name": campaign,
                "session_number": 2,
                "title": "Secret Lair",
                "summary": "DM spoiler plot.",
                "is_revealed": False,
            },
        ]
    )

    seen_counts = []

    def _fake_journey(sessions):
        seen_counts.append([s["title"] for s in sessions])
        return {"nodes": [{"label": s["title"]} for s in sessions]}

    current_user = {"id": "p_1", "username": "player"}
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    try:
        client = TestClient(app)
        with patch(
            "server.routers.session_router.session_service.generate_journey_graph",
            side_effect=_fake_journey,
        ):
            player_resp = client.post(f"/api/v1/campaigns/{campaign}/sessions/journey")
            assert player_resp.status_code == 200
            assert seen_counts[-1] == ["Public Tavern"]

            current_user["id"] = "dm_1"
            dm_resp = client.post(f"/api/v1/campaigns/{campaign}/sessions/journey")
            assert dm_resp.status_code == 200
            assert seen_counts[-1] == ["Public Tavern", "Secret Lair"]
    finally:
        app.dependency_overrides.clear()


def test_assets_upload_and_list_url_encode_campaign_name(tmp_path, monkeypatch):
    limiter.reset()
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["test_assets_qa_db"]
    db = _AsyncDBWrapper(raw_db)

    campaign = "Dark Citadel"
    raw_db["campaigns"].insert_one({"campaign_name": campaign, "owner_id": "dm_1"})
    raw_db["campaign_members"].insert_one(
        {"campaign_id": campaign, "user_id": "dm_1", "role": "dm"}
    )

    from server.routers import assets_router

    monkeypatch.setattr(assets_router, "ASSETS_DIR", str(tmp_path))

    current_user = {"id": "dm_1", "username": "dm"}
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    try:
        client = TestClient(app)
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        up_resp = client.post(
            "/api/v1/campaigns/Dark%20Citadel/assets",
            files={"file": ("battlemap.png", png_bytes, "image/png")},
            data={"kind": "map"},
        )
        assert up_resp.status_code == 200
        uploaded = up_resp.json()
        assert uploaded["url"].startswith("/api/v1/campaigns/Dark%20Citadel/assets/")

        list_resp = client.get("/api/v1/campaigns/Dark%20Citadel/assets?kind=map")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) == 1
        assert items[0]["url"] == uploaded["url"]
    finally:
        app.dependency_overrides.clear()


def test_join_campaign_preserves_mixed_case_invite_codes():
    limiter.reset()
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["test_join_qa_db"]
    db = _AsyncDBWrapper(raw_db)

    campaign = "Citadel"
    raw_db["campaigns"].insert_one(
        {
            "campaign_name": campaign,
            "owner_id": "dm_1",
            "invite_code": "AbC9xYz_1234qRsT",
        }
    )
    raw_db["characters"].insert_many(
        [
            {"char_id": "char_p1", "char_name": "Kael", "owner_id": "p_1"},
            {"char_id": "char_p2", "char_name": "Lyra", "owner_id": "p_2"},
        ]
    )

    current_user = {"id": "p_1", "username": "player1"}
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    try:
        client = TestClient(app)
        resp_exact = client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": "AbC9xYz_1234qRsT", "character_id": "char_p1"},
        )
        assert resp_exact.status_code == 200
        assert resp_exact.json()["campaign_name"] == campaign

        current_user["id"] = "p_2"
        current_user["username"] = "player2"
        resp_ci = client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": "abc9xyz_1234qrst", "character_id": "char_p2"},
        )
        assert resp_ci.status_code == 200
        assert resp_ci.json()["campaign_name"] == campaign

        resp_bad = client.post(
            "/api/v1/campaigns/join",
            json={"invite_code": "WrongCode", "character_id": "char_p2"},
        )
        assert resp_bad.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_remove_homonym_character_does_not_disconnect_other_players_socket(monkeypatch):
    limiter.reset()
    mock_client = mongomock.MongoClient()
    raw_db = mock_client["test_homonym_disconnect_db"]
    db = _AsyncDBWrapper(raw_db)

    campaign = "Citadel"
    raw_db["campaigns"].insert_one(
        {
            "campaign_name": campaign,
            "owner_id": "dm_1",
            "party": ["kael_c1.json", "lyra_c1b.json", "kael_c2.json"],
        }
    )
    raw_db["campaign_members"].insert_many(
        [
            {"campaign_id": campaign, "user_id": "dm_1", "role": "dm"},
            {
                "campaign_id": campaign,
                "user_id": "p_1",
                "role": "player",
                "character_id": "c1",
                "character_ids": ["c1", "c1b"],
            },
            {
                "campaign_id": campaign,
                "user_id": "p_2",
                "role": "player",
                "character_id": "c2",
                "character_ids": ["c2"],
            },
        ]
    )
    raw_db["characters"].insert_many(
        [
            {
                "char_id": "c1",
                "char_name": "Kael",
                "owner_id": "p_1",
                "active_campaign": campaign,
            },
            {
                "char_id": "c1b",
                "char_name": "Lyra",
                "owner_id": "p_1",
                "active_campaign": campaign,
            },
            {
                "char_id": "c2",
                "char_name": "Kael",
                "owner_id": "p_2",
                "active_campaign": campaign,
            },
        ]
    )

    from server.routers import websocket_router
    from server.routers.websocket_router import CampaignConnection

    class _DummyWS:
        def __init__(self):
            self.close = AsyncMock()
            self.send_json = AsyncMock()

    ws_p1_kael = _DummyWS()
    ws_p2_kael = _DummyWS()

    orig_active = websocket_router.manager.active_connections
    websocket_router.manager.active_connections = {
        campaign: [
            CampaignConnection(
                websocket=ws_p1_kael, role="player", character="Kael", user_id="p_1"
            ),
            CampaignConnection(
                websocket=ws_p2_kael, role="player", character="Kael", user_id="p_2"
            ),
        ]
    }
    monkeypatch.setattr(websocket_router.manager, "broadcast", AsyncMock())

    current_user = {"id": "dm_1", "username": "dm"}
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current_user
    try:
        client = TestClient(app)
        resp = client.delete(f"/api/v1/campaigns/{campaign}/party/c1")
        assert resp.status_code == 200

        ws_p1_kael.close.assert_awaited_once()
        ws_p2_kael.close.assert_not_awaited()
        remaining_uids = [
            c.user_id for c in websocket_router.manager.active_connections.get(campaign, [])
        ]
        assert remaining_uids == ["p_2"]
    finally:
        websocket_router.manager.active_connections = orig_active
        app.dependency_overrides.clear()


def test_sheet_modifier_ability_check_fallback_applies_2024_exhaustion():
    stats = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
    c_2024 = {
        "dnd_edition": EDITION_2024,
        "exhaustion_level": 2,
        "proficiency_bonus": 2,
        "stats": stats,
    }
    c_2014 = {
        "dnd_edition": EDITION_2014,
        "exhaustion_level": 2,
        "proficiency_bonus": 2,
        "stats": stats,
    }

    assert _sheet_modifier(c_2024, "ability_check", "Luck") == -4
    assert _sheet_modifier(c_2014, "ability_check", "Luck") == 0
