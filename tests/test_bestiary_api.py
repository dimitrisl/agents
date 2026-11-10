"""Integration tests for Unified Bestiary REST API endpoints (/api/v1/bestiary).

Verifies all 6 endpoints, query filters, source flag combinations, clone flows,
official SRD immutability (403), ownership enforcement (403), privacy scoping,
and fractional CR mechanics.
"""

from typing import Any, Generator, List, Optional

import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.repositories.rules_repository import RulesRepository
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.rate_limiter import limiter

# --- In-Memory Async MongoDB Mock ---


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

    async def find_one_and_update(self, *args, **kwargs):
        return self._coll.find_one_and_update(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._coll.count_documents(*args, **kwargs)

    def find(self, *args, **kwargs):
        return _AsyncCursor(self._coll.find(*args, **kwargs))


class _AsyncDatabase:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name: str) -> _AsyncCollection:
        return _AsyncCollection(self._db[name])

    def __getattr__(self, name: str) -> _AsyncCollection:
        return _AsyncCollection(getattr(self._db, name))


# --- Fixtures ---


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def mock_db() -> _AsyncDatabase:
    client = mongomock.MongoClient()
    return _AsyncDatabase(client["phyrexian_forge_test"])


@pytest.fixture
def auth_context():
    """Stateful holder for current authenticated user."""
    return {"user": {"id": "user_dm_alice", "username": "dm_alice"}}


@pytest.fixture
def client(mock_db: _AsyncDatabase, auth_context: dict) -> Generator[TestClient, None, None]:
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: auth_context["user"]

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides = original_overrides


# ============================================================================
# Class 1: TestGetBestiaryList (GET /api/v1/bestiary)
# ============================================================================


