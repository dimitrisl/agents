"""Tier 5 Backend Adversarial Test Suite for Milestone 6.

White-box adversarial stress testing covering:
1. Cache mutation attacks against `RulesRepository` (ensuring cached monster records cannot be mutated).
2. Immutability bypass attempts on `srd_*` monsters (PUT, PATCH, DELETE under various auth contexts and malformed IDs).
3. Ownership tampering on custom monsters (cross-user modification, unauthenticated modifications, falsified `creator_dm_id`).
4. Malformed/adversarial search query strings (regex special chars, ReDoS tokens, NoSQL injection tokens, unicode, script tags).
5. CR edge cases (extreme values, fractional string vs float, missing CR, invalid CR strings, discrepancy analysis).
6. Clone attacks (deep clone chains, self-referential `based_on`, nonexistent `based_on` ID, cascade isolation).
7. Schema validation stress (oversized arrays, negative/out-of-bounds stats, missing optional keys, null values).
8. Static rules JSON integrity and full CR 0 to CR 24 coverage.
"""

from typing import Any, Generator, List, Optional

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.core.schemas import (
    Monster,
    MonsterStats,
)
from backend.repositories.rules_repository import RulesRepository
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter

# --------------------------------------------------------------------------- #
# In-Memory Async MongoDB Mock Fixture Helpers                                #
# --------------------------------------------------------------------------- #


class _AsyncCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._iter = None

    def __iter__(self):
        return iter(self._cursor)

    def __aiter__(self):
        self._iter = iter(list(self._cursor))
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    async def to_list(self, length: Optional[int] = None) -> List[Any]:
        docs = list(self._cursor)
        if length is not None:
            docs = docs[:length]
        return docs


