import mongomock
import pytest
from fastapi.testclient import TestClient

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.core.schemas import CharacterSchema, EquipmentItem, Weapon
from backend.services.inventory_service import (
    compute_coin_weight_lb,
    parse_weight_lb,
    sync_character_inventory,
)
from backend.services.stats_service import sync_character_stats
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app


class _LocalAsyncCollection:
    def __init__(self, coll):
        self._coll = coll

    async def find_one(self, query=None, *args, **kwargs):
        return self._coll.find_one(query or {}, *args, **kwargs)

    async def insert_one(self, doc):
        return self._coll.insert_one(doc)

    async def update_one(self, query, update, upsert=False):
        class _Res:
            def __init__(self, r):
                self.matched_count = r.matched_count
                self.modified_count = r.modified_count

        return _Res(self._coll.update_one(query, update, upsert=upsert))

    async def find_one_and_update(self, *args, **kwargs):
        return self._coll.find_one_and_update(*args, **kwargs)


class _LocalAsyncDatabase:
    def __init__(self, mongo_db):
        self._db = mongo_db
        self._colls = {}

    def __getitem__(self, name: str):
        if name not in self._colls:
            self._colls[name] = _LocalAsyncCollection(self._db[name])
        return self._colls[name]


def _base_char(edition: str = EDITION_2014, **overrides):
    data = {
        "char_id": "inv-test-262",
        "char_name": "Kael",
        "char_class": "Fighter",
        "char_level": 5,
        "classes": [{"class_name": "Fighter", "level": 5}],
        "dnd_edition": edition,
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 16, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
        "saving_throws": ["STR", "CON"],
        "currency": {"cp": 0, "sp": 0, "ep": 0, "gp": 0, "pp": 0},
        "weapons": [],
        "equipment": [],
        "features_traits": [],
    }
    data.update(overrides)
    return data