class TestGetBestiaryList:
    def test_get_bestiary_default_filters(self, client: TestClient):
        res = client.get("/api/v1/bestiary")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert all(m["origin"] == "official" for m in data)

    def test_get_bestiary_filter_edition_2014(self, client: TestClient):
        res = client.get("/api/v1/bestiary?edition=2014")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 80
        assert all("2014" in str(m.get("edition")) for m in data)

    def test_get_bestiary_filter_edition_2024(self, client: TestClient):
        res = client.get("/api/v1/bestiary?edition=2024")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 75
        assert all("2024" in str(m.get("edition")) for m in data)

    def test_get_bestiary_filter_search_name(self, client: TestClient):
        res = client.get("/api/v1/bestiary?search=goblin")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        assert all("goblin" in m.get("name", "").lower() for m in data)

    def test_get_bestiary_filter_search_case_insensitivity(self, client: TestClient):
        res = client.get("/api/v1/bestiary?search=DRAGON")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        assert all("dragon" in m.get("name", "").lower() for m in data)

    def test_get_bestiary_filter_search_empty_match(self, client: TestClient):
        res = client.get("/api/v1/bestiary?search=nonexistent_monster_xyz_999999")
        assert res.status_code == 200
        assert res.json() == []

    def test_get_bestiary_filter_by_cr_integer(self, client: TestClient):
        res = client.get("/api/v1/bestiary?cr=1")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        for m in data:
            assert str(m.get("cr")) == "1" or m.get("cr_numeric") == 1.0

    def test_get_bestiary_filter_by_cr_fractional(self, client: TestClient):
        res = client.get("/api/v1/bestiary?cr=1/4")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        for m in data:
            assert str(m.get("cr")) == "1/4" or m.get("cr_numeric") == 0.25

    def test_get_bestiary_filter_by_cr_zero(self, client: TestClient):
        res = client.get("/api/v1/bestiary?cr=0")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        for m in data:
            assert str(m.get("cr")) == "0" or m.get("cr_numeric") == 0.0

    def test_get_bestiary_filter_by_monster_type(self, client: TestClient):
        res = client.get("/api/v1/bestiary?monster_type=undead")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        assert all("undead" in str(m.get("type", "")).lower() for m in data)

    def test_get_bestiary_include_official_false(self, client: TestClient):
        client.post(
            "/api/v1/bestiary",
            json={
                "name": "Blight Beetle",
                "edition": "2024",
                "cr": "1",
                "ac": 12,
                "hp": 22,
                "stats": {
                    "str": 10,
                    "dex": 12,
                    "con": 12,
                    "int": 3,
                    "wis": 10,
                    "cha": 4,
                },
            },
        )
        res = client.get("/api/v1/bestiary?include_official=false&include_mine=true")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["name"] == "Blight Beetle"
        assert data[0]["origin"] == "custom"

    def test_get_bestiary_include_mine_isolation(self, client: TestClient, auth_context: dict):
        # Alice creates private monster
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        client.post(
            "/api/v1/bestiary",
            json={
                "name": "Alice Secret Monster",
                "is_public": False,
                "edition": "2024",
                "cr": "2",
                "ac": 13,
                "hp": 30,
            },
        )

        # Bob queries his own custom monsters
        auth_context["user"] = {"id": "user_dm_bob", "username": "dm_bob"}
        res = client.get(
            "/api/v1/bestiary?include_official=false&include_mine=true&include_community=false"
        )
        assert res.status_code == 200
        assert not any(m["name"] == "Alice Secret Monster" for m in res.json())

    def test_get_bestiary_include_community_public_only(
        self, client: TestClient, auth_context: dict
    ):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        client.post(
            "/api/v1/bestiary",
            json={
                "name": "Public Minotaur",
                "is_public": True,
                "edition": "2024",
                "cr": "3",
                "ac": 14,
                "hp": 45,
            },
        )
        client.post(
            "/api/v1/bestiary",
            json={
                "name": "Private Sphinx",
                "is_public": False,
                "edition": "2024",
                "cr": "5",
                "ac": 16,
                "hp": 80,
            },
        )

        # Switch to Bob
        auth_context["user"] = {"id": "user_dm_bob", "username": "dm_bob"}
        res = client.get(
            "/api/v1/bestiary?include_official=false&include_mine=false&include_community=true"
        )
        assert res.status_code == 200
        names = [m["name"] for m in res.json()]
        assert "Public Minotaur" in names
        assert "Private Sphinx" not in names

    def test_get_bestiary_all_source_flags_false_returns_empty(self, client: TestClient):
        res = client.get(
            "/api/v1/bestiary?include_official=false&include_mine=false&include_community=false"
        )
        assert res.status_code == 200
        assert res.json() == []

    def test_get_bestiary_deduplication_mine_and_community(
        self, client: TestClient, auth_context: dict
    ):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        created = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Shared Chimera",
                "is_public": True,
                "edition": "2024",
                "cr": "6",
                "ac": 14,
                "hp": 90,
            },
        ).json()

        res = client.get(
            "/api/v1/bestiary?include_official=false&include_mine=true&include_community=true"
        )
        assert res.status_code == 200
        data = res.json()
        ids = [m["id"] for m in data if m["id"] == created["id"]]
        assert len(ids) == 1, "Public monster owned by user must appear exactly once"


# ============================================================================
# Class 2: TestGetBestiaryById (GET /api/v1/bestiary/{id})
# ============================================================================


