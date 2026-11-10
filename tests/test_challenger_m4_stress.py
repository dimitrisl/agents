"""Empirical Challenger 2 Stress Test Suite for Milestone 4.

Focus:
1. Bestiary Browser filtering:
   - Multi-filter combinations (Edition, CR ranges, monster types, source chips).
   - Empty search results state.
   - Case-insensitive search queries and whitespace trimming.
2. Monster operations:
   - Cloning/forking (based_on, unique id, custom origin, creator_dm_id).
   - Visibility toggle (toggling state, official SRD immutability 403, non-owner 403).
   - Deletion (custom deletion 200, official SRD immutability 403, non-owner 403).
3. Riddle & Trap Generator:
   - Input binding, error handling, markdown structure, 401 unauth, 422 validation.
"""

import mongomock
import pytest
from fastapi.testclient import TestClient

from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter


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

    async def to_list(self, length=None):
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


@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def mock_db():
    client = mongomock.MongoClient()
    return _AsyncDatabase(client["phyrexian_forge_stress"])


@pytest.fixture
def dm_user():
    return {"id": "dm_challenger_1", "username": "challenger_dm", "role": "dm"}


@pytest.fixture
def other_dm_user():
    return {"id": "dm_other_999", "username": "other_dm", "role": "dm"}


@pytest.fixture
def client(mock_db, dm_user):
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: dm_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Bestiary Filtering Stress Tests
# ==============================================================================