class _AsyncCollection:
    def __init__(self, coll):
        self._coll = coll

    async def insert_one(self, *args, **kwargs):
        return self._coll.insert_one(*args, **kwargs)

    async def insert_many(self, *args, **kwargs):
        return self._coll.insert_many(*args, **kwargs)

    async def find_one(self, *args, **kwargs):
        return self._coll.find_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._coll.update_one(*args, **kwargs)

    async def update_many(self, *args, **kwargs):
        return self._coll.update_many(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._coll.delete_one(*args, **kwargs)

    async def delete_many(self, *args, **kwargs):
        return self._coll.delete_many(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._coll.count_documents(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursor(self._coll.find(*args, **kwargs))


class _AsyncDatabase:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name: str):
        return _AsyncCollection(self._db[name])

    def __getattr__(self, name: str):
        return _AsyncCollection(getattr(self._db, name))


# --------------------------------------------------------------------------- #
# Test Fixtures                                                               #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def mock_db() -> _AsyncDatabase:
    client = mongomock.MongoClient()
    return _AsyncDatabase(client["phyrexian_forge_adversarial"])


@pytest.fixture
def dm_user_1() -> dict:
    return {"id": "dm_adversary_alpha", "username": "alpha_dm", "role": "dm"}


@pytest.fixture
def dm_user_2() -> dict:
    return {"id": "dm_adversary_beta", "username": "beta_dm", "role": "dm"}


@pytest.fixture
def client(mock_db: _AsyncDatabase, dm_user_1: dict) -> Generator[TestClient, None, None]:
    """TestClient default-authenticated as DM Alpha."""
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: dm_user_1
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture
def client_unauth(mock_db: _AsyncDatabase) -> Generator[TestClient, None, None]:
    """TestClient with no user authentication configured."""
    app.dependency_overrides[get_database] = lambda: mock_db
    # Do not override get_current_user so real auth dependency runs
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


# ==============================================================================
# Suite 1: RulesRepository Cache Mutation Attacks
# ==============================================================================


class TestRulesRepositoryCacheMutation:
    """Stress tests verifying that callers mutating returned monster objects
    cannot corrupt or alter internal module-level RulesRepository caches."""

    def test_get_all_monsters_cache_mutation_defense(self):
        """Mutating objects returned by get_all_monsters must not alter subsequent calls."""
        repo = RulesRepository()

        # 1. Fetch initial monsters list
        monsters_first = repo.get_all_monsters("2014")
        assert len(monsters_first) > 0
        original_name = monsters_first[0]["name"]
        original_hp = monsters_first[0]["hp"]
        original_str = monsters_first[0]["stats"]["str"]

        # 2. Hostile in-place mutation of the returned list and dictionaries
        monsters_first[0]["name"] = "HOSTILE_MUTATED_MONSTER"
        monsters_first[0]["hp"] = -99999
        monsters_first[0]["stats"]["str"] = 9999
        monsters_first[0]["actions"].clear()
        monsters_first[0]["injected_exploit"] = True
        monsters_first.pop()

        # 3. Fetch second time — must be pristine deep copies
        monsters_second = repo.get_all_monsters("2014")
        assert monsters_second[0]["name"] == original_name
        assert monsters_second[0]["hp"] == original_hp
        assert monsters_second[0]["stats"]["str"] == original_str
        assert len(monsters_second[0]["actions"]) > 0
        assert "injected_exploit" not in monsters_second[0]
        assert len(monsters_second) == len(monsters_first) + 1

    def test_search_monsters_cache_mutation_defense(self):
        """Mutating results from search_monsters must not alter cache."""
        repo = RulesRepository()

        search_first = repo.search_monsters(query="goblin")
        assert len(search_first) > 0
        original_goblin_name = search_first[0]["name"]

        # Hostile mutation
        search_first[0]["name"] = "CORRUPTED_GOBLIN"
        search_first[0]["type"] = "aberration_hacked"

        search_second = repo.search_monsters(query="goblin")
        assert search_second[0]["name"] == original_goblin_name
        assert search_second[0]["type"] != "aberration_hacked"

    def test_get_monster_by_id_cache_mutation_defense(self):
        """Mutating monster record returned by get_monster_by_id must not alter cache."""
        repo = RulesRepository()

        m1 = repo.get_monster_by_id("srd_goblin_2014")
        assert m1 is not None
        original_ac = m1["ac"]

        # Hostile mutation
        m1["ac"] = 999
        m1["traits"].append({"name": "FakeTrait", "description": "Hacked"})

        m2 = repo.get_monster_by_id("srd_goblin_2014")
        assert m2 is not None
        assert m2["ac"] == original_ac
        trait_names = [t["name"] for t in m2["traits"]]
        assert "FakeTrait" not in trait_names

    def test_norm_edition_adversarial_inputs(self):
        """_norm_edition helper must handle adversarial inputs gracefully without throwing."""
        repo = RulesRepository()
        adversarial_editions = [
            None,
            "",
            "   ",
            123,
            0,
            -1,
            "2024_revised",
            "edition_2024_phb",
            "5.5e (2024)",
            "5e (2014)",
            "legacy",
            "DROP TABLE monsters;",
            {"edition": "2024"},
            ["2024"],
        ]
        for ed in adversarial_editions:
            # Should not raise exception
            monsters = repo.get_all_monsters(str(ed))
            assert isinstance(monsters, list)
            assert len(monsters) > 0

    def test_get_monster_by_id_adversarial_queries(self):
        """Path traversal, null bytes, and SQL injection strings in get_monster_by_id safely return None."""
        repo = RulesRepository()
        adversarial_ids = [
            "../../etc/passwd",
            "..\\..\\windows\\system32",
            "srd_goblin\x00_2014",
            "' OR '1'='1",
            "; DROP TABLE custom_monsters;--",
            "<script>alert(1)</script>",
            "srd_" + "a" * 1000,
            "",
            "   ",
            None,
            12345,
            {"id": "srd_goblin_2014"},
        ]
        for aid in adversarial_ids:
            res = repo.get_monster_by_id(aid)
            assert res is None


# ==============================================================================
# Suite 2: CR Numeric Parsing, Boundary & Discrepancy Analysis
# ==============================================================================


class TestCRNumericParsingAndFilteringAdversarial:
    """Stress tests on challenge rating parser, boundary values, and search discrepancies."""

    def test_parse_cr_numeric_fractions_and_integers(self):
        """Standard fraction and integer representations parse accurately."""
        assert RulesRepository._parse_cr_numeric("1/8") == pytest.approx(0.125)
        assert RulesRepository._parse_cr_numeric("1/4") == pytest.approx(0.25)
        assert RulesRepository._parse_cr_numeric("1/2") == pytest.approx(0.5)
        assert RulesRepository._parse_cr_numeric("0") == pytest.approx(0.0)
        assert RulesRepository._parse_cr_numeric("0.0") == pytest.approx(0.0)
        assert RulesRepository._parse_cr_numeric("1") == pytest.approx(1.0)
        assert RulesRepository._parse_cr_numeric("24") == pytest.approx(24.0)
        assert RulesRepository._parse_cr_numeric("30") == pytest.approx(30.0)

    def test_parse_cr_numeric_adversarial_strings(self):
        """Adversarial/malformed challenge rating inputs default safely to 0.0."""
        assert RulesRepository._parse_cr_numeric("1/0") == 0.0  # Zero division
        assert RulesRepository._parse_cr_numeric("0/0") == 0.0  # Zero division
        assert RulesRepository._parse_cr_numeric("1/2/3") == 0.0  # Multi-slash
        assert RulesRepository._parse_cr_numeric("abc/def") == 0.0  # Non-numeric
        assert RulesRepository._parse_cr_numeric("1/foo") == 0.0
        assert RulesRepository._parse_cr_numeric("/2") == 0.0
        assert RulesRepository._parse_cr_numeric("1/") == 0.0
        assert RulesRepository._parse_cr_numeric("") == 0.0
        assert RulesRepository._parse_cr_numeric("   ") == 0.0
        assert RulesRepository._parse_cr_numeric(None) == 0.0
        assert RulesRepository._parse_cr_numeric(object()) == 0.0
        assert RulesRepository._parse_cr_numeric([]) == 0.0
        assert RulesRepository._parse_cr_numeric({}) == 0.0

    def test_parse_cr_numeric_extreme_floats(self):
        """Extreme floats ('nan', 'inf', negative) behavior verification."""
        import math

        nan_res = RulesRepository._parse_cr_numeric("nan")
        assert math.isnan(nan_res)

        inf_res = RulesRepository._parse_cr_numeric("inf")
        assert math.isinf(inf_res)

        neg_fraction = RulesRepository._parse_cr_numeric("-1/4")
        assert neg_fraction == pytest.approx(-0.25)

    def test_cr_filter_discrepancy_empirical_verification(self, client, mock_db):
        """Empirical verification of CR filter discrepancy between static SRD and custom MongoDB:
        Static SRD rules repo has a guard `if cr_target in ('0', '0.0') or target_num > 0`
        which prevents invalid strings like 'garbage_cr' from returning CR 0 official monsters.
        However, in custom monsters MongoDB query, target_cr_num is 0.0 for invalid strings,
        causing a query range [-1e-4, 1e-4] which matches custom CR 0 monsters."""
        # Insert a CR 0 custom monster
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Zero Custom Beast",
                "cr": "0",
                "hp": 5,
                "ac": 10,
                "edition": "2014",
            },
        )
        assert res.status_code == 201
        custom_id = res.json()["id"]

        # Query with an invalid/garbage CR string
        resp = client.get(
            "/api/v1/bestiary",
            params={
                "cr": "unparseable_garbage_cr",
                "include_official": True,
                "include_mine": True,
            },
        )
        assert resp.status_code == 200
        results = resp.json()

        # Official CR 0 monsters are NOT returned (protected by RulesRepository guard)
        official_zero = [r for r in results if r.get("origin") == "official" and r.get("cr") == "0"]
        assert len(official_zero) == 0

        # Custom CR 0 monster IS returned due to bestiary_router line 133-146 treating
        # unparseable string as 0.0 without the same string guard
        custom_matched = [r for r in results if r["id"] == custom_id]
        assert len(custom_matched) == 1, (
            "Custom CR 0 monster matched query cr='unparseable_garbage_cr' because "
            "bestiary_router computes target_cr_num=0.0 and queries cr_numeric in [-1e-4, 1e-4]"
        )

    def test_cr_filter_fraction_tolerance_float_matching(self, client):
        """Querying cr='0.5' matches '1/2' and vice versa via numeric cr_numeric matching."""
        # Create a custom monster with CR "1/2"
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Half Orc Scout",
                "cr": "1/2",
                "hp": 15,
                "ac": 13,
            },
        )
        assert res.status_code == 201

        # Query by decimal "0.5"
        resp = client.get(
            "/api/v1/bestiary",
            params={"cr": "0.5", "include_mine": True, "include_official": False},
        )
        assert resp.status_code == 200
        matches = resp.json()
        assert any(m["name"] == "Half Orc Scout" for m in matches)

        # Query by fraction "1/2"
        resp2 = client.get(
            "/api/v1/bestiary",
            params={"cr": "1/2", "include_mine": True, "include_official": False},
        )
        assert resp2.status_code == 200
        matches2 = resp2.json()
        assert any(m["name"] == "Half Orc Scout" for m in matches2)


