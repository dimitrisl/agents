from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services.user_admin_service import (
    build_deletion_preview,
    delete_user_cascade,
)
from scripts.promote_admin import promote_user
from server.db_async import get_database
from server.dependencies.auth import get_current_user, require_admin
from server.dependencies.campaign import require_campaign_member
from server.rate_limiter import limiter
from server.routers.admin_router import router as admin_router
from server.routers.campaign_router import router as campaign_router


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


@pytest.fixture
def admin_client(mock_db):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(campaign_router, prefix="/api/v1")

    admin_user = {
        "id": "admin_user_1",
        "username": "admin",
        "is_admin": True,
    }
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_admin] = lambda: admin_user
    app.dependency_overrides[require_campaign_member()] = lambda: {
        "user_id": "admin_user_1",
        "username": "admin",
        "role": "dm",
    }

    client = TestClient(app)
    return client


# ==============================================================
# Admin User Service & Deletion Preview Tests (#154)
# ==============================================================
@pytest.mark.anyio
async def test_build_deletion_preview_blocks_last_admin(mock_db):
    target_user = {
        "_id": ObjectId(),
        "id": "target_id",
        "username": "sole_admin",
        "is_admin": True,
        "created_at": datetime.now(timezone.utc),
    }
    mock_db["users"].find_one = AsyncMock(return_value=target_user)
    mock_db["users"].count_documents = AsyncMock(return_value=1)

    preview = await build_deletion_preview(mock_db, "target_id")
    assert preview.can_delete is False
    assert any("last remaining administrator" in r.lower() for r in preview.blocking_reasons)


def test_admin_deletion_preview_endpoint_blocks_self(admin_client, mock_db):
    # Admin preview route should block self-deletion
    res = admin_client.get("/api/v1/admin/users/admin_user_1/deletion-preview")
    assert res.status_code == 200
    preview = res.json()
    assert preview["can_delete"] is False
    assert any("cannot delete your own account" in r.lower() for r in preview["blocking_reasons"])


@pytest.mark.anyio
async def test_delete_user_cascade_success(mock_db):
    target_id = "target_user_id"
    target_user = {
        "_id": ObjectId(),
        "id": target_id,
        "username": "player1",
        "is_admin": False,
        "created_at": datetime.now(timezone.utc),
    }
    mock_db["users"].find_one = AsyncMock(return_value=target_user)
    mock_db["users"].count_documents = AsyncMock(return_value=2)

    cursor_mock = MagicMock()
    cursor_mock.to_list = AsyncMock(return_value=[])
    mock_db["campaigns"].find = MagicMock(return_value=cursor_mock)
    mock_db["characters"].find = MagicMock(return_value=cursor_mock)

    report = await delete_user_cascade(mock_db, target_id, {"id": "admin_id", "username": "admin"})
    assert report.user_id == target_id
    assert report.username == "player1"
    mock_db["users"].delete_one.assert_called_once()


# ==============================================================
# Admin Promotion Script Tests (#154)
# ==============================================================
@pytest.mark.anyio
async def test_promote_user_script(mock_db):
    user_doc = {"_id": ObjectId(), "username": "bob", "is_admin": False}
    mock_db["users"].find_one = AsyncMock(return_value=user_doc)
    mock_db["users"].update_one = AsyncMock(
        return_value=MagicMock(modified_count=1, matched_count=1)
    )

    promoted = await promote_user(mock_db, "bob")
    assert promoted is True
    mock_db["users"].update_one.assert_called_once()


# ==============================================================
# Whisper Reporting & Admin Inspection Tests (#155)
# ==============================================================
def test_admin_list_reports(admin_client, mock_db):
    cursor_mock = MagicMock()
    cursor_mock.sort = MagicMock(return_value=cursor_mock)
    cursor_mock.limit = MagicMock(return_value=cursor_mock)
    report_doc = {
        "_id": ObjectId(),
        "report_id": "rep_123",
        "whisper_id": "wh_456",
        "campaign_name": "Curse of Strahd",
        "reported_by_user_id": "user_789",
        "reported_by_username": "victim",
        "reason": "Harassment in whisper",
        "created_at": datetime.now(timezone.utc),
        "status": "open",
    }
    cursor_mock.to_list = AsyncMock(return_value=[report_doc])
    mock_db["whisper_reports"].find = MagicMock(return_value=cursor_mock)

    res = admin_client.get("/api/v1/admin/reports")
    assert res.status_code == 200
    reports = res.json()
    assert len(reports) == 1
    assert reports[0]["report_id"] == "rep_123"
    assert reports[0]["reason"] == "Harassment in whisper"


