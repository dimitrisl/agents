import copy
import io
import json
from unittest.mock import MagicMock, patch

import mongomock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.core.providers.gemini_provider import GeminiProvider
from backend.core.schemas import CharacterSchema
from backend.repositories.rules_repository import RulesRepository
from backend.services.character_import_service import CharacterImportService
from backend.services.stats_service import calculate_ac, sync_character_stats
from backend.services.vtt_service import VTTService
from scripts.cleanup_fake_users import _build_fake_user_query
from server.config import Settings
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import get_real_ip, limiter


class _AsyncColl:
    def __init__(self, coll):
        self._coll = coll

    async def find_one(self, query=None, *args, **kwargs):
        return self._coll.find_one(query or {}, *args, **kwargs)

    async def insert_one(self, doc):
        return self._coll.insert_one(doc)

    async def update_one(self, query, update, upsert=False):
        class Res:
            def __init__(self, r):
                self.matched_count = r.matched_count
                self.modified_count = r.modified_count

        return Res(self._coll.update_one(query, update, upsert=upsert))

    async def update_many(self, query, update, *args, **kwargs):
        return self._coll.update_many(query, update, *args, **kwargs)

    async def delete_one(self, query, *args, **kwargs):
        return self._coll.delete_one(query, *args, **kwargs)

    async def delete_many(self, query, *args, **kwargs):
        return self._coll.delete_many(query, *args, **kwargs)

    async def count_documents(self, query=None):
        return self._coll.count_documents(query or {})

    async def distinct(self, field, *args, **kwargs):
        return self._coll.distinct(field, *args, **kwargs)

    def find(self, query=None, *args, **kwargs):
        cursor = self._coll.find(query or {}, *args, **kwargs)

        class _AsyncCursor:
            def __init__(self, c):
                self._items = list(c)
                self._idx = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx < len(self._items):
                    item = self._items[self._idx]
                    self._idx += 1
                    return item
                raise StopAsyncIteration

            async def to_list(self, length=None):
                return list(self._items)

        return _AsyncCursor(cursor)


class _AsyncDB:
    def __init__(self, name="review_fixes_db"):
        self._client = mongomock.MongoClient()
        self._db = self._client[name]
        self._colls = {}

    def __getitem__(self, item):
        if item not in self._colls:
            self._colls[item] = _AsyncColl(self._db[item])
        return self._colls[item]

    def __getattr__(self, item):
        return self[item]


def test_settings_rejects_placeholder_and_ephemeral_secrets_in_non_debug():
    with pytest.raises(RuntimeError, match="insecure placeholder"):
        Settings(
            DEBUG_MODE=False,
            JWT_SECRET_KEY="replace_with_a_secure_random_hex_string_in_production",
            _env_file=None,
        )

    ephemeral_settings = Settings(DEBUG_MODE=False, JWT_SECRET_KEY=None, _env_file=None)
    assert ephemeral_settings.is_ephemeral_secret is True
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be explicitly configured"):
        ephemeral_settings.validate_production_secrets()

    prod_settings = Settings(
        DEBUG_MODE=False,
        JWT_SECRET_KEY="a" * 64,
        _env_file=None,
    )
    assert prod_settings.is_ephemeral_secret is False
    prod_settings.validate_production_secrets()


def test_rate_limiter_uses_rightmost_untrusted_forwarded_ip():
    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.headers = {"x-forwarded-for": "10.0.0.5, 198.51.100.88, 127.0.0.1"}
    assert get_real_ip(req) == "198.51.100.88"


def test_vtt_fog_rect_dos_rejected_before_allocation():
    vtt = VTTService()
    with pytest.raises(ValueError, match="exceeds maximum limit"):
        vtt._extract_valid_cell_indices(
            {"rect": {"x": 0, "y": 0, "w": 100000, "h": 100000}},
            width=30,
            height=30,
        )


def test_2014_vs_2024_draconic_ac_multiclass_hp_and_masteries():
    # 2024 Draconic Resilience: 10 + DEX (+2) + CHA (+0) = 12 (no 13 floor)
    ac_2024 = calculate_ac(
        dex_score=14,
        equipment=[],
        features=[{"name": "Draconic Resilience"}],
        cha_score=10,
        edition=EDITION_2024,
    )
    assert ac_2024 == 12

    # 2014 Draconic Resilience: 13 + DEX (+2) = 15 regardless of CHA 10
    ac_2014 = calculate_ac(
        dex_score=14,
        equipment=[],
        features=[{"name": "Draconic Resilience"}],
        cha_score=10,
        edition=EDITION_2014,
    )
    assert ac_2014 == 15

    # Multiclass Fighter 5 / Draconic Sorcerer 3 (total level 8) -> only +3 Draconic HP
    for ed in (EDITION_2014, EDITION_2024):
        mc = {
            "char_name": "Kael",
            "char_class": "Fighter",
            "char_level": 8,
            "classes": [
                {"class_name": "Fighter", "level": 5, "subclass": "Champion"},
                {"class_name": "Sorcerer", "level": 3, "subclass": "Draconic Sorcery"},
            ],
            "race": "Human",
            "background": "Soldier" if ed == EDITION_2014 else "Wayfarer",
            "dnd_edition": ed,
            "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 14},
            "base_stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 10, "CHA": 14},
            "features_traits": [{"name": "Draconic Resilience", "description": "+1 HP/Sorc level"}],
        }
        synced = sync_character_stats(mc)
        assert synced["feat_hp_bonus"] == 3
        if "2024" in ed:
            # Fighter 5 (4 masteries) + Paladin/Ranger/Rogue etc. (test Fighter 5 here = 4)
            assert len(synced["weapon_masteries"]) == 4

    # 2024 Multiclass Fighter 2 (3 masteries) + Paladin 2 (2 masteries) = 5 masteries
    fp_2024 = sync_character_stats(
        {
            "char_name": "Gideon",
            "char_class": "Fighter",
            "char_level": 4,
            "classes": [
                {"class_name": "Fighter", "level": 2},
                {"class_name": "Paladin", "level": 2},
            ],
            "race": "Human",
            "background": "Wayfarer",
            "dnd_edition": EDITION_2024,
            "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 14},
            "weapons": [{"name": "Longsword"}],
        }
    )
    assert len(fp_2024["weapon_masteries"]) == 5


def test_schema_preserves_multiclass_char_class_string():
    char = CharacterSchema(
        char_name="Multiclass Hero",
        char_class="Fighter 5 / Wizard 3",
        char_level=8,
        race="Human",
        background="Sage",
        stats={"STR": 16, "DEX": 12, "CON": 14, "INT": 16, "WIS": 10, "CHA": 8},
    )
    assert char.char_class == "Fighter 5 / Wizard 3"
    assert char.subclass is None


def test_ddb_import_separates_half_proficiency_and_preserves_hp_temp():
    ddb_payload = {
        "name": "Bardi",
        "race": {"fullName": "Half-Elf"},
        "classes": [{"level": 5, "definition": {"name": "Bard", "hitDice": 8}}],
        "stats": [{"id": i, "value": 12} for i in range(1, 7)],
        "modifiers": {
            "class": [
                {"type": "half-proficiency", "subType": "athletics"},
                {"type": "expertise", "subType": "persuasion"},
            ]
        },
        "baseHitPoints": 30,
        "temporaryHitPoints": 9,
    }
    parsed, _ = CharacterImportService.parse_dndbeyond_character(ddb_payload)
    assert "Persuasion" in parsed["skill_expertise"]
    assert "Athletics" not in parsed["skill_expertise"]
    assert parsed["hp_temp"] == 9
    assert "temp_hp" not in parsed


def test_rules_repository_returns_copy_preventing_cache_mutation():
    repo = RulesRepository()
    weapons_1 = repo.get_all_weapons()
    assert len(weapons_1) > 0
    orig_name = weapons_1[0]["name"]
    weapons_1[0]["name"] = "TAMPERED_WEAPON"
    weapons_2 = repo.get_all_weapons()
    assert weapons_2[0]["name"] == orig_name


def test_cleanup_fake_users_query_never_targets_normal_users_by_default():
    q = _build_fake_user_query(include_unknown=False)
    assert "$and" in q
    assert {"username": {"$nin": list(q["$and"][0]["username"]["$nin"])}}


def test_forge_apply_level_up_ignores_client_auto_features_and_unknown_spells():
    db = _AsyncDB("forge_apply_sec")
    db._db["characters"].insert_one(
        {
            "char_id": "sec_wiz_2",
            "owner_id": "u1",
            "char_name": "Elara",
            "char_class": "Wizard",
            "char_level": 2,
            "classes": [{"class_name": "Wizard", "level": 2, "subclass": None}],
            "race": "Human",
            "background": "Sage",
            "dnd_edition": EDITION_2024,
            "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 16, "WIS": 12, "CHA": 10},
            "base_stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 16, "WIS": 12, "CHA": 10},
            "hp_max": 16,
            "hp_current": 16,
            "version": 1,
        }
    )

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "wiz"}
    limiter.reset()
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": "sec_wiz_2",
                "analysis": {
                    "hp_increase": 6,
                    "new_total_hp": 22,
                    "automatic_changes": [
                        {"name": "God Mode Cheat Feature", "description": "Infinite HP"}
                    ],
                    "choices_required": [{"type": "spell", "label": "Learn Spell", "options": []}],
                },
                "user_choices": {
                    "level_up_class": "Wizard",
                    "subclass_0": "Evoker",
                    "spell_0": "Completely Fake Spell Name 999",
                },
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        feat_names = {f["name"] for f in body["features_traits"]}
        assert "God Mode Cheat Feature" not in feat_names
        assert "Completely Fake Spell Name 999" not in (body["spells"].get("cantrips") or [])
    finally:
        app.dependency_overrides = orig


def test_rules_spells_and_bestiary_respect_edition_filters():
    db = _AsyncDB("bestiary_rules_ed")
    db._db["official_monsters"].insert_one(
        {
            "id": "srd_test_imp_2024",
            "name": "Test Imp",
            "edition": "2024",
            "origin": "official",
            "is_public": True,
            "size": "Tiny",
            "type": "Fiend",
            "cr": "1",
            "cr_numeric": 1.0,
            "ac": 13,
            "hp": 21,
            "max_hp": 21,
            "speed": "20 ft.",
            "stats": {"str": 6, "dex": 17, "con": 13, "int": 11, "wis": 12, "cha": 14},
        }
    )
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "dm"}
    limiter.reset()
    try:
        client = TestClient(app)
        # Full edition string should match stored "2024" in official_monsters
        res_bestiary = client.get(
            "/api/v1/bestiary",
            params={"edition": EDITION_2024, "cr": "1", "search": "Test Imp"},
        )
        assert res_bestiary.status_code == 200
        assert len(res_bestiary.json()) == 1

        # 2024 Level 1 Paladin gets 1st-level spells; 2014 Level 1 Paladin gets only 0/cantrips (none)
        res_2024 = client.get(
            "/api/v1/rules/spells",
            params={"char_class": "Paladin", "char_level": 1, "edition": EDITION_2024},
        )
        assert res_2024.status_code == 200
        assert len(res_2024.json()) > 0

        res_2014 = client.get(
            "/api/v1/rules/spells",
            params={"char_class": "Paladin", "char_level": 1, "edition": EDITION_2014},
        )
        assert res_2014.status_code == 200
        assert res_2014.json() == []
    finally:
        app.dependency_overrides = orig