# ==============================================================================
# Suite 3: Official SRD Immutability Defense
# ==============================================================================


class TestOfficialSRDImmutabilityDefense:
    """Rigorous tests confirming that official SRD monsters (srd_*) cannot be
    modified, updated, patched, or deleted through any HTTP path or auth context."""

    def test_put_official_monster_direct_id_returns_403(self, client):
        """Direct PUT against official SRD monster returns 403 Forbidden."""
        resp = client.put(
            "/api/v1/bestiary/srd_goblin_2014",
            json={"name": "Hacked Goblin", "hp": 999},
        )
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"].lower()

    def test_delete_official_monster_direct_id_returns_403(self, client):
        """Direct DELETE against official SRD monster returns 403 Forbidden."""
        resp = client.delete("/api/v1/bestiary/srd_goblin_2014")
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"].lower()

    def test_patch_visibility_official_monster_returns_403(self, client):
        """Direct PATCH visibility against official SRD monster returns 403 Forbidden."""
        resp = client.patch(
            "/api/v1/bestiary/srd_goblin_2014/visibility",
            json={"is_public": False},
        )
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"].lower()

    def test_put_official_monster_url_encoded_returns_403(self, client):
        """URL-encoded srd%5f prefix is decoded and rejected with 403 Forbidden."""
        resp = client.put(
            "/api/v1/bestiary/srd%5fgoblin_2014",
            json={"name": "Encoded Hacked Goblin"},
        )
        assert resp.status_code == 403

    def test_case_variation_on_official_monster_safely_rejected(self, client):
        """Targeting uppercase 'SRD_goblin_2014' or mixed-case is safely rejected
        without mutating or deleting anything (returns 404 because MongoDB doesn't have it)."""
        put_resp = client.put(
            "/api/v1/bestiary/SRD_goblin_2014",
            json={"name": "Uppercase Exploit"},
        )
        # Does NOT succeed in mutating; returns 404 because it is not in custom_monsters
        assert put_resp.status_code in (403, 404)

        del_resp = client.delete("/api/v1/bestiary/SRD_goblin_2014")
        assert del_resp.status_code in (403, 404)

        patch_resp = client.patch(
            "/api/v1/bestiary/SRD_goblin_2014/visibility",
            json={"is_public": False},
        )
        assert patch_resp.status_code in (403, 404)

        # Confirm the underlying SRD monster is completely untouched
        repo = RulesRepository()
        goblin = repo.get_monster_by_id("srd_goblin_2014")
        assert goblin["name"] == "Goblin"

    def test_put_and_delete_official_monster_without_srd_prefix(self, client):
        """Targeting 'goblin_2014' without 'srd_' prefix returns 404, preventing bypass."""
        put_resp = client.put(
            "/api/v1/bestiary/goblin_2014",
            json={"name": "Prefix-less exploit"},
        )
        assert put_resp.status_code == 404

        del_resp = client.delete("/api/v1/bestiary/goblin_2014")
        assert del_resp.status_code == 404