class TestGetBestiaryById:
    def test_get_official_2014_monster_by_id(self, client: TestClient):
        res = client.get("/api/v1/bestiary/srd_goblin_2014")
        assert res.status_code == 200
        m = res.json()
        assert m["id"] == "srd_goblin_2014"
        assert m["origin"] == "official"
        assert m["is_public"] is True
        assert len(m["actions"]) > 0

    def test_get_official_2024_monster_by_id(self, client: TestClient):
        res = client.get("/api/v1/bestiary/srd_goblin_2024")
        assert res.status_code == 200
        m = res.json()
        assert m["id"] == "srd_goblin_2024"
        assert "2024" in str(m["edition"])

    def test_get_own_custom_private_monster_by_id(self, client: TestClient, auth_context: dict):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        created = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Secret Golem",
                "is_public": False,
                "edition": "2024",
                "cr": "4",
                "ac": 16,
                "hp": 70,
            },
        ).json()

        res = client.get(f"/api/v1/bestiary/{created['id']}")
        assert res.status_code == 200
        assert res.json()["name"] == "Secret Golem"

    def test_get_community_public_monster_by_id(self, client: TestClient, auth_context: dict):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        created = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Public Drake",
                "is_public": True,
                "edition": "2024",
                "cr": "3",
                "ac": 14,
                "hp": 55,
            },
        ).json()

        # Bob fetches it
        auth_context["user"] = {"id": "user_dm_bob", "username": "dm_bob"}
        res = client.get(f"/api/v1/bestiary/{created['id']}")
        assert res.status_code == 200
        assert res.json()["name"] == "Public Drake"

    def test_get_other_user_private_monster_rejected(self, client: TestClient, auth_context: dict):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        created = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Alice Fortress Guardian",
                "is_public": False,
                "edition": "2024",
                "cr": "10",
                "ac": 18,
                "hp": 150,
            },
        ).json()

        # Bob attempts fetch
        auth_context["user"] = {"id": "user_dm_bob", "username": "dm_bob"}
        res = client.get(f"/api/v1/bestiary/{created['id']}")
        assert res.status_code in (403, 404)

    def test_get_monster_not_found_returns_404(self, client: TestClient):
        res = client.get("/api/v1/bestiary/custom_nonexistent_id_999")
        assert res.status_code == 404

    def test_get_official_monster_not_found_returns_404(self, client: TestClient):
        res = client.get("/api/v1/bestiary/srd_nonexistent_creature_999")
        assert res.status_code == 404

    def test_get_monster_path_traversal_returns_404(self, client: TestClient):
        res = client.get("/api/v1/bestiary/..%2F..%2Fetc%2Fpasswd")
        assert res.status_code in (404, 422)


# ============================================================================
# Class 3: TestCreateBestiaryMonster (POST /api/v1/bestiary)
# ============================================================================