def test_parse_weight_lb_and_schema_coercion():
    assert parse_weight_lb(None) is None
    assert parse_weight_lb(True) is None
    assert parse_weight_lb("2 lb.") == 2.0
    assert parse_weight_lb("1.5 lbs") == 1.5
    assert parse_weight_lb("1/2 lb.") == 0.5
    assert parse_weight_lb("1 1/2 lb.") == 1.5
    assert parse_weight_lb("-5 lb.") == 0.0
    assert parse_weight_lb(0) == 0.0

    w = Weapon(name="Longbow", ammo_count=0, ammo_max=20, weight="1 1/2 lb.")
    assert w.ammo_count == 0
    assert w.ammo_max == 20
    assert w.weight == 1.5

    w_neg = Weapon(name="Rock", weight="-3 lb.")
    assert w_neg.weight == 0.0

    item = EquipmentItem(name="Feather Token", weight="1/2 lb.", uses_current=3, uses_max=3)
    assert item.weight == 0.5
    assert item.uses_current == 3
    assert item.uses_max == 3


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_catalog_weights_coin_weight_and_bag_of_holding_stash(edition: str):
    char = _base_char(
        edition,
        currency={"cp": 25, "sp": 25, "ep": 0, "gp": 100, "pp": 0},  # 150 coins = 3.0 lb
        weapons=[
            {"name": "Longbow", "ammo_count": 18, "ammo_max": 20},  # 2.0 lb
            {"name": "Dagger", "weight_ignored": True},  # 1.0 lb resolved, excluded from carried
        ],
        equipment=[
            {"name": "Plate Armor", "equipped": True, "quantity": 1},  # 65.0 lb
            {"name": "Potion of Healing", "quantity": 4},  # 4 * 0.5 = 2.0 lb
            {"name": "Bag of Holding", "quantity": 1},  # 15.0 lb container
            {
                "name": "Gold Bars",
                "weight": 50.0,
                "quantity": 2,
                "weight_ignored": True,
            },  # inside bag
            {"name": "Weightless Charm", "weight": 0.0, "quantity": 1},  # explicit 0 stays 0
        ],
    )
    synced = sync_character_stats(char)

    assert synced["carrying_capacity_lb"] == 240.0  # 15 * 16
    assert compute_coin_weight_lb(synced["currency"]) == 3.0
    assert synced["weight_breakdown"]["weapons_lb"] == 2.0
    assert synced["weight_breakdown"]["equipment_lb"] == 82.0  # 65 + 2 + 15
    assert synced["weight_breakdown"]["coins_lb"] == 3.0
    assert synced["total_weight_lb"] == 87.0  # 82 + 2 + 3
    assert synced["encumbrance_status"] == "encumbered"  # > 5*16 (80), <= 10*16 (160)

    longbow = next(w for w in synced["weapons"] if w["name"] == "Longbow")
    assert longbow["ammo_count"] == 18
    assert longbow["ammo_max"] == 20
    assert longbow["resolved_weight_lb"] == 2.0

    dagger = next(w for w in synced["weapons"] if w["name"] == "Dagger")
    assert dagger["resolved_weight_lb"] == 1.0

    charm = next(eq for eq in synced["equipment"] if eq["name"] == "Weightless Charm")
    assert charm["weight"] == 0.0
    assert charm["resolved_weight_lb"] == 0.0


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_carrying_capacity_size_powerful_build_brawny_and_bear_aspect(edition: str):
    # Goliath has Powerful Build -> x2 (non-stacking with Brawny)
    goliath = _base_char(
        edition,
        race="Goliath",
        features_traits=[
            {
                "name": "Brawny",
                "description": "You count as if you were one size larger for the purpose of determining your carrying capacity.",
            }
        ],
    )
    sync_character_inventory(goliath)
    assert goliath["carrying_capacity_lb"] == 480.0  # 15 * 16 * 2 (not x4)

    # Halfling (Small) still has 15 * STR per 5e/2024 PHB
    halfling = _base_char(
        edition,
        race="Halfling",
        stats={"STR": 10, "DEX": 16, "CON": 14, "INT": 10, "WIS": 12, "CHA": 10},
    )
    sync_character_inventory(halfling)
    assert halfling["carrying_capacity_lb"] == 150.0

    # Goliath Barbarian with Bear Aspect stacks (Powerful Build x2 * Bear x2 = x4)
    bear_goliath = _base_char(
        edition,
        race="Goliath",
        char_class="Barbarian",
        subclass="Path of the Totem Warrior",
        char_level=6,
        classes=[{"class_name": "Barbarian", "subclass": "Path of the Totem Warrior", "level": 6}],
        features_traits=[
            {
                "name": "Aspect of the Beast (Bear)",
                "description": "Your carrying capacity is doubled.",
            }
        ],
    )
    sync_character_inventory(bear_goliath)
    assert bear_goliath["carrying_capacity_lb"] == 960.0  # 15 * 16 * 4

    # Generic 3-way prompt or Eagle choice must NOT double carrying capacity
    eagle_human = _base_char(
        edition,
        features_traits=[
            {
                "name": "Aspect of the Beast",
                "description": "Gain passive supernatural might from Bear (double carrying capacity, Adv vs push/break), Eagle (1-mile sight), or Wolf (track at fast pace).",
            }
        ],
    )
    sync_character_inventory(eagle_human)
    assert eagle_human["carrying_capacity_lb"] == 240.0

    # Firbolg & Bugbear fallback species + Dart weight parity across Python & TS
    firbolg = _base_char(
        edition,
        race="Firbolg",
        stats={"STR": 14, "DEX": 12, "CON": 14, "INT": 10, "WIS": 14, "CHA": 10},
        weapons=[{"name": "Dart"}],
    )
    sync_character_inventory(firbolg)
    assert firbolg["carrying_capacity_lb"] == 420.0  # 15 * 14 * 2
    assert firbolg["weapons"][0]["resolved_weight_lb"] == 0.25


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_http_crud_ammo_encumbrance_and_dm_suppression(edition: str):
    mock_db = _LocalAsyncDatabase(mongomock.MongoClient()["test_db_262"])
    user_doc = {"id": "u-262", "username": "archer", "is_admin": False}
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: user_doc

    try:
        client = TestClient(app)
        create_res = client.post(
            "/api/v1/characters",
            json={
                "char_name": "Sylva",
                "char_class": "Ranger",
                "char_level": 5,
                "dnd_edition": edition,
                "race": "Human",
                "background": "Outlander",
                "stats": {"STR": 10, "DEX": 18, "CON": 14, "INT": 12, "WIS": 14, "CHA": 10},
                "currency": {"gp": 100},  # 2 lb
                "weapons": [{"name": "Longbow", "ammo_count": 20, "ammo_max": 20}],  # 2 lb
                "equipment": [
                    {
                        "name": "Gauntlets of Ogre Power",
                        "equipped": True,
                        "attuned": True,
                    },  # 2 lb, STR -> 19
                    {"name": "Chain Mail", "equipped": True, "quantity": 1},  # 55 lb
                    {"name": "Explorer's Pack", "quantity": 2},  # 118 lb
                ],
            },
        )
        assert create_res.status_code == 201, create_res.text
        created = create_res.json()
        cid = created["char_id"]
        assert created["stats"]["STR"] == 19
        assert created["carrying_capacity_lb"] == 285.0  # 15 * 19
        assert (
            created["total_weight_lb"] == 179.0
        )  # 2 coins + 2 bow + 2 gauntlets + 55 chain + 118 packs
        assert created["encumbrance_status"] == "encumbered"  # > 95 (5*19), <= 190 (10*19)
        assert created["weapons"][0]["ammo_count"] == 20

        # Shot fired -> PUT updates ammo to 0 & GET hydrates cleanly
        updated_weapons = [{**created["weapons"][0], "ammo_count": 0}]
        put_res = client.put(
            f"/api/v1/characters/{cid}", json={**created, "weapons": updated_weapons}
        )
        assert put_res.status_code == 200, put_res.text
        saved = put_res.json()
        assert saved["weapons"][0]["ammo_count"] == 0
        assert saved["weapons"][0]["ammo_max"] == 20

        get_res = client.get(f"/api/v1/characters/{cid}")
        assert get_res.status_code == 200
        assert get_res.json()["weapons"][0]["ammo_count"] == 0
        assert get_res.json()["total_weight_lb"] == 179.0

        # Suppression drops Gauntlets STR 19 -> 10 => capacity drops from 285 to 150 => over_capacity
        suppressed = sync_character_stats({**saved, "magic_items_suppressed": True})
        assert suppressed["stats"]["STR"] == 10
        assert suppressed["carrying_capacity_lb"] == 150.0
        assert suppressed["encumbrance_status"] == "over_capacity"

        validated = CharacterSchema.model_validate(suppressed)
        assert validated.total_weight_lb == 179.0
    finally:
        app.dependency_overrides = orig


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_campaign_party_loot_distribute_and_state_suppression_sync(edition: str):
    class _CampAsyncColl:
        def __init__(self, coll):
            self._coll = coll

        async def find_one(self, query=None, *args, **kwargs):
            return self._coll.find_one(query or {}, *args, **kwargs)

        def find(self, query=None, *args, **kwargs):
            docs = list(self._coll.find(query or {}, *args, **kwargs))

            class _Cur:
                def __init__(self, d):
                    self._d = d

                def sort(self, *a, **k):
                    return self

                async def to_list(self, length=None):
                    return list(self._d)

                def __aiter__(self):
                    self._it = iter(self._d)
                    return self

                async def __anext__(self):
                    try:
                        return next(self._it)
                    except StopIteration:
                        raise StopAsyncIteration

            return _Cur(docs)

        async def insert_one(self, doc):
            return self._coll.insert_one(doc)

        async def update_one(self, query, update, upsert=False):
            r = self._coll.update_one(query, update, upsert=upsert)

            class _Res:
                matched_count = r.matched_count
                modified_count = r.modified_count

            return _Res()

        async def find_one_and_update(self, *args, **kwargs):
            return self._coll.find_one_and_update(*args, **kwargs)

    class _CampAsyncDB:
        def __init__(self, mongo_db):
            self._db = mongo_db
            self._colls = {}

        def __getitem__(self, name: str):
            if name not in self._colls:
                self._colls[name] = _CampAsyncColl(self._db[name])
            return self._colls[name]

    mock_db = _CampAsyncDB(mongomock.MongoClient()[f"camp_262_{edition[:4]}"])
    dm_user = {"id": "dm-262", "username": "dm", "is_admin": False}
    camp_name = f"Keep 262 {edition[:4]}"
    char_id = f"camp-hero-{edition[:4]}"
    mock_db["campaigns"]._coll.insert_one(
        {"campaign_name": camp_name, "dm_id": "dm-262", "dnd_edition": edition}
    )
    mock_db["campaign_members"]._coll.insert_one(
        {"campaign_id": camp_name, "user_id": "dm-262", "role": "dm"}
    )
    mock_db["homebrew_content"]._coll.insert_one(
        {"campaign_id": camp_name, "homebrew_type": "item", "name": "Runed Cask", "weight": 8.0}
    )
    mock_db["characters"]._coll.insert_one(
        {
            **_base_char(
                edition,
                char_id=char_id,
                owner_id="dm-262",
                active_campaign=camp_name,
                stats={"STR": 19, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
                base_stats={"STR": 10, "DEX": 14, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
                equip_stat_bonuses={"STR": 9, "DEX": 0, "CON": 0, "INT": 0, "WIS": 0, "CHA": 0},
                equipment=[
                    {
                        "name": "Gauntlets of Ogre Power",
                        "equipped": True,
                        "attuned": True,
                    },  # 2 lb, STR -> 19
                    {"name": "Runed Cask", "quantity": 1},  # homebrew 8.0 lb
                ],
                version=1,
            )
        }
    )

    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: dm_user
    try:
        client = TestClient(app)
        # 1. GET /party preserves campaign homebrew weight and computes capacity with STR 19
        party_res = client.get(f"/api/v1/campaigns/{camp_name}/party")
        assert party_res.status_code == 200, party_res.text
        hero = party_res.json()[0]
        assert hero["carrying_capacity_lb"] == 285.0
        assert hero["total_weight_lb"] == 10.0

        # 2. GET /characters/{cid} preserves positive resolved_weight_lb on homebrew items
        single_res = client.get(f"/api/v1/characters/{char_id}")
        assert single_res.status_code == 200
        assert single_res.json()["total_weight_lb"] == 10.0

        # 3. POST /loot/distribute adds Chain Mail (55 lb) + 100 gp (2 lb) and updates total_weight_lb atomically
        loot_res = client.post(
            f"/api/v1/campaigns/{camp_name}/loot/distribute",
            json={
                "character_ids": [char_id],
                "currency": {"gp": 100},
                "items": [{"type": "equipment", "name": "Chain Mail", "quantity": 1}],
                "reason": "Vault cache",
            },
        )
        assert loot_res.status_code == 200, loot_res.text
        updated_doc = mock_db["characters"]._coll.find_one({"char_id": char_id})
        assert updated_doc["total_weight_lb"] == 67.0  # 10 + 55 + 2
        assert updated_doc["equipment"][-1]["resolved_weight_lb"] == 55.0

        # 4. PATCH /party/{cid}/state toggling Athas suppression lowers STR 19 -> 10 => capacity 150 lb
        patch_res = client.patch(
            f"/api/v1/campaigns/{camp_name}/party/{char_id}/state",
            json={"magic_items_suppressed": True},
        )
        assert patch_res.status_code == 200, patch_res.text
        sup_doc = mock_db["characters"]._coll.find_one({"char_id": char_id})
        assert sup_doc["carrying_capacity_lb"] == 150.0
    finally:
        app.dependency_overrides = orig
