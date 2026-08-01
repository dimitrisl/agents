import asyncio
import io
import logging
import os
import time
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

from backend.core.schemas import CharacterSchema, SuccessResponseSchema
from backend.services.forge_service import process_character_update
from backend.services.rules_service import parse_character_from_text
from backend.utils.pdf_exporter import export_character_to_pdf
from backend.utils.pdf_importer import extract_text_and_fields_from_pdf
from server.db_async import get_database
from server.dependencies.auth import get_current_user

router = APIRouter(prefix="/characters", tags=["Characters"])
logger = logging.getLogger("PhyrexianForge.CharacterRouter")

# Debounce registry: char_id -> (char_dict, timestamp)
_pending_updates: dict[str, tuple[dict, float]] = {}
_PENDING_TTL_SECONDS = 30.0


def _cleanup_stale_pending():
    """Remove entries older than TTL to prevent unbounded memory growth."""
    now = time.monotonic()
    stale = [k for k, (_, ts) in _pending_updates.items() if now - ts > _PENDING_TTL_SECONDS]
    for k in stale:
        del _pending_updates[k]


@router.get("", response_model=List[CharacterSchema])
async def list_characters(current_user: dict = Depends(get_current_user)):
    db = get_database()
    cursor = db["characters"].find({"owner_id": current_user["id"]})
    characters = []
    async for doc in cursor:
        doc.pop("_id", None)
        try:
            characters.append(CharacterSchema.model_validate(doc, strict=False))
        except Exception as e:
            logger.warning("Skipping legacy character %s: %s", doc.get("char_name", "Unknown"), e)
            pass
    return characters


@router.post("", response_model=CharacterSchema, status_code=status.HTTP_201_CREATED)
async def create_character(
    char_in: CharacterSchema, current_user: dict = Depends(get_current_user)
):
    db = get_database()
    char_dict = char_in.model_dump()
    char_dict["owner_id"] = current_user["id"]

    # Ensure stats & derived properties are synchronized
    char_dict = process_character_update(char_dict)

    await db["characters"].update_one(
        {"char_id": char_dict["char_id"]}, {"$set": char_dict}, upsert=True
    )
    return CharacterSchema.model_validate(char_dict, strict=False)


@router.get("/{char_id}", response_model=CharacterSchema)
async def get_character(char_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    doc = await db["characters"].find_one({"char_id": char_id, "owner_id": current_user["id"]})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    doc.pop("_id", None)
    return CharacterSchema.model_validate(doc, strict=False)


@router.put("/{char_id}", response_model=CharacterSchema)
async def update_character(
    char_id: str,
    char_in: CharacterSchema,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    existing = await db["characters"].find_one({"char_id": char_id, "owner_id": current_user["id"]})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")

    char_dict = char_in.model_dump()
    char_dict["char_id"] = char_id
    char_dict["owner_id"] = current_user["id"]

    # Register this exact dict object as the latest pending update
    _cleanup_stale_pending()
    _pending_updates[char_id] = (char_dict, time.monotonic())

    # Debounce window: wait briefly to allow subsequent keystrokes/requests to supersede this one
    await asyncio.sleep(0.4)

    # If this request's payload was superseded by a newer one, abort processing
    # and return the LATEST unprocessed payload to prevent the frontend cursor from jumping back.
    if _pending_updates.get(char_id) is not None and _pending_updates[char_id][0] is not char_dict:
        return CharacterSchema.model_validate(_pending_updates[char_id][0], strict=False)

    # Re-calculate and sync stats using threadpool to prevent blocking the async event loop
    char_dict = await run_in_threadpool(process_character_update, char_dict)

    await db["characters"].update_one({"char_id": char_id}, {"$set": char_dict})

    # Update the pending registry with the PROCESSED dict so straggler requests return the correctly synced stats
    _pending_updates[char_id] = (char_dict, time.monotonic())

    return CharacterSchema.model_validate(char_dict, strict=False)


@router.delete("/{char_id}", response_model=SuccessResponseSchema)
async def delete_character(char_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    result = await db["characters"].delete_one({"char_id": char_id, "owner_id": current_user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")

    # Clean up local portrait if exists
    portrait_path = os.path.join("data", "portraits", f"{char_id}.png")
    if os.path.exists(portrait_path):
        try:
            os.remove(portrait_path)
        except Exception as e:
            logger.warning("Failed to delete portrait for %s: %s", char_id, e)

    return {"success": True, "message": f"Character {char_id} deleted."}


@router.post("/{char_id}/export-pdf", response_class=FileResponse)
async def export_pdf(char_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    doc = await db["characters"].find_one({"char_id": char_id, "owner_id": current_user["id"]})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    doc.pop("_id", None)
    char_dict = CharacterSchema.model_validate(doc, strict=False).model_dump()
    char_dict = process_character_update(char_dict)

    pdf_bytes = export_character_to_pdf(char_dict, "5E_CharacterSheet_Fillable.pdf")
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate character PDF",
        )

    char_name_clean = char_dict.get("char_name", "hero").replace(" ", "_").lower()
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={char_name_clean}_sheet.pdf"},
    )


@router.post("/import-pdf", response_model=CharacterSchema)
async def import_pdf(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a PDF.",
        )

    contents = await file.read()
    file_io = io.BytesIO(contents)
    sheet_text = extract_text_and_fields_from_pdf(file_io)

    if not sheet_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract text from PDF.",
        )

    parsed_char = parse_character_from_text(sheet_text)
    if not parsed_char:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse character data from PDF text.",
        )
    parsed_char["owner_id"] = current_user["id"]
    parsed_char = process_character_update(parsed_char)
    return CharacterSchema.model_validate(parsed_char, strict=False)
