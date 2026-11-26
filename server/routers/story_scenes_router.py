"""REST + WebSocket cast router for DM Story Scenes & Ephemeral Player Visual Handout Pop-ups (#288)."""

import datetime
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.schemas import (
    StorySceneCastRequest,
    StorySceneCreateRequest,
    StorySceneDismissRequest,
    StorySceneSchema,
    StorySceneUpdateRequest,
    SuccessResponseSchema,
)
from backend.services.story_scene_service import (
    build_scene_popup_payload,
    cleanup_unreferenced_story_assets,
    normalize_story_cards,
    resolve_cast_targets,
)
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.dependencies.campaign import require_campaign_role

router = APIRouter(prefix="/campaigns/{name}/story-scenes", tags=["Story Scenes"])


async def _require_campaign(db: AsyncIOMotorDatabase, name: str) -> Dict[str, Any]:
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return camp


@router.get("", response_model=List[StorySceneSchema])
async def list_story_scenes(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Retrieve all DM Story Scenes and their visual cards (DM only, zero player spoiler leak)."""
    await _require_campaign(db, name)
    cursor = db["campaign_story_scenes"].find({"campaign_name": name}).sort("order", 1)
    if hasattr(cursor, "to_list"):
        raw_docs = await cursor.to_list(length=None)
    elif hasattr(cursor, "__aiter__"):
        raw_docs = [doc async for doc in cursor]
    else:
        raw_docs = list(cursor)

    scenes: List[StorySceneSchema] = []
    for doc in raw_docs:
        doc.pop("_id", None)
        scenes.append(StorySceneSchema(**doc))
    return scenes


@router.post("", response_model=StorySceneSchema, status_code=status.HTTP_201_CREATED)
async def create_story_scene(
    name: str,
    payload: StorySceneCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Create a prepared Story Scene with ordered handout cards (DM only)."""
    await _require_campaign(db, name)
    now = datetime.datetime.now(datetime.timezone.utc)
    scene_id = str(uuid.uuid4())
    if payload.order is not None:
        next_order = payload.order
    else:
        cursor = db["campaign_story_scenes"].find({"campaign_name": name}).sort("order", -1)
        if hasattr(cursor, "to_list"):
            top_docs = await cursor.to_list(length=1)
        elif hasattr(cursor, "__aiter__"):
            top_docs = [doc async for doc in cursor]
        else:
            top_docs = list(cursor)
        max_order = (
            max((int(d.get("order") or 0) for d in top_docs), default=-1) if top_docs else -1
        )
        next_order = max_order + 1

    try:
        cards = normalize_story_cards(payload.cards)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    scene_doc: Dict[str, Any] = {
        "scene_id": scene_id,
        "campaign_name": name,
        "title": payload.title.strip(),
        "dm_notes": payload.dm_notes or "",
        "order": next_order,
        "cards": cards,
        "created_at": now,
        "updated_at": now,
    }
    await db["campaign_story_scenes"].insert_one(scene_doc)
    scene_doc.pop("_id", None)
    return StorySceneSchema(**scene_doc)


@router.post("/dismiss", response_model=SuccessResponseSchema)
async def dismiss_story_scene_popup(
    name: str,
    payload: StorySceneDismissRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Remotely clear any open story popup on connected player screens."""
    await _require_campaign(db, name)
    resolved_char_ids, target_user_ids, target_char_names = await resolve_cast_targets(
        db, name, payload.target_mode, payload.target_char_ids
    )

    from server.routers.websocket_router import manager

    frame = {
        "type": "scene_popup_dismiss",
        "payload": {
            "target_mode": payload.target_mode,
            "target_char_ids": resolved_char_ids,
        },
    }
    if payload.target_mode == "selected":
        await manager.broadcast(
            name,
            frame,
            characters=target_char_names,
            user_ids=target_user_ids or None,
        )
    else:
        await manager.broadcast(name, frame)

    return {"success": True, "message": "Dismissed active story popup on player screens."}


@router.put("/{scene_id}", response_model=StorySceneSchema)
async def update_story_scene(
    name: str,
    scene_id: str,
    payload: StorySceneUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Update a Story Scene's title, notes, ordering, or handout cards atomically (DM only)."""
    await _require_campaign(db, name)
    existing = await db["campaign_story_scenes"].find_one(
        {"campaign_name": name, "scene_id": scene_id}
    )
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story scene not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    update_fields: Dict[str, Any] = {"updated_at": now}
    if payload.title is not None:
        update_fields["title"] = payload.title.strip()
    if payload.dm_notes is not None:
        update_fields["dm_notes"] = payload.dm_notes
    if payload.order is not None:
        update_fields["order"] = payload.order

    removed_urls: List[str] = []
    if payload.cards is not None:
        try:
            new_cards = normalize_story_cards(payload.cards)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        update_fields["cards"] = new_cards
        new_urls = {c["image_url"] for c in new_cards if c.get("image_url")}
        old_urls = {
            str(c.get("image_url") or "")
            for c in (existing.get("cards") or [])
            if isinstance(c, dict) and c.get("image_url")
        }
        removed_urls = list(old_urls - new_urls)

    await db["campaign_story_scenes"].update_one(
        {"campaign_name": name, "scene_id": scene_id},
        {"$set": update_fields},
    )

    if removed_urls:
        await cleanup_unreferenced_story_assets(db, name, removed_urls, exclude_scene_id=None)

    updated = await db["campaign_story_scenes"].find_one(
        {"campaign_name": name, "scene_id": scene_id}
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story scene not found")
    updated.pop("_id", None)
    return StorySceneSchema(**updated)


@router.delete("/{scene_id}", response_model=SuccessResponseSchema)
async def delete_story_scene(
    name: str,
    scene_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Delete a Story Scene and prune any unreferenced uploaded scene assets (DM only)."""
    await _require_campaign(db, name)
    scene = await db["campaign_story_scenes"].find_one(
        {"campaign_name": name, "scene_id": scene_id}
    )
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story scene not found")

    candidate_urls = [
        str(c.get("image_url") or "")
        for c in (scene.get("cards") or [])
        if isinstance(c, dict) and c.get("image_url")
    ]
    await db["campaign_story_scenes"].delete_one({"campaign_name": name, "scene_id": scene_id})
    if candidate_urls:
        await cleanup_unreferenced_story_assets(db, name, candidate_urls)

    return {"success": True, "message": f"Story scene {scene_id} deleted."}


@router.post("/{scene_id}/cast", response_model=SuccessResponseSchema)
async def cast_story_scene_card(
    name: str,
    scene_id: str,
    payload: StorySceneCastRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Broadcast a visual card pop-up to all online players or selected characters (ephemeral WS)."""
    await _require_campaign(db, name)
    scene = await db["campaign_story_scenes"].find_one(
        {"campaign_name": name, "scene_id": scene_id}
    )
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story scene not found")

    card = next(
        (
            c
            for c in (scene.get("cards") or [])
            if isinstance(c, dict) and str(c.get("card_id") or "") == payload.card_id
        ),
        None,
    )
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story card not found in scene"
        )

    if not str(card.get("image_url") or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot broadcast a handout card without an image.",
        )

    resolved_char_ids, target_user_ids, target_char_names = await resolve_cast_targets(
        db, name, payload.target_mode, payload.target_char_ids
    )
    ws_payload = build_scene_popup_payload(
        scene,
        card,
        target_mode=payload.target_mode,
        target_char_ids=resolved_char_ids,
    )

    from server.routers.websocket_router import manager

    frame = {"type": "scene_popup", "payload": ws_payload}
    if payload.target_mode == "selected":
        await manager.broadcast(
            name,
            frame,
            characters=target_char_names,
            user_ids=target_user_ids or None,
        )
    else:
        await manager.broadcast(name, frame)

    return {
        "success": True,
        "message": (
            f"Cast '{ws_payload['title']}' to {len(resolved_char_ids)} selected target(s)."
            if payload.target_mode == "selected"
            else f"Cast '{ws_payload['title']}' to all connected players."
        ),
    }