# ==============================================================================
# Suite 4: Custom Monster Ownership and Tampering Defense
# ==============================================================================


class TestCustomMonsterOwnershipAndTamperingDefense:
    """Verifies strict cross-user ownership isolation, privacy scoping,
    and immunity to falsified creator_dm_id injection."""

    def test_unauthenticated_requests_rejected_with_401(self, client_unauth):
        """All Bestiary REST operations require authentication."""
        assert client_unauth.get("/api/v1/bestiary").status_code == 401
        assert client_unauth.get("/api/v1/bestiary/srd_goblin_2014").status_code == 401
        assert client_unauth.post("/api/v1/bestiary", json={"name": "A"}).status_code == 401
        assert client_unauth.put("/api/v1/bestiary/some_id", json={"name": "A"}).status_code == 401
        assert (
            client_unauth.patch(
                "/api/v1/bestiary/some_id/visibility", json={"is_public": True}
            ).status_code
            == 401
        )
        assert client_unauth.delete("/api/v1/bestiary/some_id").status_code == 401

    def test_cross_user_private_monster_retrieval_forbidden(self, client, dm_user_1, dm_user_2):
        """DM Beta cannot GET DM Alpha's private custom monster (403 Forbidden)."""
        app.dependency_overrides[get_current_user] = lambda: dm_user_1
        create_res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Alpha Private Chimera",
                "is_public": False,
                "hp": 100,
                "ac": 15,
            },
        )
        assert create_res.status_code == 201
        monster_id = create_res.json()["id"]

        # DM Alpha can view it
        get_alpha = client.get(f"/api/v1/bestiary/{monster_id}")
        assert get_alpha.status_code == 200

        # DM Beta cannot view it
        app.dependency_overrides[get_current_user] = lambda: dm_user_2
        get_beta = client.get(f"/api/v1/bestiary/{monster_id}")
        assert get_beta.status_code == 403
        assert "permission" in get_beta.json()["detail"].lower()

    def test_cross_user_private_monster_not_leaked_in_lists(self, client, dm_user_1, dm_user_2):
        """Private monsters never leak into other users' search results."""
        app.dependency_overrides[get_current_user] = lambda: dm_user_1
        client.post(
            "/api/v1/bestiary",
            json={
                "name": "SuperSecretBossMonsterXYZ",
                "is_public": False,
                "hp": 250,
                "ac": 18,
            },
        )

        # DM Beta queries mine
        app.dependency_overrides[get_current_user] = lambda: dm_user_2
        res_mine = client.get(
            "/api/v1/bestiary",
            params={"include_mine": True, "include_community": False, "include_official": False},
        )
        assert all("SuperSecretBossMonsterXYZ" not in m["name"] for m in res_mine.json())

        # DM Beta queries community
        res_community = client.get(
            "/api/v1/bestiary",
            params={"include_mine": False, "include_community": True, "include_official": False},
        )
        assert all("SuperSecretBossMonsterXYZ" not in m["name"] for m in res_community.json())

    def test_cross_user_update_tampering_rejected_with_403(self, client, dm_user_1, dm_user_2):
        """DM Beta cannot update DM Alpha's monster (403 Forbidden)."""
        app.dependency_overrides[get_current_user] = lambda: dm_user_1
        create_res = client.post(
            "/api/v1/bestiary",
            json={"name": "Alpha Guardian", "hp": 50, "ac": 12},
        )
        monster_id = create_res.json()["id"]

        # DM Beta attempts update
        app.dependency_overrides[get_current_user] = lambda: dm_user_2
        put_res = client.put(
            f"/api/v1/bestiary/{monster_id}",
            json={"name": "Defaced by Beta", "hp": 1},
        )
        assert put_res.status_code == 403
        assert "own this monster" in put_res.json()["detail"].lower()

        # Confirm monster remained intact
        app.dependency_overrides[get_current_user] = lambda: dm_user_1
        get_res = client.get(f"/api/v1/bestiary/{monster_id}")
        assert get_res.json()["name"] == "Alpha Guardian"
        assert get_res.json()["hp"] == 50

    def test_cross_user_visibility_tampering_rejected_with_403(self, client, dm_user_1, dm_user_2):
        """DM Beta cannot toggle visibility of DM Alpha's monster (403 Forbidden)."""
        app.dependency_overrides[get_current_user] = lambda: dm_user_1
        create_res = client.post(
            "/api/v1/bestiary",
            json={"name": "Alpha Secret Beast", "is_public": False},
        )
        monster_id = create_res.json()["id"]

        # DM Beta attempts toggle
        app.dependency_overrides[get_current_user] = lambda: dm_user_2
        patch_res = client.patch(
            f"/api/v1/bestiary/{monster_id}/visibility",
            json={"is_public": True},
        )
        assert patch_res.status_code == 403

        # Confirm is_public is still False
        app.dependency_overrides[get_current_user] = lambda: dm_user_1
        get_res = client.get(f"/api/v1/bestiary/{monster_id}")
        assert get_res.json()["is_public"] is False

    def test_cross_user_deletion_tampering_rejected_with_403(self, client, dm_user_1, dm_user_2):
        """DM Beta cannot delete DM Alpha's monster (403 Forbidden)."""
        app.dependency_overrides[get_current_user] = lambda: dm_user_1
        create_res = client.post(
            "/api/v1/bestiary",
            json={"name": "Alpha Indestructible", "hp": 75},
        )
        monster_id = create_res.json()["id"]

        # DM Beta attempts deletion
        app.dependency_overrides[get_current_user] = lambda: dm_user_2
        del_res = client.delete(f"/api/v1/bestiary/{monster_id}")
        assert del_res.status_code == 403

        # Confirm monster still exists
        app.dependency_overrides[get_current_user] = lambda: dm_user_1
        get_res = client.get(f"/api/v1/bestiary/{monster_id}")
        assert get_res.status_code == 200

    def test_falsified_creator_dm_id_and_origin_injection_on_create(self, client):
        """Client attempting to falsify creator_dm_id, origin, or id on creation is overridden."""
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Spoofed Monster",
                "creator_dm_id": "spoofed_admin_id",
                "origin": "official",
                "id": "srd_spoofed_god",
                "hp": 100,
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["creator_dm_id"] == "dm_adversary_alpha"
        assert data["origin"] == "custom"
        assert data["id"] != "srd_spoofed_god"

    def test_falsified_creator_dm_id_and_origin_injection_on_update(self, client):
        """Client attempting to change creator_dm_id, origin, or id via PUT has fields stripped."""
        create_res = client.post(
            "/api/v1/bestiary",
            json={"name": "Immutable Provenance Beast", "hp": 50},
        )
        monster_id = create_res.json()["id"]

        # Attempt to transfer ownership or promote to official via PUT
        update_res = client.put(
            f"/api/v1/bestiary/{monster_id}",
            json={
                "name": "Updated Name",
                "creator_dm_id": "transferred_owner",
                "origin": "official",
                "id": "srd_new_id",
            },
        )
        assert update_res.status_code == 200
        updated = update_res.json()
        assert updated["id"] == monster_id
        assert updated["creator_dm_id"] == "dm_adversary_alpha"
        assert updated["origin"] == "custom"

    def test_public_monster_still_ownership_protected(self, client, dm_user_1, dm_user_2):
        """Making a custom monster public allows other DMs to read it, but NOT to edit or delete it."""
        app.dependency_overrides[get_current_user] = lambda: dm_user_1
        create_res = client.post(
            "/api/v1/bestiary",
            json={"name": "Alpha Community Hydra", "is_public": True, "hp": 150},
        )
        monster_id = create_res.json()["id"]

        # DM Beta can read it
        app.dependency_overrides[get_current_user] = lambda: dm_user_2
        get_res = client.get(f"/api/v1/bestiary/{monster_id}")
        assert get_res.status_code == 200

        # DM Beta cannot edit it
        put_res = client.put(
            f"/api/v1/bestiary/{monster_id}",
            json={"name": "Beta Defaced Hydra"},
        )
        assert put_res.status_code == 403

        # DM Beta cannot delete it
        del_res = client.delete(f"/api/v1/bestiary/{monster_id}")
        assert del_res.status_code == 403


