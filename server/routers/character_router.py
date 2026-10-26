import io
import json
import logging
import os
import re
import urllib.parse
import uuid
from functools import partial
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from backend.core.schemas import CharacterSchema, SuccessResponseSchema
from backend.services.character_import_service import (
    CharacterImportService,
    DndBeyondImportError,
    DndBeyondInvalidUrlError,
    DndBeyondNotFoundError,
    DndBeyondPrivateError,
    DndBeyondUpstreamError,
)
from backend.services.forge_service import process_character_update
from backend.services.homebrew_service import HomebrewService
from backend.services.rules_service import parse_character_from_text
from backend.utils.image_utils import PORTRAIT_DIR, _secure_filename
from backend.utils.import_utils import FoundryImportError, import_vtt_character
from backend.utils.path_safety import safe_path
from backend.utils.pdf_exporter import export_character_to_pdf
from backend.utils.pdf_importer import (
    PDFPageLimitExceededError,
    extract_text_and_fields_from_pdf,
)
from server.config import settings
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.rate_limiter import limiter

homebrew_service = HomebrewService()


router = APIRouter(prefix="/characters", tags=["Characters"])
logger = logging.getLogger("PhyrexianForge.CharacterRouter")


class ImportCharacterResponse(CharacterSchema):
    warnings: List[str] = Field(default_factory=list)


class DndBeyondImportRequest(BaseModel):
    url_or_id: str


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


async def _save_owned_character(db: AsyncIOMotorDatabase, char_dict: dict, owner_id: str) -> None:
    """
    Upserts a character that belongs to ``owner_id``.

    The filter includes ``owner_id`` so a char_id owned by somebody else never matches
    (and is therefore never overwritten). In that case the upsert tries to insert, and
    the unique index on ``char_id`` rejects it, which is what closes the race between
    the ownership pre-check and the write.
    """
    try:
        await db["characters"].update_one(
            {"char_id": char_dict["char_id"], "owner_id": owner_id},
            {"$set": char_dict},
            upsert=True,
        )
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot overwrite a character owned by another user.",
        )


@router.post("", response_model=CharacterSchema, status_code=status.HTTP_201_CREATED)
async def create_character(
    char_in: CharacterSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    char_dict = char_in.model_dump()
    char_dict["owner_id"] = current_user["id"]

    if not char_dict.get("char_id"):
        char_dict["char_id"] = str(uuid.uuid4())
    else:
        existing = await db["characters"].find_one({"char_id": char_dict["char_id"]})
        if existing and existing.get("owner_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot overwrite a character owned by another user.",
            )

    homebrew_items = await _get_homebrew_for_character(db, char_dict.get("active_campaign"))

    # Ensure stats & derived properties are synchronized
    char_dict = await run_in_threadpool(
        partial(process_character_update, char_dict, homebrew_content=homebrew_items)
    )

    await _save_owned_character(db, char_dict, current_user["id"])
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
        partial(process_character_update, char_dict, homebrew_content=homebrew_items)
    )

    client_version = char_dict.get("version", 0)
    if existing.get("version", 0) > client_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict: Character was modified elsewhere. Please refresh.",
        )

    char_dict["version"] = client_version + 1

    result = await db["characters"].update_one(
        {"char_id": char_id, "owner_id": current_user["id"], "version": client_version},
        {"$set": char_dict},
    )
    if result.modified_count == 0 and result.matched_count == 0:
        # It means the version in the database is no longer client_version
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict: Character was modified concurrently during processing. Please refresh.",
        )

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
    if htype == "monster":
        raise HTTPException(
            status_code=400, detail="Monsters cannot be added to a character sheet."
        )
    if htype not in {"weapon", "item", "spell", "feat", "feature"}:
        raise HTTPException(status_code=400, detail=f"Unsupported homebrew type: {htype}")

    from backend.core.schemas import EquipmentItem, FeatureTrait, Weapon

    # Use CharacterSchema to structure
    char = CharacterSchema(**char_doc)

    if htype == "weapon":
        char.weapons.append(Weapon.model_validate(item_doc))
    elif htype == "item":
        char.equipment.append(EquipmentItem.model_validate(item_doc))
    elif htype == "spell":
        level = item_doc.get("level", 0)
        lvl_key = "cantrips" if level == 0 else f"level_{level}"
        spell_name = item_doc.get("name")
        if spell_name:
            if hasattr(char.spells, lvl_key):
                lvl_list = getattr(char.spells, lvl_key)
                if spell_name not in lvl_list:
                    lvl_list.append(spell_name)
            if spell_name not in char.prepared_spells:
                char.prepared_spells.append(spell_name)
    elif htype in ("feat", "feature"):
        default_name = "Unknown Feat" if htype == "feat" else "Unknown Feature"
        char.features_traits.append(
            FeatureTrait.model_validate(
                {
                    "name": item_doc.get("name", default_name),
                    "description": item_doc.get("description", ""),
                    "source": "Homebrew",
                }
            )
        )

    # Process updates (handles stats, max hp, etc.)
    char_dict = char.model_dump(by_alias=True)

    homebrew_items = await _get_homebrew_for_character(db, campaign_id)

    updated_char = await run_in_threadpool(
        partial(process_character_update, char_dict, homebrew_content=homebrew_items)
    )

    client_version = char_doc.get("version", 0)
    updated_char["version"] = client_version + 1

    result = await db["characters"].update_one(
        {"char_id": char_id, "owner_id": current_user["id"], "version": client_version},
        {"$set": updated_char},
    )
    if result.modified_count == 0 and result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict: Character was modified concurrently. Please refresh.",
        )

    return CharacterSchema.model_validate(updated_char, strict=False)


