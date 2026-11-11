"""
Unified Bestiary REST API Router.

Provides search, retrieval, creation, cloning, updating, visibility toggling,
and deletion of monsters across static official SRD knowledge bases and
MongoDB custom DM monsters. Enforces strict read-only immutability on official SRD
records (srd_* IDs) and DM ownership checks on custom monsters.
"""

import datetime
import functools
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.schemas import (
    BestiaryCreateRequest,
    BestiaryDeleteResponse,
    BestiaryUpdateRequest,
    BestiaryVisibilityRequest,
    BestiaryVisibilityResponse,
    Monster,
)
from backend.repositories.rules_repository import RulesRepository
from server.db_async import get_database
from server.dependencies.auth import get_current_user

logger = logging.getLogger("PhyrexianForge.BestiaryRouter")

router = APIRouter(prefix="/bestiary", tags=["Bestiary"])


@functools.lru_cache(maxsize=1)
def get_rules_repo() -> RulesRepository:
    """Cached singleton provider for RulesRepository."""
    return RulesRepository()


def _is_safe_id(monster_id: str) -> bool:
    """Validates that monster ID does not contain path traversal characters."""
    if not monster_id or not isinstance(monster_id, str):
        return False
    if ".." in monster_id or "/" in monster_id or "\\" in monster_id:
        return False
    return True