def test_image_magic_bytes_validation_on_portrait_and_asset_uploads(tmp_path, monkeypatch):
    from server.routers import assets_router

    db = _AsyncDB("upload_magic_db")
    db._db["characters"].insert_one(
        {
            "char_id": "char_magic",
            "owner_id": "u1",
            "char_name": "Kael",
            "version": 1,
        }
    )
    db._db["campaign_members"].insert_one(
        {"campaign_id": "MagicRealm", "user_id": "u1", "role": "dm"}
    )
    monkeypatch.setattr(assets_router, "ASSETS_DIR", str(tmp_path))

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "u1"}
    limiter.reset()
    try:
        client = TestClient(app)
        spoofed_png = io.BytesIO(b"<html><script>alert(1)</script></html>")
        p_resp = client.post(
            "/api/v1/characters/char_magic/portrait-upload",
            files={"file": ("evil.png", spoofed_png, "image/png")},
        )
        assert p_resp.status_code == 400
        assert "signature" in p_resp.json()["detail"].lower()

        a_resp = client.post(
            "/api/v1/campaigns/MagicRealm/assets",
            files={"file": ("evil.png", io.BytesIO(b"MZ_FAKE_EXE"), "image/png")},
            data={"kind": "map"},
        )
        assert a_resp.status_code == 400
        assert "signature" in a_resp.json()["detail"].lower()

        # Simulate concurrent version race during portrait upload -> 409 & cleanup NOT called
        valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        raw_chars = db._db["characters"]
        db["characters"]._coll = MagicMock(wraps=raw_chars)
        db["characters"]._coll.find_one.return_value = {
            "char_id": "char_magic",
            "owner_id": "u1",
            "char_name": "Kael",
            "version": 1,
            "char_portrait": "/api/v1/portraits/old.png",
        }
        db["characters"]._coll.update_one.return_value = MagicMock(
            matched_count=0, modified_count=0
        )
        with patch("server.routers.character_router._cleanup_character_portraits") as mock_cleanup:
            race_resp = client.post(
                "/api/v1/characters/char_magic/portrait-upload",
                files={"file": ("good.png", io.BytesIO(valid_png), "image/png")},
            )
            assert race_resp.status_code == 409
            mock_cleanup.assert_not_called()
    finally:
        app.dependency_overrides = orig


def test_gemini_provider_surfaces_429_and_503_in_generate_json():
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.api_key = "fake"
    provider.client = MagicMock()
    provider._get_model = MagicMock(return_value="gemini-2.5-flash")

    provider.client.models.generate_content.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED")
    with patch(
        "backend.core.providers.gemini_provider.get_ai_settings",
        return_value={"temperature": 0.2},
    ):
        with pytest.raises(HTTPException) as exc_info:
            provider.generate_json("test prompt")
        assert exc_info.value.status_code == 429

        provider.client.models.generate_content.side_effect = RuntimeError("503 high demand")
        with pytest.raises(HTTPException) as exc_503:
            provider.generate_json("test prompt")
        assert exc_503.value.status_code == 503


def test_character_schema_trailing_and_extra_whitespace_class():
    base_stats = {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
    for raw_cls in ("Fighter ", " Fighter  ", "Rogue  "):
        c = CharacterSchema(
            char_name="Test",
            char_class=raw_cls,
            race="Human",
            background="Soldier",
            stats=dict(base_stats),
        )
        assert c.char_class == raw_cls.strip()
        assert c.subclass is None

    c_with_sub = CharacterSchema(
        char_name="Test2",
        char_class="Fighter   Battle Master ",
        race="Human",
        background="Soldier",
        stats=dict(base_stats),
    )
    assert c_with_sub.char_class == "Fighter"
    assert c_with_sub.subclass == "Battle Master"

    c_with_lvl = CharacterSchema(
        char_name="Test3",
        char_class="Fighter  5",
        race="Human",
        background="Soldier",
        stats=dict(base_stats),
    )
    assert c_with_lvl.char_class == "Fighter  5"
    assert c_with_lvl.subclass is None


def test_deterministic_encounter_maps_cr_to_xp_across_tiers():
    from backend.services.dm_service import _build_deterministic_encounter, _monster_xp

    repo = RulesRepository()
    for edition in (EDITION_2014, EDITION_2024):
        lookup = {m["name"]: m for m in repo.get_all_monsters(edition) if "name" in m}
        for lvl in (1, 3, 8, 15):
            enc = _build_deterministic_encounter(4, lvl, "Forest", edition, "Medium")
            assert enc and enc["monsters"]
            picked = enc["monsters"][0]
            srd_entry = lookup[picked["name"]]
            unit_xp = _monster_xp(srd_entry)
            assert unit_xp >= 10
            if lvl <= 3:
                assert picked["name"] != "Aboleth"
                assert float(srd_entry.get("cr_numeric", 0)) <= 4.0


def test_forge_character_level4_feats_and_stat_choices_2014_2024():
    from backend.services.forge_service import _enforce_deterministic_forge_stats, forge_character

    mock_wiz = {
        "char_name": "Merlin",
        "char_class": "Wizard",
        "subclass": "Evoker",
        "char_level": 4,
        "race": "Human",
        "background": "Sage",
        "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 15, "WIS": 12, "CHA": 10},
        "advancements": [
            {"level": "1st", "type": "Origin Feat", "name": "Alert"},
            {"level": 4, "type": "Feat", "name": "Heavily Armored"},
        ],
    }
    with patch("backend.services.forge_service.generate_ai_json", return_value=mock_wiz):
        wiz = forge_character(
            target_level=4,
            forge_race="Human",
            forge_class="Wizard",
            forge_background="Sage",
            concept="Armored caster",
            edition=EDITION_2024,
        )
    # Heavily Armored has stat_choice_options=["STR", "CON"], so INT must NOT receive the feat +1
    # Wizard Sage (+2 INT, +1 CON from background) starting array [15 INT, 14 CON]: +2 INT -> 17, +1 CON -> 15 + 1 CON (Heavily Armored) -> 16!
    assert wiz["stats"]["INT"] == 17
    assert wiz["stats"]["CON"] == 16
    assert any("heavily armored" in str(f.get("name", "")).lower() for f in wiz["features_traits"])

    mock_ftr = {
        "char_name": "Brutus",
        "char_class": "Fighter",
        "subclass": "Champion",
        "char_level": 4,
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 15, "DEX": 13, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10},
        "advancements": [{"level": "4th", "type": "Feat", "name": "Tough"}],
    }
    for edition in (EDITION_2014, EDITION_2024):
        with patch("backend.services.forge_service.generate_ai_json", return_value=dict(mock_ftr)):
            ftr = forge_character(
                target_level=4,
                forge_race="Human",
                forge_class="Fighter",
                forge_background="Soldier",
                concept="Tank",
                edition=edition,
            )
        assert any("tough" in str(f.get("name", "")).lower() for f in ftr["features_traits"])
        assert ftr["feat_hp_bonus"] == 8  # +2/lvl * 4 = 8

    # Level 19 Epic Boon at Level 4 must be rejected, and "Ability Score Improvement" treated as +2 ASI
    repo = RulesRepository()
    test_asi = {
        "char_class": "Fighter",
        "stats": {"STR": 15, "DEX": 14, "CON": 13, "INT": 8, "WIS": 12, "CHA": 10},
        "advancements": [
            {"level": 4, "type": "Feat", "name": "Boon of Combat Prowess"},
        ],
    }
    _enforce_deterministic_forge_stats(
        test_asi,
        char_class="Fighter",
        race="Human",
        background="Soldier",
        target_level=4,
        edition=EDITION_2024,
        stats_mode="standard",
        rolled_stats=None,
        auto_feats=True,
        repo=repo,
    )
    assert test_asi["advancements"][-1]["type"] == "ASI"
    # Soldier gives +2 STR +1 CON; fallback L4 ASI adds +2 STR (17 -> 19)
    assert test_asi["stats"]["STR"] == 19

    test_named_asi = {
        "char_class": "Fighter",
        "stats": {"STR": 15, "DEX": 14, "CON": 13, "INT": 8, "WIS": 12, "CHA": 10},
        "advancements": [{"level": 4, "type": "Feat", "name": "Ability Score Improvement"}],
    }
    _enforce_deterministic_forge_stats(
        test_named_asi,
        char_class="Fighter",
        race="Human",
        background="Soldier",
        target_level=4,
        edition=EDITION_2024,
        stats_mode="standard",
        rolled_stats=None,
        auto_feats=True,
        repo=repo,
    )
    assert test_named_asi["stats"]["STR"] == 19
    assert test_named_asi["advancements"][-1]["type"] == "ASI"


def test_2024_draconic_sorcerer_level_2_to_3_with_custom_hp_and_null_version():
    from backend.services.forge_service import analyze_level_up

    # Level 2 Sorcerer (d6, CON 14 +2): L1=8, L2=6 -> hp_max=14, no subclass yet, version=None legacy doc
    char_doc = {
        "char_id": "drac_l2",
        "owner_id": "u1",
        "char_name": "Pyra",
        "char_class": "Sorcerer",
        "char_level": 2,
        "subclass": None,
        "classes": [{"class_name": "Sorcerer", "level": 2, "subclass": None}],
        "race": "Human",
        "background": "Sage",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 12, "WIS": 10, "CHA": 16},
        "base_stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 12, "WIS": 10, "CHA": 16},
        "hp_max": 14,
        "hp_current": 14,
        "features_traits": [],
        "version": None,
    }
    analysis = analyze_level_up(
        char_doc, user_choices={"level_up_class": "Sorcerer", "subclass": "Draconic Sorcery"}
    )
    assert analysis["hp_increase"] == 7  # 4 + 2 (CON) + 1 (Draconic L3)
    assert analysis["hp_bonus_per_level"] == 1

    db = _AsyncDB("drac_l3_db")
    db._db["characters"].insert_one(dict(char_doc))

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "sorc"}
    limiter.reset()
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": "drac_l2",
                "analysis": analysis,
                "user_choices": {
                    "level_up_class": "Sorcerer",
                    "subclass_0": "Draconic Sorcery",
                    "hp_method": "average",
                    "custom_hp_increase": str(analysis["hp_increase"]),
                },
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # Exact 2024 L3 Draconic Sorcerer HP = (6+2+1) + 2*(4+2+1) = 23 (never double-counted 24!)
        assert body["hp_max"] == 23
        assert body["hp_current"] == 23
        assert body["feat_hp_bonus"] == 3
        assert body["version"] == 1
    finally:
        app.dependency_overrides = orig


def test_parse_character_from_text_clamps_hp_handles_non_int_and_multiclass():
    from backend.services.rules_service import parse_character_from_text

    # 1) Bogus huge hp_max & hp_current + non-int CON -> resets & clamps hp_current <= hp_max
    core_bad = {
        "char_name": "ImportBad",
        "char_class": "Wizard",
        "char_level": "four",
        "race": "Human",
        "background": "Sage",
        "stats": {"STR": 8, "DEX": 14, "CON": "ten", "INT": 16, "WIS": 12, "CHA": 10},
        "hp_max": 9999,
        "hp_current": 9999,
    }
    combat_empty = {"armor_class": 99, "weapons": []}
    with patch(
        "backend.services.rules_service.generate_ai_json", side_effect=[core_bad, combat_empty]
    ):
        parsed = parse_character_from_text("Level 4 Wizard text", edition=EDITION_2024)
    assert parsed["hp_max"] < 9999
    assert parsed["hp_current"] == parsed["hp_max"]

    # 2) Valid high-rolled multiclass Wizard 5 / Fighter 3 (max HP = 5*8 + 3*12 = 76 > single-class Wizard max 64)
    core_mc = {
        "char_name": "BladesingerTank",
        "char_class": "Wizard",
        "char_level": 8,
        "classes": [
            {"class_name": "Wizard", "level": 5, "subclass": "Evoker"},
            {"class_name": "Fighter", "level": 3, "subclass": "Champion"},
        ],
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 16, "WIS": 10, "CHA": 8},
        "hp_max": 72,
        "hp_current": 150,  # exceeds hp_max -> clamped to 72
    }
    with patch(
        "backend.services.rules_service.generate_ai_json",
        side_effect=[core_mc, {"weapons": []}],
    ):
        parsed_mc = parse_character_from_text("Wizard 5 Fighter 3 text", edition=EDITION_2014)
    assert parsed_mc["hp_max"] == 72
    assert parsed_mc["hp_current"] == 72


