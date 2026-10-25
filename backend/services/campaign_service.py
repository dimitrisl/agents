import datetime
import inspect
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("PhyrexianForge.CampaignService")


async def _maybe_await(val: Any) -> Any:
    """Helper to await a value only if it is awaitable (ensures unit tests with sync MagicMocks pass)."""
    if inspect.isawaitable(val):
        return await val
    return val


async def delete_campaign_cascade(
    db: Any,
    campaign_name: str,
    broadcast: bool = True,
    now: Optional[datetime.datetime] = None,
) -> Dict[str, int]:
    """
    Deletes a campaign and its associated records with full cascade:
    1. Detaches party characters (preserves sheets, clears active_campaign).
    2. Archives whispers instead of deleting (#155).
    3. Deletes members, encounters, entities, session logs, skeletons, homebrew.
    4. Deletes VTT scenes, history, assets and cleans up uploaded map files (#156).
    5. Deletes campaign document and broadcasts campaign_deleted.
    """
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Unset active_campaign for all characters currently in this campaign
    await _maybe_await(
        db["characters"].update_many(
            {"active_campaign": campaign_name},
            {"$unset": {"active_campaign": ""}},
        )
    )

    # 2. Archive whispers instead of deleting (#155)
    await _maybe_await(
        db["campaign_whispers"].update_many(
            {"campaign_name": campaign_name, "archived_at": None},
            {"$set": {"archived_at": now}},
        )
    )

    # 3. Delete related campaign documents
    await _maybe_await(db["campaign_members"].delete_many({"campaign_id": campaign_name}))
    await _maybe_await(db["campaign_roll_requests"].delete_many({"campaign_name": campaign_name}))
    await _maybe_await(db["campaign_encounters"].delete_many({"campaign_name": campaign_name}))
    await _maybe_await(db["campaign_entities"].delete_many({"campaign_name": campaign_name}))
    await _maybe_await(db["session_logs"].delete_many({"campaign_name": campaign_name}))
    await _maybe_await(db["campaign_skeletons"].delete_many({"campaign_name": campaign_name}))
    await _maybe_await(
        db["homebrew_content"].delete_many(
            {"$or": [{"campaign_name": campaign_name}, {"campaign_id": campaign_name}]}
        )
    )

    # 4. Clean up VTT scenes, scene history and campaign assets (#156)
    try:
        assets_cursor = db["campaign_assets"].find({"campaign_name": campaign_name})
        if hasattr(assets_cursor, "__aiter__"):
            async for asset in assets_cursor:
                filename = asset.get("filename")
                if filename:
                    file_path = os.path.join("data", "uploads", filename)
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logger.warning("Failed to remove asset file %s: %s", file_path, e)
    except Exception as e:
        logger.warning("Failed iterating campaign_assets during cascade: %s", e)

    await _maybe_await(db["campaign_assets"].delete_many({"campaign_name": campaign_name}))
    await _maybe_await(db["campaign_scenes"].delete_many({"campaign_name": campaign_name}))
    await _maybe_await(db["campaign_scene_history"].delete_many({"campaign_name": campaign_name}))

    # 5. Delete campaign document
    await _maybe_await(db["campaigns"].delete_one({"campaign_name": campaign_name}))

    # 6. WebSocket broadcast
    if broadcast:
        try:
            from server.routers.websocket_router import manager

            await _maybe_await(manager.broadcast(campaign_name, {"type": "campaign_deleted"}))
        except Exception as e:
            logger.warning("Error broadcasting campaign_deleted for %s: %s", campaign_name, e)

    return {"success": True}
