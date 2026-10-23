import datetime
import logging
import os
import re
from typing import Any, List, Optional, Set

from fastapi import HTTPException, status

from backend.core.schemas import UserDeletionPreview, UserDeletionReport
from backend.services.campaign_service import _maybe_await, delete_campaign_cascade
from backend.utils.image_utils import PORTRAIT_DIR
from backend.utils.path_safety import safe_path

logger = logging.getLogger("PhyrexianForge.UserAdminService")


async def _find_dm_campaigns_for_user(db: Any, user_id: str) -> List[dict]:
    """Finds campaigns owned by this user or where they are DM."""
    dm_camps = []
    seen = set()

    # 1. Campaigns where owner_id == user_id
    cursor = db["campaigns"].find({"owner_id": user_id})
    if hasattr(cursor, "__aiter__"):
        async for camp in cursor:
            name = camp.get("campaign_name")
            if name and name not in seen:
                seen.add(name)
                dm_camps.append(camp)
    else:
        # Mock / list fallback
        items = await _maybe_await(cursor)
        if isinstance(items, list):
            for camp in items:
                name = camp.get("campaign_name")
                if name and name not in seen:
                    seen.add(name)
                    dm_camps.append(camp)

    # 2. Legacy fallback: campaign_members where user_id == user_id and role == "dm"
    mem_cursor = db["campaign_members"].find({"user_id": user_id, "role": "dm"})
    if hasattr(mem_cursor, "__aiter__"):
        async for m in mem_cursor:
            cname = m.get("campaign_id")
            if cname and cname not in seen:
                camp = await _maybe_await(db["campaigns"].find_one({"campaign_name": cname}))
                if camp and camp.get("campaign_name") not in seen:
                    seen.add(camp["campaign_name"])
                    dm_camps.append(camp)
    else:
        items = await _maybe_await(mem_cursor)
        if isinstance(items, list):
            for m in items:
                cname = m.get("campaign_id")
                if cname and cname not in seen:
                    camp = await _maybe_await(db["campaigns"].find_one({"campaign_name": cname}))
                    if camp and camp.get("campaign_name") not in seen:
                        seen.add(camp["campaign_name"])
                        dm_camps.append(camp)

    return dm_camps


def _find_portrait_files_for_char_ids(char_ids: Set[str]) -> List[str]:
    """Scans PORTRAIT_DIR for files belonging to any of the char_ids."""
    matched_files = []
    if not os.path.exists(PORTRAIT_DIR) or not char_ids:
        return matched_files

    patterns = [
        re.compile(rf"^{re.escape(cid)}(?:_\d+)?\.(?:png|jpg|jpeg|webp)$", re.IGNORECASE)
        for cid in char_ids
    ]

    try:
        for fname in os.listdir(PORTRAIT_DIR):
            if any(p.match(fname) for p in patterns):
                matched_files.append(fname)
    except Exception as e:
        logger.warning("Error reading portrait dir: %s", e)

    return matched_files


async def build_deletion_preview(
    db: Any, user_id: str, current_admin_user: Optional[dict] = None
) -> UserDeletionPreview:
    """Computes exact counts for what will be deleted/detached without mutating anything."""
    user = await _maybe_await(db["users"].find_one({"id": user_id}))
    if not user:
        user = await _maybe_await(db["users"].find_one({"username": user_id}))
    if (
        not user
        and current_admin_user
        and (
            current_admin_user.get("id") == user_id or current_admin_user.get("username") == user_id
        )
    ):
        user = current_admin_user
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    actual_user_id = user.get("id") or user_id
    username = user.get("username", "Unknown")

    can_delete = True
    blocking_reasons: List[str] = []

    # Check self deletion
    if current_admin_user and (
        actual_user_id == current_admin_user.get("id")
        or username == current_admin_user.get("username")
    ):
        can_delete = False
        blocking_reasons.append("You cannot delete your own account.")

    # Check last remaining administrator
    if user.get("is_admin"):
        admin_count = await _maybe_await(db["users"].count_documents({"is_admin": True}))
        if admin_count <= 1:
            can_delete = False
            blocking_reasons.append("Cannot delete the last remaining administrator.")

    # 1. Characters owned by user
    char_ids = set()
    char_count = 0
    char_cursor = db["characters"].find({"owner_id": actual_user_id})
    if hasattr(char_cursor, "__aiter__"):
        async for c in char_cursor:
            char_count += 1
            if c.get("char_id"):
                char_ids.add(c["char_id"])
    else:
        chars = await _maybe_await(char_cursor)
        if isinstance(chars, list):
            char_count = len(chars)
            for c in chars:
                if c.get("char_id"):
                    char_ids.add(c["char_id"])
        else:
            char_count = await _maybe_await(
                db["characters"].count_documents({"owner_id": actual_user_id})
            )

    # 2. Portraits
    portrait_files = _find_portrait_files_for_char_ids(char_ids)

    # 3. DM campaigns
    dm_camps = await _find_dm_campaigns_for_user(db, actual_user_id)
    dm_camp_names = [c["campaign_name"] for c in dm_camps if c.get("campaign_name")]

    # 4. Other players' characters in those campaigns that will be detached
    detached_chars = 0
    if dm_camp_names:
        detached_chars = await _maybe_await(
            db["characters"].count_documents(
                {
                    "active_campaign": {"$in": dm_camp_names},
                    "owner_id": {"$ne": actual_user_id},
                }
            )
        )

    # 5. Memberships in other DMs' campaigns
    memberships_to_remove = await _maybe_await(
        db["campaign_members"].count_documents(
            {
                "user_id": actual_user_id,
                "campaign_id": {"$nin": dm_camp_names},
            }
        )
    )

    # 6. Pending roll requests for user's characters in other campaigns
    roll_requests_to_delete = 0
    if char_ids:
        roll_requests_to_delete = await _maybe_await(
            db["campaign_roll_requests"].count_documents(
                {
                    "$or": [
                        {"char_filename": {"$in": list(char_ids)}},
                        {"char_filename": {"$in": [f"{cid}.json" for cid in char_ids]}},
                    ]
                }
            )
        )

    # 7. Whispers that will be archived in the DM campaigns
    whispers_to_archive = 0
    if dm_camp_names:
        whispers_to_archive = await _maybe_await(
            db["campaign_whispers"].count_documents(
                {
                    "campaign_name": {"$in": dm_camp_names},
                    "archived_at": None,
                }
            )
        )

    return UserDeletionPreview(
        user_id=actual_user_id,
        username=username,
        characters_to_delete=char_count,
        portraits_to_delete=len(portrait_files),
        dm_campaigns_to_delete=len(dm_camp_names),
        dm_campaign_names=dm_camp_names,
        player_characters_to_detach=detached_chars,
        memberships_to_remove=memberships_to_remove,
        roll_requests_to_delete=roll_requests_to_delete,
        whispers_to_archive=whispers_to_archive,
        can_delete=can_delete,
        blocking_reasons=blocking_reasons,
    )


