import io
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

    async def count_documents(self, query=None):
        return self._coll.count_documents(query or {})

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
