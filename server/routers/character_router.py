import io
import logging
import os
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from backend.core.schemas import CharacterSchema, SuccessResponseSchema
from backend.services.forge_service import process_character_update
from backend.services.homebrew_service import HomebrewService
from backend.services.rules_service import parse_character_from_text
from backend.utils.pdf_exporter import export_character_to_pdf
from backend.utils.pdf_importer import extract_text_and_fields_from_pdf
from server.db_async import get_database
from server.dependencies.auth import get_current_user

homebrew_service = HomebrewService()


router = APIRouter(prefix="/characters", tags=["Characters"])
logger = logging.getLogger("PhyrexianForge.CharacterRouter")


class UnreadableCharacterSchema(BaseModel):
    char_id: Optional[str] = None
    char_name: Optional[str] = None
    reason: str


class CharacterListResponse(BaseModel):
    characters: List[CharacterSchema]
    unreadable: List[UnreadableCharacterSchema]


@router.get("", response_model=CharacterListResponse)
async def list_characters(
    current_user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_database)
):
    cursor = db["characters"].find({"owner_id": current_user["id"]})
    characters = []
    unreadable = []
    async for doc in cursor:
        doc.pop("_id", None)
        try:
            characters.append(CharacterSchema.model_validate(doc, strict=False))
        except Exception as e:
            logger.warning("Skipping legacy character %s: %s", doc.get("char_name", "Unknown"), e)
            unreadable.append(
                UnreadableCharacterSchema(
                    char_id=doc.get("char_id"),
                    char_name=doc.get("char_name", "Unknown"),
                    reason=str(e),
                )
            )
    return CharacterListResponse(characters=characters, unreadable=unreadable)


async def _get_homebrew_for_character(db: AsyncIOMotorDatabase, campaign_id: str) -> list:
    homebrew_items = []
    if campaign_id:
        cursor = db["homebrew_content"].find({"campaign_id": campaign_id})
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            homebrew_items.append(doc)
    return homebrew_items


@router.post("", response_model=CharacterSchema, status_code=status.HTTP_201_CREATED)
async def create_character(
    char_in: CharacterSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    char_dict = char_in.model_dump()
    char_dict["owner_id"] = current_user["id"]

    homebrew_items = await _get_homebrew_for_character(db, char_dict.get("active_campaign"))

    # Ensure stats & derived properties are synchronized
    char_dict = await run_in_threadpool(
        process_character_update, char_dict, None, None, None, homebrew_items
    )

    await db["characters"].update_one(
        {"char_id": char_dict["char_id"]}, {"$set": char_dict}, upsert=True
    )
    return CharacterSchema.model_validate(char_dict, strict=False)


@router.get("/{char_id}", response_model=CharacterSchema)
async def get_character(
    char_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
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
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    existing = await db["characters"].find_one({"char_id": char_id, "owner_id": current_user["id"]})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")

    char_dict = char_in.model_dump()
    char_dict["char_id"] = char_id
    char_dict["owner_id"] = current_user["id"]

    homebrew_items = await _get_homebrew_for_character(db, char_dict.get("active_campaign"))

    # Re-calculate and sync stats using threadpool to prevent blocking the async event loop
    char_dict = await run_in_threadpool(
        process_character_update, char_dict, None, None, None, homebrew_items
    )

    await db["characters"].update_one({"char_id": char_id}, {"$set": char_dict})

    return CharacterSchema.model_validate(char_dict, strict=False)


@router.post("/{char_id}/homebrew/{item_id}", response_model=CharacterSchema)
async def add_homebrew_to_character(
    char_id: str,
    item_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    char_doc = await db["characters"].find_one({"char_id": char_id, "owner_id": current_user["id"]})
    if not char_doc:
        raise HTTPException(status_code=404, detail="Character not found")

    campaign_id = char_doc.get("active_campaign")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="Character is not in an active campaign")

    item_doc = await homebrew_service.get_homebrew_item(db, item_id, campaign_id)
    if not item_doc:
        raise HTTPException(status_code=404, detail="Homebrew item not found in this campaign")

    # Add to character based on type
    htype = item_doc.get("homebrew_type")

    # Use CharacterSchema to structure
    char = CharacterSchema(**char_doc)

    if htype == "weapon":
        char.weapons.append(item_doc)
    elif htype == "item":
        char.equipment.append(item_doc)
    elif htype == "spell":
        # Add to known spells based on level? Or just a generic list?
        # For now, put it in equipment to at least show it, or features.
        # Actually spells go to the spellbook, but `spell_list` is complex.
        # Let's add it to prepared_spells and spell lists.
        level = item_doc.get("level", 0)
        lvl_key = "cantrips" if level == 0 else f"level_{level}"
        if hasattr(char.spells, lvl_key):
            getattr(char.spells, lvl_key).append(item_doc.get("name"))
        char.prepared_spells.append(item_doc.get("name"))
    elif htype == "feat":
        item_doc["source"] = "Homebrew"
        item_doc["name"] = item_doc.get("name", "Unknown Feat")
        item_doc["description"] = item_doc.get("description", "")
        char.features_traits.append(item_doc)
    elif htype == "feature":
        item_doc["source"] = "Homebrew"
        item_doc["name"] = item_doc.get("name", "Unknown Feature")
        item_doc["description"] = item_doc.get("description", "")
        char.features_traits.append(item_doc)

    # Process updates (handles stats, max hp, etc.)
    char_dict = char.model_dump(by_alias=True)

    homebrew_items = await _get_homebrew_for_character(db, campaign_id)

    updated_char = await run_in_threadpool(
        process_character_update, char_dict, None, None, None, homebrew_items
    )
    await db["characters"].update_one({"char_id": char_id}, {"$set": updated_char})

    return CharacterSchema.model_validate(updated_char, strict=False)


@router.delete("/{char_id}", response_model=SuccessResponseSchema)
async def delete_character(
    char_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
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


@router.post("/{char_id}/export-pdf", response_class=StreamingResponse)
async def export_pdf(
    char_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await db["characters"].find_one({"char_id": char_id, "owner_id": current_user["id"]})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    doc.pop("_id", None)
    char_dict = CharacterSchema.model_validate(doc, strict=False).model_dump()
    homebrew_items = await _get_homebrew_for_character(db, char_dict.get("active_campaign"))
    char_dict = await run_in_threadpool(
        process_character_update, char_dict, None, None, None, homebrew_items
    )

    pdf_bytes = export_character_to_pdf(
        char_dict, "data/pdf_mappings/5E_CharacterSheet_Fillable.pdf"
    )
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
async def import_pdf(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
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

    # Assign a new unique char_id for imported characters if they don't have one
    import uuid

    if not parsed_char.get("char_id"):
        parsed_char["char_id"] = str(uuid.uuid4())

    homebrew_items = await _get_homebrew_for_character(db, parsed_char.get("active_campaign"))
    parsed_char = await run_in_threadpool(
        process_character_update, parsed_char, None, None, None, homebrew_items
    )
    await db["characters"].update_one(
        {"char_id": parsed_char["char_id"]}, {"$set": parsed_char}, upsert=True
    )
    return CharacterSchema.model_validate(parsed_char, strict=False)