class TestCreateBestiaryMonster:
    def test_create_custom_monster_scratch_success(self, client: TestClient, auth_context: dict):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Grave Ghoul",
                "edition": "2024",
                "cr": "2",
                "ac": 13,
                "hp": 36,
                "stats": {
                    "str": 14,
                    "dex": 12,
                    "con": 14,
                    "int": 6,
                    "wis": 10,
                    "cha": 6,
                },
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert "id" in data
        assert not data["id"].startswith("srd_")
        assert data["creator_dm_id"] == "user_dm_alice"
        assert data["origin"] == "custom"
        assert data["cr_numeric"] == 2.0
        assert data["max_hp"] == 36
        assert data["is_public"] is False

    def test_clone_official_monster_via_based_on(self, client: TestClient):
        repo = RulesRepository()
        orig_goblin = repo.get_monster_by_id("srd_goblin_2014")
        assert orig_goblin is not None

        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Goblin Chieftain",
                "based_on": "srd_goblin_2014",
                "edition": "2014",
                "cr": "1",
                "ac": 16,
                "hp": 24,
                "stats": {
                    "str": 10,
                    "dex": 16,
                    "con": 12,
                    "int": 10,
                    "wis": 10,
                    "cha": 10,
                },
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["based_on"] == "srd_goblin_2014"
        assert data["origin"] == "custom"

        # Verify RulesRepository copy was not mutated
        after_goblin = repo.get_monster_by_id("srd_goblin_2014")
        assert after_goblin["name"] == orig_goblin["name"]

    def test_clone_custom_monster_via_based_on(self, client: TestClient):
        parent = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Alpha Wolf",
                "edition": "2024",
                "cr": "2",
                "ac": 13,
                "hp": 30,
            },
        ).json()

        child_res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Dire Alpha Wolf",
                "based_on": parent["id"],
                "edition": "2024",
                "cr": "3",
                "ac": 14,
                "hp": 45,
            },
        )
        assert child_res.status_code == 201
        assert child_res.json()["based_on"] == parent["id"]

    @pytest.mark.parametrize(
        ("cr_in", "expected_numeric"),
        [
            ("0", 0.0),
            ("1/8", 0.125),
            ("1/4", 0.25),
            ("1/2", 0.5),
            ("1", 1.0),
            ("10", 10.0),
        ],
    )
    def test_create_fractional_cr_parsing(
        self, client: TestClient, cr_in: str, expected_numeric: float
    ):
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": f"Test CR {cr_in}",
                "edition": "2024",
                "cr": cr_in,
                "ac": 10,
                "hp": 10,
            },
        )
        assert res.status_code == 201
        assert abs(res.json()["cr_numeric"] - expected_numeric) < 1e-4

    def test_create_monster_with_structured_actions_and_traits(self, client: TestClient):
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Stalker Beast",
                "edition": "2024",
                "cr": "3",
                "ac": 14,
                "hp": 50,
                "traits": [{"name": "Stench", "description": "Con save or poisoned."}],
                "actions": [
                    {
                        "name": "Claw",
                        "attack_bonus": 5,
                        "damage_dice": "2d6+3",
                        "damage_type": "slashing",
                        "description": "+5 to hit, 2d6+3 slashing.",
                    }
                ],
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert len(data["traits"]) == 1
        assert data["traits"][0]["name"] == "Stench"
        assert len(data["actions"]) == 1
        assert data["actions"][0]["name"] == "Claw"
        assert data["actions"][0]["attack_bonus"] == 5
        assert data["actions"][0]["damage_dice"] == "2d6+3"

    def test_create_monster_with_flat_damage_action(self, client: TestClient):
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Tiny Familiar",
                "edition": "2024",
                "cr": "0",
                "ac": 12,
                "hp": 2,
                "actions": [
                    {
                        "name": "Talons",
                        "attack_bonus": 3,
                        "damage_dice": "1",
                        "damage_type": "slashing",
                    }
                ],
            },
        )
        assert res.status_code == 201
        assert res.json()["actions"][0]["damage_dice"] == "1"

    def test_create_monster_action_without_attack_roll(self, client: TestClient):
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Blink Beast",
                "edition": "2024",
                "cr": "1",
                "ac": 12,
                "hp": 20,
                "actions": [
                    {
                        "name": "Teleport",
                        "attack_bonus": None,
                        "damage_dice": None,
                        "damage_type": None,
                        "description": "Teleports 30 ft.",
                    }
                ],
            },
        )
        assert res.status_code == 201
        assert res.json()["actions"][0]["name"] == "Teleport"

    def test_create_monster_validation_failure_missing_name(self, client: TestClient):
        res = client.post(
            "/api/v1/bestiary",
            json={
                "edition": "2024",
                "cr": "1",
                "ac": 10,
                "hp": 10,
            },
        )
        assert res.status_code == 422

    def test_create_monster_validation_failure_out_of_bounds_stats(self, client: TestClient):
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Overpowered",
                "edition": "2024",
                "cr": "1",
                "ac": 10,
                "hp": 10,
                "stats": {"str": 35},
            },
        )
        assert res.status_code == 422

    def test_create_monster_validation_failure_negative_hp(self, client: TestClient):
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Invalid HP",
                "edition": "2024",
                "cr": "1",
                "ac": 10,
                "hp": -5,
            },
        )
        assert res.status_code == 422

    def test_create_monster_overwrites_client_spoofed_origin(self, client: TestClient):
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Spoofed Origin",
                "origin": "official",
                "edition": "2024",
                "cr": "1",
                "ac": 10,
                "hp": 10,
            },
        )
        assert res.status_code == 201
        assert res.json()["origin"] == "custom"

    def test_create_monster_overwrites_client_spoofed_creator(
        self, client: TestClient, auth_context: dict
    ):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Spoofed Creator",
                "creator_dm_id": "root_admin",
                "edition": "2024",
                "cr": "1",
                "ac": 10,
                "hp": 10,
            },
        )
        assert res.status_code == 201
        assert res.json()["creator_dm_id"] == "user_dm_alice"


# ============================================================================
# Class 4: TestUpdateBestiaryMonster (PUT /api/v1/bestiary/{id})
# ============================================================================