def test_rules_repository_returns_deep_copies():
    repo = RulesRepository()
    feats = repo.get_all_feats(EDITION_2024)
    feats[0]["stat_bonus"]["STR"] = 999
    assert repo.get_all_feats(EDITION_2024)[0]["stat_bonus"]["STR"] != 999

    races = repo.get_available_races(EDITION_2024)
    if races and isinstance(races[0].get("traits"), list) and races[0]["traits"]:
        races[0]["traits"][0]["name"] = "CORRUPTED"
        assert repo.get_available_races(EDITION_2024)[0]["traits"][0]["name"] != "CORRUPTED"

    spells = repo.get_all_spells(EDITION_2024)
    spells[0]["classes"].append("FAKE_CLASS")
    assert "FAKE_CLASS" not in repo.get_all_spells(EDITION_2024)[0]["classes"]


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_l2_fighter_empty_spells_dict_not_forced_to_eldritch_knight_2014_and_2024(edition):
    from backend.services.forge_service import analyze_level_up

    fighter_l2 = CharacterSchema(
        char_id="f_l2",
        char_name="Valerius",
        char_class="Fighter",
        char_level=2,
        classes=[{"class_name": "Fighter", "level": 2, "subclass": None}],
        race="Human",
        background="Soldier",
        dnd_edition=edition,
        stats={"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
    ).model_dump()

    synced = sync_character_stats(fighter_l2)
    assert not synced.get("subclass")
    assert synced.get("spell_ability") in (None, "", "None")
    assert synced.get("spell_slots") == {}

    analysis = analyze_level_up(synced, user_choices={"level_up_class": "Fighter"})
    subclass_choices = [c for c in analysis["choices_required"] if c.get("type") == "subclass"]
    assert len(subclass_choices) == 1
    assert "Champion" in subclass_choices[0]["options"]


def test_2024_draconic_sorcerer_l3_take_average_ignores_stale_pre_subclass_custom_hp():
    from backend.services.forge_service import analyze_level_up

    char_doc = {
        "char_id": "drac_stale_l2",
        "owner_id": "u1",
        "char_name": "Lyra Emberveil",
        "char_class": "Sorcerer",
        "char_level": 2,
        "classes": [{"class_name": "Sorcerer", "level": 2, "subclass": None}],
        "race": "Tiefling",
        "background": "Sage",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 12, "WIS": 10, "CHA": 17},
        "hp_max": 14,
        "hp_current": 14,
        "feat_hp_bonus": 0,
        "features_traits": [],
        "version": 0,
    }
    pre_analysis = analyze_level_up(char_doc, user_choices={"level_up_class": "Sorcerer"})
    assert pre_analysis["hp_increase"] == 6
    assert pre_analysis["new_total_hp"] == 20

    # Re-analysis when user selects subclass_0 = Draconic Sorcery while Take Average is active
    post_analysis = analyze_level_up(
        char_doc,
        user_choices={
            "level_up_class": "Sorcerer",
            "subclass_0": "Draconic Sorcery",
            "hp_method": "average",
            "custom_hp_increase": "6",
        },
    )
    assert post_analysis["hp_increase"] == 7
    assert post_analysis["new_total_hp"] == 23

    db = _AsyncDB("drac_stale_l3_db")
    db._db["characters"].insert_one(dict(char_doc))

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "sorc"}
    limiter.reset()
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": "drac_stale_l2",
                "analysis": pre_analysis,
                "user_choices": {
                    "level_up_class": "Sorcerer",
                    "subclass_0": "Draconic Sorcery",
                    "hp_method": "average",
                    "custom_hp_increase": "6",
                },
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["hp_max"] == 23
        assert body["hp_current"] == 23
        assert body["armor_class"] == 15
        feat_names = [
            f.get("name", "") for f in body.get("features_traits", []) if isinstance(f, dict)
        ]
        assert any("Draconic Resilience" in n for n in feat_names)
    finally:
        app.dependency_overrides = orig


@pytest.mark.parametrize(
    "edition_param",
    ["2014", "2014 Edition", "2014 Legacy", "2024", "2024 Edition", "2024 Revision", "5.5e"],
)
def test_rules_spells_accepts_all_edition_variants(edition_param):
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "tester"}
    limiter.reset()
    try:
        client = TestClient(app)
        resp = client.get("/api/v1/rules/spells", params={"edition": edition_param})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list) and len(data) > 0
    finally:
        app.dependency_overrides = orig


def test_2024_rogue_weapon_masteries_preserved_on_sync():
    rogue_doc = {
        "char_id": "rog_l3",
        "char_name": "Vex Nightwhisper",
        "char_class": "Rogue",
        "char_level": 3,
        "classes": [{"class_name": "Rogue", "level": 3, "subclass": "Thief"}],
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 8, "DEX": 16, "CON": 14, "INT": 12, "WIS": 12, "CHA": 10},
        "weapons": [
            {"name": "Shortsword", "damage_dice": "1d6"},
            {"name": "Shortbow", "damage_dice": "1d6"},
            {"name": "Dagger", "damage_dice": "1d4"},
        ],
        "weapon_masteries": ["Vex (Shortbow)", "Vex (Shortsword)"],
    }
    synced = sync_character_stats(rogue_doc)
    assert synced["weapon_masteries"] == ["Vex (Shortbow)", "Vex (Shortsword)"]


def test_join_campaign_broadcasts_party_member_joined_ws_event():
    db = _AsyncDB("join_ws_db")
    db._db["campaigns"].insert_one(
        {
            "campaign_name": "Test Join WS",
            "owner_id": "dm1",
            "invite_code": "INV-JOIN-1",
            "party": [],
        }
    )
    db._db["characters"].insert_one(
        {
            "char_id": "hero1",
            "owner_id": "p1",
            "char_name": "Aldric",
            "char_class": "Cleric",
            "char_level": 2,
        }
    )

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "p1", "username": "player1"}
    limiter.reset()
    try:
        from unittest.mock import AsyncMock

        client = TestClient(app)
        with patch(
            "server.routers.websocket_router.manager.broadcast", new_callable=AsyncMock
        ) as mock_bcast:
            resp = client.post(
                "/api/v1/campaigns/join",
                json={"invite_code": "INV-JOIN-1", "character_id": "hero1"},
            )
            assert resp.status_code == 200
            mock_bcast.assert_awaited_once()
            args, _ = mock_bcast.await_args
            assert args[0] == "Test Join WS"
            assert args[1]["type"] == "party_member_joined"
            assert args[1]["payload"]["char_id"] == "hero1"
    finally:
        app.dependency_overrides = orig


def test_level_up_apply_encounter_sync_isolates_homonyms_and_preserves_monsters():
    from backend.services.forge_service import analyze_level_up

    char_doc = {
        "char_id": "c1",
        "owner_id": "u1",
        "char_name": "Aria",
        "char_class": "Fighter",
        "char_level": 2,
        "classes": [{"class_name": "Fighter", "level": 2, "subclass": None}],
        "race": "Human",
        "background": "Soldier",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8},
        "hp_max": 20,
        "hp_current": 14,
        "active_campaign": "Homonym Keep",
        "version": 1,
    }
    analysis = analyze_level_up(char_doc, user_choices={"level_up_class": "Fighter"})

    db = _AsyncDB("homonym_enc_db")
    db._db["characters"].insert_one(dict(char_doc))
    db._db["characters"].insert_one(
        {
            "char_id": "c2",
            "owner_id": "u2",
            "char_name": "Aria",
            "char_class": "Wizard",
            "char_level": 2,
            "hp_max": 12,
            "hp_current": 11,
            "armor_class": 13,
            "active_campaign": "Homonym Keep",
        }
    )
    db._db["campaigns"].insert_one(
        {"campaign_name": "Homonym Keep", "owner_id": "dm1", "dnd_edition": EDITION_2024}
    )
    db._db["campaign_encounters"].insert_one(
        {
            "campaign_name": "Homonym Keep",
            "round": 1,
            "danger_indicator": "Easy",
            "combatants": [
                {
                    "id": "e1",
                    "char_id": "c1",
                    "name": "Aria",
                    "hp": 14,
                    "max_hp": 20,
                    "ac": 16,
                    "is_player": True,
                },
                {
                    "id": "e2",
                    "char_id": "c2",
                    "name": "Aria",
                    "hp": 11,
                    "max_hp": 12,
                    "ac": 13,
                    "is_player": True,
                },
                {
                    "id": "m1",
                    "name": "Goblin",
                    "hp": 7,
                    "max_hp": 7,
                    "ac": 15,
                    "is_player": False,
                    "cr": "1/4",
                },
            ],
        }
    )

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "p1"}
    limiter.reset()
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": "c1",
                "analysis": analysis,
                "user_choices": {
                    "level_up_class": "Fighter",
                    "subclass_0": "Champion",
                    "hp_method": "average",
                },
            },
        )
        assert resp.status_code == 200
        enc = db._db["campaign_encounters"].find_one({"campaign_name": "Homonym Keep"})
        rows = {c["id"]: c for c in enc["combatants"]}
        # c1 updated to L3 full HP
        assert rows["e1"]["hp"] == 28
        assert rows["e1"]["max_hp"] == 28
        # c2 homonym with distinct char_id MUST stay completely untouched!
        assert rows["e2"]["hp"] == 11
        assert rows["e2"]["max_hp"] == 12
        assert rows["e2"]["ac"] == 13
        # Monster stays untouched
        assert rows["m1"]["hp"] == 7
        assert enc.get("danger_indicator") in {"Trivial", "Easy", "Medium", "Hard", "Deadly"}
    finally:
        app.dependency_overrides = orig


def test_fighter_eldritch_knight_inference_respects_multiclass_and_classes_subclass():
    # 1) Fighter 1 / Wizard 2 (total level=3, Wizard spells) -> NOT Eldritch Knight
    f1_w2 = CharacterSchema(
        char_id="mc_fw",
        char_name="GandalfFighter",
        char_class="Fighter",
        char_level=3,
        classes=[
            {"class_name": "Fighter", "level": 1, "subclass": None},
            {"class_name": "Wizard", "level": 2, "subclass": None},
        ],
        race="Human",
        background="Sage",
        dnd_edition=EDITION_2024,
        stats={"STR": 14, "DEX": 12, "CON": 14, "INT": 16, "WIS": 10, "CHA": 8},
        spells={"cantrips": ["Fire Bolt"], "level_1": ["Magic Missile"]},
    ).model_dump()
    s_fw = sync_character_stats(f1_w2)
    assert s_fw.get("subclass") in (None, "")
    assert s_fw["classes"][0].get("subclass") in (None, "")
    assert s_fw.get("spell_ability") == "INT"

    # 2) Fighter 2 / Sorcerer 1 (CHA 16, INT 8, Sorcerer spells) -> spell_ability CHA, NOT EK
    f2_s1 = CharacterSchema(
        char_id="mc_fs",
        char_name="SorcBlade",
        char_class="Fighter",
        char_level=3,
        classes=[
            {"class_name": "Fighter", "level": 2, "subclass": None},
            {"class_name": "Sorcerer", "level": 1, "subclass": None},
        ],
        race="Human",
        background="Soldier",
        dnd_edition=EDITION_2024,
        stats={"STR": 16, "DEX": 12, "CON": 14, "INT": 8, "WIS": 10, "CHA": 16},
        spells={"cantrips": ["Light"], "level_1": ["Shield"]},
    ).model_dump()
    s_fs = sync_character_stats(f2_s1)
    assert s_fs.get("subclass") in (None, "")
    assert s_fs["classes"][0].get("subclass") in (None, "")
    assert s_fs.get("spell_ability") == "CHA"

    # 3) Single-class Fighter 3 with classes[0].subclass="Champion" and racial Misty Step -> stays Champion, NOT INT/EK
    champ = {
        "char_id": "champ_3",
        "char_name": "ElvenChamp",
        "char_class": "Fighter",
        "char_level": 3,
        "subclass": None,
        "classes": [{"class_name": "Fighter", "level": 3, "subclass": "Champion"}],
        "race": "High Elf",
        "background": "Soldier",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 8, "WIS": 12, "CHA": 14},
        "spells": {"level_2": ["Misty Step"]},
    }
    s_champ = sync_character_stats(champ)
    assert s_champ["classes"][0]["subclass"] == "Champion"
    assert s_champ.get("subclass") != "Eldritch Knight"
    assert s_champ.get("spell_ability") == "CHA"
    assert s_champ.get("spell_slots") == {}

    # 4) Legacy Fighter 3 with no subclass and populated spells -> legitimately infers Eldritch Knight
    ek = CharacterSchema(
        char_id="ek_3",
        char_name="EldritchL3",
        char_class="Fighter",
        char_level=3,
        classes=[{"class_name": "Fighter", "level": 3, "subclass": None}],
        race="Human",
        background="Sage",
        dnd_edition=EDITION_2014,
        stats={"STR": 16, "DEX": 10, "CON": 14, "INT": 14, "WIS": 10, "CHA": 8},
        spells={"cantrips": ["Fire Bolt"], "level_1": ["Shield"]},
    ).model_dump()
    s_ek = sync_character_stats(ek)
    assert s_ek.get("subclass") == "Eldritch Knight"
    assert s_ek["classes"][0]["subclass"] == "Eldritch Knight"
    assert s_ek.get("spell_ability") == "INT"
    assert s_ek["spell_slots"]["level_1"]["max"] == 2

    # 5) 2024 Edition Fighter L3 with spells also writes Eldritch Knight back to classes[0]
    ek_2024 = CharacterSchema(
        char_id="ek_2024_3",
        char_name="Eldritch2024",
        char_class="Fighter",
        char_level=3,
        classes=[{"class_name": "Fighter", "level": 3, "subclass": None}],
        race="Human",
        background="Sage",
        dnd_edition=EDITION_2024,
        stats={"STR": 16, "DEX": 10, "CON": 14, "INT": 14, "WIS": 10, "CHA": 8},
        spells={"cantrips": ["Fire Bolt"], "level_1": ["Shield"]},
    ).model_dump()
    s_ek_2024 = sync_character_stats(ek_2024)
    assert s_ek_2024.get("subclass") == "Eldritch Knight"
    assert s_ek_2024["classes"][0]["subclass"] == "Eldritch Knight"

    # 6) Malformed non-dict entries in classes fall back cleanly without IndexError
    malformed = {
        "char_id": "bad_cls_1",
        "char_name": "Malformed",
        "char_class": "Fighter",
        "char_level": 2,
        "classes": ["not_a_dict"],
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8},
    }
    s_malformed = sync_character_stats(malformed)
    assert s_malformed["classes"][0]["class_name"] == "Fighter"
    assert s_malformed["classes"][0]["level"] == 2


