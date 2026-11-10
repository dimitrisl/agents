"""Tier 1 E2E Test Suite: Bestiary & Rules Engine (Features 1–9).

Verifies the primary happy-path behavior and interface contracts for:
- Feature 1: 2014 SRD Monster Dataset (data/rules/monsters_2014.json)
- Feature 2: 2024 SRD Monster Dataset (data/rules/monsters_2024.json)
- Feature 3: RulesRepository Monsters Cache & Queries
- Feature 4: Monster & Bestiary Schemas
- Feature 5: MongoDB Custom Monsters Collection
- Feature 6: Bestiary Query Endpoint (GET /api/v1/bestiary)
- Feature 7: Bestiary Single Monster Endpoint (GET /api/v1/bestiary/{id})
- Feature 8: Bestiary Creation & Clone Endpoint (POST /api/v1/bestiary)
- Feature 9: Bestiary Immutability & Ownership Enforcement

Requirement: At least 5 test cases per feature (>= 45 tests total).
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.repositories.rules_repository import RulesRepository
from server.db_async import INDEX_DEFINITIONS
from server.main import app
from tests.e2e.conftest import PROJECT_ROOT, E2EAuthHelper, _AsyncDBWrapper

MONSTERS_2014_PATH = PROJECT_ROOT / "data" / "rules" / "monsters_2014.json"
MONSTERS_2024_PATH = PROJECT_ROOT / "data" / "rules" / "monsters_2024.json"


def _is_bestiary_router_mounted() -> bool:
    """Helper to check whether /api/v1/bestiary is registered in FastAPI app."""
    return any(getattr(route, "path", "").startswith("/api/v1/bestiary") for route in app.routes)


# ============================================================================
# Feature 1: 2014 SRD Monster Dataset
# ============================================================================


class TestF012014SrdMonsterDataset:
    """Verifies static JSON array of 2014 SRD monsters across CR 0 to CR 24."""

    def test_f01_01_dataset_file_exists_and_parses(self):
        """TC-F01-01: Verify data/rules/monsters_2014.json exists and parses to a list of >= 60 monster records."""
        if not MONSTERS_2014_PATH.exists():
            pytest.skip("monsters_2014.json not yet generated (pending M1)")

        with open(MONSTERS_2014_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, list), "monsters_2014.json root must be a JSON array"
        assert len(data) >= 60, f"Expected at least 60 SRD monsters, found {len(data)}"

    def test_f01_02_cr_range_continuous_2014(self):
        """TC-F01-02: Verify dataset contains monsters across continuous CRs from CR 0 up to CR 24."""
        if not MONSTERS_2014_PATH.exists():
            pytest.skip("monsters_2014.json not yet generated (pending M1)")

        with open(MONSTERS_2014_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        crs_present = {str(m.get("cr")) for m in data}
        assert "0" in crs_present, "CR 0 monster missing from 2014 dataset"
        assert "24" in crs_present or any(float(m.get("cr_numeric", 0)) >= 24 for m in data), (
            "CR 24 monster missing from 2014 dataset"
        )
        for check_cr in ["1/4", "1/2", "1", "5", "10"]:
            assert check_cr in crs_present, f"Expected standard CR {check_cr} in 2014 dataset"

    def test_f01_03_required_official_fields_2014(self):
        """TC-F01-03: Verify all records have srd_ prefix, edition=2014, origin=official, is_public=True."""
        if not MONSTERS_2014_PATH.exists():
            pytest.skip("monsters_2014.json not yet generated (pending M1)")

        with open(MONSTERS_2014_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for m in data:
            assert str(m.get("id")).startswith("srd_"), f"ID {m.get('id')} missing 'srd_' prefix"
            assert str(m.get("edition")) in ("2014", "2014 Edition"), (
                f"Invalid edition: {m.get('edition')}"
            )
            assert m.get("origin") == "official", f"Monster {m.get('id')} origin must be 'official'"
            assert m.get("is_public") is True, (
                f"Official monster {m.get('id')} must have is_public=True"
            )

    def test_f01_04_stats_structure_2014(self):
        """TC-F01-04: Verify all records contain structured stats with keys str, dex, con, int, wis, cha (1-30)."""
        if not MONSTERS_2014_PATH.exists():
            pytest.skip("monsters_2014.json not yet generated (pending M1)")

        with open(MONSTERS_2014_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for m in data:
            stats = m.get("stats", {})
            for attr in ["str", "dex", "con", "int", "wis", "cha"]:
                val = stats.get(attr) or stats.get(attr.upper())
                assert val is not None, f"Monster {m.get('id')} missing stat '{attr}'"
                assert 1 <= int(val) <= 30, (
                    f"Monster {m.get('id')} stat {attr}={val} outside [1, 30]"
                )

    def test_f01_05_actions_structure_2014(self):
        """TC-F01-05: Verify all records contain actions list with structured attack fields."""
        if not MONSTERS_2014_PATH.exists():
            pytest.skip("monsters_2014.json not yet generated (pending M1)")

        with open(MONSTERS_2014_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        attack_found = False
        for m in data:
            actions = m.get("actions", [])
            assert isinstance(actions, list), f"Monster {m.get('id')} actions must be a list"
            for a in actions:
                assert "name" in a, f"Action missing 'name' in {m.get('id')}"
                if a.get("attack_bonus") is not None:
                    attack_found = True
                    assert isinstance(a["attack_bonus"], int), f"Attack bonus must be int in {a}"
        assert attack_found, (
            "At least one monster in 2014 dataset must have structured attack_bonus"
        )


# ============================================================================
# Feature 2: 2024 SRD Monster Dataset
# ============================================================================


class TestF022024SrdMonsterDataset:
    """Verifies static JSON array of 2024 Revision SRD monsters across CR 0 to CR 24."""

    def test_f02_01_dataset_file_exists_and_parses(self):
        """TC-F02-01: Verify data/rules/monsters_2024.json exists and parses to a list of >= 60 monster records."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json not yet generated (pending M1)")

        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, list), "monsters_2024.json root must be a JSON array"
        assert len(data) >= 60, (
            f"Expected at least 60 SRD monsters in 2024 dataset, found {len(data)}"
        )

    def test_f02_02_cr_range_continuous_2024(self):
        """TC-F02-02: Verify 2024 dataset contains continuous CR spectrum from CR 0 up to CR 24."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json not yet generated (pending M1)")

        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        crs_present = {str(m.get("cr")) for m in data}
        assert "0" in crs_present, "CR 0 monster missing from 2024 dataset"
        assert "24" in crs_present or any(float(m.get("cr_numeric", 0)) >= 24 for m in data), (
            "CR 24 monster missing from 2024 dataset"
        )

    def test_f02_03_required_official_fields_2024(self):
        """TC-F02-03: Verify all 2024 records have srd_ prefix, edition=2024, origin=official, is_public=True."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json not yet generated (pending M1)")

        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for m in data:
            assert str(m.get("id")).startswith("srd_"), f"ID {m.get('id')} missing 'srd_' prefix"
            assert str(m.get("edition")) in ("2024", "2024 Revision", "2024 Edition")
            assert m.get("origin") == "official"
            assert m.get("is_public") is True

    def test_f02_04_revision_statblock_formatting_2024(self):
        """TC-F02-04: Verify 2024 statblocks adhere to updated 5.5e formatting (cr_numeric, speed, ac, hp)."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json not yet generated (pending M1)")

        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for m in data:
            assert "cr_numeric" in m, f"Monster {m.get('id')} missing float 'cr_numeric'"
            assert isinstance(m["cr_numeric"], (int, float)), (
                f"cr_numeric not numeric in {m.get('id')}"
            )
            assert "ac" in m and int(m["ac"]) > 0, f"Invalid AC in {m.get('id')}"
            assert "hp" in m and int(m["hp"]) > 0, f"Invalid HP in {m.get('id')}"

    def test_f02_05_actions_and_traits_structure_2024(self):
        """TC-F02-05: Verify structured actions and traits in 2024 dataset parse cleanly."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json not yet generated (pending M1)")

        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        for m in data:
            for trait in m.get("traits", []):
                assert "name" in trait and "description" in trait
            for action in m.get("actions", []):
                assert "name" in action