# ==============================================================================
# Suite 5: Adversarial Search and Injection Defense
# ==============================================================================


class TestAdversarialSearchAndInjectionDefense:
    """Verifies that search inputs with regex metacharacters, NoSQL injection tokens,
    ReDoS patterns, XSS tags, and Unicode survive without server errors or injection."""

    def test_search_regex_special_characters_escaped(self, client):
        """Regex metacharacters (.*, ^$, [], +, ?) do not trigger broad wildcard matching."""
        # Query with '.*'
        resp = client.get(
            "/api/v1/bestiary",
            params={"search": ".*", "include_official": True},
        )
        assert resp.status_code == 200
        # Should not match all monsters (must only match monsters with literal '.*' in name)
        results = resp.json()
        assert len(results) == 0

    def test_search_redos_payload_survives_without_backtracking(self, client):
        """ReDoS payload does not cause server hang or catastrophic backtracking."""
        redos_payload = "a" * 500 + "!@#"
        resp = client.get(
            "/api/v1/bestiary",
            params={"search": redos_payload},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_nosql_injection_tokens(self, client):
        """NoSQL injection tokens in search query parameter are treated as literal strings."""
        tokens = [
            '{"$gt": ""}',
            '{"$ne": null}',
            "[$ne]",
            '{"$regex": ".*"}',
            "'$or': [{}, {}]",
        ]
        for token in tokens:
            resp = client.get("/api/v1/bestiary", params={"search": token})
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)

    def test_search_xss_and_html_injection(self, client):
        """XSS payloads in search queries execute safely without 500 error."""
        xss_queries = [
            "<script>alert(1)</script>",
            '<img src=x onerror="alert(document.cookie)">',
            "<svg/onload=alert(1)>",
            "javascript:alert(1)",
        ]
        for xss in xss_queries:
            resp = client.get("/api/v1/bestiary", params={"search": xss})
            assert resp.status_code == 200
            assert resp.json() == []

    def test_search_unicode_and_emojis(self, client):
        """Search handles Unicode, emojis, and control characters safely."""
        queries = ["🐉", "⚔️", "\u200b", "\ufeff", "Dragón", "Goblïn"]
        for q in queries:
            resp = client.get("/api/v1/bestiary", params={"search": q})
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)

    def test_search_whitespace_variations(self, client):
        """Whitespace-only search query is treated as no-op (returns monsters matching other filters)."""
        resp_all = client.get(
            "/api/v1/bestiary",
            params={"include_official": True, "edition": "2014"},
        )
        count_all = len(resp_all.json())

        resp_ws = client.get(
            "/api/v1/bestiary",
            params={"search": "   \t\n  ", "include_official": True, "edition": "2014"},
        )
        assert resp_ws.status_code == 200
        assert len(resp_ws.json()) == count_all

    def test_adversarial_monster_type_query(self, client):
        """Creature type filter handles adversarial strings safely:
        1. Impossible non-matching types return empty list.
        2. In MongoDB custom monsters, re.escape treats '.*' as literal string,
           preventing regex wildcards."""
        resp_alien = client.get(
            "/api/v1/bestiary",
            params={
                "monster_type": "impossible_nonexistent_alien_type_xyz",
                "include_official": True,
            },
        )
        assert resp_alien.status_code == 200
        assert len(resp_alien.json()) == 0

        # Custom monsters use MongoDB regex with re.escape
        client.post(
            "/api/v1/bestiary",
            json={"name": "Custom Humanoid Warrior", "type": "humanoid", "hp": 25},
        )
        resp_custom = client.get(
            "/api/v1/bestiary",
            params={
                "monster_type": ".*humanoid.*",
                "include_official": False,
                "include_mine": True,
            },
        )
        assert resp_custom.status_code == 200
        # Custom humanoid does NOT match because re.escape escapes '.*' to literal '\\.\\*'
        assert len(resp_custom.json()) == 0


