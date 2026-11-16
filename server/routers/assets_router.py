import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.utils.image_utils import ALLOWED_IMAGE_EXTENSIONS, stream_validated_image_upload
from server.db_async import get_database
from server.dependencies.campaign import require_campaign_member

router = APIRouter(prefix="/campaigns/{name}/assets", tags=["Assets"])

ASSETS_DIR = "data/uploads"
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
os.makedirs(ASSETS_DIR, exist_ok=True)


@router.post("")
async def upload_asset(
    name: str,
    file: UploadFile = File(...),
    kind: str = Form("map"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_member()),
) -> Dict[str, Any]:
    """Upload an asset (image) for a campaign."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed.",
        )

    raw_filename = file.filename or ""
    file_extension = os.path.splitext(raw_filename)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    base_dir = os.path.realpath(ASSETS_DIR)
    file_path = os.path.realpath(os.path.join(base_dir, unique_filename))
    if os.path.commonpath([base_dir, file_path]) != base_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")

    await stream_validated_image_upload(file, file_path, file_extension, max_bytes=MAX_UPLOAD_BYTES)

    asset_doc = {
        "filename": unique_filename,
        "campaign_name": name,
        "uploaded_by_user_id": campaign_member.get("user_id", ""),
        "kind": kind if kind in ("map", "token") else "map",
        "created_at": datetime.now(timezone.utc),
    }
    await db["campaign_assets"].insert_one(asset_doc)

    encoded_name = quote(name, safe="")
    return {
        "url": f"/api/v1/campaigns/{encoded_name}/assets/{unique_filename}",
        "filename": unique_filename,
        "kind": asset_doc["kind"],
    }


@router.get("")
async def list_assets(
    name: str,
    kind: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_member()),
) -> List[Dict[str, Any]]:
    """List uploaded assets for a campaign."""
    query: Dict[str, Any] = {"campaign_name": name}
    if kind:
        query["kind"] = kind

    cursor = db["campaign_assets"].find(query).sort("created_at", -1)
    encoded_name = quote(name, safe="")
    assets = await cursor.to_list(length=200)
    result = []
    for a in assets:
        result.append(
            {
                "filename": a["filename"],
                "campaign_name": a["campaign_name"],
                "uploaded_by_user_id": a.get("uploaded_by_user_id", ""),
                "kind": a.get("kind", "map"),
                "created_at": a.get("created_at").isoformat()
                if isinstance(a.get("created_at"), datetime)
                else str(a.get("created_at")),
                "url": f"/api/v1/campaigns/{encoded_name}/assets/{a['filename']}",
            }
        )
    return result


@router.get("/{filename}")
async def get_asset(
    name: str,
    filename: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_member()),
):
    """Retrieve an uploaded asset."""
    file_path = os.path.abspath(os.path.join(ASSETS_DIR, filename))
    base_dir = os.path.abspath(ASSETS_DIR)

    if os.path.commonpath([base_dir, file_path]) != base_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Asset not found")

    asset = await db["campaign_assets"].find_one({"filename": filename})
    if not asset or asset.get("campaign_name") != name:
        raise HTTPException(status_code=404, detail="Asset not found")

    return FileResponse(file_path)