@pytest.mark.parametrize(
    "char_class,subclass,target_level",
    [
        ("Barbarian", "Path of the Berserker", 3),
        ("Bard", "College of Lore", 3),
        ("Druid", "Circle of the Moon", 2),
        ("Monk", "Way of the Open Hand", 3),
        ("Paladin", "Oath of Devotion", 3),
        ("Ranger", "Hunter", 3),
        ("Warlock", "The Fiend", 1),
        ("Artificer", "Alchemist", 3),
    ],
)
def test_resolve_level_up_automatic_features_replaces_all_2014_subclass_placeholders(
    char_class, subclass, target_level
):
    from backend.services.forge_service import resolve_level_up_automatic_features

    features = resolve_level_up_automatic_features(
        char_class=char_class,
        target_level=target_level,
        subclass_to_use=subclass,
        edition=EDITION_2014,
    )
    names = [str(f.get("name", "")) for f in features]
    assert names, f"Expected features for {char_class} L{target_level}"
    raw_placeholders = {
        "Primal Path",
        "Bard College",
        "Druid Circle",
        "Monastic Tradition",
        "Sacred Oath",
        "Ranger Archetype",
        "Otherworldly Patron",
        "Artificer Specialist",
    }
    assert not any(n in raw_placeholders for n in names)


def test_2024_draconic_sorcerer_roll_before_subclass_applies_l3_bonus():
    from backend.services.forge_service import analyze_level_up

    char_doc = {
        "char_id": "drac_roll_l2",
        "owner_id": "u1",
        "char_name": "Lyra Roll",
        "char_class": "Sorcerer",
        "char_level": 2,
        "classes": [{"class_name": "Sorcerer", "level": 2, "subclass": None}],
        "race": "Tiefling",
        "background": "Sage",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 12, "WIS": 10, "CHA": 17},
        "hp_max": 14,
        "hp_current": 14,
        "feat_hp_bonus": 0,
        "features_traits": [],
        "version": 0,
    }
    pre_analysis = analyze_level_up(char_doc, user_choices={"level_up_class": "Sorcerer"})

    db = _AsyncDB("drac_roll_l3_db")
    db._db["characters"].insert_one(dict(char_doc))

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "sorc"}
    limiter.reset()
    try:
        client = TestClient(app)
        # Player rolled max d6 (6) + CON (2) = 8 BEFORE selecting Draconic Sorcery (hp_bonus_included=0)
        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": "drac_roll_l2",
                "analysis": pre_analysis,
                "user_choices": {
                    "level_up_class": "Sorcerer",
                    "subclass_0": "Draconic Sorcery",
                    "hp_method": "roll",
                    "hp_bonus_included": "0",
                    "custom_hp_increase": "8",
                },
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # 14 + (6+2+1) + 2 retroactive L1-L2 Draconic = 25
        assert body["hp_max"] == 25
        assert body["hp_current"] == 25
        assert not any(
            "hp_bonus_included" in (f.get("description") or "").lower()
            for f in body.get("features_traits", [])
        )

        # 2014 Fighter Level 1 -> 2 roll level-up also never persists hp_bonus_included as a trait
        f_doc = {
            "char_id": "fighter_roll_2014",
            "owner_id": "u1",
            "char_name": "Torin",
            "char_class": "Fighter",
            "char_level": 1,
            "classes": [{"class_name": "Fighter", "level": 1, "subclass": None}],
            "race": "Human",
            "background": "Soldier",
            "dnd_edition": EDITION_2014,
            "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8},
            "hp_max": 12,
            "hp_current": 12,
            "feat_hp_bonus": 0,
            "features_traits": [
                {"name": "0", "description": "Selected for hp_bonus_included"},
            ],
            "version": 0,
        }
        db._db["characters"].insert_one(dict(f_doc))
        f_analysis = analyze_level_up(f_doc, user_choices={"level_up_class": "Fighter"})
        resp_2014 = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": "fighter_roll_2014",
                "analysis": f_analysis,
                "user_choices": {
                    "level_up_class": "Fighter",
                    "hp_method": "roll",
                    "hp_bonus_included": "0",
                    "custom_hp_increase": "9",
                },
            },
        )
        assert resp_2014.status_code == 200
        f_body = resp_2014.json()
        assert f_body["hp_max"] == 21
        assert not any(
            "hp_bonus_included" in (f.get("description") or "").lower()
            for f in f_body.get("features_traits", [])
        )
    finally:
        app.dependency_overrides = orig
        limiter.reset()


def test_add_party_member_broadcasts_party_member_joined_ws_event():
    db = _AsyncDB("add_member_ws_db")
    db._db["campaigns"].insert_one({"campaign_name": "Test Add WS", "owner_id": "dm1", "party": []})
    db._db["campaign_members"].insert_one(
        {"campaign_id": "Test Add WS", "user_id": "dm1", "role": "dm"}
    )
    db._db["characters"].insert_one(
        {
            "char_id": "dm_hero",
            "owner_id": "dm1",
            "char_name": "DMCompanion",
            "char_class": "Cleric",
            "char_level": 2,
        }
    )

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "dm1", "username": "dm"}
    limiter.reset()
    try:
        from unittest.mock import AsyncMock

        client = TestClient(app)
        with patch(
            "server.routers.websocket_router.manager.broadcast", new_callable=AsyncMock
        ) as mock_bcast:
            resp = client.post(
                "/api/v1/campaigns/Test%20Add%20WS/party/members",
                json={"character_id": "dm_hero"},
            )
            assert resp.status_code == 200
            mock_bcast.assert_awaited_once()
            args, _ = mock_bcast.await_args
            assert args[0] == "Test Add WS"
            assert args[1]["type"] == "party_member_joined"
            assert args[1]["payload"]["char_id"] == "dm_hero"
    finally:
        app.dependency_overrides = orig


def test_cleanup_fake_users_cascades_all_campaign_collections_and_preserves_real_users():
    import asyncio

    from scripts.cleanup_fake_users import run_cleanup

    db = _AsyncDB("cleanup_cascade_db")
    db._db["users"].insert_many(
        [
            {"id": "qa_u1", "username": "qa_g1_dm_1", "email": "dm@phyrexian.test"},
            {"id": "real_u1", "username": "mitsos", "email": "mitsos@real.dnd"},
        ]
    )
    db._db["campaigns"].insert_many(
        [
            {"campaign_name": "Shadowfell Keep 1", "owner_id": "qa_u1", "party": []},
            {"campaign_name": "Real Campaign", "owner_id": "real_u1", "party": []},
        ]
    )
    for coll in (
        "campaign_roll_logs",
        "campaign_encounters",
        "campaign_entities",
        "session_logs",
        "campaign_skeletons",
        "homebrew_content",
        "campaign_whispers",
        "campaign_scenes",
        "campaign_assets",
        "campaign_scene_history",
    ):
        db._db[coll].insert_many(
            [
                {"campaign_name": "Shadowfell Keep 1", "val": 1},
                {"campaign_name": "Real Campaign", "val": 2},
            ]
        )

    with patch("scripts.cleanup_fake_users.get_database", return_value=db):
        asyncio.run(run_cleanup(dry_run=False, include_unknown=False))

    assert db._db["users"].count_documents({"username": "qa_g1_dm_1"}) == 0
    assert db._db["users"].count_documents({"username": "mitsos"}) == 1
    assert db._db["campaigns"].count_documents({"campaign_name": "Shadowfell Keep 1"}) == 0
    assert db._db["campaigns"].count_documents({"campaign_name": "Real Campaign"}) == 1
    for coll in (
        "campaign_roll_logs",
        "campaign_encounters",
        "campaign_entities",
        "session_logs",
        "campaign_skeletons",
        "homebrew_content",
        "campaign_whispers",
        "campaign_scenes",
        "campaign_assets",
        "campaign_scene_history",
    ):
        assert db._db[coll].count_documents({"campaign_name": "Shadowfell Keep 1"}) == 0
        assert db._db[coll].count_documents({"campaign_name": "Real Campaign"}) == 1


def test_forge_preview_portrait_promoted_on_create_and_referenced_previews_never_pruned():
    import os
    import time

    from backend.utils.image_utils import PORTRAIT_DIR, prune_unreferenced_preview_portraits

    os.makedirs(PORTRAIT_DIR, exist_ok=True)
    preview_fname = "preview_a1b2c3d4e5f6_1700000000.png"
    referenced_preview = "preview_111122223333_1700000001.png"
    orphan_preview = "preview_999988887777_1700000002.png"
    promoted_path = None
    created_files = [
        os.path.join(PORTRAIT_DIR, preview_fname),
        os.path.join(PORTRAIT_DIR, referenced_preview),
        os.path.join(PORTRAIT_DIR, orphan_preview),
    ]
    for p in created_files:
        with open(p, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
        os.utime(p, (time.time() - 90000, time.time() - 90000))

    db = _AsyncDB("preview_promote_db")
    db._db["characters"].insert_one(
        {
            "char_id": "legacy_preview_owner",
            "owner_id": "u_other",
            "char_name": "Legacy",
            "char_portrait": f"/api/v1/portraits/{referenced_preview}",
        }
    )

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "player"}
    limiter.reset()
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/characters",
            json={
                "char_id": "saved_hero_1",
                "char_name": "PromotedHero",
                "char_class": "Fighter",
                "race": "Human",
                "background": "Soldier",
                "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8},
                "char_portrait": f"/api/v1/portraits/{preview_fname}",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["char_portrait"].startswith("/api/v1/portraits/saved_hero_1_")
        promoted_fname = os.path.basename(body["char_portrait"])
        promoted_path = os.path.join(PORTRAIT_DIR, promoted_fname)
        assert os.path.isfile(promoted_path)
        assert not os.path.exists(os.path.join(PORTRAIT_DIR, preview_fname))

        # Aged preview_ referenced in DB must survive pruning; aged unreferenced preview_ is deleted
        referenced = db._db["characters"].distinct("char_portrait")
        removed = prune_unreferenced_preview_portraits(referenced, max_age_seconds=86400)
        assert removed >= 1
        assert os.path.isfile(os.path.join(PORTRAIT_DIR, referenced_preview))
        assert not os.path.exists(os.path.join(PORTRAIT_DIR, orphan_preview))
    finally:
        app.dependency_overrides = orig
        limiter.reset()
        for p in created_files + ([promoted_path] if promoted_path else []):
            if p and os.path.exists(p):
                os.remove(p)


def test_level_up_analysis_http_preserves_hp_bonus_per_level_2014_and_2024():
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "player"}
    limiter.reset()
    try:
        client = TestClient(app)

        # 2024 Draconic Sorcery Level 2 -> 3 returns hp_bonus_per_level = 1 over HTTP
        sorc_2024 = {
            "char_id": "sorc_http_2024",
            "char_name": "Ember",
            "char_class": "Sorcerer",
            "char_level": 2,
            "classes": [{"class_name": "Sorcerer", "level": 2, "subclass": None}],
            "race": "Human",
            "background": "Sage",
            "dnd_edition": EDITION_2024,
            "hp_max": 14,
            "hp_current": 14,
            "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 12, "WIS": 10, "CHA": 17},
        }
        resp_2024 = client.post(
            "/api/v1/forge/level-up-analysis",
            json={"character": sorc_2024, "user_choices": {"subclass_0": "Draconic Sorcery"}},
        )
        assert resp_2024.status_code == 200
        body_2024 = resp_2024.json()
        assert body_2024["hp_bonus_per_level"] == 1
        assert body_2024["hp_increase"] == 7  # 4 + 2 CON + 1 Draconic

        # 2014 Tough Fighter Level 1 -> 2 returns hp_bonus_per_level = 2 over HTTP
        tough_2014 = {
            "char_id": "tough_http_2014",
            "char_name": "Garrick",
            "char_class": "Fighter",
            "char_level": 1,
            "classes": [{"class_name": "Fighter", "level": 1, "subclass": None}],
            "race": "Human",
            "background": "Soldier",
            "dnd_edition": EDITION_2014,
            "hp_max": 14,
            "hp_current": 14,
            "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 10, "WIS": 10, "CHA": 8},
            "features_traits": [{"name": "Tough", "description": "+2 HP per level"}],
        }
        resp_2014 = client.post(
            "/api/v1/forge/level-up-analysis",
            json={"character": tough_2014, "user_choices": {}},
        )
        assert resp_2014.status_code == 200
        body_2014 = resp_2014.json()
        assert body_2014["hp_bonus_per_level"] == 2
        assert body_2014["hp_increase"] == 10  # 6 + 2 CON + 2 Tough
    finally:
        app.dependency_overrides = orig
        limiter.reset()