# ==============================================================================
# Suite 6: Clone Attacks, Deep Chains & Cascade Isolation
# ==============================================================================


class TestCloneAttacksAndProvenance:
    """Tests clone reference integrity, nonexistent based_on handling,
    deep clone hierarchies, and cascade deletion isolation."""

    def test_clone_nonexistent_based_on_id_succeeds(self, client):
        """Cloning with a nonexistent based_on ID records the reference without crashing."""
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Ghost Clone",
                "based_on": "nonexistent_monster_id_9999",
                "hp": 20,
                "ac": 11,
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["based_on"] == "nonexistent_monster_id_9999"

    def test_clone_whitespace_based_on_trimmed(self, client):
        """based_on with leading/trailing whitespace is properly trimmed."""
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Trimmed Clone",
                "based_on": "   srd_goblin_2014   ",
                "hp": 20,
            },
        )
        assert res.status_code == 201
        assert res.json()["based_on"] == "srd_goblin_2014"

    def test_deep_clone_chain_independence(self, client):
        """A -> B -> C -> D clone chain: all nodes maintain independent state,
        and deleting an intermediate node does not break or cascade to others."""
        # 1. Node A (from SRD)
        res_a = client.post(
            "/api/v1/bestiary",
            json={"name": "Monster Alpha", "based_on": "srd_goblin_2014", "hp": 10},
        )
        id_a = res_a.json()["id"]

        # 2. Node B (from A)
        res_b = client.post(
            "/api/v1/bestiary",
            json={"name": "Monster Beta", "based_on": id_a, "hp": 20},
        )
        id_b = res_b.json()["id"]

        # 3. Node C (from B)
        res_c = client.post(
            "/api/v1/bestiary",
            json={"name": "Monster Gamma", "based_on": id_b, "hp": 30},
        )
        id_c = res_c.json()["id"]

        # 4. Node D (from C)
        res_d = client.post(
            "/api/v1/bestiary",
            json={"name": "Monster Delta", "based_on": id_c, "hp": 40},
        )
        id_d = res_d.json()["id"]

        # Verify all 4 exist with distinct IDs and independent HPs
        assert len({id_a, id_b, id_c, id_d}) == 4

        # Mutate B
        put_b = client.put(f"/api/v1/bestiary/{id_b}", json={"hp": 99})
        assert put_b.status_code == 200

        # Verify A, C, D unchanged
        assert client.get(f"/api/v1/bestiary/{id_a}").json()["hp"] == 10
        assert client.get(f"/api/v1/bestiary/{id_c}").json()["hp"] == 30
        assert client.get(f"/api/v1/bestiary/{id_d}").json()["hp"] == 40

        # Delete B (intermediate node)
        del_b = client.delete(f"/api/v1/bestiary/{id_b}")
        assert del_b.status_code == 200

        # Verify A, C, D remain completely functional
        assert client.get(f"/api/v1/bestiary/{id_a}").status_code == 200
        assert client.get(f"/api/v1/bestiary/{id_c}").status_code == 200
        assert client.get(f"/api/v1/bestiary/{id_d}").status_code == 200


