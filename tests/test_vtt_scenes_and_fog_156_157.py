from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from backend.core.schemas import (
    VTTFogSchema,
    VTTGridSchema,
    VTTStateSchema,
    VTTTokenSchema,
)
from backend.services.vtt_service import VTTService
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.rate_limiter import limiter
from server.routers.assets_router import router as assets_router
from server.routers.campaign_router import router as campaign_router

# ============================================================================
# Unit Tests for VTTService Fog & Redaction Math
# ============================================================================


def test_remap_fog_indices_growth():
    # 10x10 grid -> cell at x=2, y=3 is idx 32
    revealed = [32]
    remapped = VTTService.remap_fog_indices(revealed, 10, 10, 20, 20)
    # in 20x20: y=3, x=2 -> 3 * 20 + 2 = 62
    assert remapped == [62]


def test_remap_fog_indices_shrink_prunes_oob():
    # 20x20 grid -> cell at x=15, y=15 (index 315)
    # shrinking to 10x10 drops (15, 15)
    revealed = [0, 315]  # 0 is (0,0), kept
    remapped = VTTService.remap_fog_indices(revealed, 20, 20, 10, 10)
    assert remapped == [0]


def test_remap_fog_indices_same_size():
    revealed = [1, 5, 20]
    remapped = VTTService.remap_fog_indices(revealed, 10, 10, 10, 10)
    assert remapped == [1, 5, 20]


def test_extract_valid_cell_indices_bounds_check():
    svc = VTTService()
    # Within bounds (10x10)
    indices = svc._extract_valid_cell_indices(
        {"cells": [[0, 0], [9, 9]], "rect": {"x": 1, "y": 1, "w": 2, "h": 2}}, 10, 10
    )
    assert 0 in indices
    assert 99 in indices
    assert (1 * 10 + 1) in indices  # 11

    # Out of bounds raises ValueError
    with pytest.raises(ValueError, match="out of grid bounds"):
        svc._extract_valid_cell_indices({"cells": [[10, 5]]}, 10, 10)

    with pytest.raises(ValueError, match="out of grid bounds"):
        svc._extract_valid_cell_indices({"cells": [[-1, 0]]}, 10, 10)


def test_extract_valid_cell_indices_limit_exceeded():
    svc = VTTService()
    # 60x60 = 3600 cells > 2500
    with pytest.raises(ValueError, match="exceeds maximum limit"):
        svc._extract_valid_cell_indices({"rect": {"x": 0, "y": 0, "w": 60, "h": 60}}, 100, 100)


def test_fog_redaction_for_player_and_dm():
    # Grid: 10x10, cell_size: 50
    # Cell (0, 0) is px (0..50, 0..50) -> index 0
    # Cell (1, 0) is px (50..100, 0..50) -> index 1
    # Cell (2, 2) is px (100..150, 100..150) -> index 22
    token_hero = VTTTokenSchema(id="t1", name="Aragorn", x=10, y=10, size=1)  # cell 0
    token_enemy_unrevealed = VTTTokenSchema(id="t2", name="Orc 1", x=120, y=120, size=1)  # cell 22
    token_enemy_revealed = VTTTokenSchema(id="t3", name="Orc 2", x=60, y=10, size=1)  # cell 1
    token_hidden = VTTTokenSchema(
        id="t4", name="Invisible Stalker", x=10, y=10, size=1, is_hidden=True
    )
    # Large 2x2 creature (size=2) at x=50, y=50 -> spans cells (1,1), (2,1), (1,2), (2,2)
    # Indices in 10x10: 11, 12, 21, 22. If cell 11 is revealed, creature is visible!
    token_large = VTTTokenSchema(id="t5", name="Troll", x=50, y=50, size=2)

    # Fog enabled, revealed = [1, 11] (cell 1 and cell 11)
    state = VTTStateSchema(
        is_active=True,
        grid=VTTGridSchema(width=10, height=10, cell_size=50),
        tokens=[
            token_hero,
            token_enemy_unrevealed,
            token_enemy_revealed,
            token_hidden,
            token_large,
        ],
        fog=VTTFogSchema(enabled=True, revealed=[1, 11]),
    )

    # Redact for player "Aragorn":
    # 1. token_hidden is hidden -> excluded
    # 2. token_hero is Aragorn's own token -> ALWAYS visible even though cell 0 is not revealed!
    # 3. token_enemy_unrevealed in cell 22 -> cell 22 not revealed -> excluded
    # 4. token_enemy_revealed in cell 1 -> revealed -> visible
    # 5. token_large spans cell 11 which is revealed -> visible
    redacted = VTTService.redact_for_player(state, player_character_name="Aragorn")
    redacted_names = [t.name for t in redacted.tokens]

    assert "Aragorn" in redacted_names
    assert "Orc 2" in redacted_names
    assert "Troll" in redacted_names
    assert "Orc 1" not in redacted_names
    assert "Invisible Stalker" not in redacted_names


