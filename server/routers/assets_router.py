import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from server.db_async import get_database
from server.dependencies.campaign import require_campaign_member

router = APIRouter(prefix="/campaigns/{name}/assets", tags=["Assets"])

ASSETS_DIR = "data/uploads"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
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
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image extension '{file_extension}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    file_path = os.path.join(ASSETS_DIR, unique_filename)

    total_bytes = 0
    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Uploaded image exceeds the 10 MB limit.",
                    )
                buffer.write(chunk)
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    asset_doc = {
        "filename": unique_filename,
        "campaign_name": name,
        "uploaded_by_user_id": campaign_member.get("user_id", ""),
        "kind": kind if kind in ("map", "token") else "map",
        "created_at": datetime.now(timezone.utc),
    }
    await db["campaign_assets"].insert_one(asset_doc)

    return {
        "url": f"/api/v1/campaigns/{name}/assets/{unique_filename}",
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
                "url": f"/api/v1/campaigns/{name}/assets/{a['filename']}",
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
    if asset and asset.get("campaign_name") != name:
        raise HTTPException(status_code=404, detail="Asset not found")

    return FileResponse(file_path)