# ==============================================================================
# Suite 7: Schema Validation Stress, Boundaries & Payload Hardening
# ==============================================================================


class TestSchemaValidationStressAndBoundaries:
    """Defensive schema boundary testing against Pydantic validation rules."""

    def test_monster_stats_boundaries_and_rejections(self):
        """Stats strictly enforce range 1 to 30."""
        # Valid boundary stats
        valid_min = MonsterStats(str=1, dex=1, con=1, int=1, wis=1, cha=1)
        assert valid_min.str == 1

        valid_max = MonsterStats(str=30, dex=30, con=30, int=30, wis=30, cha=30)
        assert valid_max.str == 30

        # Out-of-bounds rejections
        with pytest.raises(Exception):
            MonsterStats(str=0)

        with pytest.raises(Exception):
            MonsterStats(str=-5)

        with pytest.raises(Exception):
            MonsterStats(str=31)

        with pytest.raises(Exception):
            MonsterStats(str=100)

    def test_monster_stats_case_normalization(self):
        """Stats dictionary with uppercase or mixed-case keys is normalized."""
        stats = MonsterStats.model_validate({"STR": 16, "Dex": 14, "CON": 12})
        assert stats.str == 16
        assert stats.dex == 14
        assert stats.con == 12

    def test_monster_hp_boundaries(self, client):
        """HP strictly enforces 1 <= hp <= 2000."""
        # Valid boundaries
        res_min = client.post("/api/v1/bestiary", json={"name": "Min HP", "hp": 1})
        assert res_min.status_code == 201

        res_max = client.post("/api/v1/bestiary", json={"name": "Max HP", "hp": 2000})
        assert res_max.status_code == 201

        # Out of bounds
        assert client.post("/api/v1/bestiary", json={"name": "Zero HP", "hp": 0}).status_code == 422
        assert (
            client.post("/api/v1/bestiary", json={"name": "Neg HP", "hp": -10}).status_code == 422
        )
        assert (
            client.post("/api/v1/bestiary", json={"name": "Oversized HP", "hp": 2001}).status_code
            == 422
        )

    def test_monster_ac_boundaries(self, client):
        """AC strictly enforces ac >= 0."""
        res_zero = client.post("/api/v1/bestiary", json={"name": "AC Zero", "ac": 0})
        assert res_zero.status_code == 201

        res_neg = client.post("/api/v1/bestiary", json={"name": "AC Negative", "ac": -1})
        assert res_neg.status_code == 422

    def test_empty_or_whitespace_monster_name(self, client):
        """Empty or whitespace-only monster names are rejected with 422."""
        assert client.post("/api/v1/bestiary", json={"name": ""}).status_code == 422
        assert client.post("/api/v1/bestiary", json={"name": "   "}).status_code == 422
        assert client.post("/api/v1/bestiary", json={"name": "\t\n"}).status_code == 422

    def test_oversized_arrays_stress(self, client):
        """Payloads with large numbers of traits and actions serialize without failure."""
        traits = [{"name": f"Trait {i}", "description": f"Desc {i}"} for i in range(100)]
        actions = [
            {
                "name": f"Attack {i}",
                "attack_bonus": i % 10,
                "damage_dice": "1d8+2",
                "damage_type": "slashing",
                "description": f"Attack action {i}",
            }
            for i in range(100)
        ]

        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Hundred Action Colossus",
                "traits": traits,
                "actions": actions,
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert len(data["traits"]) == 100
        assert len(data["actions"]) == 100

    def test_missing_and_null_required_fields(self, client):
        """Missing or null required fields are properly caught by Pydantic."""
        assert client.post("/api/v1/bestiary", json={}).status_code == 422
        assert client.post("/api/v1/bestiary", json={"name": None}).status_code == 422

    def test_extreme_string_lengths(self, client):
        """Extremely long descriptions (20,000 chars) are stored safely."""
        long_desc = "Phyrexian bio-mechanical text. " * 600
        res = client.post(
            "/api/v1/bestiary",
            json={"name": "Colossal Scribe", "description": long_desc},
        )
        assert res.status_code == 201
        data = res.json()
        assert len(data["description"]) == len(long_desc)