class TestUpdateBestiaryMonster:
    def test_owner_update_custom_monster_success(self, client: TestClient, auth_context: dict):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        monster = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Old Golem",
                "edition": "2024",
                "cr": "2",
                "ac": 12,
                "hp": 40,
            },
        ).json()

        res = client.put(
            f"/api/v1/bestiary/{monster['id']}",
            json={"name": "Armored Golem", "ac": 15},
        )
        assert res.status_code == 200
        updated = res.json()
        assert updated["name"] == "Armored Golem"
        assert updated["ac"] == 15

        # Verify through subsequent GET
        get_res = client.get(f"/api/v1/bestiary/{monster['id']}")
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Armored Golem"

    def test_update_official_srd_2014_rejected_with_403(self, client: TestClient):
        res = client.put(
            "/api/v1/bestiary/srd_goblin_2014",
            json={"name": "Hacked Goblin"},
        )
        assert res.status_code == 403

    def test_update_official_srd_2024_rejected_with_403(self, client: TestClient):
        res = client.put(
            "/api/v1/bestiary/srd_goblin_2024",
            json={"ac": 25},
        )
        assert res.status_code == 403

    def test_non_owner_update_rejected_with_403(self, client: TestClient, auth_context: dict):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        monster = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Alice Wyrm",
                "edition": "2024",
                "cr": "5",
                "ac": 15,
                "hp": 80,
            },
        ).json()

        # Bob attempts update
        auth_context["user"] = {"id": "user_dm_bob", "username": "dm_bob"}
        attack_res = client.put(
            f"/api/v1/bestiary/{monster['id']}",
            json={"name": "Defaced Wyrm"},
        )
        assert attack_res.status_code == 403

        # Switch back to Alice and verify monster was untouched
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        get_res = client.get(f"/api/v1/bestiary/{monster['id']}")
        assert get_res.json()["name"] == "Alice Wyrm"

    def test_update_nonexistent_monster_returns_404(self, client: TestClient):
        res = client.put(
            "/api/v1/bestiary/nonexistent_id_123",
            json={"name": "Ghost"},
        )
        assert res.status_code == 404

    def test_update_recalculates_cr_numeric_on_cr_change(self, client: TestClient):
        monster = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Evolving Beast",
                "edition": "2024",
                "cr": "1",
                "ac": 12,
                "hp": 30,
            },
        ).json()
        assert monster["cr_numeric"] == 1.0

        update_res = client.put(
            f"/api/v1/bestiary/{monster['id']}",
            json={"cr": "1/2"},
        )
        assert update_res.status_code == 200
        assert update_res.json()["cr_numeric"] == 0.5


# ============================================================================
# Class 5: TestToggleBestiaryVisibility (PATCH /api/v1/bestiary/{id}/visibility)
# ============================================================================