DEFAULT_PORTRAIT_NAMES = {
    "default.png",
    "default.jpg",
    "default.jpeg",
    "default.webp",
    "default_portrait.png",
    "default_portrait.jpg",
    "placeholder.png",
    "placeholder.jpg",
    "placeholder.webp",
    "anvil.png",
    "knight.png",
    "logo.png",
}


def _get_coll(db: AsyncIOMotorDatabase, name: str):
    """Safely retrieves a collection from db whether db is AsyncIOMotorDatabase or dict mock."""
    if isinstance(db, dict):
        return db.get(name)
    try:
        return db[name]
    except (KeyError, TypeError):
        return None


def _is_default_or_shared_asset_name(filename: str) -> bool:
    """Returns True if the filename corresponds to a default or shared template asset."""
    if not filename or filename == ".gitkeep":
        return True
    lower = filename.lower().strip()
    if lower in DEFAULT_PORTRAIT_NAMES:
        return True
    base_name, _ = os.path.splitext(lower)
    if base_name in {"default", "placeholder", "anvil", "knight", "logo"}:
        return True
    if base_name.startswith("default_") or base_name.startswith("placeholder_"):
        return True
    return False


async def _cleanup_character_portraits(
    db: AsyncIOMotorDatabase,
    char_id: str,
    char_portrait: Optional[str],
) -> None:
    """
    Cleans up any local portrait image files on disk associated with the character,
    ensuring shared assets (used by other characters) or default placeholder assets
    are not deleted.
    """
    safe_char_id = _secure_filename(char_id)
    candidate_filenames = set()

    # 1. From char_portrait field
    if char_portrait and isinstance(char_portrait, str):
        trimmed = char_portrait.strip()
        # Skip inline data URIs
        if not trimmed.startswith("data:"):
            parsed = urllib.parse.urlparse(trimmed)
            is_http = trimmed.startswith("http://") or trimmed.startswith("https://")
            path = parsed.path
            is_local = (
                not is_http
                or path.startswith(f"{settings.API_V1_STR}/portraits/")
                or path.startswith("/api/v1/portraits/")
                or "/portraits/" in path
            )
            if is_local and path:
                fname = os.path.basename(path)
                fname = _secure_filename(fname)
                if fname and not _is_default_or_shared_asset_name(fname):
                    candidate_filenames.add(fname)

    # 2. Standard safe_char_id.png
    if safe_char_id and not _is_default_or_shared_asset_name(f"{safe_char_id}.png"):
        candidate_filenames.add(f"{safe_char_id}.png")

    # 3. Any files on disk matching safe_char_id.* or safe_char_id_*.*
    if safe_char_id and os.path.exists(PORTRAIT_DIR) and os.path.isdir(PORTRAIT_DIR):
        try:
            for disk_file in os.listdir(PORTRAIT_DIR):
                if disk_file.startswith(f"{safe_char_id}.") or disk_file.startswith(
                    f"{safe_char_id}_"
                ):
                    if not _is_default_or_shared_asset_name(disk_file):
                        candidate_filenames.add(disk_file)
        except Exception as e:
            logger.warning("Error scanning portrait directory %s: %s", PORTRAIT_DIR, e)

    char_coll = _get_coll(db, "characters")

    # For each candidate, check if it's referenced by any OTHER character in the database
    for fname in candidate_filenames:
        try:
            if char_coll is not None:
                # Path-delimited regex so "hero.png" doesn't falsely match "test_hero.png"
                regex_pattern = rf"(^|[/\\]){re.escape(fname)}$"
                shared_count = await char_coll.count_documents(
                    {
                        "char_id": {"$ne": char_id},
                        "$or": [
                            {"char_portrait": fname},
                            {"char_portrait": f"{settings.API_V1_STR}/portraits/{fname}"},
                            {"char_portrait": f"data/portraits/{fname}"},
                            {"char_portrait": {"$regex": regex_pattern}},
                        ],
                    }
                )
                if shared_count > 0:
                    logger.info(
                        "Skipping portrait deletion for %s: shared by %d other character(s)",
                        fname,
                        shared_count,
                    )
                    continue

            # Ensure path is safely within the portraits directory
            full_path = safe_path(os.path.join(PORTRAIT_DIR, fname), scope="portraits")
            if os.path.exists(full_path) and os.path.isfile(full_path):
                os.remove(full_path)
                logger.info("Deleted character portrait: %s", full_path)
        except Exception as e:
            logger.warning("Failed to delete portrait %s for %s: %s", fname, char_id, e)


