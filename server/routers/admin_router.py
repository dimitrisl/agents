import datetime
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from backend.core.schemas import (
    AdminUserSchema,
    UserDeletionPreview,
    UserDeletionReport,
    WhisperReportSchema,
    WhisperReportUpdateRequest,
)
from backend.services.campaign_service import _maybe_await
from backend.services.user_admin_service import (
    _find_dm_campaigns_for_user,
    build_deletion_preview,
    delete_user_cascade,
)
from server.db_async import get_database
from server.dependencies.auth import is_user_recently_active, require_admin
from server.routers.websocket_router import manager

logger = logging.getLogger("PhyrexianForge.AdminRouter")

router = APIRouter(prefix="/admin", tags=["Admin"])


class AdminUserListResponse(BaseModel):
    users: List[AdminUserSchema]
    total: int


@router.get("/users", response_model=AdminUserListResponse)
async def list_admin_users(
    search: Optional[str] = Query(None, description="Search by username, email, or name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    query: Dict[str, Any] = {}
    if search and search.strip():
        term = search.strip()
        query["$or"] = [
            {"username": {"$regex": term, "$options": "i"}},
            {"email": {"$regex": term, "$options": "i"}},
            {"name": {"$regex": term, "$options": "i"}},
        ]

    total = await _maybe_await(db["users"].count_documents(query))
    cursor = db["users"].find(query).sort("created_at", -1).skip(skip).limit(limit)

    users_list = []
    users_raw = []
    if hasattr(cursor, "__aiter__"):
        async for u in cursor:
            users_raw.append(u)
    else:
        items = await _maybe_await(cursor)
        if isinstance(items, list):
            users_raw.extend(items)

    ws_online_uids = manager.get_online_user_ids()
    for u in users_raw:
        uid = u.get("id") or f"local_user_{u.get('username')}"
        uname = u.get("username", "Unknown")
        is_online = (uid in ws_online_uids) or is_user_recently_active(uid, uname)
        char_count = await _maybe_await(db["characters"].count_documents({"owner_id": uid}))
        dm_camps = await _find_dm_campaigns_for_user(db, uid)
        dm_camp_count = len(dm_camps)
        member_camp_count = await _maybe_await(
            db["campaign_members"].count_documents({"user_id": uid})
        )
        users_list.append(
            AdminUserSchema(
                id=uid,
                username=uname,
                email=u.get("email"),
                name=u.get("name"),
                created_at=u.get("created_at"),
                is_admin=bool(u.get("is_admin", False)),
                is_online=is_online,
                character_count=char_count,
                dm_campaign_count=dm_camp_count,
                member_campaign_count=member_camp_count,
            )
        )

    return AdminUserListResponse(users=users_list, total=total)


@router.get("/users/{user_id}/deletion-preview", response_model=UserDeletionPreview)
async def get_user_deletion_preview(
    user_id: str,
    admin_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await build_deletion_preview(db, user_id, current_admin_user=admin_user)


@router.delete("/users/{user_id}", response_model=UserDeletionReport)
async def delete_user(
    user_id: str,
    admin_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await delete_user_cascade(db, user_id, admin_user)


@router.get("/reports", response_model=List[WhisperReportSchema])
async def list_whisper_reports(
    status_filter: Optional[str] = Query(None, alias="status"),
    admin_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    query: Dict[str, Any] = {}
    if status_filter and status_filter.strip():
        query["status"] = status_filter.strip().lower()

    cursor = db["whisper_reports"].find(query).sort("created_at", -1).limit(100)
    if hasattr(cursor, "to_list"):
        raw_reports = await _maybe_await(cursor.to_list(length=100))
    elif hasattr(cursor, "__aiter__"):
        raw_reports = [r async for r in cursor]
    else:
        raw_reports = list(cursor)

    reports = []
    for r in raw_reports:
        r.pop("_id", None)
        wid = r.get("whisper_id")
        if wid:
            w = await _maybe_await(db["campaign_whispers"].find_one({"id": wid}))
            if w:
                w.pop("_id", None)
                r["whisper"] = w
        reports.append(WhisperReportSchema(**r))

    return reports


async def _fetch_context_whispers(db: Any, whisper: dict) -> List[dict]:
    cname = whisper.get("campaign_name")
    u1 = whisper.get("sender_user_id")
    u2 = whisper.get("recipient_user_id")
    pair_query: Dict[str, Any] = {"campaign_name": cname}
    if u1 and u2:
        pair_query["$or"] = [
            {"sender_user_id": u1, "recipient_user_id": u2},
            {"sender_user_id": u2, "recipient_user_id": u1},
        ]
    else:
        s1 = whisper.get("sender")
        s2 = whisper.get("recipient")
        pair_query["$or"] = [
            {"sender": s1, "recipient": s2},
            {"sender": s2, "recipient": s1},
        ]

    sort_field = "created_at" if whisper.get("created_at") is not None else "timestamp"
    target_val = whisper.get(sort_field)

    async def _run_query(filter_dict: dict, sort_order: int, limit: int) -> List[dict]:
        cursor = db["campaign_whispers"].find(filter_dict).sort(sort_field, sort_order).limit(limit)
        if hasattr(cursor, "to_list"):
            raw = await _maybe_await(cursor.to_list(length=limit))
        elif hasattr(cursor, "__aiter__"):
            raw = [w async for w in cursor]
        else:
            raw = list(cursor)
        out = []
        for w in raw:
            w.pop("_id", None)
            out.append(w)
        return out

    if target_val is not None:
        before_query = {**pair_query, sort_field: {"$lt": target_val}}
        after_query = {**pair_query, sort_field: {"$gt": target_val}}
        before_whispers = await _run_query(before_query, -1, 10)
        before_whispers.reverse()
        after_whispers = await _run_query(after_query, 1, 10)
        return before_whispers + [whisper] + after_whispers
    else:
        whispers = await _run_query(pair_query, -1, 20)
        whispers.reverse()
        return whispers


@router.get("/reports/{report_id}", response_model=WhisperReportSchema)
@router.get("/reports/{report_id}/context", response_model=WhisperReportSchema)
@router.get("/whisper-reports/{report_id}/context", response_model=WhisperReportSchema)
async def get_whisper_report_detail(
    report_id: str,
    admin_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    report = await _maybe_await(db["whisper_reports"].find_one({"report_id": report_id}))
    if not report:
        raise HTTPException(status_code=404, detail="Whisper report not found")
    report.pop("_id", None)

    whisper = await _maybe_await(db["campaign_whispers"].find_one({"id": report.get("whisper_id")}))
    if whisper:
        whisper.pop("_id", None)
        report["whisper"] = whisper

    context_whispers = []
    if whisper:
        context_whispers = await _fetch_context_whispers(db, whisper)

    report["context_whispers"] = context_whispers

    # Log to admin_audit_log
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        await _maybe_await(
            db["admin_audit_log"].insert_one(
                {
                    "action": "view_whisper_report",
                    "admin_user_id": admin_user["id"],
                    "admin_username": admin_user.get("username"),
                    "report_id": report_id,
                    "whisper_id": report.get("whisper_id"),
                    "created_at": now,
                }
            )
        )
    except Exception as e:
        logger.warning("Error writing view_whisper_report to audit log: %s", e)

    return WhisperReportSchema(**report)


@router.patch("/reports/{report_id}", response_model=WhisperReportSchema)
async def update_whisper_report(
    report_id: str,
    payload: WhisperReportUpdateRequest,
    admin_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    target_status = payload.status.lower().strip()
    if target_status not in ("open", "resolved", "dismissed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be 'open', 'resolved', or 'dismissed'.",
        )

    report = await _maybe_await(db["whisper_reports"].find_one({"report_id": report_id}))
    if not report:
        raise HTTPException(status_code=404, detail="Whisper report not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    update_doc: Dict[str, Any] = {
        "status": target_status,
        "resolved_at": now if target_status in ("resolved", "dismissed") else None,
        "resolved_by_user_id": admin_user["id"]
        if target_status in ("resolved", "dismissed")
        else None,
    }
    if payload.resolution_note is not None:
        update_doc["resolution_note"] = payload.resolution_note.strip()

    await _maybe_await(
        db["whisper_reports"].update_one({"report_id": report_id}, {"$set": update_doc})
    )

    # Check remaining open reports for this whisper
    wid = report.get("whisper_id")
    if wid:
        open_count = await _maybe_await(
            db["whisper_reports"].count_documents({"whisper_id": wid, "status": "open"})
        )
        await _maybe_await(
            db["campaign_whispers"].update_one(
                {"id": wid}, {"$set": {"has_open_report": open_count > 0}}
            )
        )

    # Audit log
    try:
        await _maybe_await(
            db["admin_audit_log"].insert_one(
                {
                    "action": "update_whisper_report",
                    "admin_user_id": admin_user["id"],
                    "admin_username": admin_user.get("username"),
                    "report_id": report_id,
                    "new_status": target_status,
                    "created_at": now,
                }
            )
        )
    except Exception as e:
        logger.warning("Error writing update_whisper_report to audit log: %s", e)

    updated_report = await _maybe_await(db["whisper_reports"].find_one({"report_id": report_id}))
    updated_report.pop("_id", None)
    return WhisperReportSchema(**updated_report)
