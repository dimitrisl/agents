from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.homebrew_schemas import (
    HomebrewCreateRequest,
    HomebrewExportResponse,
    HomebrewImportRequest,
)
from backend.services.homebrew_service import HomebrewService
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.dependencies.campaign import require_campaign_role

router = APIRouter(prefix="/campaigns/{name}/homebrew", tags=["Homebrew Forge"])
homebrew_service = HomebrewService()


@router.get("", response_model=List[Dict[str, Any]])
async def get_homebrew(
    name: str,
    type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    member: dict = Depends(require_campaign_role("dm", "player")),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Retrieve homebrew items for the campaign. DMs and players can read."""
    return await homebrew_service.get_campaign_homebrew(db, name, type)


@router.post("/forge")
async def forge_homebrew(
    name: str,
    payload: HomebrewCreateRequest,
    current_user: dict = Depends(get_current_user),
    member: dict = Depends(require_campaign_role("dm")),  # Only DM can forge
):
    """Uses AI to forge a structured homebrew item based on a natural language prompt."""
    if not payload.prompt:
        raise HTTPException(status_code=400, detail="Prompt is required for AI Forging.")

    try:
        return await homebrew_service.forge_with_ai(payload.prompt, payload.type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to forge item: {str(e)}")


@router.post("")
async def create_homebrew(
    name: str,
    payload: HomebrewCreateRequest,
    current_user: dict = Depends(get_current_user),
    member: dict = Depends(require_campaign_role("dm")),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Saves a fully structured homebrew entity."""
    if not payload.data:
        raise HTTPException(status_code=400, detail="Data payload is required to save homebrew.")

    # Optional: We could validate payload.data against the schema using schema_map from service
    # For now, assume payload.data is pre-validated by the client guided form
    item_id = await homebrew_service.create_homebrew(db, name, current_user["id"], payload.data)
    return {"success": True, "id": item_id, "message": "Homebrew created successfully"}


@router.delete("/{item_id}")
async def delete_homebrew(
    name: str,
    item_id: str,
    current_user: dict = Depends(get_current_user),
    member: dict = Depends(require_campaign_role("dm")),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    success = await homebrew_service.delete_homebrew(db, item_id, name)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found or unauthorized.")
    return {"success": True, "message": "Item deleted."}


@router.get("/export", response_model=HomebrewExportResponse)
async def export_homebrew(
    name: str,
    current_user: dict = Depends(get_current_user),
    member: dict = Depends(require_campaign_role("dm")),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    items = await homebrew_service.get_campaign_homebrew(db, name)
    return HomebrewExportResponse(campaign_id=name, items=items)


@router.post("/import")
async def import_homebrew(
    name: str,
    payload: HomebrewImportRequest,
    current_user: dict = Depends(get_current_user),
    member: dict = Depends(require_campaign_role("dm")),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    count = 0
    for item in payload.items:
        await homebrew_service.create_homebrew(db, name, current_user["id"], item)
        count += 1
    return {"success": True, "message": f"Imported {count} items successfully."}