async def _cleanup_campaign_references(
    db: AsyncIOMotorDatabase,
    char_id: str,
    char: dict,
    owner_id: str,
) -> None:
    """
    Cascading cleanup of campaign party membership, VTT tokens, encounters,
    roll requests, and campaign membership records.
    """
    pattern = rf"(^|[_]){re.escape(char_id)}(\.json)?$"
    active_campaign = char.get("active_campaign")
    char_name = char.get("char_name")
    slug_name = char_name.lower().replace(" ", "_") if char_name else ""
    standard_filename = f"{slug_name}_{char_id}.json" if slug_name else f"{char_id}.json"

    camp_coll = _get_coll(db, "campaigns")
    enc_coll = _get_coll(db, "campaign_encounters")
    req_coll = _get_coll(db, "campaign_roll_requests")
    mem_coll = _get_coll(db, "campaign_members")
    char_coll = _get_coll(db, "characters")

    # 1. Locate all campaigns that reference this character in their party or active_campaign
    affected_campaigns = set()
    if active_campaign:
        affected_campaigns.add(active_campaign)

    if camp_coll is not None:
        try:
            campaign_query = {
                "$or": [
                    {"party": {"$regex": pattern}},
                    {"party": char_id},
                    {"party": f"{char_id}.json"},
                    {"party": standard_filename},
                ]
            }
            if active_campaign:
                campaign_query["$or"].append({"campaign_name": active_campaign})

            cursor = camp_coll.find(campaign_query)
            async for camp in cursor:
                camp_name = camp.get("campaign_name")
                if camp_name:
                    affected_campaigns.add(camp_name)
                party = camp.get("party") or []
                to_remove = [
                    item
                    for item in party
                    if item == char_id
                    or item == f"{char_id}.json"
                    or item == standard_filename
                    or item.endswith(f"_{char_id}.json")
                    or bool(re.search(pattern, item))
                ]
                if to_remove:
                    update_filter = (
                        {"_id": camp["_id"]} if "_id" in camp else {"campaign_name": camp_name}
                    )
                    await camp_coll.update_one(
                        update_filter,
                        {"$pull": {"party": {"$in": to_remove}}},
                    )
        except Exception as e:
            logger.warning("Error during campaign party cleanup for %s: %s", char_id, e)

        # 2. Blanket update to pull any remaining character ID references in party
        try:
            blanket_pull_targets = [char_id, f"{char_id}.json"]
            if standard_filename not in blanket_pull_targets:
                blanket_pull_targets.append(standard_filename)
            await camp_coll.update_many(
                {},
                {"$pull": {"party": {"$in": blanket_pull_targets}}},
            )
        except Exception as e:
            logger.warning("Error running blanket party update for %s: %s", char_id, e)

        # 3. Clean up VTT state tokens
        try:
            await camp_coll.update_many(
                {},
                {"$pull": {"vtt_state.tokens": {"id": char_id}}},
            )
        except Exception as e:
            logger.warning("Error removing VTT tokens for %s: %s", char_id, e)

    # 4. Clean up campaign encounters
    if enc_coll is not None:
        try:
            await enc_coll.update_many(
                {},
                {"$pull": {"combatants": {"char_id": char_id}}},
            )
            await enc_coll.update_many(
                {},
                {"$pull": {"combatants": {"id": char_id}}},
            )
            await enc_coll.update_many(
                {"activeCombatantId": char_id},
                {"$set": {"activeCombatantId": None}},
            )
        except Exception as e:
            logger.warning("Error removing combatants for %s: %s", char_id, e)

    # 5. Clean up pending campaign roll requests
    if req_coll is not None:
        try:
            await req_coll.delete_many(
                {
                    "$or": [
                        {"char_filename": {"$regex": pattern}},
                        {"char_filename": char_id},
                        {"char_filename": f"{char_id}.json"},
                        {"char_filename": standard_filename},
                    ]
                }
            )
        except Exception as e:
            logger.warning("Error deleting campaign roll requests for %s: %s", char_id, e)

    # 6. Reconcile campaign_members records
    if mem_coll is not None:
        # 6a. Any records explicitly pointing at character_id == char_id
        try:
            cursor_members = mem_coll.find({"character_id": char_id})
            async for member_doc in cursor_members:
                m_camp = member_doc.get("campaign_id")
                m_user = member_doc.get("user_id")
                if m_camp:
                    affected_campaigns.add(m_camp)
                filter_doc = (
                    {"_id": member_doc["_id"]}
                    if "_id" in member_doc
                    else {"campaign_id": m_camp, "user_id": m_user}
                )
                if member_doc.get("role") != "dm":
                    other_count = (
                        await char_coll.count_documents(
                            {
                                "owner_id": m_user,
                                "active_campaign": m_camp,
                                "char_id": {"$ne": char_id},
                            }
                        )
                        if char_coll is not None
                        else 0
                    )
                    if other_count == 0:
                        await mem_coll.delete_one(filter_doc)
                    else:
                        other_char = (
                            await char_coll.find_one(
                                {
                                    "owner_id": m_user,
                                    "active_campaign": m_camp,
                                    "char_id": {"$ne": char_id},
                                }
                            )
                            if char_coll is not None
                            else None
                        )
                        if other_char:
                            await mem_coll.update_one(
                                filter_doc,
                                {"$set": {"character_id": other_char["char_id"]}},
                            )
                        else:
                            await mem_coll.update_one(
                                filter_doc,
                                {"$set": {"character_id": None}},
                            )
                else:
                    # DM membership is preserved; character_id cleared
                    await mem_coll.update_one(
                        filter_doc,
                        {"$set": {"character_id": None}},
                    )
        except Exception as e:
            logger.warning("Error reconciling campaign_members character_id for %s: %s", char_id, e)

        # 6b. For the character's owner across all affected campaigns, clean up membership if they have no remaining characters
        try:
            for camp_name in list(affected_campaigns):
                member_doc = await mem_coll.find_one(
                    {
                        "campaign_id": camp_name,
                        "user_id": owner_id,
                    }
                )
                if member_doc and member_doc.get("role") != "dm":
                    other_count = (
                        await char_coll.count_documents(
                            {
                                "owner_id": owner_id,
                                "active_campaign": camp_name,
                                "char_id": {"$ne": char_id},
                            }
                        )
                        if char_coll is not None
                        else 0
                    )
                    filter_doc = (
                        {"_id": member_doc["_id"]}
                        if "_id" in member_doc
                        else {"campaign_id": camp_name, "user_id": owner_id}
                    )
                    if other_count == 0:
                        await mem_coll.delete_one(filter_doc)
                    elif not member_doc.get("character_id"):
                        other_char = (
                            await char_coll.find_one(
                                {
                                    "owner_id": owner_id,
                                    "active_campaign": camp_name,
                                    "char_id": {"$ne": char_id},
                                }
                            )
                            if char_coll is not None
                            else None
                        )
                        if other_char:
                            await mem_coll.update_one(
                                filter_doc,
                                {"$set": {"character_id": other_char["char_id"]}},
                            )
        except Exception as e:
            logger.warning(
                "Error reconciling campaign_members for affected campaigns %s: %s",
                affected_campaigns,
                e,
            )

    # 7. Broadcast websocket update to all affected campaigns
    try:
        from server.routers.websocket_router import manager

        for camp_name in affected_campaigns:
            await manager.broadcast(
                camp_name,
                {"type": "party_update", "payload": {"action": "removed", "char_id": char_id}},
            )
            if char_name:
                await manager.broadcast(
                    camp_name,
                    {
                        "type": "presence_update",
                        "payload": {"character": char_name, "status": "offline"},
                    },
                )
    except Exception as e:
        logger.warning("Error broadcasting websocket party update for %s: %s", char_id, e)