def test_admin_get_report_with_context(admin_client, mock_db):
    report_dt = datetime.now(timezone.utc)
    report_doc = {
        "_id": ObjectId(),
        "report_id": "rep_123",
        "whisper_id": "wh_456",
        "campaign_name": "Curse of Strahd",
        "reported_by_user_id": "user_789",
        "reported_by_username": "victim",
        "reason": "Harassment in whisper",
        "created_at": report_dt,
        "status": "open",
    }
    reported_whisper = {
        "_id": ObjectId(),
        "id": "wh_456",
        "whisper_id": "wh_456",
        "campaign_name": "Curse of Strahd",
        "sender_id": "bully_id",
        "recipient_id": "user_789",
        "message": "Offensive message",
        "created_at": report_dt,
    }

    mock_db["whisper_reports"].find_one = AsyncMock(return_value=report_doc)
    mock_db["campaign_whispers"].find_one = AsyncMock(return_value=reported_whisper)

    cursor_ctx = MagicMock()
    cursor_ctx.sort = MagicMock(return_value=cursor_ctx)
    cursor_ctx.limit = MagicMock(return_value=cursor_ctx)
    cursor_ctx.to_list = AsyncMock(return_value=[])

    mock_db["campaign_whispers"].find = MagicMock(return_value=cursor_ctx)

    res = admin_client.get("/api/v1/admin/reports/rep_123")
    assert res.status_code == 200
    data = res.json()
    assert data["report_id"] == "rep_123"
    assert data["whisper"]["message"] == "Offensive message"


