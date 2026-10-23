#!/usr/bin/env python3
"""CLI utility and async helper to migrate legacy campaign vtt_state to campaign_scenes collections."""

import asyncio
import datetime
import logging
import sys
import uuid
from typing import Any

from backend.core.schemas import VTTFogSchema, VTTGridSchema
from backend.services.campaign_service import _maybe_await
from server.db_async import close_mongo_connection, connect_to_mongo, get_database

logger = logging.getLogger("PhyrexianForge.MigrateVttScenes")


async def migrate_campaigns_to_scenes(db: Any) -> int:
    """Migrates all campaigns with legacy inline vtt_state to campaign_scenes. Idempotent."""
    cursor = db["campaigns"].find({})
    migrated_count = 0
    now = datetime.datetime.now(datetime.timezone.utc)

    if hasattr(cursor, "__aiter__"):
        async for camp in cursor:
            cname = camp.get("campaign_name")
            if not cname:
                continue

            vtt_st = camp.get("vtt_state") or {}
            active_scene_id = vtt_st.get("active_scene_id")

            # Check if active scene already exists
            if active_scene_id:
                existing = await _maybe_await(
                    db["campaign_scenes"].find_one({"scene_id": active_scene_id})
                )
                if existing:
                    continue

            # Check if any scene exists for this campaign
            scene_doc = await _maybe_await(db["campaign_scenes"].find_one({"campaign_name": cname}))
            if scene_doc:
                sid = scene_doc["scene_id"]
                await _maybe_await(
                    db["campaigns"].update_one(
                        {"_id": camp["_id"]},
                        {"$set": {"vtt_state.active_scene_id": sid}},
                    )
                )
                continue

            # Need migration: create Default scene
            new_scene_id = str(uuid.uuid4())
            grid_dict = vtt_st.get("grid") or VTTGridSchema().model_dump()
            tokens_list = vtt_st.get("tokens") or []
            default_scene = {
                "scene_id": new_scene_id,
                "campaign_name": cname,
                "name": "Default",
                "dm_notes": "",
                "grid": grid_dict,
                "tokens": tokens_list,
                "fog": VTTFogSchema().model_dump(),
                "order": 0,
                "created_at": now,
                "updated_at": now,
                "last_activated_at": now,
            }
            await _maybe_await(db["campaign_scenes"].insert_one(default_scene))
            await _maybe_await(
                db["campaigns"].update_one(
                    {"_id": camp["_id"]},
                    {
                        "$set": {
                            "vtt_state.active_scene_id": new_scene_id,
                            "vtt_state.is_active": bool(vtt_st.get("is_active", False)),
                        }
                    },
                )
            )
            migrated_count += 1

    return migrated_count


async def main_async() -> int:
    await connect_to_mongo()
    db = await get_database()
    try:
        count = await migrate_campaigns_to_scenes(db)
        print(f"Successfully migrated {count} campaign(s) to campaign_scenes.")
        return 0
    finally:
        await close_mongo_connection()


def main():
    sys.exit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