class TestToggleBestiaryVisibility:
    def test_owner_toggles_visibility_to_public(self, client: TestClient, auth_context: dict):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        monster = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Secret Shadow",
                "is_public": False,
                "edition": "2024",
                "cr": "2",
                "ac": 12,
                "hp": 25,
            },
        ).json()
        assert monster["is_public"] is False

        res = client.patch(
            f"/api/v1/bestiary/{monster['id']}/visibility",
            json={"is_public": True},
        )
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["is_public"] is True

        get_res = client.get(f"/api/v1/bestiary/{monster['id']}")
        assert get_res.json()["is_public"] is True

    def test_owner_toggles_visibility_to_private(self, client: TestClient, auth_context: dict):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        monster = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Public Drake",
                "is_public": True,
                "edition": "2024",
                "cr": "2",
                "ac": 12,
                "hp": 25,
            },
        ).json()
        assert monster["is_public"] is True

        res = client.patch(
            f"/api/v1/bestiary/{monster['id']}/visibility",
            json={"is_public": False},
        )
        assert res.status_code == 200
        assert res.json()["is_public"] is False

    def test_toggle_official_srd_visibility_rejected_with_403(self, client: TestClient):
        res = client.patch(
            "/api/v1/bestiary/srd_goblin_2014/visibility",
            json={"is_public": False},
        )
        assert res.status_code == 403

    def test_non_owner_toggle_visibility_rejected_with_403(
        self, client: TestClient, auth_context: dict
    ):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        monster = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Alice Drake",
                "is_public": False,
                "edition": "2024",
                "cr": "2",
                "ac": 12,
                "hp": 25,
            },
        ).json()

        # Bob attempts toggle
        auth_context["user"] = {"id": "user_dm_bob", "username": "dm_bob"}
        attack_res = client.patch(
            f"/api/v1/bestiary/{monster['id']}/visibility",
            json={"is_public": True},
        )
        assert attack_res.status_code == 403

    def test_toggle_visibility_nonexistent_returns_404(self, client: TestClient):
        res = client.patch(
            "/api/v1/bestiary/nonexistent_id/visibility",
            json={"is_public": True},
        )
        assert res.status_code == 404

    def test_toggle_visibility_invalid_payload_returns_422(self, client: TestClient):
        res = client.patch(
            "/api/v1/bestiary/some_id/visibility",
            json={"is_public": "not_a_bool"},
        )
        assert res.status_code == 422


# ============================================================================
# Class 6: TestDeleteBestiaryMonster (DELETE /api/v1/bestiary/{id})
# ============================================================================


class TestDeleteBestiaryMonster:
    def test_owner_delete_custom_monster_success(self, client: TestClient, auth_context: dict):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        monster = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Condemned Beast",
                "edition": "2024",
                "cr": "1",
                "ac": 10,
                "hp": 15,
            },
        ).json()

        res = client.delete(f"/api/v1/bestiary/{monster['id']}")
        assert res.status_code == 200
        assert res.json()["success"] is True

        # Subsequent GET returns 404
        get_res = client.get(f"/api/v1/bestiary/{monster['id']}")
        assert get_res.status_code == 404

    def test_delete_official_srd_2014_rejected_with_403(self, client: TestClient):
        res = client.delete("/api/v1/bestiary/srd_goblin_2014")
        assert res.status_code == 403

        # Confirm monster is still available
        get_res = client.get("/api/v1/bestiary/srd_goblin_2014")
        assert get_res.status_code == 200

    def test_delete_official_srd_2024_rejected_with_403(self, client: TestClient):
        res = client.delete("/api/v1/bestiary/srd_ancient_red_dragon_2024")
        assert res.status_code == 403

    def test_non_owner_delete_rejected_with_403(self, client: TestClient, auth_context: dict):
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        monster = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Indestructible Beast",
                "edition": "2024",
                "cr": "5",
                "ac": 15,
                "hp": 80,
            },
        ).json()

        # Bob attempts delete
        auth_context["user"] = {"id": "user_dm_bob", "username": "dm_bob"}
        attack_res = client.delete(f"/api/v1/bestiary/{monster['id']}")
        assert attack_res.status_code == 403

        # Verify monster still exists
        auth_context["user"] = {
            "id": "user_dm_alice",
            "username": "dm_alice",
        }
        get_res = client.get(f"/api/v1/bestiary/{monster['id']}")
        assert get_res.status_code == 200

    def test_delete_nonexistent_monster_returns_404(self, client: TestClient):
        res = client.delete("/api/v1/bestiary/nonexistent_monster_444")
        assert res.status_code == 404


# ============================================================================
# Class 7: TestBestiaryAuthEnforcement (Unauthenticated 401s)
# ============================================================================