async def delete_user_cascade(db: Any, user_id: str, admin_user: dict) -> UserDeletionReport:
    """Executes full cascading deletion of a user idempotently."""
    user = await _maybe_await(db["users"].find_one({"id": user_id}))
    if not user:
        user = await _maybe_await(db["users"].find_one({"username": user_id}))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    actual_user_id = user.get("id") or user_id

    # Guard 1: Admin cannot delete themselves
    if actual_user_id == admin_user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot delete their own account.",
        )

    # Guard 2: Cannot delete the last admin
    if user.get("is_admin"):
        admin_count = await _maybe_await(db["users"].count_documents({"is_admin": True}))
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last admin account.",
            )

    now = datetime.datetime.now(datetime.timezone.utc)
    preview = await build_deletion_preview(db, actual_user_id)

    # 1. Cascade DM campaigns (archives whispers, detaches other players' characters, deletes VTT scenes/assets)
    for cname in preview.dm_campaign_names:
        try:
            await delete_campaign_cascade(db, cname, broadcast=True, now=now)
        except Exception as e:
            logger.warning("Error deleting DM campaign %s: %s", cname, e)

    # 2. For user's characters: remove from other campaigns' party arrays, encounters & roll requests
    char_ids = set()
    char_cursor = db["characters"].find({"owner_id": actual_user_id})
    if hasattr(char_cursor, "__aiter__"):
        async for c in char_cursor:
            if c.get("char_id"):
                char_ids.add(c["char_id"])
    else:
        chars = await _maybe_await(char_cursor)
        if isinstance(chars, list):
            for c in chars:
                if c.get("char_id"):
                    char_ids.add(c["char_id"])

    for cid in char_ids:
        try:
            # Pull from party arrays in remaining campaigns
            await _maybe_await(
                db["campaigns"].update_many(
                    {},
                    {"$pull": {"party": {"$in": [cid, f"{cid}.json"]}}},
                )
            )
            # Pull from combatants in encounters
            await _maybe_await(
                db["campaign_encounters"].update_many(
                    {},
                    {"$pull": {"combatants": {"$or": [{"char_id": cid}, {"id": cid}]}}},
                )
            )
            # Delete pending roll requests
            await _maybe_await(
                db["campaign_roll_requests"].delete_many(
                    {
                        "$or": [
                            {"char_filename": cid},
                            {"char_filename": f"{cid}.json"},
                        ]
                    }
                )
            )
        except Exception as e:
            logger.warning("Error cleaning character %s from other campaigns: %s", cid, e)

    # 3. Delete user's memberships in other campaigns
    await _maybe_await(db["campaign_members"].delete_many({"user_id": actual_user_id}))

    # 4. Delete portrait files on disk
    portrait_files = _find_portrait_files_for_char_ids(char_ids)
    for fname in portrait_files:
        try:
            full_path = safe_path(os.path.join(PORTRAIT_DIR, fname), scope="portraits")
            if os.path.exists(full_path):
                os.remove(full_path)
        except Exception as e:
            logger.warning("Failed removing portrait %s: %s", fname, e)

    # 5. Delete characters
    await _maybe_await(db["characters"].delete_many({"owner_id": actual_user_id}))

    # 6. Disconnect WebSockets for this user
    try:
        from server.routers.websocket_router import manager

        await _maybe_await(manager.disconnect_user(actual_user_id))
    except Exception as e:
        logger.warning("Error disconnecting websockets for user %s: %s", actual_user_id, e)

    # 7. Delete user document last
    delete_filter = {"id": actual_user_id}
    if user.get("username"):
        delete_filter = {"$or": [{"id": actual_user_id}, {"username": user["username"]}]}
    await _maybe_await(db["users"].delete_one(delete_filter))

    # 8. Record in admin_audit_log
    try:
        await _maybe_await(
            db["admin_audit_log"].insert_one(
                {
                    "action": "delete_user",
                    "admin_user_id": admin_user["id"],
                    "admin_username": admin_user.get("username"),
                    "target_user_id": actual_user_id,
                    "target_username": user.get("username"),
                    "counts": preview.model_dump(),
                    "created_at": now,
                }
            )
        )
    except Exception as e:
        logger.warning("Failed writing to admin_audit_log: %s", e)

    return UserDeletionReport(**preview.model_dump(), deleted=True)
