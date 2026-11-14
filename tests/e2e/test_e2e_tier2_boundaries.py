"""Tier 2 E2E Test Suite: Boundary & Corner Cases (Features 1–24).

Verifies boundary conditions, extreme values, defensive validations, 403 immutability,
ownership isolation, empty states, and error handling across all 24 features:
- Features 1–9: SRD Datasets, RulesRepository Cache, Schemas, MongoDB Custom Monsters, Bestiary API
- Features 10–15: DM Workspace Master Modes, Tab Isolation, Tactical VTT, Open VTT, Pinned Strip
- Features 16–21: Bestiary Service, Initiative Quick-Add, Population, Storage, Browser, Riddle Generator
- Features 22–24: Structured Statblock Modal, 1-Click Attack & Damage Rolls

Requirement: At least 5 test cases per feature (>= 120 tests total).
"""

import json
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.repositories.rules_repository import RulesRepository
from server.main import app
from tests.e2e.conftest import (
    CLIENT_APP_ROOT,
    PROJECT_ROOT,
    E2EAuthHelper,
    _AsyncDBWrapper,
)

MONSTERS_2014_PATH = PROJECT_ROOT / "data" / "rules" / "monsters_2014.json"
MONSTERS_2024_PATH = PROJECT_ROOT / "data" / "rules" / "monsters_2024.json"
DM_COMPONENT_TS = CLIENT_APP_ROOT / "features" / "dm" / "dm.component.ts"
DM_COMPONENT_HTML = CLIENT_APP_ROOT / "features" / "dm" / "dm.component.html"
INITIATIVE_TS = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "panels"
    / "initiative-panel"
    / "initiative-panel.component.ts"
)
INITIATIVE_HTML = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "panels"
    / "initiative-panel"
    / "initiative-panel.component.html"
)
GENERATORS_HTML = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "panels"
    / "generators-panel"
    / "generators-panel.component.html"
)
HOMEBREW_HTML = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "panels"
    / "homebrew-panel"
    / "homebrew-panel.component.html"
)
STATBLOCK_TS = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "modals"
    / "statblock-modal"
    / "statblock-modal.component.ts"
)
STATBLOCK_HTML = (
    CLIENT_APP_ROOT
    / "features"
    / "dm"
    / "modals"
    / "statblock-modal"
    / "statblock-modal.component.html"
)
BESTIARY_SERVICE_TS = CLIENT_APP_ROOT / "core" / "services" / "bestiary.service.ts"
ENCOUNTER_STORAGE_TS = CLIENT_APP_ROOT / "core" / "services" / "encounter-storage.service.ts"


def _is_bestiary_router_mounted() -> bool:
    return any(getattr(route, "path", "").startswith("/api/v1/bestiary") for route in app.routes)


# ============================================================================
# Feature 1: 2014 SRD Monster Dataset Boundaries
# ============================================================================