def test_pdf_exporter_skips_data_uri_portraits_without_path_traversal_warning(caplog):
    from backend.utils.pdf_exporter import create_image_overlay

    with caplog.at_level("WARNING"):
        res = create_image_overlay(
            "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3C%2Fsvg%3E"
        )
    assert res is None
    assert "Blocked path traversal attempt" not in caplog.text


def test_forge_portrait_supports_unsaved_preview_and_blocks_other_owners_char_id():
    from unittest.mock import AsyncMock

    db = _AsyncDB("forge_portrait_unsaved_db")
    db._db["characters"].insert_one(
        {
            "char_id": "victim_char",
            "owner_id": "victim_user",
            "char_name": "SecretHero",
            "char_class": "Rogue",
        }
    )

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "actor_1", "username": "actor"}
    limiter.reset()
    try:
        client = TestClient(app)
        with patch(
            "server.routers.forge_router.generate_portrait_url",
            new_callable=AsyncMock,
            return_value="/api/v1/portraits/temp_hero.png",
        ):
            # Unsaved Forge preview succeeds with version=0 while pinning ephemeral char_id and ignoring char_portrait
            resp_ok = client.post(
                "/api/v1/forge/portrait",
                json={
                    "char_id": "temp",
                    "force": False,
                    "character_data": {
                        "char_id": "victim_char",
                        "char_portrait": "data/portraits/../../server/config.py",
                        "char_name": "Preview",
                        "char_class": "Fighter",
                        "race": "Elf",
                    },
                },
            )
            assert resp_ok.status_code == 200
            assert resp_ok.json() == {
                "success": True,
                "portrait_url": "/api/v1/portraits/temp_hero.png",
                "version": 0,
            }

        # Verify arguments passed to generate_portrait_url never trust victim char_id or char_portrait
        with patch(
            "server.routers.forge_router.generate_portrait_url",
            new_callable=AsyncMock,
            return_value="/api/v1/portraits/preview_safe.png",
        ) as mock_gen:
            resp_preview = client.post(
                "/api/v1/forge/portrait",
                json={
                    "char_id": "temp",
                    "force": False,
                    "character_data": {
                        "char_id": "victim_char",
                        "char_portrait": "data/portraits/../../server/config.py",
                        "char_class": "Bard",
                        "race": "Goblin",
                    },
                },
            )
            assert resp_preview.status_code == 200
            called_dict = mock_gen.await_args.args[0]
            assert called_dict["char_id"].startswith("preview_")
            assert called_dict["char_id"] != "victim_char"
            assert "char_portrait" not in called_dict

            # Cannot piggyback character_data on another user's persisted char_id
            resp_idor = client.post(
                "/api/v1/forge/portrait",
                json={
                    "char_id": "victim_char",
                    "force": True,
                    "character_data": {"char_class": "Bard", "race": "Human"},
                },
            )
            assert resp_idor.status_code == 404
    finally:
        app.dependency_overrides = orig
        limiter.reset()


def test_generate_portrait_url_blocks_legacy_path_traversal_probe():
    import asyncio
    from unittest.mock import AsyncMock

    from backend.utils.image_utils import generate_portrait_url

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(side_effect=RuntimeError("network disabled in test"))

    with patch("backend.utils.image_utils.httpx.AsyncClient", return_value=mock_client):
        res = asyncio.run(
            generate_portrait_url(
                {
                    "char_id": "preview_probe",
                    "race": "Human",
                    "char_class": "Fighter",
                    "char_portrait": "data/portraits/../../server/config.py",
                },
                force=False,
            )
        )
    assert res is None


def test_barbarian_2014_path_feature_and_all_2024_level3_subclasses_resolve():
    import json

    from backend.core.constants import SUBCLASSES_2024
    from backend.services.forge_service import resolve_level_up_automatic_features

    for lvl in (6, 10, 14):
        feats = resolve_level_up_automatic_features(
            char_class="Barbarian",
            target_level=lvl,
            subclass_to_use="Path of the Berserker",
            edition=EDITION_2014,
        )
        names = [f.get("name") for f in feats]
        assert "Path feature" not in names
        assert "Path of the Berserker Subclass Feature" in names

    # Exhaustively verify every 2024 subclass in BOTH SUBCLASSES_2024 and data/rules/subclasses.json
    with open("data/rules/subclasses.json") as f:
        json_2024 = json.load(f)["2024 Edition"]

    for source_map in (SUBCLASSES_2024, json_2024):
        for cls_name, sub_list in source_map.items():
            for sub_name in sub_list:
                feats = resolve_level_up_automatic_features(
                    char_class=cls_name,
                    target_level=3,
                    subclass_to_use=sub_name,
                    edition=EDITION_2024,
                )
                assert any(
                    sub_name.lower() in (f.get("name") or "").lower()
                    and not (f.get("name") or "").endswith(" Subclass Feature")
                    for f in feats
                ), f"Expected dedicated 2024 L3 entry for {cls_name} ({sub_name}), got {feats}"
                if cls_name == "Wizard" and sub_name == "Evoker":
                    evoker_desc = " ".join(f.get("description", "") for f in feats)
                    assert "miss with your cantrip attack roll" in evoker_desc
                    assert "pass your cantrip attack roll" not in evoker_desc


def test_parse_edition_is_case_insensitive_over_http():
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "player"}
    limiter.reset()
    try:
        client = TestClient(app)
        for query_ed in ("5.5E", "2024 edition", "2014 legacy"):
            resp = client.get(f"/api/v1/rules/classes?edition={query_ed}")
            assert resp.status_code == 200, f"Failed for {query_ed}: {resp.text}"
            assert "Fighter" in resp.json()
    finally:
        app.dependency_overrides = orig
        limiter.reset()