# ============================================================================
# API Integration Tests for Scenes, History & Asset Isolation (#156, #157)
# ============================================================================


@pytest.fixture
def vtt_test_app():
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(campaign_router, prefix="/api/v1")
    app.include_router(assets_router, prefix="/api/v1")
    return app


@pytest.fixture
def mock_db():
    db = MagicMock()
    collections = {}

    def get_col(name):
        if name not in collections:
            col = MagicMock()
            col.insert_one = AsyncMock(return_value=MagicMock(acknowledged=True))
            col.update_one = AsyncMock(
                return_value=MagicMock(acknowledged=True, matched_count=1, modified_count=1)
            )
            col.update_many = AsyncMock(
                return_value=MagicMock(acknowledged=True, matched_count=1, modified_count=1)
            )
            col.delete_one = AsyncMock(return_value=MagicMock(acknowledged=True))
            col.delete_many = AsyncMock(return_value=MagicMock(acknowledged=True))
            col.find_one = AsyncMock(return_value=None)
            col.count_documents = AsyncMock(return_value=0)
            collections[name] = col
        return collections[name]

    db.__getitem__.side_effect = get_col
    return db


def test_scene_crud_dm_and_player_permissions(vtt_test_app, mock_db):
    dm_user = {"id": "dm_user_id", "username": "dm_bob"}
    vtt_test_app.dependency_overrides[get_database] = lambda: mock_db
    vtt_test_app.dependency_overrides[get_current_user] = lambda: dm_user

    dm_member = {
        "campaign_id": "TestCampaign",
        "user_id": "dm_user_id",
        "username": "dm_bob",
        "role": "dm",
    }
    camp_doc = {
        "campaign_name": "TestCampaign",
        "owner_id": "dm_user_id",
        "vtt_state": {"is_active": True},
    }
    mock_db["campaign_members"].find_one = AsyncMock(return_value=dm_member)
    mock_db["campaigns"].find_one = AsyncMock(return_value=camp_doc)

    client = TestClient(vtt_test_app)

    # 1. Create a scene as DM
    scene_data = {
        "name": "Goblin Ambush",
        "dm_notes": "Secret trap on square (4,5)",
        "grid": {"width": 25, "height": 25, "cell_size": 50},
        "tokens": [],
    }
    res = client.post("/api/v1/campaigns/TestCampaign/scenes", json=scene_data)
    assert res.status_code == status.HTTP_201_CREATED
    created_scene = res.json()
    assert created_scene["name"] == "Goblin Ambush"
    assert created_scene["dm_notes"] == "Secret trap on square (4,5)"
    mock_db["campaign_scenes"].insert_one.assert_called_once()

    # 2. Player access denied (403)
    player_user = {"id": "player_id", "username": "player_alice"}
    vtt_test_app.dependency_overrides[get_current_user] = lambda: player_user
    player_member = {
        "campaign_id": "TestCampaign",
        "user_id": "player_id",
        "username": "player_alice",
        "role": "player",
    }
    mock_db["campaign_members"].find_one = AsyncMock(return_value=player_member)

    res_player = client.get("/api/v1/campaigns/TestCampaign/scenes")
    assert res_player.status_code == status.HTTP_403_FORBIDDEN