@router.delete("/{char_id}", response_model=SuccessResponseSchema)
async def delete_character(
    char_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    char_coll = _get_coll(db, "characters")
    if char_coll is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        )

    char = await char_coll.find_one({"char_id": char_id, "owner_id": current_user["id"]})
    if not char:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")

    result = await char_coll.delete_one({"char_id": char_id, "owner_id": current_user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")

    try:
        await _cleanup_character_portraits(db, char_id, char.get("char_portrait"))
    except Exception as e:
        logger.warning("Failed cascading portrait cleanup for %s: %s", char_id, e)

    try:
        await _cleanup_campaign_references(db, char_id, char, current_user["id"])
    except Exception as e:
        logger.warning("Failed cascading campaign cleanup for %s: %s", char_id, e)

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
        partial(process_character_update, char_dict, homebrew_content=homebrew_items)
    )

    pdf_bytes = await run_in_threadpool(
        export_character_to_pdf,
        char_dict,
        "data/pdf_mappings/5E_CharacterSheet_Fillable.pdf",
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


@router.post("/import-pdf", response_model=ImportCharacterResponse)
@limiter.limit("5/minute")
async def import_pdf(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a PDF.",
        )

    # Chunked read to enforce size limit before memory exhaustion
    total_bytes = 0
    buffer = io.BytesIO()
    while chunk := await file.read(1024 * 1024):
        total_bytes += len(chunk)
        if total_bytes > settings.MAX_PDF_IMPORT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"PDF file size exceeds maximum limit of {settings.MAX_PDF_IMPORT_BYTES // (1024 * 1024)} MB.",
            )
        buffer.write(chunk)

    buffer.seek(0)
    magic_bytes = buffer.read(5)
    if magic_bytes != b"%PDF-":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF file format (missing PDF header magic bytes).",
        )
    buffer.seek(0)

    try:
        sheet_text = await run_in_threadpool(
            extract_text_and_fields_from_pdf,
            buffer,
            max_pages=settings.MAX_PDF_IMPORT_PAGES,
        )
    except PDFPageLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not read PDF contents: {exc}",
        )

    if not sheet_text or not sheet_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract text from PDF.",
        )

    if len(sheet_text) > settings.MAX_PDF_TEXT_CHARS:
        logger.warning(
            "Extracted PDF sheet text (%d chars) exceeds MAX_PDF_TEXT_CHARS (%d); truncating.",
            len(sheet_text),
            settings.MAX_PDF_TEXT_CHARS,
        )
        sheet_text = sheet_text[: settings.MAX_PDF_TEXT_CHARS]

    parsed_char = await run_in_threadpool(parse_character_from_text, sheet_text)
    if not parsed_char:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse character data from PDF text.",
        )

    parsed_char["owner_id"] = current_user["id"]
    parsed_char["user_id"] = current_user["id"]
    parsed_char.setdefault("race", "Unknown")
    parsed_char.setdefault("background", "Unknown")
    parsed_char.setdefault("alignment", "Neutral")
    # Always assign fresh UUID for imported character to avoid collisions/overwrites
    parsed_char["char_id"] = str(uuid.uuid4())

    homebrew_items = await _get_homebrew_for_character(db, parsed_char.get("active_campaign"))
    parsed_char = await run_in_threadpool(
        partial(process_character_update, parsed_char, homebrew_content=homebrew_items)
    )
    await _save_owned_character(db, parsed_char, current_user["id"])
    return ImportCharacterResponse(**parsed_char, warnings=[])


