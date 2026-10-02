import os
import shutil
import uuid
from typing import Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from server.db_async import get_database
from server.dependencies.campaign import require_campaign_member

router = APIRouter(prefix="/campaigns/{name}/assets", tags=["Assets"])

ASSETS_DIR = "data/uploads"
os.makedirs(ASSETS_DIR, exist_ok=True)


@router.post("")
async def upload_asset(
    name: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_member()),
) -> Dict[str, str]:
    """Upload an asset (image) for a campaign."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed.",
        )

    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    file_path = os.path.join(ASSETS_DIR, unique_filename)

    with open(file_path, "wb") as buffer:
        import asyncio

        await asyncio.to_thread(shutil.copyfileobj, file.file, buffer)

    return {"url": f"/api/campaigns/{name}/assets/{unique_filename}"}


@router.get("/{filename}")
async def get_asset(
    name: str,
    filename: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_member()),
):
    """Retrieve an uploaded asset."""
    file_path = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Asset not found")

    return FileResponse(file_path)