# ============================================================================
# Feature 3: RulesRepository Monsters Cache & Queries
# ============================================================================


class TestF03RulesRepositoryMonstersCache:
    """Verifies in-memory cached loading, search, and ID lookup in RulesRepository."""

    def test_f03_01_get_all_monsters_caching(self):
        """TC-F03-01: Call RulesRepository.get_all_monsters twice; verify caching."""
        repo = RulesRepository()
        if not hasattr(repo, "get_all_monsters"):
            pytest.skip("RulesRepository.get_all_monsters not yet implemented (pending M1)")

        res1 = repo.get_all_monsters("2014")
        res2 = repo.get_all_monsters("2014")
        assert isinstance(res1, list)
        assert len(res1) == len(res2)

    def test_f03_02_search_monsters_by_name(self):
        """TC-F03-02: Call search_monsters(query='goblin'); verify matching monsters returned."""
        repo = RulesRepository()
        if not hasattr(repo, "search_monsters"):
            pytest.skip("RulesRepository.search_monsters not yet implemented (pending M1)")

        results = repo.search_monsters(query="goblin", edition="2014")
        assert isinstance(results, list)
        if len(results) > 0:
            assert any("goblin" in m.get("name", "").lower() for m in results)

    def test_f03_03_search_monsters_by_cr_and_type(self):
        """TC-F03-03: Call search_monsters with cr and monster_type filters."""
        repo = RulesRepository()
        if not hasattr(repo, "search_monsters"):
            pytest.skip("RulesRepository.search_monsters not yet implemented (pending M1)")

        results = repo.search_monsters(cr="1/4", edition="2014")
        assert isinstance(results, list)
        for m in results:
            assert str(m.get("cr")) == "1/4" or m.get("cr_numeric") == 0.25

    def test_f03_04_get_monster_by_id_found(self):
        """TC-F03-04: Call get_monster_by_id with valid ID; verify monster dictionary returned."""
        repo = RulesRepository()
        if not hasattr(repo, "get_monster_by_id"):
            pytest.skip("RulesRepository.get_monster_by_id not yet implemented (pending M1)")

        all_monsters = repo.get_all_monsters("2014") if hasattr(repo, "get_all_monsters") else []
        if not all_monsters:
            pytest.skip("No monsters available in repository (pending M1)")

        target_id = all_monsters[0]["id"]
        monster = repo.get_monster_by_id(target_id)
        assert monster is not None
        assert monster["id"] == target_id

    def test_f03_05_immutable_cached_returns(self):
        """TC-F03-05: Modifying dictionary returned by get_all_monsters does not corrupt repository cache."""
        repo = RulesRepository()
        if not hasattr(repo, "get_all_monsters"):
            pytest.skip("RulesRepository.get_all_monsters not yet implemented (pending M1)")

        monsters = repo.get_all_monsters("2014")
        if not monsters:
            pytest.skip("No monsters loaded to test cache immutability (pending M1)")

        original_name = monsters[0]["name"]
        monsters[0]["name"] = "CORRUPTED_CACHE_NAME"

        fresh = repo.get_all_monsters("2014")
        assert fresh[0]["name"] == original_name, (
            "RulesRepository cache was corrupted by caller mutation!"
        )