def test_cleanup_fake_users_dry_run_reports_all_cascade_collections(capsys):
    import asyncio

    from scripts.cleanup_fake_users import run_cleanup

    db = _AsyncDB("cleanup_dryrun_db")
    db._db["users"].insert_one(
        {"id": "qa_u1", "username": "qa_g1_dm_1", "email": "dm@phyrexian.test"}
    )
    db._db["campaigns"].insert_one({"campaign_name": "Shadowfell Keep 1", "owner_id": "qa_u1"})
    for coll in (
        "campaign_entities",
        "session_logs",
        "campaign_skeletons",
        "homebrew_content",
        "campaign_assets",
        "campaign_scene_history",
    ):
        db._db[coll].insert_one({"campaign_name": "Shadowfell Keep 1", "filename": "missing.webp"})

    with patch("scripts.cleanup_fake_users.get_database", return_value=db):
        asyncio.run(run_cleanup(dry_run=True, include_unknown=False))

    out = capsys.readouterr().out
    for expected_label in (
        "10. Found 1 fake campaign entities.",
        "11. Found 1 fake session logs.",
        "12. Found 1 fake campaign skeletons.",
        "13. Found 1 fake homebrew entries.",
        "14. Found 1 fake campaign assets",
        "15. Found 1 fake scene history records.",
    ):
        assert expected_label in out
    assert db._db["campaigns"].count_documents({"campaign_name": "Shadowfell Keep 1"}) == 1


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_non_repeatable_feat_dedup_blocked_on_level_up_and_flagged_by_audit(edition):
    """Tough (or any non-repeatable feat) cannot be picked twice, never double-stacks HP, and fails Rules Audit."""
    from backend.services.forge_service import analyze_level_up
    from backend.services.progression_service import get_level_up_vitals
    from backend.services.rules_service import autofix_character_build
    from backend.services.stats_service import sync_character_stats
    from backend.services.validation_service import deterministic_validate_build

    is_2024 = "2024" in edition
    fighter_l5 = {
        "char_id": f"valerius_{'24' if is_2024 else '14'}",
        "owner_id": "u_qa",
        "char_name": "Valerius",
        "char_class": "Fighter",
        "subclass": "Champion",
        "char_level": 5,
        "classes": [{"class_name": "Fighter", "level": 5, "subclass": "Champion"}],
        "race": "Human",
        "background": "Soldier",
        "dnd_edition": edition,
        "stats": {"STR": 18, "DEX": 13, "CON": 16, "INT": 10, "WIS": 12, "CHA": 8},
        "base_stats": {"STR": 18, "DEX": 13, "CON": 16, "INT": 10, "WIS": 12, "CHA": 8},
        "hp_max": 59,  # 13 + 4*(6+3) + 10 (Tough at L1..5)
        "hp_current": 59,
        "feat_hp_bonus": 10,
        "con_mod_applied": 3,
        "features_traits": [
            {"name": "Feat: Tough", "description": "+2 HP per level", "source": "Feat"},
            {"name": "Feat: Alert", "description": "Init bonus", "source": "Feat"},
        ],
        "advancements": [{"level": 1, "type": "Feat", "name": "Tough"}],
        "version": 1,
    }

    # 1. analyze_level_up filters already-owned Tough & Alert and omits raw 'Ability Score Improvement'
    analysis = analyze_level_up(fighter_l5, user_choices={"level_up_class": "Fighter"})
    feat_choice = next(c for c in analysis["choices_required"] if c["type"] == "feat")
    assert "Tough" not in feat_choice["options"]
    assert "Alert" not in feat_choice["options"]
    assert "Ability Score Improvement" not in feat_choice["options"]
    assert feat_choice["feat_metadata"]
    if is_2024:
        assert feat_choice["feat_metadata"]["Charger"]["has_stat_choice"] is True
        assert feat_choice["feat_metadata"]["Charger"]["stat_choice_options"] == ["STR", "DEX"]
        assert feat_choice["feat_metadata"]["Actor"]["has_stat_choice"] is False
        assert feat_choice["feat_metadata"]["Actor"]["stat_bonus"] == {"CHA": 1}

    # 2. level-up-apply rejects duplicate non-repeatable Tough, identical +1/+1 stats, and illegal half-feat stat
    db = _AsyncDB(f"dupe_feat_{'24' if is_2024 else '14'}")
    db._db["characters"].insert_one(dict(fighter_l5))

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_qa", "username": "qa"}
    limiter.reset()
    try:
        client = TestClient(app)
        resp_dupe = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": fighter_l5["char_id"],
                "analysis": analysis,
                "user_choices": {"level_up_class": "Fighter", "feat_0": "Tough"},
            },
        )
        assert resp_dupe.status_code == 400
        assert "already has non-repeatable feat" in resp_dupe.json()["detail"].lower()

        resp_same_stats = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": fighter_l5["char_id"],
                "analysis": analysis,
                "user_choices": {
                    "level_up_class": "Fighter",
                    "feat_0": "+1 to two Stats",
                    "feat_stat1_0": "STR",
                    "feat_stat2_0": "STR",
                },
            },
        )
        assert resp_same_stats.status_code == 400

        if is_2024:
            resp_bad_half = client.post(
                "/api/v1/forge/level-up-apply",
                json={
                    "character_id": fighter_l5["char_id"],
                    "analysis": analysis,
                    "user_choices": {
                        "level_up_class": "Fighter",
                        "feat_0": "Charger",
                        "feat_stat1_0": "CHA",
                    },
                },
            )
            assert resp_bad_half.status_code == 400
    finally:
        app.dependency_overrides = orig
        limiter.reset()

    # 3. Corrupted doc with double Tough + double Alert never double-stacks HP/Initiative and fails Rules Audit
    corrupted = copy.deepcopy(fighter_l5)
    corrupted["char_level"] = 10
    corrupted["classes"][0]["level"] = 10
    corrupted["hp_max"] = 129
    corrupted["feat_hp_bonus"] = 40
    corrupted["features_traits"].append(
        {"name": "Tough", "description": "Selected via Level Up.", "source": None}
    )
    corrupted["features_traits"].append(
        {"name": "Alert", "description": "Selected via Level Up.", "source": None}
    )

    vitals = get_level_up_vitals(
        "Fighter", 9, 16, edition=edition, features=corrupted["features_traits"]
    )
    assert vitals["hp_bonus_per_level"] == 2  # Never 4

    synced = sync_character_stats(copy.deepcopy(corrupted))
    assert synced["feat_hp_bonus"] == 20  # Never 40
    expected_init = (
        synced["proficiency_bonus"] + 1  # 2024: Alert (+PB) + DEX(+1), Remarkable Athlete = Adv
        if is_2024
        else 5
        + 2
        + 1  # 2014 Champion L10: Alert (+5) + Remarkable Athlete (ceil(PB/2)=+2) + DEX(+1)
    )
    assert synced["initiative_modifier"] == expected_init  # Never double-counted Alert

    _, issues = deterministic_validate_build(corrupted)
    assert any("tough" in msg.lower() and "duplicate" in msg.lower() for msg in issues)

    fixed = autofix_character_build(copy.deepcopy(corrupted))
    assert fixed["validation_result"]["is_valid"] is False
    fixed_char = fixed["character"]
    assert fixed_char["feat_hp_bonus"] == 20
    assert fixed_char["hp_max"] == 109  # 129 - 20 excess Tough HP

    # 4. Halfling 'Lucky' (Race trait) + Repeated ASI class features must NOT trigger false duplicate-feat errors
    halfling = {
        "char_id": "halfling_ok",
        "owner_id": "u_qa",
        "char_name": "Pip",
        "char_class": "Fighter",
        "subclass": "Champion",
        "char_level": 8,
        "classes": [{"class_name": "Fighter", "level": 8, "subclass": "Champion"}],
        "race": "Halfling",
        "background": "Criminal",
        "dnd_edition": edition,
        "stats": {"STR": 10, "DEX": 20, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        "features_traits": [
            {
                "name": "Lucky",
                "description": "When you roll a 1 on the d20, reroll.",
                "source": None,
            },
            {"name": "Ability Score Improvement", "description": "L4 ASI", "source": None},
            {"name": "Ability Score Improvement", "description": "L6 ASI", "source": None},
            {"name": "Ability Score Improvement", "description": "L8 ASI", "source": None},
        ],
    }
    _, halfling_issues = deterministic_validate_build(halfling)
    assert halfling_issues == []


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_level_up_analysis_reflects_con_bump_tough_and_exposes_metadata_over_http(edition):
    """POST /forge/level-up-analysis previews retroactive CON & Tough HP and serializes feat_metadata."""
    rogue_l9 = {
        "char_id": "vex_preview",
        "owner_id": "u_qa",
        "char_name": "Vex Shadowstep",
        "char_class": "Rogue",
        "subclass": "Thief",
        "char_level": 9,
        "classes": [{"class_name": "Rogue", "level": 9, "subclass": "Thief"}],
        "race": "Elf",
        "background": "Criminal",
        "dnd_edition": edition,
        "stats": {"STR": 8, "DEX": 20, "CON": 15, "INT": 14, "WIS": 12, "CHA": 10},
        "hp_max": 66,  # (8+2) + 8*(5+2) = 66
        "hp_current": 66,
        "features_traits": [],
        "version": 9,
    }

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_qa", "username": "qa"}
    limiter.reset()
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forge/level-up-analysis",
            json={
                "character": rogue_l9,
                "user_choices": {
                    "level_up_class": "Rogue",
                    "feat_0": "+2 to one Stat",
                    "feat_stat1_0": "CON",
                },
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["hp_increase"] == 8  # 5 + new CON (+3)
        assert body["new_total_hp"] == 83  # 66 + 8 + 9*1 retroactive CON
        feat_choice = next(c for c in body["choices_required"] if c["type"] == "feat")
        assert feat_choice["feat_metadata"]["Tough"]["has_stat_choice"] is False
        assert feat_choice["feat_metadata"]["Tough"]["hp_bonus_per_level"] == 2

        resp_tough = client.post(
            "/api/v1/forge/level-up-analysis",
            json={
                "character": rogue_l9,
                "user_choices": {"level_up_class": "Rogue", "feat_0": "Tough"},
            },
        )
        assert resp_tough.status_code == 200
        body_tough = resp_tough.json()
        assert body_tough["hp_bonus_per_level"] == 2
        assert body_tough["hp_increase"] == 9  # 5 + 2 (CON) + 2 (Tough)
        assert body_tough["new_total_hp"] == 93  # 66 + 9 + 9*2 retroactive Tough
    finally:
        app.dependency_overrides = orig
        limiter.reset()


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_level_up_apply_adds_learned_spells_to_prepared_spells(edition):
    """Leveled spells picked via /forge/level-up-apply are appended to both spells and prepared_spells."""
    from backend.services.forge_service import analyze_level_up

    sorc_l5 = {
        "char_id": f"sorc_prep_{'24' if '2024' in edition else '14'}",
        "owner_id": "u_qa",
        "char_name": "Lyra",
        "char_class": "Sorcerer",
        "subclass": "Draconic Sorcery" if "2024" in edition else "Draconic Bloodline",
        "char_level": 5,
        "classes": [
            {
                "class_name": "Sorcerer",
                "level": 5,
                "subclass": "Draconic Sorcery" if "2024" in edition else "Draconic Bloodline",
            }
        ],
        "race": "Tiefling",
        "background": "Sage",
        "dnd_edition": edition,
        "stats": {"STR": 8, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 18},
        "hp_max": 37,
        "hp_current": 37,
        "spells": {"cantrips": ["Fire Bolt"], "level_1": ["Magic Missile"]},
        "prepared_spells": ["Fire Bolt", "Magic Missile"],
        "version": 1,
    }
    analysis = analyze_level_up(sorc_l5, user_choices={"level_up_class": "Sorcerer"})

    db = _AsyncDB(f"prep_spells_{'24' if '2024' in edition else '14'}")
    db._db["characters"].insert_one(dict(sorc_l5))

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_qa", "username": "qa"}
    limiter.reset()
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": sorc_l5["char_id"],
                "analysis": analysis,
                "user_choices": {"level_up_class": "Sorcerer", "spell_0": "Fireball"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "Fireball" in body["spells"]["level_3"]
        assert "Fireball" in body["prepared_spells"]
        assert body["prepared_spells"].count("Magic Missile") == 1
    finally:
        app.dependency_overrides = orig
        limiter.reset()


def test_all_2024_subclasses_resolve_concrete_higher_level_features():
    """Every 2024 subclass across all 13 classes resolves specific subclass feature names at every subclass level."""
    import glob

    from backend.services.forge_service import resolve_level_up_automatic_features

    with open("data/rules/subclasses.json") as f:
        subclasses_2024 = json.load(f)["2024 Edition"]

    for cls_file in sorted(glob.glob("data/rules/classes/2024/*.json")):
        with open(cls_file) as cf:
            cls_data = json.load(cf)
        cls_name = cls_data["class_name"]
        sub_levels = [
            int(lvl_str)
            for lvl_str, lvl_info in sorted(
                cls_data.get("progression", {}).items(), key=lambda item: int(item[0])
            )
            if any(
                "subclass" in feat.get("name", "").lower() for feat in lvl_info.get("features", [])
            )
        ]
        for sub_name in subclasses_2024.get(cls_name, []):
            for lvl in sub_levels:
                feats = resolve_level_up_automatic_features(
                    char_class=cls_name,
                    target_level=lvl,
                    subclass_to_use=sub_name,
                    edition=EDITION_2024,
                )
                assert any(
                    sub_name.lower() in (f.get("name") or "").lower()
                    and not (f.get("name") or "").endswith(" Subclass Feature")
                    for f in feats
                ), (
                    f"Missing concrete 2024 subclass feature for {cls_name} ({sub_name}) at L{lvl}: {feats}"
                )

    # Verify the two exact QA cases (Draconic Sorcery L6, Thief L9)
    sorc_l6 = resolve_level_up_automatic_features("Sorcerer", 6, "Draconic Sorcery", EDITION_2024)
    assert any(f.get("name") == "Elemental Affinity (Draconic Sorcery)" for f in sorc_l6)
    rogue_l9 = resolve_level_up_automatic_features("Rogue", 9, "Thief", EDITION_2024)
    assert any(f.get("name") == "Supreme Sneak (Thief)" for f in rogue_l9)


def test_subclass_features_stamped_source_and_never_collide_with_feats():
    """Class/subclass features are stamped cleanly and never trigger false-positive feat collisions."""
    from backend.services.forge_service import analyze_level_up, resolve_level_up_automatic_features
    from backend.services.validation_service import (
        build_feat_lookup,
        deterministic_validate_build,
        resolve_known_feat,
    )

    # Class-only call (no subclass) stamps source == "Class"
    fighter_l2 = resolve_level_up_automatic_features("Fighter", 2, None, EDITION_2024)
    assert fighter_l2
    assert all(f.get("source") == "Class" for f in fighter_l2)

    collision_checks = [
        (
            "Fighter",
            7,
            "Psi Warrior",
            EDITION_2024,
            "Telekinetic Adept (Psi Warrior)",
            "Telekinetic",
        ),
        (
            "Fighter",
            18,
            "Psi Warrior",
            EDITION_2024,
            "Telekinetic Master (Psi Warrior)",
            "Telekinetic",
        ),
        ("Cleric", 6, "Life Domain", EDITION_2024, "Blessed Healer (Life Domain)", "Healer"),
        (
            "Paladin",
            15,
            "Oath of the Ancients",
            EDITION_2024,
            "Undying Sentinel (Oath of the Ancients)",
            "Sentinel",
        ),
        (
            "Sorcerer",
            3,
            "Aberrant Sorcery",
            EDITION_2024,
            "Psionic Spells & Telepathic Speech (Aberrant Sorcery)",
            "Telepathic",
        ),
        ("Fighter", 7, "Champion", EDITION_2014, "Remarkable Athlete (Champion)", "Athlete"),
    ]

    for cls_name, lvl, sub_name, ed, expected_feat_name, real_feat in collision_checks:
        resolved = resolve_level_up_automatic_features(cls_name, lvl, sub_name, ed)
        matched = [f for f in resolved if f.get("name") == expected_feat_name]
        assert matched, f"Expected {expected_feat_name} in {resolved}"
        assert matched[0].get("source") == "Subclass"
        feat_lookup = build_feat_lookup(ed)
        assert resolve_known_feat(expected_feat_name, feat_lookup, source="Subclass") is None
        assert resolve_known_feat(expected_feat_name, feat_lookup, source=None) is None

        # Taking the homonymous real feat remains valid and audit preserves both entries
        hero = {
            "char_id": f"col_{cls_name}_{lvl}",
            "owner_id": "u_qa",
            "char_name": "Test Hero",
            "char_class": cls_name,
            "subclass": sub_name,
            "char_level": 7,
            "classes": [{"class_name": cls_name, "level": 7, "subclass": sub_name}],
            "race": "Human",
            "background": "Soldier",
            "dnd_edition": ed,
            "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 12, "WIS": 12, "CHA": 12},
            "base_stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 12, "WIS": 12, "CHA": 12},
            "features_traits": [
                {"name": expected_feat_name, "description": "Subclass feature", "source": None},
                {"name": f"Feat: {real_feat}", "description": "Feat", "source": "Feat"},
            ],
            "version": 1,
        }
        analysis = analyze_level_up(copy.deepcopy(hero), user_choices={"level_up_class": cls_name})
        feat_choices = [c for c in analysis.get("choices_required", []) if c.get("type") == "feat"]
        if feat_choices:
            # Already owns real_feat explicitly -> excluded once, NOT because of subclass feature
            assert real_feat not in feat_choices[0]["options"]

        # Without real_feat, hero with ONLY the subclass feature can still pick real_feat at L8
        hero_no_feat = copy.deepcopy(hero)
        hero_no_feat["features_traits"] = [
            {"name": expected_feat_name, "description": "Subclass feature", "source": None}
        ]
        analysis_open = analyze_level_up(hero_no_feat, user_choices={"level_up_class": cls_name})
        open_feat_choices = [
            c for c in analysis_open.get("choices_required", []) if c.get("type") == "feat"
        ]
        if open_feat_choices:
            assert real_feat in open_feat_choices[0]["options"]

        is_valid, issues = deterministic_validate_build(copy.deepcopy(hero))
        assert not any(
            expected_feat_name.lower() in i.lower() or "duplicate" in i.lower() for i in issues
        ), f"False positive audit failure on {expected_feat_name}: {issues}"


def test_2024_repeatable_skilled_and_magic_initiate_allowed_twice():
    """In 2024 Edition, Skilled and Magic Initiate remain repeatable across analysis, apply, and audit."""
    from backend.services.forge_service import analyze_level_up
    from backend.services.validation_service import (
        build_feat_lookup,
        deterministic_validate_build,
        is_feat_repeatable,
    )

    feat_lookup_2024 = build_feat_lookup(EDITION_2024)
    for feat_name in ("Skilled", "Magic Initiate"):
        assert is_feat_repeatable(feat_lookup_2024.get(feat_name.lower()), feat_name) is True

    hero = {
        "char_id": "repeatable_2024",
        "owner_id": "u_qa",
        "char_name": "Versatile Hero",
        "char_class": "Fighter",
        "subclass": "Champion",
        "char_level": 3,
        "classes": [{"class_name": "Fighter", "level": 3, "subclass": "Champion"}],
        "race": "Human",
        "background": "Sage",
        "dnd_edition": EDITION_2024,
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        "base_stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        "hp_max": 31,
        "hp_current": 31,
        "features_traits": [
            {"name": "Origin Feat: Skilled", "description": "3 skills", "source": "Origin Feat"},
            {
                "name": "Origin Feat: Magic Initiate (Wizard)",
                "description": "Spells",
                "source": "Origin Feat",
            },
        ],
        "version": 1,
    }

    analysis = analyze_level_up(copy.deepcopy(hero), user_choices={"level_up_class": "Fighter"})
    feat_choices = [c for c in analysis["choices_required"] if c["type"] == "feat"]
    assert feat_choices
    assert "Skilled" in feat_choices[0]["options"]
    assert "Magic Initiate" in feat_choices[0]["options"]

    db = _AsyncDB("repeatable_2024_db")
    db._db["characters"].insert_one(copy.deepcopy(hero))
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_qa", "username": "qa"}
    limiter.reset()
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": hero["char_id"],
                "analysis": analysis,
                "user_choices": {"level_up_class": "Fighter", "feat_0": "Skilled"},
            },
        )
        assert resp.status_code == 200
        updated = resp.json()
        skilled_entries = [
            f
            for f in updated.get("features_traits", [])
            if "skilled" in (f.get("name") or "").lower()
        ]
        assert len(skilled_entries) == 2

        _, issues = deterministic_validate_build(updated)
        assert not any("skilled" in i.lower() or "duplicate" in i.lower() for i in issues)
    finally:
        app.dependency_overrides = orig
        limiter.reset()


def test_2014_half_feats_stat_validation_and_case_insensitive_spell_dedup():
    """2014 half-feats expose stat metadata, accept lowercase stats, reject missing/invalid picks with 400, and dedup spells case-insensitively."""
    from backend.services.forge_service import analyze_level_up

    hero_2014 = {
        "char_id": "sorc_2014_half",
        "owner_id": "u_qa",
        "char_name": "Kaelen",
        "char_class": "Sorcerer",
        "subclass": "Draconic Bloodline",
        "char_level": 7,
        "classes": [{"class_name": "Sorcerer", "level": 7, "subclass": "Draconic Bloodline"}],
        "race": "Human",
        "background": "Sage",
        "dnd_edition": EDITION_2014,
        "stats": {"STR": 8, "DEX": 14, "CON": 15, "INT": 12, "WIS": 12, "CHA": 16},
        "base_stats": {"STR": 8, "DEX": 14, "CON": 15, "INT": 12, "WIS": 12, "CHA": 16},
        "hp_max": 47,
        "hp_current": 47,
        "spells": {"level_1": ["magic missile"], "level_3": ["fireball"]},
        "prepared_spells": [],
        "version": 1,
    }

    analysis = analyze_level_up(
        copy.deepcopy(hero_2014), user_choices={"level_up_class": "Sorcerer"}
    )
    feat_choices = [c for c in analysis["choices_required"] if c["type"] == "feat"]
    assert feat_choices
    meta = feat_choices[0]["feat_metadata"]
    assert meta["Resilient"]["has_stat_choice"] is True
    assert len(meta["Resilient"]["stat_choice_options"]) == 6
    assert meta["Observant"]["has_stat_choice"] is True
    assert meta["Observant"]["stat_choice_options"] == ["INT", "WIS"]

    db = _AsyncDB("half_feats_2014_db")
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_qa", "username": "qa"}
    limiter.reset()
    try:
        client = TestClient(app)

        invalid_payloads = [
            {"level_up_class": "Sorcerer", "feat_0": "+2 to one Stat"},
            {"level_up_class": "Sorcerer", "feat_0": "+2 to one Stat", "feat_stat1_0": "XYZ"},
            {"level_up_class": "Sorcerer", "feat_0": "+1 to two Stats", "feat_stat1_0": "CHA"},
            {
                "level_up_class": "Sorcerer",
                "feat_0": "+1 to two Stats",
                "feat_stat1_0": "CHA",
                "feat_stat2_0": "FOO",
            },
            {"level_up_class": "Sorcerer", "feat_0": "Resilient"},
            {"level_up_class": "Sorcerer", "feat_0": "Resilient", "feat_stat1_0": "XYZ"},
            {"level_up_class": "Sorcerer", "feat_0": "Observant", "feat_stat1_0": "STR"},
        ]
        for bad_choices in invalid_payloads:
            db._db["characters"].replace_one(
                {"char_id": hero_2014["char_id"]}, copy.deepcopy(hero_2014), upsert=True
            )
            resp = client.post(
                "/api/v1/forge/level-up-apply",
                json={
                    "character_id": hero_2014["char_id"],
                    "analysis": analysis,
                    "user_choices": bad_choices,
                },
            )
            assert resp.status_code == 400, (
                f"Expected 400 for {bad_choices}, got {resp.status_code}: {resp.text}"
            )

        # Lowercase 'con' on Resilient succeeds and bumps CON 15 -> 16; Fireball dedups case-insensitively on level_3
        db._db["characters"].replace_one(
            {"char_id": hero_2014["char_id"]}, copy.deepcopy(hero_2014), upsert=True
        )
        ok_analysis = copy.deepcopy(analysis)
        spell_idx = len(ok_analysis["choices_required"])
        ok_analysis["choices_required"].append(
            {"type": "spell", "label": "Learn 1 Level 3 spell", "options": ["Fireball"]}
        )
        resp_ok = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": hero_2014["char_id"],
                "analysis": ok_analysis,
                "user_choices": {
                    "level_up_class": "Sorcerer",
                    "feat_0": "Resilient",
                    "feat_stat1_0": "con",
                    f"spell_{spell_idx}": "Fireball",
                },
            },
        )
        assert resp_ok.status_code == 200
        body = resp_ok.json()
        assert body["stats"]["CON"] == 16
        assert [s.lower() for s in body["spells"]["level_3"]].count("fireball") == 1
        assert "Fireball" in body["prepared_spells"]
    finally:
        app.dependency_overrides = orig
        limiter.reset()


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_heavy_armor_strength_penalty_and_exemptions_both_editions(edition):
    """Low STR heavy armor applies -10 ft speed penalty unless immune (2014 Dwarf / Boots / Gauntlets) and logs audit notice."""
    from backend.services.rules_service import autofix_character_build

    base_stats = {"STR": 10, "DEX": 12, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10}
    hero_plate = {
        "char_name": "Sir Heavy",
        "race": "Human",
        "char_class": "Fighter",
        "char_level": 5,
        "background": "Soldier",
        "dnd_edition": edition,
        "base_speed": 30,
        "stats": dict(base_stats),
        "saving_throws": ["STR", "CON"],
        "skill_proficiencies": ["Athletics", "Perception"],
        "equipment": [{"name": "Plate Armor", "type": "Armor", "equipped": True, "quantity": 1}],
        "weapons": [],
        "features_traits": [
            {"name": "Defense", "source": "Class", "description": "Fighting style."}
        ],
    }
    penalized = sync_character_stats(copy.deepcopy(hero_plate))
    assert penalized["heavy_armor_speed_penalty"] == 10
    assert penalized["speed"] == 20

    # Audit surfaces informative suggestion about Plate Armor STR 15 requirement
    audit = autofix_character_build(copy.deepcopy(hero_plate))
    suggestions = " ".join(audit["validation_result"].get("suggestions", []))
    assert "Plate Armor" in suggestions
    assert "15" in suggestions

    # Chain Mail has min_str 13: STR 12 -> -10 ft; STR 13 -> 0 penalty
    hero_chain = copy.deepcopy(hero_plate)
    hero_chain["equipment"] = [
        {"name": "Chain Mail", "type": "Armor", "equipped": True, "quantity": 1}
    ]
    assert (
        sync_character_stats({**hero_chain, "stats": {**base_stats, "STR": 12}})[
            "heavy_armor_speed_penalty"
        ]
        == 10
    )
    assert (
        sync_character_stats({**hero_chain, "stats": {**base_stats, "STR": 13}})[
            "heavy_armor_speed_penalty"
        ]
        == 0
    )

    # Gauntlets of Ogre Power raise STR to 19 -> clears Plate Armor penalty
    with_gauntlets = copy.deepcopy(hero_plate)
    with_gauntlets["equipment"].append(
        {
            "name": "Gauntlets of Ogre Power",
            "type": "Wondrous Item",
            "equipped": True,
            "quantity": 1,
        }
    )
    gauntlets_synced = sync_character_stats(with_gauntlets)
    assert gauntlets_synced["stats"]["STR"] == 19
    assert gauntlets_synced["heavy_armor_speed_penalty"] == 0
    assert gauntlets_synced["speed"] == 30

    # Boots of Striding and Springing exempt low-STR wearer from Heavy Armor penalty
    with_boots = copy.deepcopy(hero_plate)
    with_boots["equipment"].append(
        {
            "name": "Boots of Striding and Springing",
            "type": "Wondrous Item",
            "equipped": True,
            "quantity": 1,
        }
    )
    boots_synced = sync_character_stats(with_boots)
    assert boots_synced["heavy_armor_speed_penalty"] == 0
    assert boots_synced["speed"] == 30

    # Dwarf exemption applies in 2014 (base speed 25 -> stays 25), NOT 2024 (base speed 30 -> 20)
    dwarf_hero = {
        **copy.deepcopy(hero_plate),
        "race": "Dwarf",
        "base_speed": 25 if edition == EDITION_2014 else 30,
    }
    dwarf_synced = sync_character_stats(dwarf_hero)
    if edition == EDITION_2014:
        assert dwarf_synced["heavy_armor_speed_penalty"] == 0
        assert dwarf_synced["speed"] == 25
    else:
        assert dwarf_synced["heavy_armor_speed_penalty"] == 10
        assert dwarf_synced["speed"] == 20