class TestBestiaryFilteringStress:
    """Rigorous stress-testing of multi-filter combinations, case insensitivity,
    whitespace trimming, and empty states."""

    def test_multi_filter_combination_edition_and_type_and_cr(self, client):
        """Verify strict intersection of edition=2014, cr=1/4, and type=humanoid."""
        resp = client.get(
            "/api/v1/bestiary",
            params={
                "edition": "2014",
                "cr": "1/4",
                "monster_type": "humanoid",
                "include_official": True,
                "include_mine": False,
                "include_community": False,
            },
        )
        assert resp.status_code == 200
        monsters = resp.json()
        assert len(monsters) > 0
        for m in monsters:
            assert m["edition"] == "2014"
            assert m["cr"] == "1/4"
            assert "humanoid" in m["type"].lower()

    def test_multi_filter_2024_edition_dragons(self, client):
        """Verify 2024 edition dragons query."""
        resp = client.get(
            "/api/v1/bestiary",
            params={
                "edition": "2024",
                "monster_type": "dragon",
                "include_official": True,
            },
        )
        assert resp.status_code == 200
        monsters = resp.json()
        assert len(monsters) > 0
        for m in monsters:
            assert m["edition"] == "2024"
            assert "dragon" in m["type"].lower()

    def test_source_chips_all_off_returns_empty_list(self, client):
        """When include_official=False, include_mine=False, and include_community=False,
        result must be immediately empty."""
        resp = client.get(
            "/api/v1/bestiary",
            params={
                "include_official": False,
                "include_mine": False,
                "include_community": False,
            },
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_case_insensitive_and_whitespace_search(self, client):
        """Verify queries like '  gObLiN  ', '  DRAGON  ', and 'zOmBiE' match properly."""
        queries = ["  gObLiN  ", "DRAGON", "zOmBiE", "  aDuLt ReD dRaGoN  "]
        for q in queries:
            resp = client.get(
                "/api/v1/bestiary",
                params={"search": q, "include_official": True},
            )
            assert resp.status_code == 200
            monsters = resp.json()
            assert len(monsters) > 0
            clean_q = q.strip().lower()
            assert any(clean_q in m["name"].lower() for m in monsters)

    def test_empty_search_results_state_for_nonexistent_query(self, client):
        """Verify search with nonsensical query yields 200 OK with empty list."""
        resp = client.get(
            "/api/v1/bestiary",
            params={"search": "xYzNonExistentMonster999!@#$%", "include_official": True},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_fractional_cr_values_stress(self, client):
        """Verify all standard fractional CR values ('1/8', '1/4', '1/2') correctly filter."""
        for frac_cr in ["1/8", "1/4", "1/2"]:
            resp = client.get(
                "/api/v1/bestiary",
                params={"cr": frac_cr, "include_official": True},
            )
            assert resp.status_code == 200
            monsters = resp.json()
            assert len(monsters) > 0
            for m in monsters:
                assert m["cr"] == frac_cr

    def test_nonexistent_monster_type_returns_empty(self, client):
        """Filtering by an unsupported monster type like 'cyborg_automaton' returns empty."""
        resp = client.get(
            "/api/v1/bestiary",
            params={"monster_type": "cyborg_automaton", "include_official": True},
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ==============================================================================
# 2. Monster Operations Stress Tests (Clone, Visibility, Delete)
# ==============================================================================


class TestMonsterOperationsStress:
    """Stress tests verifying cloning provenance, visibility security invariants,
    and deletion protections for SRD and custom monsters."""

    def test_clone_official_srd_monster_provenance_and_fields(self, client, dm_user):
        """Cloning an official SRD monster creates a custom monster with based_on,
        new uuid, custom origin, and current user as creator."""
        # 1. Fetch official Goblin
        srd_resp = client.get("/api/v1/bestiary/srd_goblin_2014")
        assert srd_resp.status_code == 200
        srd_goblin = srd_resp.json()

        # 2. Clone it via POST /api/v1/bestiary
        clone_payload = {
            "name": "Goblin Chieftain (Boss)",
            "edition": srd_goblin["edition"],
            "size": srd_goblin["size"],
            "type": srd_goblin["type"],
            "alignment": srd_goblin["alignment"],
            "cr": "1",
            "cr_numeric": 1.0,
            "ac": 16,
            "hp": 24,
            "speed": srd_goblin["speed"],
            "stats": srd_goblin["stats"],
            "traits": srd_goblin["traits"],
            "actions": srd_goblin["actions"],
            "based_on": "srd_goblin_2014",
            "is_public": False,
        }
        create_resp = client.post("/api/v1/bestiary", json=clone_payload)
        assert create_resp.status_code == 201
        cloned = create_resp.json()

        # Invariant checks:
        assert cloned["id"] != "srd_goblin_2014"
        assert not cloned["id"].startswith("srd_")
        assert cloned["based_on"] == "srd_goblin_2014"
        assert cloned["origin"] == "custom"
        assert cloned["creator_dm_id"] == dm_user["id"]
        assert cloned["name"] == "Goblin Chieftain (Boss)"
        assert cloned["ac"] == 16
        assert cloned["hp"] == 24
        assert cloned["is_public"] is False

    def test_official_srd_monster_cannot_have_visibility_toggled(self, client):
        """PATCH /visibility on official srd_* monster must return HTTP 403 Forbidden."""
        resp = client.patch(
            "/api/v1/bestiary/srd_goblin_2014/visibility",
            json={"is_public": False},
        )
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"].lower()

    def test_custom_monster_visibility_toggle_cycle(self, client):
        """Custom monster visibility can be toggled private -> public -> private."""
        # Create private custom monster
        create_resp = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Shadow Creeper",
                "cr": "2",
                "hp": 30,
                "ac": 13,
                "is_public": False,
            },
        )
        assert create_resp.status_code == 201
        monster_id = create_resp.json()["id"]

        # Toggle to Public
        pub_resp = client.patch(
            f"/api/v1/bestiary/{monster_id}/visibility",
            json={"is_public": True},
        )
        assert pub_resp.status_code == 200
        assert pub_resp.json()["is_public"] is True

        # Verify through GET
        get_resp = client.get(f"/api/v1/bestiary/{monster_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["is_public"] is True

        # Toggle back to Private
        priv_resp = client.patch(
            f"/api/v1/bestiary/{monster_id}/visibility",
            json={"is_public": False},
        )
        assert priv_resp.status_code == 200
        assert priv_resp.json()["is_public"] is False

    def test_non_owner_cannot_toggle_visibility(self, client, other_dm_user):
        """Attempting to toggle visibility on a custom monster owned by another DM returns HTTP 403."""
        # Create monster as dm_user
        create_resp = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Secret Lich",
                "cr": "18",
                "hp": 150,
                "ac": 17,
                "is_public": False,
            },
        )
        monster_id = create_resp.json()["id"]

        # Switch auth to other_dm_user
        app.dependency_overrides[get_current_user] = lambda: other_dm_user
        resp = client.patch(
            f"/api/v1/bestiary/{monster_id}/visibility",
            json={"is_public": True},
        )
        assert resp.status_code == 403
        assert "do not own" in resp.json()["detail"].lower()

    def test_official_srd_monster_cannot_be_deleted(self, client):
        """DELETE on official srd_* monster must return HTTP 403 Forbidden."""
        resp = client.delete("/api/v1/bestiary/srd_goblin_2014")
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"].lower()

        # Verify srd_goblin_2014 still exists
        get_resp = client.get("/api/v1/bestiary/srd_goblin_2014")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Goblin"

    def test_custom_monster_can_be_deleted_by_owner(self, client):
        """Owner can delete their custom monster cleanly."""
        create_resp = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Temporary Minion",
                "cr": "1/2",
                "hp": 12,
                "ac": 11,
            },
        )
        monster_id = create_resp.json()["id"]

        # Delete it
        del_resp = client.delete(f"/api/v1/bestiary/{monster_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

        # Verify subsequent GET returns 404
        get_resp = client.get(f"/api/v1/bestiary/{monster_id}")
        assert get_resp.status_code == 404

    def test_non_owner_cannot_delete_custom_monster(self, client, other_dm_user):
        """Non-owner attempting to DELETE returns HTTP 403 Forbidden."""
        create_resp = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Protected Dragon",
                "cr": "10",
                "hp": 180,
                "ac": 18,
            },
        )
        monster_id = create_resp.json()["id"]

        # Switch auth to other_dm_user
        app.dependency_overrides[get_current_user] = lambda: other_dm_user
        del_resp = client.delete(f"/api/v1/bestiary/{monster_id}")
        assert del_resp.status_code == 403
        assert "do not own" in del_resp.json()["detail"].lower()