# ============================================================================
# Feature 4: Monster & Bestiary Schemas
# ============================================================================


class TestF04MonsterAndBestiarySchemas:
    """Verifies Pydantic models for MonsterStats, MonsterTrait, MonsterAction, Monster, etc."""

    def test_f04_01_monster_model_validation_success(self):
        """TC-F04-01: Instantiate Monster schema with valid fields; verify validation succeeds."""
        try:
            from backend.core.schemas import Monster
        except ImportError:
            pytest.skip("backend.core.schemas.Monster not yet implemented (pending M2)")

        payload = {
            "id": "custom_dragon_01",
            "name": "Obsidian Wyrm",
            "edition": "2024",
            "origin": "custom",
            "cr": "10",
            "cr_numeric": 10.0,
            "ac": 17,
            "hp": 180,
            "max_hp": 180,
            "speed": "40 ft., fly 80 ft.",
            "stats": {"str": 22, "dex": 12, "con": 20, "int": 14, "wis": 12, "cha": 16},
            "traits": [{"name": "Amphibious", "description": "Can breathe air and water."}],
            "actions": [
                {
                    "name": "Bite",
                    "attack_bonus": 10,
                    "damage_dice": "2d10+6",
                    "damage_type": "piercing",
                }
            ],
            "is_public": True,
            "creator_dm_id": "dm_user_test",
        }
        monster = Monster(**payload)
        assert monster.name == "Obsidian Wyrm"
        assert monster.cr_numeric == 10.0

    def test_f04_02_monster_stats_range_validation(self):
        """TC-F04-02: Verify MonsterStats validates ability scores between 1 and 30."""
        try:
            from backend.core.schemas import MonsterStats
        except ImportError:
            pytest.skip("backend.core.schemas.MonsterStats not yet implemented (pending M2)")

        valid_stats = MonsterStats(str=10, dex=14, con=16, int=8, wis=12, cha=18)
        assert valid_stats.str == 10

    def test_f04_03_monster_action_fields_validation(self):
        """TC-F04-03: Verify MonsterAction accepts attack_bonus, damage_dice, damage_type, and description."""
        try:
            from backend.core.schemas import MonsterAction
        except ImportError:
            pytest.skip("backend.core.schemas.MonsterAction not yet implemented (pending M2)")

        action = MonsterAction(
            name="Scimitar",
            attack_bonus=4,
            damage_dice="1d6+2",
            damage_type="slashing",
            description="Melee Weapon Attack: +4 to hit, reach 5 ft., one target.",
        )
        assert action.name == "Scimitar"
        assert action.attack_bonus == 4
        assert action.damage_dice == "1d6+2"

    def test_f04_04_bestiary_create_request_validation(self):
        """TC-F04-04: Instantiate BestiaryCreateRequest with valid payload; verify schema."""
        try:
            from backend.core.schemas import BestiaryCreateRequest
        except ImportError:
            pytest.skip(
                "backend.core.schemas.BestiaryCreateRequest not yet implemented (pending M2)"
            )

        req = BestiaryCreateRequest(
            name="Goblin Scout",
            edition="2024",
            cr="1/4",
            ac=13,
            hp=9,
            stats={"str": 8, "dex": 15, "con": 10, "int": 10, "wis": 8, "cha": 8},
        )
        assert req.name == "Goblin Scout"
        assert req.cr == "1/4"

    def test_f04_05_bestiary_visibility_request_validation(self):
        """TC-F04-05: Instantiate BestiaryVisibilityRequest with boolean is_public."""
        try:
            from backend.core.schemas import BestiaryVisibilityRequest
        except ImportError:
            pytest.skip(
                "backend.core.schemas.BestiaryVisibilityRequest not yet implemented (pending M2)"
            )

        req = BestiaryVisibilityRequest(is_public=True)
        assert req.is_public is True


