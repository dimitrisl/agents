import io
import os
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from backend.core.schemas import CharacterSchema
from backend.services.forge_service import process_character_update
from backend.services.rules_service import parse_character_from_text
from backend.utils.pdf_exporter import export_character_to_pdf
from backend.utils.pdf_importer import extract_text_and_fields_from_pdf
from server.db_async import get_database
from server.dependencies.auth import get_current_user

router = APIRouter(prefix="/characters", tags=["Characters"])


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
            print(f"Failed to load legacy character {doc.get('char_name', 'Unknown')}: {e}")
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

    # Re-calculate and sync stats
    char_dict = process_character_update(char_dict)

    await db["characters"].update_one({"char_id": char_id}, {"$set": char_dict})
    return CharacterSchema.model_validate(char_dict, strict=False)


@router.delete("/{char_id}")
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
        except Exception:
            pass

    return {"success": True, "message": f"Character {char_id} deleted."}


@router.post("/{char_id}/export-pdf")
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
    return CharacterSchema.model_validate(parsed_char, strict=False)
