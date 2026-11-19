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

    from backend.services.rest_service import dm_control_reset_fields, reset_campaign_dm_controls

    # 1. Unset active_campaign and clear DM campaign controls for all characters in this campaign
    try:
        cursor = db["characters"].find({"active_campaign": campaign_name})
        if hasattr(cursor, "to_list"):
            affected = await cursor.to_list(length=500)
            for doc in affected:
                if isinstance(doc, dict) and doc.get("char_id"):
                    reset_doc = reset_campaign_dm_controls(doc)
                    reset_doc.pop("_id", None)
                    reset_doc.pop("active_campaign", None)
                    await _maybe_await(
                        db["characters"].update_one(
                            {"char_id": doc["char_id"]},
                            {"$unset": {"active_campaign": ""}, "$set": reset_doc},
                        )
                    )
    except Exception as e:
        logger.debug("Skipping per-hero re-sync in delete_campaign_cascade: %s", e)

    await _maybe_await(
        db["characters"].update_many(
            {"active_campaign": campaign_name},
            {"$unset": {"active_campaign": ""}, "$set": dm_control_reset_fields()},
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
    await _maybe_await(db["campaign_roll_logs"].delete_many({"campaign_name": campaign_name}))
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


def build_party_update_payload(
    char_doc: Dict[str, Any],
    *,
    source: str = "dm",
    action: Optional[str] = None,
) -> Dict[str, Any]:
    """Builds a consistent WebSocket `party_update` payload across DM and Player mutations."""
    payload: Dict[str, Any] = {
        "char_id": char_doc.get("char_id"),
        "char_name": char_doc.get("char_name", "Unknown"),
        "hp_current": int(char_doc.get("hp_current") or 0),
        "hp_max": int(char_doc.get("hp_max") or 0),
        "hp_temp": int(char_doc.get("hp_temp") or 0),
        "ac": int(char_doc.get("armor_class", 10) or 10),
        "ac_breakdown": char_doc.get("ac_breakdown"),
        "level": int(char_doc.get("char_level", 1) or 1),
        "speed": int(char_doc.get("speed", 30) or 0),
        "heavy_armor_speed_penalty": int(char_doc.get("heavy_armor_speed_penalty") or 0),
        "base_speed": char_doc.get("base_speed"),
        "base_hp_max": char_doc.get("base_hp_max"),
        "pre_dm_hp_max": char_doc.get("pre_dm_hp_max"),
        "passive_perception": char_doc.get("passive_perception"),
        "skills": char_doc.get("skills"),
        "saving_throw_values": char_doc.get("saving_throw_values"),
        "initiative_modifier": char_doc.get("initiative_modifier"),
        "initiative_bonus": char_doc.get("initiative_bonus"),
        "initiative_advantage": char_doc.get("initiative_advantage"),
        "spell_save_dc": char_doc.get("spell_save_dc"),
        "spell_attack_bonus": char_doc.get("spell_attack_bonus"),
        "global_attack_bonus": char_doc.get("global_attack_bonus"),
        "global_damage_bonus": char_doc.get("global_damage_bonus"),
        "equip_stat_bonuses": char_doc.get("equip_stat_bonuses"),
        "equip_hp_bonus": char_doc.get("equip_hp_bonus"),
        "stats": char_doc.get("stats"),
        "base_stats": char_doc.get("base_stats"),
        "weapons": char_doc.get("weapons"),
        "conditions": char_doc.get("conditions", []),
        "concentrating_on": char_doc.get("concentrating_on"),
        "death_saves": char_doc.get("death_saves"),
        "inspiration": bool(char_doc.get("inspiration", False)),
        "exhaustion_level": int(char_doc.get("exhaustion_level", 0) or 0),
        "exhaustion_bypass": bool(char_doc.get("exhaustion_bypass", False)),
        "magic_items_suppressed": bool(char_doc.get("magic_items_suppressed", False)),
        "dm_modifiers": char_doc.get("dm_modifiers"),
        "dm_short_rest_unlocked": bool(char_doc.get("dm_short_rest_unlocked", False)),
        "dm_long_rest_unlocked": bool(char_doc.get("dm_long_rest_unlocked", False)),
        "dm_level_up_unlocked": bool(char_doc.get("dm_level_up_unlocked", False)),
        "hit_dice_used": char_doc.get("hit_dice_used"),
        "spell_slots": char_doc.get("spell_slots"),
        "class_resources": char_doc.get("class_resources"),
        "version": char_doc.get("version"),
        "source": source,
    }
    if action:
        payload["action"] = action
    return payload