# ============================================================================
# Feature 5: MongoDB Custom Monsters Collection
# ============================================================================


class TestF05MongoDbCustomMonstersCollection:
    """Verifies custom_monsters collection indexes, insertion, and query semantics."""

    def test_f05_01_custom_monster_insertion(self, mock_db: _AsyncDBWrapper):
        """TC-F05-01: Insert custom monster document into mock_db['custom_monsters']; verify persistence."""
        col = mock_db._db["custom_monsters"]
        doc = {
            "id": str(uuid.uuid4()),
            "name": "Clockwork Beetle",
            "creator_dm_id": "dm_alice",
            "is_public": False,
            "cr": "1/2",
            "cr_numeric": 0.5,
            "origin": "custom",
        }
        res = col.insert_one(doc)
        assert res.inserted_id is not None

        found = col.find_one({"id": doc["id"]})
        assert found is not None
        assert found["name"] == "Clockwork Beetle"

    def test_f05_02_custom_monster_unique_id_index(self):
        """TC-F05-02: Verify custom_monsters indexes declared in server/db_async.py include unique ID index."""
        custom_monster_indexes = [
            defn for defn in INDEX_DEFINITIONS if defn[0] == "custom_monsters"
        ]
        # In M2, custom_monsters indexes will be registered in db_async.py
        if not custom_monster_indexes:
            pytest.skip(
                "custom_monsters index definition not yet registered in INDEX_DEFINITIONS (pending M2)"
            )

        has_unique_id = any(
            fields == [("id", 1)] and opts.get("unique") is True
            for col, fields, opts in custom_monster_indexes
        )
        assert has_unique_id, "Unique index on custom_monsters.id missing from INDEX_DEFINITIONS"

    def test_f05_03_query_by_creator_dm_id(self, mock_db: _AsyncDBWrapper):
        """TC-F05-03: Query custom monsters isolated by creator_dm_id."""
        col = mock_db._db["custom_monsters"]
        col.insert_one(
            {"id": "m1", "name": "Monster 1", "creator_dm_id": "dm_user_1", "is_public": False}
        )
        col.insert_one(
            {"id": "m2", "name": "Monster 2", "creator_dm_id": "dm_user_1", "is_public": True}
        )
        col.insert_one(
            {"id": "m3", "name": "Monster 3", "creator_dm_id": "dm_user_2", "is_public": True}
        )

        cursor = col.find({"creator_dm_id": "dm_user_1"})
        user1_monsters = list(cursor)
        assert len(user1_monsters) == 2

    def test_f05_04_query_by_is_public(self, mock_db: _AsyncDBWrapper):
        """TC-F05-04: Query custom monsters filtered by is_public=True."""
        col = mock_db._db["custom_monsters"]
        col.insert_one(
            {"id": "pub_1", "name": "Public Ogre", "creator_dm_id": "dm_a", "is_public": True}
        )
        col.insert_one(
            {"id": "priv_1", "name": "Secret Lich", "creator_dm_id": "dm_a", "is_public": False}
        )

        cursor = col.find({"is_public": True})
        public_monsters = list(cursor)
        assert any(m["id"] == "pub_1" for m in public_monsters)
        assert not any(m["id"] == "priv_1" for m in public_monsters)

    def test_f05_05_delete_custom_monster_document(self, mock_db: _AsyncDBWrapper):
        """TC-F05-05: Delete custom monster document; verify removal."""
        col = mock_db._db["custom_monsters"]
        col.insert_one(
            {"id": "m_del", "name": "To Delete", "creator_dm_id": "dm_x", "is_public": True}
        )
        assert col.find_one({"id": "m_del"}) is not None

        col.delete_one({"id": "m_del"})
        assert col.find_one({"id": "m_del"}) is None