def test_2024_epic_boons_unlocked_at_l19_and_edition_isolated():
    """All 12 Epic Boons unlock at L19 in 2024 with stat cap 30, +40 HP Fortitude, +30 ft Speed; absent in 2014 and L16."""
    from backend.services.forge_service import analyze_level_up

    feats_2024 = {f["name"] for f in RulesRepository().get_all_feats(EDITION_2024)}
    expected_boons = {
        "Boon of Combat Prowess",
        "Boon of Dimensional Travel",
        "Boon of Energy Resistance",
        "Boon of Fate",
        "Boon of Fortitude",
        "Boon of Irresistible Offense",
        "Boon of Recovery",
        "Boon of Skill",
        "Boon of Speed",
        "Boon of Spell Recall",
        "Boon of the Night Spirit",
        "Boon of Truesight",
    }
    assert expected_boons.issubset(feats_2024)

    def _fighter(level: int, edition: str) -> dict:
        return {
            "char_id": f"boon-hero-{level}-{edition[:4]}",
            "owner_id": "u_qa",
            "char_name": "Astra",
            "race": "Human",
            "char_class": "Fighter",
            "subclass": "Champion",
            "char_level": level,
            "classes": [{"class_name": "Fighter", "level": level, "subclass": "Champion"}],
            "background": "Soldier",
            "dnd_edition": edition,
            "stats": {"STR": 20, "DEX": 14, "CON": 20, "INT": 10, "WIS": 12, "CHA": 10},
            "base_stats": {"STR": 20, "DEX": 14, "CON": 20, "INT": 10, "WIS": 12, "CHA": 10},
            "hp_max": 180,
            "hp_current": 180,
            "saving_throws": ["STR", "CON"],
            "skill_proficiencies": ["Athletics", "Perception"],
            "features_traits": [],
            "equipment": [],
        }

    # L15 -> L16 (2024 ASI level) must NOT offer Epic Boons yet
    l16_analysis = analyze_level_up(_fighter(15, EDITION_2024))
    l16_feat_opts = next(c for c in l16_analysis["choices_required"] if c["type"] == "feat")[
        "options"
    ]
    assert "Boon of Fortitude" not in l16_feat_opts

    # L18 -> L19 (2014 Edition) must NOT offer 2024 Epic Boons
    l19_2014_analysis = analyze_level_up(_fighter(18, EDITION_2014))
    l19_2014_opts = next(c for c in l19_2014_analysis["choices_required"] if c["type"] == "feat")[
        "options"
    ]
    assert "Boon of Fortitude" not in l19_2014_opts

    # L18 -> L19 (2024 Edition) MUST offer all 12 Epic Boons with metadata
    hero_l18 = _fighter(18, EDITION_2024)
    l19_analysis = analyze_level_up(hero_l18)
    l19_feat_choice = next(c for c in l19_analysis["choices_required"] if c["type"] == "feat")
    assert expected_boons.issubset(set(l19_feat_choice["options"]))
    assert l19_feat_choice["feat_metadata"]["Boon of Fortitude"]["flat_hp_bonus"] == 40

    # Live preview & apply Boon of Fortitude (+1 CON to 21, +40 flat HP)
    preview = analyze_level_up(
        copy.deepcopy(hero_l18),
        user_choices={
            "level_up_class": "Fighter",
            "feat_0": "Boon of Fortitude",
            "feat_stat1_0": "CON",
        },
    )
    assert (
        preview["new_total_hp"] >= hero_l18["hp_max"] + 51
    )  # 6 (d10 avg) + 5 (CON) + 40 (Fortitude)

    db = _AsyncDB("epic_boons_db")
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_qa", "username": "qa"}
    limiter.reset()
    try:
        client = TestClient(app)
        db._db["characters"].replace_one(
            {"char_id": hero_l18["char_id"]}, copy.deepcopy(hero_l18), upsert=True
        )
        resp = client.post(
            "/api/v1/forge/level-up-apply",
            json={
                "character_id": hero_l18["char_id"],
                "analysis": preview,
                "user_choices": {
                    "level_up_class": "Fighter",
                    "feat_0": "Boon of Fortitude",
                    "feat_stat1_0": "CON",
                },
            },
        )
        assert resp.status_code == 200, resp.text
        updated = resp.json()
        assert updated["char_level"] == 19
        assert updated["stats"]["CON"] == 21  # Exceeds 20 via Epic Boon cap 30
        assert updated["hp_max"] >= hero_l18["hp_max"] + 51
    finally:
        app.dependency_overrides = orig
        limiter.reset()

    # Boon of Speed grants +30 ft walking speed via sync_character_stats
    speed_hero = _fighter(19, EDITION_2024)
    speed_hero["base_speed"] = 30
    speed_hero["features_traits"] = [
        {"name": "Boon of Speed", "source": "Feat", "description": "Speed +30 ft."}
    ]
    assert sync_character_stats(speed_hero)["speed"] == 60