# ==============================================================================
# Suite 8: Static SRD Monsters Integrity & Coverage Check
# ==============================================================================


class TestStaticSRDMonstersIntegrityAndCoverage:
    """Verifies that the static JSON rule files contain zero corrupt entries,
    follow naming invariants, and span CR 0 to CR 24."""

    def test_all_srd_monsters_valid_against_canonical_pydantic_schema(self):
        """Every single monster record in 2014 and 2024 JSON passes Pydantic validation."""
        repo = RulesRepository()
        for ed in ("2014", "2024"):
            monsters = repo.get_all_monsters(ed)
            assert len(monsters) >= 80, f"Edition {ed} should have >= 80 monsters"
            for m in monsters:
                validated = Monster.model_validate(m)
                assert validated.id.startswith("srd_")
                assert validated.origin == "official"
                assert validated.is_public is True
                assert 1 <= validated.stats.str <= 30
                assert 1 <= validated.stats.dex <= 30
                assert 1 <= validated.stats.con <= 30
                assert 1 <= validated.stats.int <= 30
                assert 1 <= validated.stats.wis <= 30
                assert 1 <= validated.stats.cha <= 30
                assert validated.hp >= 1
                assert validated.ac >= 0

    def test_all_srd_monster_ids_unique_within_each_edition(self):
        """IDs are unique within each edition dataset."""
        repo = RulesRepository()
        for ed in ("2014", "2024"):
            monsters = repo.get_all_monsters(ed)
            ids = [m["id"] for m in monsters]
            assert len(ids) == len(set(ids)), f"Duplicate IDs detected in edition {ed}"

    def test_cr_coverage_spans_cr_0_to_cr_24(self):
        """Both datasets contain monsters from CR 0 up to CR 24."""
        repo = RulesRepository()
        for ed in ("2014", "2024"):
            monsters = repo.get_all_monsters(ed)
            crs = {m.get("cr_numeric") for m in monsters if m.get("cr_numeric") is not None}
            assert 0.0 in crs, f"CR 0 missing in {ed}"
            assert any(cr >= 20.0 for cr in crs), f"High CR (>= 20) missing in {ed}"
            assert any(cr == 24.0 for cr in crs), f"CR 24 missing in {ed}"

    def test_all_srd_monsters_have_structured_actions_and_stats(self):
        """Every official monster has structured actions and complete stats."""
        repo = RulesRepository()
        for ed in ("2014", "2024"):
            monsters = repo.get_all_monsters(ed)
            for m in monsters:
                assert len(m.get("actions", [])) > 0, f"{m['name']} in {ed} has empty actions"
                stats = m.get("stats", {})
                for ability in ("str", "dex", "con", "int", "wis", "cha"):
                    assert ability in stats, f"{m['name']} in {ed} missing {ability}"