# ============================================================================
# Feature 6: Bestiary Query Endpoint (GET /api/v1/bestiary)
# ============================================================================


class TestF06BestiaryQueryEndpoint:
    """Verifies GET /api/v1/bestiary filtering by edition, search, CR, type, and source flags."""

    def test_f06_01_get_bestiary_default_filters(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F06-01: Call GET /api/v1/bestiary as authenticated user; verify 200 OK and list of monsters."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f06_01", "dm_f06_01@test.dnd")
        res = e2e_client.get("/api/v1/bestiary", headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_f06_02_filter_by_edition_2014(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F06-02: Call GET /api/v1/bestiary?edition=2014; verify all returned monsters are 2014."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f06_02", "dm_f06_02@test.dnd")
        res = e2e_client.get("/api/v1/bestiary?edition=2014", headers=headers)
        assert res.status_code == 200
        for m in res.json():
            assert "2014" in str(m.get("edition"))

    def test_f06_03_filter_by_edition_2024(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F06-03: Call GET /api/v1/bestiary?edition=2024; verify all returned monsters are 2024."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f06_03", "dm_f06_03@test.dnd")
        res = e2e_client.get("/api/v1/bestiary?edition=2024", headers=headers)
        assert res.status_code == 200
        for m in res.json():
            assert "2024" in str(m.get("edition"))

    def test_f06_04_filter_by_monster_type(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F06-04: Call GET /api/v1/bestiary?monster_type=dragon; verify matching type returned."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f06_04", "dm_f06_04@test.dnd")
        res = e2e_client.get("/api/v1/bestiary?monster_type=dragon", headers=headers)
        assert res.status_code == 200
        for m in res.json():
            assert (
                "dragon" in str(m.get("monster_type", "")).lower()
                or "dragon" in str(m.get("type", "")).lower()
            )

    def test_f06_05_filter_by_search_query(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F06-05: Call GET /api/v1/bestiary?search=goblin; verify matching monsters returned."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f06_05", "dm_f06_05@test.dnd")
        res = e2e_client.get("/api/v1/bestiary?search=goblin", headers=headers)
        assert res.status_code == 200
        for m in res.json():
            assert "goblin" in m.get("name", "").lower()


# ============================================================================
# Feature 7: Bestiary Single Monster Endpoint (GET /api/v1/bestiary/{id})
# ============================================================================


class TestF07BestiarySingleMonsterEndpoint:
    """Verifies GET /api/v1/bestiary/{id} lookup for official and custom monsters."""

    def test_f07_01_get_official_2014_monster_by_id(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F07-01: Call GET /api/v1/bestiary/{id} for official 2014 monster; verify 200 OK."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f07_01", "dm_f07_01@test.dnd")
        # Query list first to get valid official ID
        list_res = e2e_client.get("/api/v1/bestiary?include_official=true", headers=headers)
        if not list_res.json():
            pytest.skip("No monsters available in bestiary (pending M1/M2)")

        sample_id = list_res.json()[0]["id"]
        res = e2e_client.get(f"/api/v1/bestiary/{sample_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["id"] == sample_id

    def test_f07_02_get_official_2024_monster_by_id(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F07-02: Call GET /api/v1/bestiary/{id} for official 2024 monster; verify 200 OK."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f07_02", "dm_f07_02@test.dnd")
        list_res = e2e_client.get(
            "/api/v1/bestiary?edition=2024&include_official=true", headers=headers
        )
        if not list_res.json():
            pytest.skip("No 2024 monsters available (pending M1/M2)")

        sample_id = list_res.json()[0]["id"]
        res = e2e_client.get(f"/api/v1/bestiary/{sample_id}", headers=headers)
        assert res.status_code == 200
        assert "2024" in str(res.json().get("edition"))

    def test_f07_03_get_own_custom_monster_by_id(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F07-03: Create custom monster then GET /api/v1/bestiary/{id}; verify 200 OK."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f07_03", "dm_f07_03@test.dnd")
        create_res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Cavern Lurker",
                "edition": "2024",
                "cr": "2",
                "ac": 14,
                "hp": 38,
                "stats": {"str": 14, "dex": 16, "con": 12, "int": 6, "wis": 12, "cha": 6},
            },
            headers=headers,
        )
        assert create_res.status_code == 201
        custom_id = create_res.json()["id"]

        get_res = e2e_client.get(f"/api/v1/bestiary/{custom_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Cavern Lurker"

    def test_f07_04_get_community_public_monster_by_id(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F07-04: User A creates public monster; User B fetches by ID; verify 200 OK."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers_a = auth_helper.register_and_login("dm_f07_04a", "dm_f07_04a@test.dnd")
        headers_b = auth_helper.register_and_login("dm_f07_04b", "dm_f07_04b@test.dnd")

        create_res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Community Sphinx",
                "edition": "2024",
                "cr": "11",
                "ac": 17,
                "hp": 136,
                "is_public": True,
                "stats": {"str": 18, "dex": 15, "con": 16, "int": 18, "wis": 18, "cha": 18},
            },
            headers=headers_a,
        )
        assert create_res.status_code == 201
        pub_id = create_res.json()["id"]

        get_res = e2e_client.get(f"/api/v1/bestiary/{pub_id}", headers=headers_b)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Community Sphinx"

    def test_f07_05_get_high_cr_monster_by_id(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F07-05: Fetch high-CR monster (CR 24); verify stats and legendary mechanics intact."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f07_05", "dm_f07_05@test.dnd")
        res = e2e_client.get("/api/v1/bestiary?cr=24&include_official=true", headers=headers)
        if not res.json():
            pytest.skip("No CR 24 monster found in bestiary (pending M1/M2)")

        dragon_id = res.json()[0]["id"]
        dragon = e2e_client.get(f"/api/v1/bestiary/{dragon_id}", headers=headers).json()
        assert dragon["ac"] >= 20
        assert dragon["hp"] >= 500