def test_admin_update_report_status(admin_client, mock_db):
    now = datetime.now(timezone.utc)
    report_doc = {
        "_id": ObjectId(),
        "report_id": "rep_123",
        "whisper_id": "wh_456",
        "campaign_name": "Curse of Strahd",
        "reported_by_user_id": "user_789",
        "reported_by_username": "victim",
        "reason": "Harassment in whisper",
        "created_at": now,
        "status": "open",
    }
    mock_db["whisper_reports"].find_one = AsyncMock(
        side_effect=[
            report_doc,
            {**report_doc, "status": "resolved", "resolution_note": "Warned user"},
        ]
    )

    res = admin_client.patch(
        "/api/v1/admin/reports/rep_123",
        json={"status": "resolved", "resolution_note": "Warned user"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "resolved"
    mock_db["whisper_reports"].update_one.assert_called_once()


def test_non_admin_gets_403(mock_db):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(admin_router, prefix="/api/v1")

    regular_user = {"id": "player_1", "username": "player", "is_admin": False}
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    # mock_db["users"].find_one returns non-admin doc
    mock_db["users"].find_one = AsyncMock(return_value=regular_user)

    client = TestClient(app)
    res = client.get("/api/v1/admin/users")
    assert res.status_code == 403
    assert "Admin privileges required" in res.json()["detail"]


def test_report_whisper_rejects_empty_reason(admin_client, mock_db):
    member_doc = {
        "campaign_id": "Curse of Strahd",
        "user_id": "admin_user_1",
        "username": "admin",
        "role": "dm",
    }
    mock_db["campaign_members"].find_one = AsyncMock(return_value=member_doc)
    res = admin_client.post(
        "/api/v1/campaigns/Curse of Strahd/whispers/wh_123/report",
        json={"reason": "   "},
    )
    assert res.status_code == 400
    assert "cannot be empty" in res.json()["detail"]


def test_report_whisper_unauthorized_user_forbidden(mock_db):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(campaign_router, prefix="/api/v1")

    unrelated_user = {"id": "unrelated_1", "username": "eavesdropper", "is_admin": False}
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: unrelated_user

    member_doc = {
        "campaign_id": "Curse of Strahd",
        "user_id": "unrelated_1",
        "username": "eavesdropper",
        "role": "player",
    }
    mock_db["campaign_members"].find_one = AsyncMock(return_value=member_doc)

    camp_doc = {"campaign_name": "Curse of Strahd"}
    private_whisper = {
        "id": "wh_private",
        "campaign_name": "Curse of Strahd",
        "sender": "Alice",
        "recipient": "Bob",
        "sender_user_id": "user_alice",
        "recipient_user_id": "user_bob",
        "message": "Secret message",
    }
    mock_db["campaigns"].find_one = AsyncMock(return_value=camp_doc)
    mock_db["campaign_whispers"].find_one = AsyncMock(return_value=private_whisper)

    client = TestClient(app)
    res = client.post(
        "/api/v1/campaigns/Curse of Strahd/whispers/wh_private/report",
        json={"reason": "I want to report this"},
    )
    assert res.status_code == 403
    assert "Not authorized" in res.json()["detail"]


def test_whisper_report_context_endpoint_and_bidirectional_context(admin_client, mock_db):
    target_time = datetime(2026, 10, 24, 12, 5, 0, tzinfo=timezone.utc)

    report_doc = {
        "_id": ObjectId(),
        "report_id": "rep_test_ctx",
        "whisper_id": "wh_target",
        "campaign_name": "Curse of Strahd",
        "reported_by_user_id": "user_bob",
        "reason": "Harassment",
        "created_at": target_time,
        "status": "open",
    }
    reported_whisper = {
        "id": "wh_target",
        "campaign_name": "Curse of Strahd",
        "sender": "Alice",
        "recipient": "Bob",
        "sender_user_id": "u_alice",
        "recipient_user_id": "u_bob",
        "message": "Reported bad message",
        "created_at": target_time,
    }

    mock_db["whisper_reports"].find_one = AsyncMock(return_value=report_doc)
    mock_db["campaign_whispers"].find_one = AsyncMock(return_value=reported_whisper)

    # Context mocks: 2 whispers before and 1 whisper after
    w_before = [
        {
            "id": "w_b1",
            "message": "Hi",
            "created_at": datetime(2026, 10, 24, 12, 1, 0, tzinfo=timezone.utc),
        },
        {
            "id": "w_b2",
            "message": "How are you",
            "created_at": datetime(2026, 10, 24, 12, 2, 0, tzinfo=timezone.utc),
        },
    ]
    w_after = [
        {
            "id": "w_a1",
            "message": "Please stop",
            "created_at": datetime(2026, 10, 24, 12, 6, 0, tzinfo=timezone.utc),
        },
    ]

    cursor_before = MagicMock()
    cursor_before.sort = MagicMock(return_value=cursor_before)
    cursor_before.limit = MagicMock(return_value=cursor_before)
    cursor_before.to_list = AsyncMock(return_value=list(reversed(w_before)))

    cursor_after = MagicMock()
    cursor_after.sort = MagicMock(return_value=cursor_after)
    cursor_after.limit = MagicMock(return_value=cursor_after)
    cursor_after.to_list = AsyncMock(return_value=w_after)

    mock_db["campaign_whispers"].find = MagicMock(side_effect=[cursor_before, cursor_after])

    # Test alias route /whisper-reports/{report_id}/context
    res = admin_client.get("/api/v1/admin/whisper-reports/rep_test_ctx/context")
    assert res.status_code == 200
    data = res.json()
    assert data["report_id"] == "rep_test_ctx"
    assert len(data["context_whispers"]) == 4  # 2 before + 1 target + 1 after
    assert data["context_whispers"][0]["id"] == "w_b1"
    assert data["context_whispers"][1]["id"] == "w_b2"
    assert data["context_whispers"][2]["id"] == "wh_target"
    assert data["context_whispers"][3]["id"] == "w_a1"


def test_list_admin_users_counts_legacy_dm_campaigns(admin_client, mock_db):
    user_doc = {
        "id": "legacy_dm_1",
        "username": "legacydm",
        "email": "legacy@example.com",
        "name": "Legacy DM",
        "created_at": "2026-01-01T00:00:00Z",
        "is_admin": False,
    }
    mock_db["users"].count_documents = AsyncMock(return_value=1)

    # Motor async cursor mock for users.find
    cursor_users = MagicMock()
    cursor_users.sort = MagicMock(return_value=cursor_users)
    cursor_users.skip = MagicMock(return_value=cursor_users)
    cursor_users.limit = MagicMock(return_value=cursor_users)
    cursor_users.__aiter__ = MagicMock(return_value=[user_doc].__iter__())  # or async iter

    async def async_iter(items):
        for item in items:
            yield item

    cursor_users.__aiter__ = lambda self: async_iter([user_doc])
    mock_db["users"].find = MagicMock(return_value=cursor_users)

    # No campaigns by owner_id
    cursor_camps = MagicMock()
    cursor_camps.__aiter__ = lambda self: async_iter([])
    # But campaign_members has role == "dm" for "Legacy Lost Mine"
    cursor_members = MagicMock()
    cursor_members.__aiter__ = lambda self: async_iter(
        [{"campaign_id": "Legacy Lost Mine", "role": "dm"}]
    )

    def mock_find(query, *args, **kwargs):
        if "owner_id" in query:
            return cursor_camps
        elif query.get("role") == "dm":
            return cursor_members
        return MagicMock(__aiter__=lambda self: async_iter([]))

    mock_db["campaigns"].find = MagicMock(side_effect=mock_find)
    mock_db["campaigns"].find_one = AsyncMock(return_value={"campaign_name": "Legacy Lost Mine"})
    mock_db["campaign_members"].find = MagicMock(side_effect=mock_find)
    mock_db["characters"].count_documents = AsyncMock(return_value=2)
    mock_db["campaign_members"].count_documents = AsyncMock(return_value=1)

    res = admin_client.get("/api/v1/admin/users")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert len(data["users"]) == 1
    u = data["users"][0]
    assert u["username"] == "legacydm"
    assert u["dm_campaign_count"] == 1
    assert u["character_count"] == 2