# ==============================================================================
# 3. Riddle & Trap Generator Stress Tests
# ==============================================================================


class TestRiddleGeneratorStress:
    """Stress tests for /api/v1/dm/riddle endpoint."""

    def test_riddle_generation_valid_location(self, client, monkeypatch):
        """Verify successful generation with location and edition."""
        monkeypatch.setattr(
            "server.routers.dm_router.generate_riddle",
            lambda loc, ed: f"# Riddle of the {loc}\n\nI speak without voice.\n\n**Answer:** Echo",
        )

        resp = client.post(
            "/api/v1/dm/riddle",
            json={"location": "Sphinx Crypt", "edition": "2014"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "riddle_markdown" in data
        assert "Riddle of the Sphinx Crypt" in data["riddle_markdown"]
        assert "Echo" in data["riddle_markdown"]

    def test_riddle_generation_missing_location_returns_422(self, client):
        """Missing location field fails schema validation with 422."""
        resp = client.post("/api/v1/dm/riddle", json={"edition": "2014"})
        assert resp.status_code == 422

    def test_riddle_generation_unauthenticated_returns_401(self, mock_db):
        """Unauthenticated call to /api/v1/dm/riddle returns 401."""
        app.dependency_overrides.clear()
        app.dependency_overrides[get_database] = lambda: mock_db
        with TestClient(app) as unauth_client:
            resp = unauth_client.post(
                "/api/v1/dm/riddle",
                json={"location": "Sunken Clockwork Foundry"},
            )
            assert resp.status_code == 401

    def test_riddle_generation_special_characters(self, client, monkeypatch):
        """Location with quotes, brackets, and unicode behaves gracefully."""
        monkeypatch.setattr(
            "server.routers.dm_router.generate_riddle",
            lambda loc, ed: f"Riddle for {loc}",
        )
        resp = client.post(
            "/api/v1/dm/riddle",
            json={"location": "O'Malley's \"Cursed\" Crypt [Level 3] ☠️"},
        )
        assert resp.status_code == 200
        assert "O'Malley's" in resp.json()["riddle_markdown"]