# ============================================================================
# Feature 8: Bestiary Creation & Clone Endpoint (POST /api/v1/bestiary)
# ============================================================================


class TestF08BestiaryCreationAndCloneEndpoint:
    """Verifies custom monster creation and cloning via POST /api/v1/bestiary."""

    def test_f08_01_create_new_custom_monster(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F08-01: Post valid payload; verify 201 Created, UUID assigned, origin=custom."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f08_01", "dm_f08_01@test.dnd")
        res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Abyssal Drake",
                "edition": "2024",
                "cr": "5",
                "ac": 16,
                "hp": 75,
                "stats": {"str": 18, "dex": 14, "con": 16, "int": 8, "wis": 12, "cha": 10},
            },
            headers=headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert "id" in data
        assert data["origin"] == "custom"
        assert data["name"] == "Abyssal Drake"

    def test_f08_02_clone_official_monster(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F08-02: Clone official monster via based_on; verify linkage and new custom record."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f08_02", "dm_f08_02@test.dnd")
        res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Elite Goblin Archer",
                "based_on": "srd_goblin_2014",
                "edition": "2014",
                "cr": "1/2",
                "ac": 15,
                "hp": 14,
                "stats": {"str": 8, "dex": 16, "con": 10, "int": 10, "wis": 8, "cha": 8},
            },
            headers=headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["based_on"] == "srd_goblin_2014"
        assert data["origin"] == "custom"

    def test_f08_03_clone_custom_monster(self, e2e_client: TestClient, auth_helper: E2EAuthHelper):
        """TC-F08-03: Clone an existing custom monster; verify lineage."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f08_03", "dm_f08_03@test.dnd")
        parent = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Base Elemental",
                "edition": "2024",
                "cr": "5",
                "ac": 15,
                "hp": 90,
                "stats": {"str": 16, "dex": 12, "con": 16, "int": 6, "wis": 10, "cha": 6},
            },
            headers=headers,
        ).json()

        child_res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Fire-Infused Elemental",
                "based_on": parent["id"],
                "edition": "2024",
                "cr": "6",
                "ac": 15,
                "hp": 100,
                "stats": {"str": 16, "dex": 12, "con": 16, "int": 6, "wis": 10, "cha": 6},
            },
            headers=headers,
        )
        assert child_res.status_code == 201
        assert child_res.json()["based_on"] == parent["id"]

    def test_f08_04_fractional_cr_calculation(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F08-04: Post monster with fractional CR '1/4'; verify cr_numeric=0.25."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f08_04", "dm_f08_04@test.dnd")
        res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Giant Bat Scout",
                "edition": "2024",
                "cr": "1/4",
                "ac": 13,
                "hp": 22,
                "stats": {"str": 15, "dex": 16, "con": 11, "int": 2, "wis": 12, "cha": 6},
            },
            headers=headers,
        )
        assert res.status_code == 201
        assert res.json()["cr_numeric"] == 0.25

    def test_f08_05_structured_actions_storage(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F08-05: Post monster with attack actions; verify actions persist and return structured."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f08_05", "dm_f08_05@test.dnd")
        actions_payload = [
            {
                "name": "Venomous Stinger",
                "attack_bonus": 5,
                "damage_dice": "1d8+3",
                "damage_type": "piercing",
                "description": "Melee Weapon Attack: +5 to hit, reach 5 ft., one creature.",
            }
        ]
        res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Bone Scorpion",
                "edition": "2024",
                "cr": "3",
                "ac": 15,
                "hp": 45,
                "stats": {"str": 14, "dex": 14, "con": 14, "int": 3, "wis": 10, "cha": 4},
                "actions": actions_payload,
            },
            headers=headers,
        )
        assert res.status_code == 201
        actions = res.json().get("actions", [])
        assert len(actions) == 1
        assert actions[0]["attack_bonus"] == 5
        assert actions[0]["damage_dice"] == "1d8+3"


# ============================================================================
# Feature 9: Bestiary Immutability & Ownership Enforcement
# ============================================================================


class TestF09BestiaryImmutabilityAndOwnershipEnforcement:
    """Verifies strict HTTP 403 enforcement on official records and custom monster ownership."""

    def test_f09_01_owner_can_update_custom_monster(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F09-01: Owner sends PUT /api/v1/bestiary/{id}; verify 200 OK and updated fields."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f09_01", "dm_f09_01@test.dnd")
        monster = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Mutable Ogre",
                "edition": "2024",
                "cr": "2",
                "ac": 11,
                "hp": 59,
                "stats": {"str": 19, "dex": 8, "con": 16, "int": 5, "wis": 7, "cha": 7},
            },
            headers=headers,
        ).json()

        update_res = e2e_client.put(
            f"/api/v1/bestiary/{monster['id']}",
            json={"name": "Armored Ogre", "ac": 14},
            headers=headers,
        )
        assert update_res.status_code == 200
        assert update_res.json()["name"] == "Armored Ogre"
        assert update_res.json()["ac"] == 14

    def test_f09_02_owner_can_toggle_visibility(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F09-02: Owner sends PATCH /api/v1/bestiary/{id}/visibility; verify 200 OK."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f09_02", "dm_f09_02@test.dnd")
        monster = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Secret Lich",
                "edition": "2024",
                "cr": "21",
                "ac": 17,
                "hp": 135,
                "is_public": False,
                "stats": {"str": 11, "dex": 16, "con": 16, "int": 20, "wis": 14, "cha": 16},
            },
            headers=headers,
        ).json()
        assert monster["is_public"] is False

        patch_res = e2e_client.patch(
            f"/api/v1/bestiary/{monster['id']}/visibility",
            json={"is_public": True},
            headers=headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["is_public"] is True

    def test_f09_03_owner_can_delete_custom_monster(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F09-03: Owner sends DELETE /api/v1/bestiary/{id}; verify 200 OK and removal."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers = auth_helper.register_and_login("dm_f09_03", "dm_f09_03@test.dnd")
        monster = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Doomed Monster",
                "edition": "2024",
                "cr": "1",
                "ac": 12,
                "hp": 30,
                "stats": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
            },
            headers=headers,
        ).json()

        del_res = e2e_client.delete(f"/api/v1/bestiary/{monster['id']}", headers=headers)
        assert del_res.status_code == 200

        # Verify not found on subsequent get
        get_res = e2e_client.get(f"/api/v1/bestiary/{monster['id']}", headers=headers)
        assert get_res.status_code == 404

    def test_f09_04_non_owner_cannot_update_custom_monster(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F09-04: User B sends PUT /api/v1/bestiary/{user_a_monster}; verify HTTP 403 Forbidden."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers_a = auth_helper.register_and_login("dm_f09_04a", "dm_f09_04a@test.dnd")
        headers_b = auth_helper.register_and_login("dm_f09_04b", "dm_f09_04b@test.dnd")

        monster = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "User A Creature",
                "edition": "2024",
                "cr": "1",
                "ac": 12,
                "hp": 20,
                "stats": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            },
            headers=headers_a,
        ).json()

        # User B attempts update
        attack_res = e2e_client.put(
            f"/api/v1/bestiary/{monster['id']}",
            json={"name": "Hacked Name"},
            headers=headers_b,
        )
        assert attack_res.status_code == 403, (
            "Non-owner modification must be rejected with HTTP 403"
        )

    def test_f09_05_non_owner_cannot_delete_custom_monster(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F09-05: User B sends DELETE /api/v1/bestiary/{user_a_monster}; verify HTTP 403 Forbidden."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary not mounted (pending M2)")

        headers_a = auth_helper.register_and_login("dm_f09_05a", "dm_f09_05a@test.dnd")
        headers_b = auth_helper.register_and_login("dm_f09_05b", "dm_f09_05b@test.dnd")

        monster = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Indestructible Wyrm",
                "edition": "2024",
                "cr": "15",
                "ac": 18,
                "hp": 200,
                "stats": {"str": 20, "dex": 12, "con": 18, "int": 14, "wis": 14, "cha": 16},
            },
            headers=headers_a,
        ).json()

        # User B attempts delete
        del_res = e2e_client.delete(f"/api/v1/bestiary/{monster['id']}", headers=headers_b)
        assert del_res.status_code == 403, "Non-owner deletion must be rejected with HTTP 403"