@router.post("/import-dndbeyond", response_model=ImportCharacterResponse)
@limiter.limit(settings.DNDBEYOND_IMPORT_RATE_LIMIT)
async def import_dndbeyond(
    request: Request,
    payload: DndBeyondImportRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    try:
        ddb_data = await CharacterImportService.fetch_dndbeyond_character(payload.url_or_id)
        char_dict, warnings = CharacterImportService.parse_dndbeyond_character(ddb_data)
        saved_char = await CharacterImportService.finalize_and_save_imported_character(
            char_dict, current_user["id"], db, sync_stats=True
        )
        return ImportCharacterResponse(**saved_char.model_dump(), warnings=warnings)
    except DndBeyondInvalidUrlError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except DndBeyondPrivateError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except DndBeyondNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except DndBeyondUpstreamError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )
    except DndBeyondImportError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to import character from D&D Beyond: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while importing from D&D Beyond: {str(e)}",
        )


@router.post("/import-foundry", response_model=ImportCharacterResponse)
@limiter.limit("10/minute")
async def import_foundry(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    if not (file.filename or "").lower().endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a JSON file.",
        )

    total_bytes = 0
    buffer = io.BytesIO()
    while chunk := await file.read(1024 * 1024):
        total_bytes += len(chunk)
        if total_bytes > settings.MAX_FOUNDRY_IMPORT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Foundry export exceeds maximum limit of {settings.MAX_FOUNDRY_IMPORT_BYTES // (1024 * 1024)} MB.",
            )
        buffer.write(chunk)

    try:
        buffer.seek(0)
        vtt_data = json.loads(buffer.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file contains invalid JSON: {exc}",
        )

    try:
        char_dict, warnings = import_vtt_character(vtt_data)
        saved_char = await CharacterImportService.finalize_and_save_imported_character(
            char_dict, current_user["id"], db, sync_stats=True
        )
        return ImportCharacterResponse(**saved_char.model_dump(), warnings=warnings)
    except FoundryImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Failed to import Foundry character: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while importing Foundry character: {str(exc)}",
        )