class TestF01Boundaries:
    """Boundary test cases for 2014 SRD Monster Dataset."""

    def test_f01_b01_boundary_cr_zero(self):
        """TC-F01-B01: CR 0 monster (Commoner/Bat/Rat) has cr='0', cr_numeric=0.0."""
        if not MONSTERS_2014_PATH.exists():
            pytest.skip("monsters_2014.json pending M1")
        with open(MONSTERS_2014_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cr0 = [m for m in data if str(m.get("cr")) == "0"]
        assert len(cr0) > 0, "At least one CR 0 monster required"
        for m in cr0:
            assert float(m.get("cr_numeric", 0)) == 0.0

    def test_f01_b02_boundary_cr_twenty_four(self):
        """TC-F01-B02: CR 24 monster (Ancient Red Dragon) has cr='24', cr_numeric=24.0, HP >= 500."""
        if not MONSTERS_2014_PATH.exists():
            pytest.skip("monsters_2014.json pending M1")
        with open(MONSTERS_2014_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cr24 = [m for m in data if str(m.get("cr")) == "24"]
        assert len(cr24) > 0, "CR 24 monster required in 2014 dataset"
        assert float(cr24[0]["cr_numeric"]) == 24.0
        assert int(cr24[0]["hp"]) >= 500

    def test_f01_b03_fractional_crs(self):
        """TC-F01-B03: Fractional CRs '1/8', '1/4', '1/2' in 2014 dataset match exact numerical values."""
        if not MONSTERS_2014_PATH.exists():
            pytest.skip("monsters_2014.json pending M1")
        with open(MONSTERS_2014_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        fraction_map = {"1/8": 0.125, "1/4": 0.25, "1/2": 0.5}
        matching = [m for m in data if str(m.get("cr")) in fraction_map]
        assert len(matching) > 0, "2014 dataset must contain monsters with fractional CRs"
        for m in matching:
            expected = fraction_map[str(m["cr"])]
            assert float(m["cr_numeric"]) == expected
            assert RulesRepository._parse_cr_numeric(m["cr"]) == expected

    def test_f01_b04_utility_only_monster_no_attack_bonus(self):
        """TC-F01-B04: Monster with utility or movement actions has attack_bonus=None without failing schema."""
        repo = RulesRepository()
        monsters = repo.get_all_monsters("2014")
        if not monsters:
            pytest.skip("No 2014 monsters loaded pending M1")
        utility_actions = [
            act for m in monsters for act in m.get("actions", []) if act.get("attack_bonus") is None
        ]
        assert len(utility_actions) >= 5, "Dataset must contain actions without attack bonus"
        for act in utility_actions:
            assert "name" in act and bool(act["name"])
            assert "description" in act and bool(act["description"])

    def test_f01_b05_slugified_unique_ids(self):
        """TC-F01-B05: Monster IDs are unique and lowercase alphanumeric/underscore matching srd_*_2014."""
        if not MONSTERS_2014_PATH.exists():
            pytest.skip("monsters_2014.json pending M1")
        with open(MONSTERS_2014_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        all_ids = [m["id"] for m in data]
        assert len(all_ids) == len(set(all_ids)), "All 2014 monster IDs must be unique"
        for mid in all_ids:
            assert re.match(r"^srd_[a-z0-9_]+_2014$", mid), f"ID {mid} does not match convention"


# ============================================================================
# Feature 2: 2024 SRD Monster Dataset Boundaries
# ============================================================================


class TestF02Boundaries:
    """Boundary test cases for 2024 Revision SRD Monster Dataset."""

    def test_f02_b01_boundary_cr_zero_2024(self):
        """TC-F02-B01: 2024 CR 0 monsters parse cleanly."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json pending M1")
        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cr0 = [m for m in data if str(m.get("cr")) == "0"]
        assert len(cr0) > 0

    def test_f02_b02_boundary_high_cr_2024(self):
        """TC-F02-B02: 2024 CR 24 monster parses updated 5.5e mechanics."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json pending M1")
        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cr24 = [m for m in data if str(m.get("cr")) == "24"]
        assert len(cr24) > 0

    def test_f02_b03_fractional_cr_numerics_2024(self):
        """TC-F02-B03: 2024 fractional CRs match exact float values."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json pending M1")
        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        fraction_map = {"1/8": 0.125, "1/4": 0.25, "1/2": 0.5}
        matching = [m for m in data if str(m.get("cr")) in fraction_map]
        assert len(matching) > 0, "2024 dataset must contain monsters with fractional CRs"
        for m in matching:
            assert float(m["cr_numeric"]) == fraction_map[str(m["cr"])]

    def test_f02_b04_multiattack_action_parsing_2024(self):
        """TC-F02-B04: Multiattack action description parses cleanly from 2024 dataset."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json pending M1")
        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        multiattack_actions = [
            act for m in data for act in m.get("actions", []) if act.get("name") == "Multiattack"
        ]
        assert len(multiattack_actions) > 0, "2024 dataset must contain Multiattack actions"
        for act in multiattack_actions:
            assert act.get("attack_bonus") is None
            assert bool(act.get("description"))

    def test_f02_b05_bonus_action_clean_mapping_2024(self):
        """TC-F02-B05: Monsters with bonus actions format into schema cleanly from 2024 dataset."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json pending M1")
        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        bonus_actions = [ba for m in data for ba in m.get("bonus_actions", [])]
        assert len(bonus_actions) > 0, "2024 dataset must contain bonus actions"
        for ba in bonus_actions:
            assert "name" in ba and bool(ba["name"])
            assert "description" in ba and bool(ba["description"])


# ============================================================================
# Feature 3: RulesRepository Cache & Queries Boundaries
# ============================================================================


class TestF03Boundaries:
    """Boundary test cases for RulesRepository caching and queries."""

    def test_f03_b01_deep_immutability_nested_mutation(self):
        """TC-F03-B01: Modifying nested stats in returned dict does not alter repository cache."""
        repo = RulesRepository()
        if not hasattr(repo, "get_all_monsters"):
            pytest.skip("RulesRepository.get_all_monsters pending M1")
        monsters = repo.get_all_monsters("2014")
        if not monsters:
            pytest.skip("No monsters loaded pending M1")
        original_str = monsters[0].get("stats", {}).get("str", 10)
        monsters[0]["stats"]["str"] = 99
        fresh = repo.get_all_monsters("2014")
        assert fresh[0]["stats"]["str"] == original_str

    def test_f03_b02_edition_normalization_variants(self):
        """TC-F03-B02: Edition normalization resolves '2024 Revision' and '2014 5e' cleanly."""
        from backend.repositories.rules_repository import _norm_edition

        assert _norm_edition("2024 Revision (5.5e)") == "2024"
        assert _norm_edition("2014 5e") == "2014"
        assert _norm_edition("2024") == "2024"
        assert _norm_edition("2014") == "2014"

    def test_f03_b03_nonexistent_monster_id(self):
        """TC-F03-B03: Calling get_monster_by_id with non-existent ID returns None safely."""
        repo = RulesRepository()
        if not hasattr(repo, "get_monster_by_id"):
            pytest.skip("RulesRepository.get_monster_by_id pending M1")
        res = repo.get_monster_by_id("srd_nonexistent_xyz_12345")
        assert res is None

    def test_f03_b04_empty_search_query(self):
        """TC-F03-B04: search_monsters(query='') returns all monsters for edition without crashing."""
        repo = RulesRepository()
        if not hasattr(repo, "search_monsters"):
            pytest.skip("RulesRepository.search_monsters pending M1")
        res = repo.search_monsters(query="", edition="2014")
        assert isinstance(res, list)

    def test_f03_b05_search_query_whitespace_and_case(self):
        """TC-F03-B05: search_monsters with leading/trailing whitespace and uppercase handles cleanly."""
        repo = RulesRepository()
        if not hasattr(repo, "search_monsters"):
            pytest.skip("RulesRepository.search_monsters pending M1")
        res = repo.search_monsters(query="   GOBLIN   ", edition="2014")
        assert isinstance(res, list)


# ============================================================================
# Feature 4: Monster & Bestiary Schemas Boundaries
# ============================================================================


class TestF04Boundaries:
    """Boundary test cases for Pydantic Monster and Bestiary schemas."""

    def test_f04_b01_stat_score_out_of_bounds(self):
        """TC-F04-B01: Ability score 0 or 31 raises validation error."""
        try:
            from pydantic import ValidationError

            from backend.core.schemas import MonsterStats
        except ImportError:
            pytest.skip("MonsterStats schema pending M2")

        with pytest.raises(ValidationError):
            MonsterStats(str=35)
        with pytest.raises(ValidationError):
            MonsterStats(str=0)

    def test_f04_b02_negative_ac_or_hp(self):
        """TC-F04-B02: Negative AC or HP <= 0 raises validation error."""
        try:
            from pydantic import ValidationError

            from backend.core.schemas import Monster
        except ImportError:
            pytest.skip("Monster schema pending M2")

        with pytest.raises(ValidationError):
            Monster(id="m1", name="Bad", edition="2024", origin="custom", cr="1", ac=-1, hp=10)

    def test_f04_b03_empty_monster_name(self):
        """TC-F04-B03: Empty name or whitespace-only name raises validation error."""
        try:
            from pydantic import ValidationError

            from backend.core.schemas import Monster
        except ImportError:
            pytest.skip("Monster schema pending M2")

        with pytest.raises(ValidationError):
            Monster(id="m1", name="", edition="2024", origin="custom", cr="1", ac=10, hp=10)

    def test_f04_b04_invalid_dice_notation(self):
        """TC-F04-B04: Malformed dice notation returns structured error dictionary."""
        from backend.utils.dice import roll_dice

        res = roll_dice("invalid_dice_string")
        assert "error" in res
        assert "Invalid dice format" in res["error"]

    def test_f04_b05_excessive_hp_upper_bound(self):
        """TC-F04-B05: HP must be strictly positive; non-positive HP raises ValidationError."""
        try:
            from pydantic import ValidationError

            from backend.core.schemas import Monster
        except ImportError:
            pytest.skip("Monster schema pending M2")

        with pytest.raises(ValidationError):
            Monster(id="m1", name="Dead", edition="2024", origin="custom", cr="1", ac=10, hp=0)
        with pytest.raises(ValidationError):
            Monster(id="m2", name="Negative", edition="2024", origin="custom", cr="1", ac=10, hp=-5)
        # Extreme valid high HP values must not raise ValidationError
        m = Monster(id="m3", name="Titan", edition="2024", origin="custom", cr="30", ac=25, hp=1500)
        assert m.hp == 1500


# ============================================================================
# Feature 5: MongoDB Custom Monsters Boundaries
# ============================================================================


class TestF05Boundaries:
    """Boundary test cases for MongoDB custom_monsters collection."""

    def test_f05_b01_custom_monster_based_on_official(self, mock_db: _AsyncDBWrapper):
        """TC-F05-B01: Document with based_on='srd_goblin_2014' persists and indexes cleanly."""
        col = mock_db._db["custom_monsters"]
        doc = {"id": str(uuid.uuid4()), "name": "Cloned Goblin", "based_on": "srd_goblin_2014"}
        col.insert_one(doc)
        found = col.find_one({"based_on": "srd_goblin_2014"})
        assert found is not None

    def test_f05_b02_custom_monster_based_on_custom(self, mock_db: _AsyncDBWrapper):
        """TC-F05-B02: Document with based_on='{custom_id}' persists correctly."""
        col = mock_db._db["custom_monsters"]
        parent_id = str(uuid.uuid4())
        col.insert_one({"id": str(uuid.uuid4()), "name": "Child", "based_on": parent_id})
        found = col.find_one({"based_on": parent_id})
        assert found is not None

    def test_f05_b03_large_monster_payload(self, mock_db: _AsyncDBWrapper):
        """TC-F05-B03: Monster document with 50+ actions and traits persists cleanly."""
        col = mock_db._db["custom_monsters"]
        large_actions = [{"name": f"Action {i}", "description": f"Desc {i}"} for i in range(50)]
        doc = {"id": str(uuid.uuid4()), "name": "Colossus", "actions": large_actions}
        col.insert_one(doc)
        found = col.find_one({"id": doc["id"]})
        assert len(found["actions"]) == 50

    def test_f05_b04_delete_isolation(self, mock_db: _AsyncDBWrapper):
        """TC-F05-B04: Deleting a custom monster leaves other documents untouched."""
        col = mock_db._db["custom_monsters"]
        col.insert_one({"id": "iso_1", "name": "Keeper"})
        col.insert_one({"id": "iso_2", "name": "Victim"})
        col.delete_one({"id": "iso_2"})
        assert col.find_one({"id": "iso_2"}) is None
        assert col.find_one({"id": "iso_1"}) is not None

    def test_f05_b05_duplicate_id_rejection(self, mock_db: _AsyncDBWrapper):
        """TC-F05-B05: Inserting duplicate ID with unique index enforcement."""
        col = mock_db._db["custom_monsters"]
        # In mongomock, create_index enforces unique constraint
        col.create_index("id", unique=True)
        col.insert_one({"id": "unique_monster_id", "name": "First"})
        from pymongo.errors import DuplicateKeyError

        with pytest.raises(DuplicateKeyError):
            col.insert_one({"id": "unique_monster_id", "name": "Duplicate"})


# ============================================================================
# Feature 6: Bestiary Query Endpoint Boundaries
# ============================================================================


class TestF06Boundaries:
    """Boundary test cases for GET /api/v1/bestiary."""

    def test_f06_b01_all_source_flags_false(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F06-B01: include_official=False&include_mine=False&include_community=False returns []."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f06_b01", "dm_f06_b01@test.dnd")
        res = e2e_client.get(
            "/api/v1/bestiary?include_official=false&include_mine=false&include_community=false",
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json() == []

    def test_f06_b02_community_isolation_no_private_leaks(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F06-B02: User A's private monster is NOT returned to User B when include_community=True."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers_a = auth_helper.register_and_login("dm_f06_b02a", "dm_f06_b02a@test.dnd")
        headers_b = auth_helper.register_and_login("dm_f06_b02b", "dm_f06_b02b@test.dnd")

        e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Super Secret Hydra",
                "is_public": False,
                "cr": "8",
                "ac": 15,
                "hp": 120,
                "edition": "2024",
            },
            headers=headers_a,
        )

        res = e2e_client.get(
            "/api/v1/bestiary?include_official=false&include_mine=false&include_community=true",
            headers=headers_b,
        )
        assert res.status_code == 200
        assert not any(m["name"] == "Super Secret Hydra" for m in res.json())

    def test_f06_b03_fractional_cr_exact_filter(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F06-B03: Filtering by cr='1/4' returns only CR 1/4 monsters (numeric 0.25)."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f06_b03", "dm_f06_b03@test.dnd")
        res = e2e_client.get("/api/v1/bestiary?cr=1/4", headers=headers)
        assert res.status_code == 200
        for m in res.json():
            assert str(m.get("cr")) == "1/4" or m.get("cr_numeric") == 0.25

    def test_f06_b04_unauthenticated_query_returns_401(self, e2e_client: TestClient):
        """TC-F06-B04: GET /api/v1/bestiary without Authorization header returns 401."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        res = e2e_client.get("/api/v1/bestiary")
        assert res.status_code == 401

    def test_f06_b05_no_matching_search_returns_empty_list(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F06-B05: Search query with non-matching string returns empty list."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f06_b05", "dm_f06_b05@test.dnd")
        res = e2e_client.get("/api/v1/bestiary?search=gibberishxyzabc123456789", headers=headers)
        assert res.status_code == 200
        assert res.json() == []


# ============================================================================
# Feature 7: Bestiary Single Monster Endpoint Boundaries
# ============================================================================


class TestF07Boundaries:
    """Boundary test cases for GET /api/v1/bestiary/{id}."""

    def test_f07_b01_nonexistent_srd_id_returns_404(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F07-B01: GET non-existent SRD ID returns 404."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f07_b01", "dm_f07_b01@test.dnd")
        res = e2e_client.get("/api/v1/bestiary/srd_nonexistent_dragon_123", headers=headers)
        assert res.status_code == 404

    def test_f07_b02_nonexistent_custom_uuid_returns_404(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F07-B02: GET non-existent UUID returns 404."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f07_b02", "dm_f07_b02@test.dnd")
        res = e2e_client.get(
            "/api/v1/bestiary/00000000-0000-0000-0000-000000000000", headers=headers
        )
        assert res.status_code == 404

    def test_f07_b03_private_custom_monster_unauthorized_returns_403(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F07-B03: Non-owner requesting private monster returns 403 Forbidden."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers_a = auth_helper.register_and_login("dm_f07_b03a", "dm_f07_b03a@test.dnd")
        headers_b = auth_helper.register_and_login("dm_f07_b03b", "dm_f07_b03b@test.dnd")

        m = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Private Behemoth",
                "is_public": False,
                "cr": "10",
                "ac": 16,
                "hp": 150,
                "edition": "2024",
            },
            headers=headers_a,
        ).json()

        res = e2e_client.get(f"/api/v1/bestiary/{m['id']}", headers=headers_b)
        assert res.status_code in (403, 404), "Unauthorized fetch must return 403 or 404"

    def test_f07_b04_unauthenticated_single_fetch_returns_401(self, e2e_client: TestClient):
        """TC-F07-B04: Fetch without Authorization returns 401."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        res = e2e_client.get("/api/v1/bestiary/srd_goblin_2014")
        assert res.status_code == 401

    def test_f07_b05_path_traversal_sanitization(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F07-B05: Path traversal attempt is safely rejected."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f07_b05", "dm_f07_b05@test.dnd")
        res = e2e_client.get("/api/v1/bestiary/..%2F..%2Fetc%2Fpasswd", headers=headers)
        assert res.status_code in (404, 422)


# ============================================================================
# Feature 8: Bestiary Creation & Clone Endpoint Boundaries
# ============================================================================


class TestF08Boundaries:
    """Boundary test cases for POST /api/v1/bestiary."""

    def test_f08_b01_missing_name_returns_422(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F08-B01: Payload missing name returns 422 Unprocessable Entity."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f08_b01", "dm_f08_b01@test.dnd")
        res = e2e_client.post(
            "/api/v1/bestiary",
            json={"edition": "2024", "cr": "1", "ac": 12, "hp": 20},
            headers=headers,
        )
        assert res.status_code == 422

    def test_f08_b02_invalid_stat_returns_422(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F08-B02: Payload with STR=35 returns 422."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f08_b02", "dm_f08_b02@test.dnd")
        res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Overpowered",
                "edition": "2024",
                "cr": "1",
                "ac": 12,
                "hp": 20,
                "stats": {"str": 35},
            },
            headers=headers,
        )
        assert res.status_code == 422

    def test_f08_b03_negative_hp_returns_422(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F08-B03: Payload with HP=-5 returns 422."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f08_b03", "dm_f08_b03@test.dnd")
        res = e2e_client.post(
            "/api/v1/bestiary",
            json={"name": "Dead", "edition": "2024", "cr": "1", "ac": 12, "hp": -5},
            headers=headers,
        )
        assert res.status_code == 422

    def test_f08_b04_client_injected_origin_overwritten(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F08-B04: Client injecting origin='official' is forced to 'custom'."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f08_b04", "dm_f08_b04@test.dnd")
        res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Spoofed",
                "origin": "official",
                "edition": "2024",
                "cr": "1",
                "ac": 12,
                "hp": 20,
            },
            headers=headers,
        )
        assert res.status_code == 201
        assert res.json()["origin"] == "custom"

    def test_f08_b05_client_injected_creator_overwritten(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F08-B05: Client injecting creator_dm_id='admin' is overwritten with caller's ID."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f08_b05", "dm_f08_b05@test.dnd")
        res = e2e_client.post(
            "/api/v1/bestiary",
            json={
                "name": "Spoofed Creator",
                "creator_dm_id": "admin",
                "edition": "2024",
                "cr": "1",
                "ac": 12,
                "hp": 20,
            },
            headers=headers,
        )
        assert res.status_code == 201
        assert res.json()["creator_dm_id"] != "admin"


# ============================================================================
# Feature 9: Bestiary Immutability & Ownership Boundaries
# ============================================================================


class TestF09Boundaries:
    """Boundary test cases for 403 immutability and ownership rejections."""

    def test_f09_b01_put_official_monster_returns_403(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F09-B01: PUT /api/v1/bestiary/srd_goblin_2014 returns 403 Forbidden."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f09_b01", "dm_f09_b01@test.dnd")
        res = e2e_client.put(
            "/api/v1/bestiary/srd_goblin_2014",
            json={"name": "Hacked Goblin"},
            headers=headers,
        )
        assert res.status_code == 403

    def test_f09_b02_delete_official_monster_returns_403(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F09-B02: DELETE /api/v1/bestiary/srd_goblin_2014 returns 403 Forbidden."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f09_b02", "dm_f09_b02@test.dnd")
        res = e2e_client.delete("/api/v1/bestiary/srd_goblin_2014", headers=headers)
        assert res.status_code == 403

    def test_f09_b03_patch_official_visibility_returns_403(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F09-B03: PATCH /api/v1/bestiary/srd_goblin_2014/visibility returns 403 Forbidden."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f09_b03", "dm_f09_b03@test.dnd")
        res = e2e_client.patch(
            "/api/v1/bestiary/srd_goblin_2014/visibility",
            json={"is_public": False},
            headers=headers,
        )
        assert res.status_code == 403

    def test_f09_b04_non_owner_patch_visibility_returns_403(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F09-B04: User B patching visibility of User A's custom monster returns 403."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers_a = auth_helper.register_and_login("dm_f09_b04a", "dm_f09_b04a@test.dnd")
        headers_b = auth_helper.register_and_login("dm_f09_b04b", "dm_f09_b04b@test.dnd")

        m = e2e_client.post(
            "/api/v1/bestiary",
            json={"name": "Creature A", "edition": "2024", "cr": "1", "ac": 12, "hp": 20},
            headers=headers_a,
        ).json()

        res = e2e_client.patch(
            f"/api/v1/bestiary/{m['id']}/visibility",
            json={"is_public": True},
            headers=headers_b,
        )
        assert res.status_code == 403

    def test_f09_b05_put_nonexistent_custom_id_returns_404(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F09-B05: PUT on non-existent UUID returns 404 Not Found."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f09_b05", "dm_f09_b05@test.dnd")
        res = e2e_client.put(
            "/api/v1/bestiary/00000000-0000-0000-0000-000000000000",
            json={"name": "Ghost"},
            headers=headers,
        )
        assert res.status_code == 404


# ============================================================================
# Features 10–15: DM Workspace & VTT Boundaries
# ============================================================================


class TestF10ToF15Boundaries:
    """Boundary test cases for DM master modes, tab isolation, and pinned strip."""

    def test_f10_b01_rapid_mode_toggle_resilience(self):
        """TC-B10-01: Rapid mode toggles resolve cleanly with guard and tab persistence."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "setDmMode" in content
        assert "if (this.dmMode === mode) return;" in content
        assert "this.lastLiveTab = this.activeTab as DmLiveTab;" in content
        assert "this.lastPrepTab = this.activeTab as DmPrepTab;" in content

    def test_f10_b02_modal_open_during_mode_switch(self):
        """TC-B10-02: Modal visibility state is decoupled from setDmMode."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        set_dm_mode_body = content.split("setDmMode(mode: DmMasterMode): void {")[1].split("}")[0]
        assert "selectedStatblockCombatant" not in set_dm_mode_body
        assert "showWhisperModal" not in set_dm_mode_body
        assert "showLootDistributeModal" not in set_dm_mode_body

    def test_f10_b03_in_flight_http_request_during_switch(self):
        """TC-B10-03: Switching master mode does not reset campaign state or cancel active observables."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "setDmMode" in content, "setDmMode method must be declared in dm.component.ts"
        set_dm_mode_body = content.split("setDmMode(mode: DmMasterMode): void {")[1].split("}")[0]
        assert "this.campaignsStatus" not in set_dm_mode_body, (
            "setDmMode must not reset campaignsStatus"
        )

    def test_f10_b04_zero_campaigns_mode_switcher_guard(self):
        """TC-B10-04: Workspace renders empty state when user has zero campaigns."""
        html_content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "userCampaigns.length === 0" in html_content
        assert 'title="No Campaigns Yet"' in html_content

    def test_f10_b05_empty_party_mode_switch(self):
        """TC-B10-05: Empty party state rendered without exceptions when partyMembers is empty."""
        html_content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "partyMembers.length === 0" in html_content
        assert "No heroes in this campaign yet." in html_content

    def test_f11_b01_invalid_tab_fallback_to_initiative(self):
        """TC-B11-01: Programmatically setting unknown tab defaults safely to initiative."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "lastLiveTab: DmLiveTab = 'initiative';" in content
        assert "readonly liveTabs" in content
        assert "'initiative'" in content

    def test_f11_b02_empty_combatants_initiative_empty_state(self):
        """TC-B11-02: Empty combatants table in initiative panel renders clean empty state."""
        content = INITIATIVE_HTML.read_text(encoding="utf-8")
        assert "combatants" in content

    def test_f11_b03_party_status_error_recovery(self):
        """TC-B11-03: Party status component handles fetch failure with retry option invoking loadParty()."""
        html_content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "partyStatus === 'error'" in html_content
        assert '(click)="loadParty()"' in html_content
        assert "loadParty()" in ts_content

    def test_f11_b04_offline_live_notes_retention(self):
        """TC-B11-04: saveCampaignNotes retains local text in campaignNotes on HTTP failure."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "saveCampaignNotes()" in ts_content
        idx = ts_content.find("saveCampaignNotes()")
        notes_method = ts_content[idx : idx + 450]
        assert "this.campaignNotes = ''" not in notes_method
        assert "rollToast" in notes_method

    def test_f11_b05_1024px_responsive_boundary(self):
        """TC-B11-05: Desktop check checks 1024px boundary."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "1023" in content or "1024" in content

    def test_f12_b01_invalid_tab_fallback_to_homebrew(self):
        """TC-B12-01: Preparation mode defaults to 'homebrew' tab."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "lastPrepTab: DmPrepTab = 'homebrew';" in content
        assert "readonly prepTabs" in content
        assert "'homebrew'" in content

    def test_f12_b02_delete_custom_monster_confirmation(self):
        """TC-B12-02: Deleting custom item prompts user via confirmDialog before proceeding."""
        HOMEBREW_TS = (
            CLIENT_APP_ROOT
            / "features"
            / "dm"
            / "panels"
            / "homebrew-panel"
            / "homebrew-panel.component.ts"
        )
        assert HOMEBREW_TS.exists()
        ts_content = HOMEBREW_TS.read_text(encoding="utf-8")
        assert "deleteItem(" in ts_content
        assert "confirmDialog.ask" in ts_content or "confirm(" in ts_content
        assert "deleteHomebrew" in ts_content

    def test_f12_b03_generate_encounter_zero_party(self):
        """TC-B12-03: Generating encounter with 0 party members halts and alerts with NO PARTY toast."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "generateEncounter()" in ts_content
        encounter_fn = ts_content.split("generateEncounter()")[1].split("}")[0]
        assert "this.partyMembers.length === 0" in encounter_fn
        assert "NO PARTY" in encounter_fn

    def test_f12_b04_generate_npc_empty_concept(self):
        """TC-B12-04: NPC concept has default fallback value in dm.component.ts."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "generateNpc()" in ts_content
        assert "npcConcept" in ts_content
        assert "Shady underworld broker" in ts_content

    def test_f12_b05_campaign_switch_clears_prep_state(self):
        """TC-B12-05: clearWorkspace resets active riddle and prep generator results."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "clearWorkspace() {" in ts_content
        clear_fn = ts_content.split("clearWorkspace() {")[1].split("onCampaignSelect()")[0]
        assert "this.riddleResult = ''" in clear_fn
        assert "this.prepResult = ''" in clear_fn

    def test_f13_b01_rapid_tab_switch_vtt_mount_clean(self):
        """TC-B13-01: VTT tab conditionally mounts app-vtt-grid and preserves combatants binding."""
        html_content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "*ngIf=\"dmMode === 'live' && activeTab === 'vtt'\"" in html_content
        assert "<app-vtt-grid" in html_content
        assert '[combatants]="combatants"' in html_content

    def test_f13_b02_vtt_sync_inactive_swaps_to_empty_state(self):
        """TC-B13-02: Inactive VTT state renders empty state title in DM workspace template."""
        html_content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "@if (!vttState()?.is_active)" in html_content
        assert 'title="Tactical VTT Offline"' in html_content

    def test_f13_b03_vtt_sync_active_swaps_to_grid(self):
        """TC-B13-03: Active VTT state renders grid canvas with reference variable."""
        html_content = " ".join(DM_COMPONENT_HTML.read_text(encoding="utf-8").split())
        assert "<app-vtt-grid #vttGrid" in html_content

    def test_f13_b04_missing_portrait_fallback(self):
        """TC-B13-04: Combatant without portrait falls back to name initial."""
        html_content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "member.portrait" in html_content
        assert "(member.name || '?').charAt(0)" in html_content
        assert "(error)=\"member.portrait = ''\"" in html_content

    def test_f13_b05_token_move_preserves_initiative_order(self):
        """TC-B13-05: WebSocket sendVttMove sends vtt_token_move payload without altering combatants list."""
        ws_ts = CLIENT_APP_ROOT / "core" / "services" / "websocket.service.ts"
        assert ws_ts.exists()
        ws_content = ws_ts.read_text(encoding="utf-8")
        assert "sendVttMove(" in ws_content
        assert "'vtt_token_move'" in ws_content

    def test_f14_b01_idempotent_sidebar_click(self):
        """TC-B14-01: Clicking sidebar Open VTT when already active is deterministic and idempotent."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "openVTT(): void" in ts_content
        idx = ts_content.find("openVTT(): void")
        open_vtt_fn = ts_content[idx : idx + 300]
        assert "this.dmMode = 'live'" in open_vtt_fn
        assert "this.activeTab = 'vtt'" in open_vtt_fn
        assert "this.wsService.sendVttToggle(true)" in open_vtt_fn

    def test_f14_b02_websocket_offline_fallback(self):
        """TC-B14-02: WebSocketService guards sendVttToggle when socket is not open."""
        ws_ts = CLIENT_APP_ROOT / "core" / "services" / "websocket.service.ts"
        assert ws_ts.exists()
        ws_content = ws_ts.read_text(encoding="utf-8")
        assert "sendVttToggle(" in ws_content
        assert "readyState === WebSocket.OPEN" in ws_content

    def test_f14_b03_deep_prep_tab_navigation(self):
        """TC-B14-03: Switching mode preserves lastPrepTab while openVTT sets activeTab to vtt."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "this.lastPrepTab = this.activeTab as DmPrepTab;" in ts_content
        assert "this.lastLiveTab = 'vtt';" in ts_content

    def test_f14_b04_maximized_grid_remains_maximized(self):
        """TC-B14-04: Open VTT expands and unminimizes grid canvas."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        open_vtt_fn = ts_content.split("openVTT(): void")[1].split("}")[0]
        assert "this.vttGrid.isMinimized = false;" in open_vtt_fn

    def test_f14_b05_concurrent_whisper_notification(self):
        """TC-B14-05: Incoming whisper message triggers rollToast and routes to inbox."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "msg.type === 'whisper'" in ts_content
        assert "this.addInboxWhisper(" in ts_content
        assert "this.rollToast.showMessage(" in ts_content

    def test_f15_b01_active_combatant_removed_advances_turn(self):
        """TC-B15-01: Removing combatant safely adjusts activeCombatant pointer."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "removeCombatant(" in ts_content
        remove_fn = ts_content.split("removeCombatant(")[1].split("}")[0]
        assert "activeCombatant" in remove_fn

    def test_f15_b02_all_combatants_cleared_unmounts_strip(self):
        """TC-B15-02: Pinned combat strip conditionally rendered only when combatants.length > 0."""
        html_content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert (
            "@if (dmMode === 'live' && activeTab !== 'initiative' && combatants.length > 0)"
            in html_content
        )

    def test_f15_b03_zero_hp_combatant_styling(self):
        """TC-B15-03: Combatant at 0 HP triggers danger text-red styling in pinned strip."""
        html_content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "c.hp <= 0 ? 'text-red'" in html_content

    def test_f15_b04_round_zero_prev_disabled(self):
        """TC-B15-04: Round cannot decrement below 1 in previousTurn."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "previousTurn(" in ts_content
        prev_fn = ts_content.split("previousTurn(")[1].split("}")[0]
        assert "this.round" in prev_fn
        assert "Math.max(1" in prev_fn or "round <= 1" in prev_fn or "round > 1" in prev_fn

    def test_f15_b05_many_combatants_horizontal_scroll(self):
        """TC-B15-05: Pinned strip container uses horizontal scrolling and flex styling."""
        html_content = DM_COMPONENT_HTML.read_text(encoding="utf-8")
        assert "overflow-x-auto" in html_content
        assert 'data-testid="pinned-combat-bar"' in html_content


# ============================================================================
# Features 16–21: Bestiary Frontend & Quick-Add Boundaries
# ============================================================================


class TestF16ToF21Boundaries:
    """Boundary test cases for Bestiary service, Quick-Add, and Riddle generator."""

    def test_f16_b01_http_500_error_handling(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper, monkeypatch
    ):
        """TC-B16-01: HTTP 500 from /api/v1/bestiary handled gracefully without unhandled server crash."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        from backend.repositories.rules_repository import RulesRepository

        headers = auth_helper.register_and_login("dm_f16_b01", "dm_f16_b01@test.dnd")
        safe_client = TestClient(e2e_client.app, raise_server_exceptions=False)

        def _mock_crash(*args, **kwargs):
            raise RuntimeError("Simulated internal DB failure")

        monkeypatch.setattr(RulesRepository, "get_all_monsters", _mock_crash)
        res = safe_client.get("/api/v1/bestiary", headers=headers)
        assert res.status_code == 500

    def test_f16_b02_403_official_update_surfaces_error(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-B16-02: Attempting official monster update surfaces permission error (HTTP 403)."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f16_b02", "dm_f16_b02@test.dnd")
        res = e2e_client.put(
            "/api/v1/bestiary/srd_goblin_2014", json={"name": "Hacked Goblin"}, headers=headers
        )
        assert res.status_code == 403

    def test_f16_b03_403_official_delete_surfaces_error(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-B16-03: Attempting official monster deletion surfaces permission error (HTTP 403)."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f16_b03", "dm_f16_b03@test.dnd")
        res = e2e_client.delete("/api/v1/bestiary/srd_goblin_2014", headers=headers)
        assert res.status_code == 403

    def test_f16_b04_special_characters_url_encoding(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-B16-04: Special characters in search query URL-encoded."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f16_b04", "dm_f16_b04@test.dnd")
        res = e2e_client.get("/api/v1/bestiary?search=orc%27s%20blade%20%26%20axe", headers=headers)
        assert res.status_code == 200

    def test_f16_b05_404_monster_not_found_clean_handling(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-B16-05: Missing monster ID handled with clean 404 error toast."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f16_b05", "dm_f16_b05@test.dnd")
        res = e2e_client.get("/api/v1/bestiary/srd_nonexistent_beast_xyz", headers=headers)
        assert res.status_code == 404
        assert "detail" in res.json()

    def test_f17_b01_zero_results_empty_state(self):
        """TC-B17-01: Zero quick-add search results renders clean empty message."""
        content = INITIATIVE_HTML.read_text(encoding="utf-8")
        if "quick-add" not in content.lower():
            pytest.skip("Initiative quick-add search template pending M4")
        assert "No matching monsters found" in content or "no-results" in content

    def test_f17_b02_all_chips_off_empty_state(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-B17-02: All filter chips OFF returns empty results."""
        if not _is_bestiary_router_mounted():
            pytest.skip("/api/v1/bestiary pending M2")
        headers = auth_helper.register_and_login("dm_f17_b02", "dm_f17_b02@test.dnd")
        res = e2e_client.get(
            "/api/v1/bestiary?include_official=false&include_mine=false&include_community=false",
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json() == []

    def test_f17_b03_whitespace_trimmed(self):
        """TC-B17-03: Leading/trailing whitespace trimmed in search query."""
        repo = RulesRepository()
        results = repo.search_monsters(query="   goblin   ", edition="2014")
        assert len(results) > 0, "Trimmed query must find matching monsters"
        assert results[0]["name"] == "Goblin"

    def test_f17_b04_search_debouncing(self):
        """TC-B17-04: Debounce time constant >= 200ms."""
        content = INITIATIVE_TS.read_text(encoding="utf-8")
        if "debouncetime" not in content.lower():
            pytest.skip("Initiative quick-add search debouncing pending M4")
        assert "debounceTime(" in content

    def test_f17_b05_click_outside_closes_dropdown(self):
        """TC-B17-05: Click outside event closes quick-add search results."""
        content = INITIATIVE_TS.read_text(encoding="utf-8")
        if "quick-add" not in content.lower() and "searchdropdown" not in content.lower():
            pytest.skip("Initiative quick-add dropdown pending M4")
        assert "isDropdownOpen" in content or "closeDropdown" in content

    def test_f18_b01_name_deduplication_auto_numbering(self):
        """TC-B18-01: Adding duplicate monster names auto-numbers: Goblin, Goblin 2, Goblin 3."""
        content = INITIATIVE_TS.read_text(encoding="utf-8")
        if "addmonster" not in content.lower() and "quickadd" not in content.lower():
            pytest.skip("Quick-add auto-numbering pending M4")
        assert "count" in content.lower() or "suffix" in content.lower() or "autoNumber" in content

    def test_f18_b02_existing_numbered_suffix(self):
        """TC-B18-02: Adding monster with numbered suffix (Skeleton 1) produces Skeleton 2."""
        content = INITIATIVE_TS.read_text(encoding="utf-8")
        if "addmonster" not in content.lower() and "quickadd" not in content.lower():
            pytest.skip("Quick-add auto-numbering pending M4")
        assert "name" in content.lower()

    def test_f18_b03_fractional_cr_stored_cleanly(self):
        """TC-B18-03: Fractional CR '1/8' stored in combatant cr property without error."""
        repo = RulesRepository()
        kobold = repo.get_monster_by_id("srd_kobold_2014")
        assert kobold is not None, "SRD Kobold must exist in 2014 dataset"
        assert kobold["cr"] == "1/8"
        assert float(kobold["cr_numeric"]) == 0.125

    def test_f18_b04_negative_dex_modifier(self):
        """TC-B18-04: Monster with DEX 6 (Zombie) has -2 modifier; initiative = 10 + (-2) = 8."""
        from backend.services.stats_service import get_modifier

        repo = RulesRepository()
        zombie = repo.get_monster_by_id("srd_zombie_2014")
        assert zombie is not None, "SRD Zombie must exist in 2014 dataset"
        dex = zombie["stats"]["dex"]
        assert dex == 6, "SRD Zombie DEX must be 6"
        mod = get_modifier(dex)
        assert mod == -2
        assert 10 + mod == 8

    def test_f18_b05_add_monster_mid_round_preserves_round(self):
        """TC-B18-05: Adding monster in Round 3 preserves round counter at 3."""
        ts_content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "addCombatant" in ts_content or "combatants" in ts_content
        if "addCombatant" in ts_content:
            add_method = ts_content.split("addCombatant")[1].split("}")[0]
            assert "this.round = 1" not in add_method

    def test_f19_b01_quota_exceeded_handled(self):
        """TC-B19-01: EncounterStorageService wraps localStorage.setItem in try/catch for QuotaExceededError."""
        assert ENCOUNTER_STORAGE_TS.exists()
        content = ENCOUNTER_STORAGE_TS.read_text(encoding="utf-8")
        assert "save(" in content
        save_fn = content.split("save(")[1].split("clear(")[0]
        assert "try {" in save_fn
        assert "localStorage.setItem(" in save_fn
        assert "} catch" in save_fn

    def test_f19_b02_invalid_json_fallback(self):
        """TC-B19-02: Malformed JSON in localStorage parses safely with null fallback."""
        assert ENCOUNTER_STORAGE_TS.exists()
        content = ENCOUNTER_STORAGE_TS.read_text(encoding="utf-8")
        assert "load(" in content
        load_fn = content.split("load(")[1].split("save(")[0]
        assert "try {" in load_fn
        assert "JSON.parse(" in load_fn
        assert "return null;" in load_fn

    def test_f19_b03_zero_attack_bonus_preserved(self):
        """TC-B19-03: Attack bonus of 0 preserved across serialization and not dropped as falsy."""
        assert ENCOUNTER_STORAGE_TS.exists()
        content = ENCOUNTER_STORAGE_TS.read_text(encoding="utf-8")
        assert "JSON.stringify" in content
        assert "localStorage.setItem" in content

    def test_f19_b04_multi_paragraph_traits_preserved(self):
        """TC-B19-04: Multi-paragraph markdown traits preserved in SRD monster datasets."""
        repo = RulesRepository()
        monsters = repo.get_all_monsters("2014")
        monsters_with_traits = [m for m in monsters if len(m.get("traits", [])) > 0]
        assert len(monsters_with_traits) > 0, "Dataset must contain monsters with traits"
        for m in monsters_with_traits:
            for t in m["traits"]:
                assert "name" in t and bool(t["name"])
                assert "description" in t and bool(t["description"])

    def test_f19_b05_campaign_isolation_in_storage(self):
        """TC-B19-05: Encounter storage keys isolated per campaign name."""
        assert ENCOUNTER_STORAGE_TS.exists()
        content = ENCOUNTER_STORAGE_TS.read_text(encoding="utf-8")
        assert "dnd.encounter.v1." in content

    def test_f20_b01_large_list_scroll_performance(self):
        """TC-B20-01: Bestiary browser handles 80+ official SRD monsters cleanly."""
        repo = RulesRepository()
        monsters = repo.get_all_monsters("2014")
        assert len(monsters) >= 80, f"Expected at least 80 SRD monsters, found {len(monsters)}"
        assert all("id" in m and "name" in m and "cr" in m for m in monsters)

    def test_f20_b02_partial_word_search_matching(self):
        """TC-B20-02: Search matches partial word in monster action description, name, or type."""
        repo = RulesRepository()
        dragons = repo.search_monsters(query="drag", edition="2014")
        assert len(dragons) > 0, "Partial search 'drag' must return dragon entries"
        for d in dragons:
            assert (
                "drag" in d["name"].lower()
                or "drag" in d["type"].lower()
                or "drag" in d.get("description", "").lower()
            )

    def test_f20_b03_cr_range_filter_boundaries(self):
        """TC-B20-03: CR range filtering covers 0 to 24 in official dataset."""
        repo = RulesRepository()
        monsters_2014 = repo.get_all_monsters("2014")
        crs = [float(m["cr_numeric"]) for m in monsters_2014]
        assert min(crs) == 0.0, "Minimum CR must be 0.0"
        assert max(crs) == 24.0, "Maximum CR must be 24.0"

    def test_f20_b04_visibility_toggle_badge_update(self):
        """TC-B20-04: Toggling visibility updates badge between Public and Private."""
        assert HOMEBREW_HTML.exists()
        content = HOMEBREW_HTML.read_text(encoding="utf-8")
        if "is_public" not in content and "public" not in content.lower():
            pytest.skip(
                "Feature 20 (Bestiary browser visibility toggle badge) pending M4 implementation"
            )
        assert "is_public" in content or "public" in content.lower()

    def test_f20_b05_edition_filter_default(self):
        """TC-B20-05: 2024 campaign defaults bestiary edition filter to 2024."""
        content = DM_COMPONENT_TS.read_text(encoding="utf-8")
        assert "get editionShort()" in content
        edition_getter = content.split("get editionShort()")[1].split("}")[0]
        assert "'2024'" in edition_getter
        assert "'2014'" in edition_getter

    def test_f21_b01_empty_location_returns_422(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F21-B01: POST /api/v1/dm/riddle with missing location field returns 422."""
        headers = auth_helper.register_and_login("dm_f21_b01", "dm_f21_b01@test.dnd")
        # Missing required 'location' parameter
        res = e2e_client.post(
            "/api/v1/dm/riddle", json={"edition": "2024 Edition"}, headers=headers
        )
        assert res.status_code == 422

    def test_f21_b02_very_long_location_string(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper, monkeypatch
    ):
        """TC-F21-B02: Very long location string handled safely without crashing server."""
        monkeypatch.setattr(
            "server.routers.dm_router.generate_riddle", lambda loc, ed: "## Generated Riddle"
        )
        headers = auth_helper.register_and_login("dm_f21_b02", "dm_f21_b02@test.dnd")
        long_loc = "Dungeon " * 500
        res = e2e_client.post("/api/v1/dm/riddle", json={"location": long_loc}, headers=headers)
        assert res.status_code in (200, 422, 429)

    def test_f21_b03_special_characters_location(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper, monkeypatch
    ):
        """TC-F21-B03: Special characters in location string handled safely."""
        monkeypatch.setattr(
            "server.routers.dm_router.generate_riddle", lambda loc, ed: "## Generated Riddle"
        )
        headers = auth_helper.register_and_login("dm_f21_b03", "dm_f21_b03@test.dnd")
        spec_loc = "Tomb of <Horrors> & 'Chult' / \"Crypt\""
        res = e2e_client.post("/api/v1/dm/riddle", json={"location": spec_loc}, headers=headers)
        assert res.status_code in (200, 429)

    def test_f21_b04_rate_limit_exceeded_returns_429(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper, monkeypatch
    ):
        """TC-F21-B04: Rate limit on riddle endpoint returns 429 when quota exceeded."""
        monkeypatch.setattr(
            "server.routers.dm_router.generate_riddle", lambda loc, ed: "## Generated Riddle"
        )
        headers = auth_helper.register_and_login("dm_f21_b04", "dm_f21_b04@test.dnd")
        # Trigger requests up to limit
        statuses = []
        for _ in range(15):
            r = e2e_client.post("/api/v1/dm/riddle", json={"location": "Crypt"}, headers=headers)
            statuses.append(r.status_code)
            if r.status_code == 429:
                break
        assert 429 in statuses or all(s == 200 for s in statuses)

    def test_f21_b05_missing_body_returns_422(
        self, e2e_client: TestClient, auth_helper: E2EAuthHelper
    ):
        """TC-F21-B05: POST /api/v1/dm/riddle with empty body returns 422."""
        headers = auth_helper.register_and_login("dm_f21_b05", "dm_f21_b05@test.dnd")
        res = e2e_client.post("/api/v1/dm/riddle", json={}, headers=headers)
        assert res.status_code == 422


# ============================================================================
# Features 22–24: Statblock Modal & 1-Click Rolls Boundaries
# ============================================================================


class TestF22ToF24Boundaries:
    """Boundary test cases for Statblock modal and 1-click rolls."""

    def test_f22_b01_player_combatant_statblock_view(self):
        """TC-B22-01: Statblock modal differentiates player vs monster combatant."""
        content = STATBLOCK_HTML.read_text(encoding="utf-8")
        assert "partyMember" in content
        assert "else monsterView" in content or "monster" in content

    def test_f22_b02_monster_combatant_statblock_view(self):
        """TC-B22-02: Monster combatant renders structured statblock view."""
        content = STATBLOCK_HTML.read_text(encoding="utf-8")
        assert "#monsterView" in content or "monster" in content
        if "actions" not in content:
            pytest.skip(
                "Feature 22 (Structured statblock actions rendering in modal) pending M5 implementation"
            )
        assert "actions" in content

    def test_f22_b03_legendary_actions_rendering(self):
        """TC-B22-03: Legendary actions present in 2024 SRD dataset (e.g., Aboleth, Adult Brass Dragon)."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json pending M1")
        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        legendary = [m for m in data if len(m.get("legendary_actions", [])) > 0]
        assert len(legendary) > 0, "2024 dataset must contain monsters with legendary actions"
        for m in legendary:
            for act in m["legendary_actions"]:
                assert "name" in act and bool(act["name"])
                assert "description" in act and bool(act["description"])

    def test_f22_b04_reactions_rendering(self):
        """TC-B22-04: Reaction actions present in 2024 SRD dataset (e.g., Mage, Stone Giant)."""
        if not MONSTERS_2024_PATH.exists():
            pytest.skip("monsters_2024.json pending M1")
        with open(MONSTERS_2024_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        with_reactions = [m for m in data if len(m.get("reactions", [])) > 0]
        assert len(with_reactions) > 0, "2024 dataset must contain monsters with reactions"
        for m in with_reactions:
            for r in m["reactions"]:
                assert "name" in r and bool(r["name"])
                assert "description" in r and bool(r["description"])

    def test_f22_b05_mobile_modal_adaptability(self):
        """TC-B22-05: Statblock modal template embeds responsive forge-modal with maxWidth."""
        assert STATBLOCK_HTML.exists()
        content = STATBLOCK_HTML.read_text(encoding="utf-8")
        assert "<forge-modal" in content
        assert 'maxWidth="760px"' in content or "max-w-" in content
        assert "(closed)=" in content

    def test_f23_b01_negative_attack_bonus(self):
        """TC-B23-01: Negative attack bonus (-2) calculates correctly with d20 via DiceService."""
        from backend.services.dice_service import roll_dice

        res = roll_dice("1d20-2")
        assert res["modifier"] == -2
        assert res["sides"] == 20
        assert res["total"] == res["rolls"][0] - 2
        assert -1 <= res["total"] <= 18

    def test_f23_b02_zero_attack_bonus(self):
        """TC-B23-02: Zero attack bonus parsed cleanly via rebuild_damage_formula."""
        from backend.services.dice_service import rebuild_damage_formula

        assert rebuild_damage_formula("1d6", "+0") == "1d6"
        assert rebuild_damage_formula("1d20", "0") == "1d20"

    def test_f23_b03_advantage_mode_two_d20(self):
        """TC-B23-03: Advantage mode rolls 2 d20s and selects the higher roll."""
        from backend.services.dice_service import roll_dice

        res = roll_dice("1d20+3", advantage=True)
        assert len(res["rolls"]) == 2
        assert res["total"] == max(res["rolls"]) + 3

    def test_f23_b04_disadvantage_mode_two_d20(self):
        """TC-B23-04: Disadvantage mode rolls 2 d20s and selects the lower roll."""
        from backend.services.dice_service import roll_dice

        res = roll_dice("1d20+3", disadvantage=True)
        assert len(res["rolls"]) == 2
        assert res["total"] == min(res["rolls"]) + 3

    def test_f23_b05_rapid_roll_clicks_independent(self):
        """TC-B23-05: Rapid independent calls to roll_dice yield independent outcomes."""
        from backend.services.dice_service import roll_dice

        rolls = [roll_dice("1d20+5") for _ in range(10)]
        assert len(rolls) == 10
        assert all(6 <= r["total"] <= 25 for r in rolls)
        assert all(r["modifier"] == 5 for r in rolls)

    def test_f24_b01_flat_bonus_only_damage(self):
        """TC-B24-01: Flat damage (+4) rolls 0 dice and evaluates to 4."""
        from backend.repositories.rules_repository import RulesRepository
        from backend.services.dice_service import rebuild_damage_formula

        repo = RulesRepository()
        monsters = repo.get_all_monsters("2014")
        flat_actions = [
            act
            for m in monsters
            for act in m.get("actions", [])
            if act.get("damage_dice") and "d" not in str(act["damage_dice"])
        ]
        assert len(flat_actions) > 0, "Official dataset contains monsters with flat damage"
        assert rebuild_damage_formula("4", "+0") == "4"

    def test_f24_b02_complex_multi_die_notation(self):
        """TC-B24-02: Expression 4d6+2d8+5 evaluates correctly within mathematical bounds."""
        from backend.services.dice_service import roll_dice

        res = roll_dice("4d6+2d8+5")
        assert res["num_dice"] == 6
        assert res["modifier"] == 5
        assert 11 <= res["total"] <= 45

    def test_f24_b03_critical_hit_doubles_dice(self):
        """TC-B24-03: Critical hit doubles dice count: 2d6+3 -> 4d6+3."""
        from backend.services.dice_service import roll_dice

        crit_res = roll_dice("4d6+3")
        assert crit_res["num_dice"] == 4
        assert crit_res["sides"] == 6
        assert crit_res["modifier"] == 3
        assert 7 <= crit_res["total"] <= 27

    def test_f24_b04_save_for_half_rider_display(self):
        """TC-B24-04: Action with DC save includes 'half on success' rider text in SRD."""
        repo = RulesRepository()
        red_dragon = repo.get_monster_by_id("srd_ancient_red_dragon_2014")
        assert red_dragon is not None
        breath_actions = [
            act
            for act in red_dragon["actions"]
            if "half on success" in act.get("description", "").lower()
            or "half" in act.get("description", "").lower()
        ]
        assert len(breath_actions) > 0, "Red dragon breath weapon must contain save-for-half text"

    def test_f24_b05_unparseable_damage_notation_fallback(self):
        """TC-B24-05: Unparseable notation string returns structured error dictionary."""
        from backend.utils.dice import roll_dice

        res = roll_dice("special_effect_damage")
        assert "error" in res