def test_delete_active_scene_returns_409(vtt_test_app, mock_db):
    dm_user = {"id": "dm_user_id", "username": "dm_bob"}
    vtt_test_app.dependency_overrides[get_database] = lambda: mock_db
    vtt_test_app.dependency_overrides[get_current_user] = lambda: dm_user

    dm_member = {
        "campaign_id": "TestCampaign",
        "user_id": "dm_user_id",
        "username": "dm_bob",
        "role": "dm",
    }
    camp_doc = {
        "campaign_name": "TestCampaign",
        "vtt_state": {"is_active": True, "active_scene_id": "scene_active_123"},
    }
    mock_db["campaign_members"].find_one = AsyncMock(return_value=dm_member)
    mock_db["campaigns"].find_one = AsyncMock(return_value=camp_doc)

    client = TestClient(vtt_test_app)
    res = client.delete("/api/v1/campaigns/TestCampaign/scenes/scene_active_123")
    assert res.status_code == status.HTTP_409_CONFLICT
    assert "cannot delete the currently active scene" in res.json()["detail"].lower()


def test_asset_campaign_isolation(vtt_test_app, mock_db):
    user = {"id": "user_1", "username": "player1"}
    vtt_test_app.dependency_overrides[get_database] = lambda: mock_db
    vtt_test_app.dependency_overrides[get_current_user] = lambda: user

    member_doc = {
        "campaign_id": "Campaign_B",
        "user_id": "user_1",
        "username": "player1",
        "role": "player",
    }
    mock_db["campaign_members"].find_one = AsyncMock(return_value=member_doc)

    client = TestClient(vtt_test_app)

    # Asset belongs to "Campaign_A"
    asset_doc = {
        "filename": "dungeon_map.png",
        "campaign_name": "Campaign_A",
        "uploaded_by_user_id": "dm_user",
    }
    mock_db["campaign_assets"].find_one = AsyncMock(return_value=asset_doc)

    # Requesting asset from Campaign_B must return 404
    res = client.get("/api/v1/campaigns/Campaign_B/assets/dungeon_map.png")
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.anyio
async def test_lazy_migration_and_script_migration(mock_db):
    # Campaign with legacy vtt_state and no scene
    legacy_camp = {
        "_id": ObjectId(),
        "campaign_name": "LegacyCamp",
        "vtt_state": {
            "is_active": True,
            "grid": {"width": 30, "height": 30, "cell_size": 50},
            "tokens": [{"id": "t1", "name": "Fighter", "x": 100, "y": 100, "size": 1}],
        },
    }

    # Setup find_one for mock_db
    def find_one_side_effect(query, *args, **kwargs):
        if "campaign_name" in query and query["campaign_name"] == "LegacyCamp":
            return legacy_camp
        return None

    inserted_scenes = {}

    async def insert_scene(doc):
        inserted_scenes[doc["scene_id"]] = doc
        return MagicMock(acknowledged=True)

    async def find_scene(query, *args, **kwargs):
        if "scene_id" in query:
            return inserted_scenes.get(query["scene_id"])
        return None

    mock_db["campaigns"].find_one = AsyncMock(side_effect=find_one_side_effect)
    mock_db["campaign_scenes"].insert_one = AsyncMock(side_effect=insert_scene)
    mock_db["campaign_scenes"].find_one = AsyncMock(side_effect=find_scene)

    svc = VTTService()
    state = await svc.get_vtt_state(mock_db, "LegacyCamp")
    assert state.is_active is True
    assert state.scene_name == "Default"
    assert len(state.tokens) == 1
    assert state.tokens[0].name == "Fighter"
    mock_db["campaign_scenes"].insert_one.assert_called_once()