@pytest.mark.parametrize(
    "edition,char_class,subclass,expected_feature",
    [
        (EDITION_2014, "Fighter", "Champion", "Improved Critical"),
        (EDITION_2024, "Sorcerer", "Draconic Sorcery", "Draconic Resilience"),
    ],
)
def test_forge_character_manual_resolves_concrete_subclass_features(
    edition, char_class, subclass, expected_feature
):
    """Creating a high-level character via forge_character_manual resolves concrete subclass feature names rather than placeholders."""
    from backend.services.forge_service import forge_character_manual

    mock_ai = {
        "char_name": "Manual Subclass Hero",
        "backstory": "Veteran adventurer.",
        "features_traits": [],
        "equipment": [],
        "weapons": [],
    }
    with patch("backend.services.forge_service.generate_ai_json", return_value=mock_ai):
        char = forge_character_manual(
            target_level=15,
            race="Human",
            char_class=char_class,
            background="Soldier",
            subclass=subclass,
            alignment="Neutral Good",
            gender="Non-binary",
            name="Manual Subclass Hero",
            base_stats={"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 16},
            skill_proficiencies=["Athletics", "Perception"],
            saving_throws=["STR", "CON"],
            spell_ability="CHA" if char_class == "Sorcerer" else None,
            concept="High level test",
            edition=edition,
            auto_spells=False,
            auto_feats=False,
        )

    names = [f["name"] for f in char.get("features_traits", [])]
    assert any(expected_feature in n for n in names)
    assert all("Subclass Feature" not in n and f"{char_class} Subclass" not in n for n in names)


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_medium_armor_mithral_and_armorer_never_penalized_and_validate_surfaces_suggestions(
    edition,
):
    """Medium armor (Breastplate, Half Plate, Half Plate +1), Mithral armor, Ring Mail, and Armorer Artificer have zero STR penalty; /rules/validate returns audit suggestions."""
    base_hero = {
        "char_name": "Medium Wearer",
        "race": "Human",
        "char_class": "Fighter",
        "char_level": 5,
        "background": "Soldier",
        "dnd_edition": edition,
        "base_speed": 30,
        "stats": {"STR": 10, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
        "saving_throws": ["STR", "CON"],
        "skill_proficiencies": ["Athletics", "Perception"],
        "weapons": [],
        "features_traits": [],
    }

    for armor_name in (
        "Breastplate",
        "Half Plate",
        "Half Plate +1",
        "Mithral Plate Armor",
        "Ring Mail",
    ):
        synced = sync_character_stats(
            {
                **copy.deepcopy(base_hero),
                "equipment": [
                    {"name": armor_name, "type": "Armor", "equipped": True, "quantity": 1}
                ],
            }
        )
        assert synced["heavy_armor_speed_penalty"] == 0, f"{armor_name} falsely penalized"
        assert synced["speed"] == 30, f"{armor_name} reduced speed"

    # Splint Armor and Plate Armor +1 trigger -10 ft at STR 10
    for heavy_name in ("Splint Armor", "Plate Armor +1"):
        synced_heavy = sync_character_stats(
            {
                **copy.deepcopy(base_hero),
                "equipment": [
                    {"name": heavy_name, "type": "Armor", "equipped": True, "quantity": 1}
                ],
            }
        )
        assert synced_heavy["heavy_armor_speed_penalty"] == 10
        assert synced_heavy["speed"] == 20

    # Armorer Artificer waives Heavy Armor STR requirement
    armorer = sync_character_stats(
        {
            **copy.deepcopy(base_hero),
            "char_class": "Artificer",
            "subclass": "Armorer",
            "classes": [{"class_name": "Artificer", "level": 5, "subclass": "Armorer"}],
            "equipment": [
                {"name": "Plate Armor", "type": "Armor", "equipped": True, "quantity": 1}
            ],
            "features_traits": [
                {"name": "Arcane Armor", "source": "Subclass", "description": "No STR req."}
            ],
        }
    )
    assert armorer["heavy_armor_speed_penalty"] == 0
    assert armorer["speed"] == 30

    # POST /api/v1/rules/validate returns Heavy Armor STR notice in suggestions
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: {"id": "u_qa", "username": "qa"}
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/rules/validate",
            json={
                "character": {
                    **copy.deepcopy(base_hero),
                    "equipment": [
                        {"name": "Plate Armor", "type": "Armor", "equipped": True, "quantity": 1}
                    ],
                }
            },
        )
        assert resp.status_code == 200
        suggestions = " ".join(resp.json()["validation_result"].get("suggestions", []))
        assert "Plate Armor" in suggestions
        assert "15" in suggestions
    finally:
        app.dependency_overrides = orig


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_warlock_third_caster_and_multiclass_inject_grants(edition):
    """Eldritch Knight / Warlock tracks separate pact slots; inject_mandatory_character_grants respects per-class levels."""
    from backend.services.rules_service import inject_mandatory_character_grants

    ek_lock = sync_character_stats(
        {
            "char_name": "Hexknight",
            "race": "Human",
            "char_class": "Fighter",
            "subclass": "Eldritch Knight",
            "char_level": 10,
            "classes": [
                {"class_name": "Fighter", "level": 7, "subclass": "Eldritch Knight"},
                {"class_name": "Warlock", "level": 3, "subclass": "Fiend Patron"},
            ],
            "dnd_edition": edition,
            "stats": {"STR": 16, "DEX": 12, "CON": 14, "INT": 14, "WIS": 10, "CHA": 16},
            "features_traits": [],
            "equipment": [],
        }
    )
    assert ek_lock["spell_slots"]["pact"] == {"max": 2, "used": 0, "level": 2}
    assert ek_lock["spell_slots"]["level_2"]["pact_max"] == 2

    # Paladin 5 / Sorcerer 3 (total level 8) must NOT receive Paladin Level 6/7/8 features (e.g. Aura of Protection)
    sorc_sub = "Draconic Sorcery" if "2024" in edition else "Draconic Bloodline"
    mc = inject_mandatory_character_grants(
        {
            "char_name": "Valkor",
            "race": "Human",
            "background": "Soldier",
            "char_class": "Paladin",
            "subclass": "Oath of Devotion",
            "char_level": 8,
            "classes": [
                {"class_name": "Paladin", "level": 5, "subclass": "Oath of Devotion"},
                {"class_name": "Sorcerer", "level": 3, "subclass": sorc_sub},
            ],
            "dnd_edition": edition,
            "features_traits": [],
        },
        edition=edition,
        is_forge=False,
    )
    feat_names = {f["name"].lower() for f in mc["features_traits"]}
    assert "extra attack" in feat_names
    assert "font of magic" in feat_names
    assert "aura of protection" not in feat_names
    expected_sorc_sub = "draconic resilience" if "2024" in edition else "draconic bloodline"
    assert any(expected_sorc_sub in n for n in feat_names)


def test_parse_character_from_text_preserves_boon_of_fortitude_hp():
    """Imported Level 19 2024 sheets with Boon of Fortitude (+40 HP) keep valid HP without stripping or double-adding."""
    from backend.services.rules_service import parse_character_from_text

    # Fighter 19, CON 20 (+5) -> max legal die HP = 19 * (10+5) = 285, plus +40 Boon of Fortitude = 325
    step1 = {
        "char_name": "Apex Bastion",
        "char_class": "Fighter",
        "subclass": "Champion",
        "char_level": 19,
        "classes": [{"class_name": "Fighter", "level": 19, "subclass": "Champion"}],
        "race": "Human",
        "background": "Soldier",
        "hp_max": 300,
        "hp_current": 300,
        "stats": {"STR": 20, "DEX": 14, "CON": 20, "INT": 10, "WIS": 12, "CHA": 10},
        "skill_proficiencies": ["Athletics", "Perception"],
        "saving_throws": ["STR", "CON"],
        "features_traits": [
            {
                "name": "Boon of Fortitude",
                "source": "Feat",
                "description": "Hit Point Maximum increases by 40.",
            }
        ],
    }
    step2 = {"weapons": [], "equipment": [], "spells": {}}
    with patch("backend.services.rules_service.generate_ai_json", side_effect=[step1, step2]):
        parsed = parse_character_from_text("Sheet text", edition=EDITION_2024)

    assert parsed["hp_max"] == 300
    assert parsed["feat_hp_bonus"] == 40