@router.get("", response_model=List[Monster])
async def list_monsters(
    edition: Optional[str] = Query(
        None, description="Edition filter ('2014', '2024', or None for all)"
    ),
    search: Optional[str] = Query(
        None, description="Case-insensitive search string in name, type, or description"
    ),
    cr: Optional[str] = Query(None, description="Challenge rating filter (e.g. '0', '1/4', '5')"),
    monster_type: Optional[str] = Query(
        None, description="Creature type filter (e.g. 'dragon', 'humanoid')"
    ),
    include_official: bool = Query(True, description="Whether to include official SRD monsters"),
    include_mine: bool = Query(
        True, description="Whether to include custom monsters owned by current user"
    ),
    include_community: bool = Query(
        False, description="Whether to include public custom monsters from other users"
    ),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[Monster]:
    """Search and query Unified Bestiary monsters across official SRD rules and MongoDB custom monsters.

    Requires user authentication.
    """
    # 1. Early return if all sources are disabled
    if not include_official and not include_mine and not include_community:
        return []

    combined_results: List[dict] = []
    repo = get_rules_repo()

    # 2. Official Monsters (MongoDB `official_monsters` or fallback to RulesRepository)
    if include_official:
        mongo_official_count = await db["official_monsters"].count_documents({})
        if mongo_official_count > 0:
            query_off: Dict[str, Any] = {}
            if edition:
                query_off["edition"] = edition
            if monster_type:
                query_off["type"] = {"$regex": re.escape(monster_type), "$options": "i"}
            if cr:
                query_off["cr"] = str(cr).strip()
            if search and search.strip():
                query_off["name"] = {"$regex": re.escape(search.strip()), "$options": "i"}

            cursor_off = db["official_monsters"].find(query_off)
            docs_off = await cursor_off.to_list(5000)
            for doc in docs_off:
                doc.pop("_id", None)
            combined_results.extend(docs_off)
        else:
            official_monsters = repo.search_monsters(
                query=search or "",
                edition=edition,
                cr=cr,
                monster_type=monster_type,
            )
            if search:
                clean_search = search.strip().lower()
                official_monsters = [
                    m for m in official_monsters if clean_search in str(m.get("name", "")).lower()
                ]
            combined_results.extend(official_monsters)

    # 3. Custom Monsters from MongoDB
    if include_mine or include_community:
        user_id = current_user.get("id")
        and_clauses: List[Dict[str, Any]] = []

        # Ownership & Visibility clause
        if include_mine and include_community:
            and_clauses.append(
                {
                    "$or": [
                        {"creator_dm_id": user_id},
                        {"is_public": True},
                    ]
                }
            )
        elif include_mine:
            and_clauses.append({"creator_dm_id": user_id})
        elif include_community:
            and_clauses.append(
                {
                    "is_public": True,
                    "creator_dm_id": {"$ne": user_id},
                }
            )

        # Edition Filter
        if edition is not None and str(edition).strip().lower() not in ("", "all"):
            norm_ed = "2024" if "2024" in str(edition) else "2014"
            and_clauses.append({"edition": {"$regex": norm_ed, "$options": "i"}})

        # CR Filter (string match or float numeric tolerance)
        if cr is not None and str(cr).strip() != "":
            target_cr_str = str(cr).strip()
            target_cr_num = RulesRepository._parse_cr_numeric(target_cr_str)
            and_clauses.append(
                {
                    "$or": [
                        {"cr": target_cr_str},
                        {
                            "cr_numeric": {
                                "$gte": target_cr_num - 1e-4,
                                "$lte": target_cr_num + 1e-4,
                            }
                        },
                    ]
                }
            )

        # Monster Type Filter
        if monster_type is not None and str(monster_type).strip() != "":
            safe_type = re.escape(str(monster_type).strip())
            and_clauses.append({"type": {"$regex": safe_type, "$options": "i"}})

        # Search Query Filter (name matching)
        if search is not None and str(search).strip() != "":
            safe_search = re.escape(str(search).strip())
            and_clauses.append({"name": {"$regex": safe_search, "$options": "i"}})

        query = {"$and": and_clauses} if and_clauses else {}
        cursor = db["custom_monsters"].find(query)
        async for doc in cursor:
            doc.pop("_id", None)
            combined_results.append(doc)

    # 4. Validate and sort
    validated_monsters: List[Monster] = []
    for item in combined_results:
        try:
            validated_monsters.append(Monster.model_validate(item))
        except Exception as e:
            logger.warning("Skipping invalid monster record %s: %s", item.get("id"), e)

    # Deterministic sort: by cr_numeric ascending, then name ascending
    validated_monsters.sort(key=lambda m: (float(m.cr_numeric or 0.0), (m.name or "").lower()))
    return validated_monsters


@router.get("/{id}", response_model=Monster)
async def get_monster(
    id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Monster:
    """Retrieve single monster by ID.

    - Official SRD monsters (srd_*) are loaded from RulesRepository.
    - Custom monsters are loaded from MongoDB custom_monsters.
    - Private custom monsters return HTTP 403 Forbidden to non-owner users.
    - Non-existent IDs return HTTP 404 Not Found.
    """
    if not _is_safe_id(id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invalid monster ID format: '{id}'",
        )

    # 1. Official monster lookup (check MongoDB first, then RulesRepository fallback)
    if id.startswith("srd_"):
        doc_off = await db["official_monsters"].find_one({"id": id})
        if doc_off:
            doc_off.pop("_id", None)
            return Monster.model_validate(doc_off)

        repo = get_rules_repo()
        monster = repo.get_monster_by_id(id)
        if monster is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Official SRD monster '{id}' not found",
            )
        return Monster.model_validate(monster)

    # 2. Custom monster lookup in MongoDB
    doc = await db["custom_monsters"].find_one({"id": id})
    if doc is None:
        # Fallback check if caller queried an official monster without the 'srd_' prefix
        repo = get_rules_repo()
        monster = repo.get_monster_by_id(id)
        if monster is not None and str(monster.get("id", "")).startswith("srd_"):
            return Monster.model_validate(monster)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monster '{id}' not found",
        )

    # 3. Privacy Access Control Check
    is_public = bool(doc.get("is_public", False))
    creator_id = doc.get("creator_dm_id")
    user_id = current_user.get("id")

    if not is_public and creator_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this private custom monster.",
        )

    doc.pop("_id", None)
    return Monster.model_validate(doc)