class TestBestiaryAuthEnforcement:
    def test_get_bestiary_unauthenticated_returns_401(self, client: TestClient):
        app.dependency_overrides.pop(get_current_user, None)
        res = client.get("/api/v1/bestiary")
        assert res.status_code == 401

    def test_get_bestiary_by_id_unauthenticated_returns_401(self, client: TestClient):
        app.dependency_overrides.pop(get_current_user, None)
        res = client.get("/api/v1/bestiary/srd_goblin_2014")
        assert res.status_code == 401

    def test_post_bestiary_unauthenticated_returns_401(self, client: TestClient):
        app.dependency_overrides.pop(get_current_user, None)
        res = client.post(
            "/api/v1/bestiary",
            json={"name": "Ghost", "edition": "2024", "cr": "1"},
        )
        assert res.status_code == 401

    def test_put_bestiary_unauthenticated_returns_401(self, client: TestClient):
        app.dependency_overrides.pop(get_current_user, None)
        res = client.put(
            "/api/v1/bestiary/some_id",
            json={"name": "Ghost"},
        )
        assert res.status_code == 401

    def test_patch_visibility_unauthenticated_returns_401(self, client: TestClient):
        app.dependency_overrides.pop(get_current_user, None)
        res = client.patch(
            "/api/v1/bestiary/some_id/visibility",
            json={"is_public": True},
        )
        assert res.status_code == 401

    def test_delete_bestiary_unauthenticated_returns_401(self, client: TestClient):
        app.dependency_overrides.pop(get_current_user, None)
        res = client.delete("/api/v1/bestiary/some_id")
        assert res.status_code == 401


# ============================================================================
# Class 8: TestBestiaryEdgeCases
# ============================================================================


class TestBestiaryEdgeCases:
    def test_edge_case_fractional_cr_query_equivalence(self, client: TestClient):
        res1 = client.get("/api/v1/bestiary?cr=0.25")
        res2 = client.get("/api/v1/bestiary?cr=1/4")
        assert res1.status_code == 200
        assert res2.status_code == 200
        names1 = [m["name"] for m in res1.json()]
        names2 = [m["name"] for m in res2.json()]
        assert names1 == names2

    def test_edge_case_cr_sorting_numeric(self, client: TestClient):
        # Create monsters across varying CRs
        test_crs = [
            ("1/8", 0.125),
            ("1/4", 0.25),
            ("1/2", 0.5),
            ("1", 1.0),
            ("2", 2.0),
            ("10", 10.0),
        ]
        for cr_str, _ in test_crs:
            client.post(
                "/api/v1/bestiary",
                json={
                    "name": f"Ordered {cr_str}",
                    "edition": "2024",
                    "cr": cr_str,
                    "ac": 12,
                    "hp": 20,
                },
            )

        res = client.get("/api/v1/bestiary?include_official=false&include_mine=true")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 6
        cr_nums = [float(m["cr_numeric"]) for m in data]
        assert cr_nums == sorted(cr_nums)
        # Verify 10.0 comes AFTER 2.0 (numeric sorting, not lexicographic "10" < "2")
        assert cr_nums[-1] == 10.0

    def test_edge_case_empty_source_combination_returns_empty_list(self, client: TestClient):
        res = client.get(
            "/api/v1/bestiary?include_official=false&include_mine=false&include_community=false"
        )
        assert res.status_code == 200
        assert res.json() == []

    def test_edge_case_whitespace_and_special_characters_in_search(self, client: TestClient):
        res1 = client.get("/api/v1/bestiary?search=  goblin   ")
        assert res1.status_code == 200
        assert len(res1.json()) > 0
        assert all("goblin" in m["name"].lower() for m in res1.json())

        # Special regex characters like & or () should not cause a 500 error
        res2 = client.get("/api/v1/bestiary?search=Ancient%20(Red)")
        assert res2.status_code == 200

    def test_edge_case_large_statblock_actions_payload(self, client: TestClient):
        many_actions = [
            {
                "name": f"Attack {i}",
                "attack_bonus": 5 + i,
                "damage_dice": "1d8+3",
                "damage_type": "slashing",
                "description": f"Attack variation number {i}.",
            }
            for i in range(15)
        ]
        res = client.post(
            "/api/v1/bestiary",
            json={
                "name": "Multi-Armed Titan",
                "edition": "2024",
                "cr": "15",
                "ac": 19,
                "hp": 250,
                "actions": many_actions,
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert len(data["actions"]) == 15
        assert data["actions"][14]["name"] == "Attack 14"