@router.post("", response_model=Monster, status_code=status.HTTP_201_CREATED)
async def create_or_clone_monster(
    payload: BestiaryCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Monster:
    """Create a new custom monster or clone an existing monster via based_on.

    Assigns a unique ID, enforces origin="custom", and sets
    creator_dm_id=current_user["id"].
    """
    user_id = current_user.get("id")
    monster_dict = payload.model_dump()

    # Assign unique custom monster ID
    monster_id = str(uuid.uuid4())
    monster_dict["id"] = monster_id

    # Strictly enforce security ownership and origin invariants
    monster_dict["creator_dm_id"] = user_id
    monster_dict["origin"] = "custom"

    # Derive cr_numeric from cr expression if missing
    if monster_dict.get("cr_numeric") is None:
        monster_dict["cr_numeric"] = RulesRepository._parse_cr_numeric(monster_dict.get("cr", "0"))

    # Set max_hp default if missing or zero
    if monster_dict.get("max_hp") is None or monster_dict.get("max_hp") <= 0:
        monster_dict["max_hp"] = monster_dict.get("hp", 10)

    # Retain based_on reference if cloning
    if payload.based_on:
        monster_dict["based_on"] = payload.based_on.strip()

    # Set ISO timestamps
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    monster_dict["created_at"] = now_iso
    monster_dict["updated_at"] = now_iso

    # Validate against canonical Monster schema before inserting
    validated = Monster.model_validate(monster_dict)
    insert_data = validated.model_dump(mode="python")

    await db["custom_monsters"].insert_one(insert_data)
    insert_data.pop("_id", None)

    return Monster.model_validate(insert_data)


@router.put("/{id}", response_model=Monster)
async def update_monster(
    id: str,
    payload: BestiaryUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Monster:
    """Update an existing custom monster owned by the authenticated DM.

    - Rejects official SRD records (srd_*) with HTTP 403 Forbidden.
    - Rejects modifications by non-owners with HTTP 403 Forbidden.
    - Returns HTTP 404 Not Found if custom monster does not exist.
    """
    # 1. Immutability check on official SRD monsters
    if id.startswith("srd_"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Official SRD monsters are read-only and cannot be modified.",
        )

    # 2. Lookup existing custom monster
    existing = await db["custom_monsters"].find_one({"id": id})
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custom monster '{id}' not found",
        )

    # 3. Ownership check
    user_id = current_user.get("id")
    if existing.get("creator_dm_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this monster.",
        )

    # 4. Prepare update document
    update_data = payload.model_dump(exclude_unset=True)

    # Strip immutable identifier fields
    update_data.pop("id", None)
    update_data.pop("creator_dm_id", None)
    update_data.pop("origin", None)
    update_data.pop("_id", None)

    # Sync cr_numeric if cr was modified
    if "cr" in update_data and "cr_numeric" not in update_data:
        update_data["cr_numeric"] = RulesRepository._parse_cr_numeric(update_data["cr"])

    # Update timestamp
    update_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if update_data:
        await db["custom_monsters"].update_one({"id": id}, {"$set": update_data})

    updated_doc = await db["custom_monsters"].find_one({"id": id})
    if updated_doc:
        updated_doc.pop("_id", None)
    return Monster.model_validate(updated_doc)


@router.patch("/{id}/visibility", response_model=BestiaryVisibilityResponse)
async def update_monster_visibility(
    id: str,
    payload: BestiaryVisibilityRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> BestiaryVisibilityResponse:
    """Toggle community visibility (is_public) for a custom monster.

    - Rejects official SRD records with HTTP 403 Forbidden.
    - Rejects requests by non-owners with HTTP 403 Forbidden.
    - Returns HTTP 404 Not Found if custom monster does not exist.
    """
    # 1. Immutability check on official SRD monsters
    if id.startswith("srd_"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Official SRD monsters are read-only and visibility cannot be changed.",
        )

    # 2. Lookup existing custom monster
    existing = await db["custom_monsters"].find_one({"id": id})
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custom monster '{id}' not found",
        )

    # 3. Ownership check
    user_id = current_user.get("id")
    if existing.get("creator_dm_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this monster.",
        )

    # 4. Update visibility
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await db["custom_monsters"].update_one(
        {"id": id},
        {"$set": {"is_public": payload.is_public, "updated_at": now_iso}},
    )

    return BestiaryVisibilityResponse(success=True, is_public=payload.is_public)


@router.delete("/{id}", response_model=BestiaryDeleteResponse)
async def delete_monster(
    id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> BestiaryDeleteResponse:
    """Delete a custom monster owned by the authenticated DM.

    - Rejects official SRD records (srd_*) with HTTP 403 Forbidden.
    - Rejects requests by non-owners with HTTP 403 Forbidden.
    - Returns HTTP 404 Not Found if custom monster does not exist.
    """
    # 1. Immutability check on official SRD monsters
    if id.startswith("srd_"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Official SRD monsters are read-only and cannot be deleted.",
        )

    # 2. Lookup existing custom monster
    existing = await db["custom_monsters"].find_one({"id": id})
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custom monster '{id}' not found",
        )

    # 3. Ownership check
    user_id = current_user.get("id")
    if existing.get("creator_dm_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this monster.",
        )

    # 4. Delete document
    await db["custom_monsters"].delete_one({"id": id})

    return BestiaryDeleteResponse(success=True, message="Monster deleted")
