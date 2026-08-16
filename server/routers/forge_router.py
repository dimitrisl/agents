from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from backend.core.schemas import (
    CharacterSchema,
    LevelUpAnalysisSchema,
    PlaystyleGuideResponse,
    PortraitResponse,
)
from backend.services.forge_service import (
    analyze_level_up,
    forge_character,
    forge_character_manual,
    generate_playstyle_guide,
)
from backend.utils.image_utils import generate_portrait_url
from server.db_async import get_database
from server.dependencies.auth import get_current_user

router = APIRouter(prefix="/forge", tags=["Forge (AI)"])


class ForgeCharacterRequest(BaseModel):
    target_level: int = 1
    race: str = "AI Choice"
    char_class: str = "AI Choice"
    background: str = "AI Choice"
    concept: str
    name: str = "AI Choice"
    gender: str = "AI Choice"
    stats_mode: str = "standard"
    alignment: str = "AI Choice"
    edition: str = "2014 Edition"
    subclass: Optional[str] = None
    custom_preferences: Optional[str] = None
    auto_spells: bool = True
    auto_feats: bool = True


class ManualEnrichRequest(BaseModel):
    target_level: int = 1
    race: str
    char_class: str
    background: str
    subclass: Optional[str] = ""
    alignment: str = "Neutral"
    gender: str = "Unknown"
    name: str
    base_stats: Dict[str, int]
    skill_proficiencies: list = []
    saving_throws: list = []
    spell_ability: Optional[str] = None
    concept: str = ""
    edition: str = "2014 Edition"
    custom_preferences: Optional[str] = None
    auto_spells: bool = True
    auto_feats: bool = True


class LevelUpRequest(BaseModel):
    character: CharacterSchema
    user_choices: Optional[Dict[str, Any]] = None


class PortraitRequest(BaseModel):
    char_id: str
    force: bool = False
    character_data: Optional[Dict[str, Any]] = None


@router.post("/generate", response_model=CharacterSchema)
async def generate_forge_character(
    payload: ForgeCharacterRequest, current_user: dict = Depends(get_current_user)
):
    char_dict = forge_character(
        target_level=payload.target_level,
        forge_race=payload.race,
        forge_class=payload.char_class,
        forge_background=payload.background,
        concept=payload.concept,
        name=payload.name,
        gender=payload.gender,
        stats_mode=payload.stats_mode,
        alignment=payload.alignment,
        edition=payload.edition,
        subclass=payload.subclass,
        custom_preferences=payload.custom_preferences,
        auto_spells=payload.auto_spells,
        auto_feats=payload.auto_feats,
    )
    if not char_dict:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to forge character with Gemini AI",
        )
    char_dict["owner_id"] = current_user["id"]
    return CharacterSchema.model_validate(char_dict, strict=False)


@router.post("/enrich-manual", response_model=CharacterSchema)
async def enrich_manual_character(
    payload: ManualEnrichRequest, current_user: dict = Depends(get_current_user)
):
    char_dict = forge_character_manual(
        target_level=payload.target_level,
        race=payload.race,
        char_class=payload.char_class,
        background=payload.background,
        subclass=payload.subclass,
        alignment=payload.alignment,
        gender=payload.gender,
        name=payload.name,
        base_stats=payload.base_stats,
        skill_proficiencies=payload.skill_proficiencies,
        saving_throws=payload.saving_throws,
        spell_ability=payload.spell_ability,
        concept=payload.concept,
        edition=payload.edition,
        custom_preferences=payload.custom_preferences,
        auto_spells=payload.auto_spells,
        auto_feats=payload.auto_feats,
    )
    if not char_dict:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enrich character",
        )
    char_dict["owner_id"] = current_user["id"]
    return CharacterSchema.model_validate(char_dict, strict=False)


@router.post("/level-up-analysis", response_model=LevelUpAnalysisSchema)
async def get_level_up_analysis(
    payload: LevelUpRequest, current_user: dict = Depends(get_current_user)
):
    char_data = payload.character.model_dump()
    analysis = analyze_level_up(char_data, payload.user_choices)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze level up options",
        )
    return LevelUpAnalysisSchema.model_validate(analysis, strict=False)


@router.post("/playstyle-guide", response_model=PlaystyleGuideResponse)
async def get_playstyle_guide(
    character: CharacterSchema, current_user: dict = Depends(get_current_user)
):
    char_data = character.model_dump()
    guide_text = generate_playstyle_guide(char_data)
    return {"guide_markdown": guide_text}


@router.post("/portrait", response_model=PortraitResponse)
async def generate_ai_portrait(
    payload: PortraitRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await db["characters"].find_one(
        {"char_id": payload.char_id, "owner_id": current_user["id"]}
    )
    if doc:
        char_dict = CharacterSchema.model_validate(doc, strict=False).model_dump()
    else:
        char_dict = payload.character_data or {"char_id": payload.char_id}

    portrait_url = await generate_portrait_url(char_dict, force=payload.force)

    if doc and portrait_url:
        char_dict["char_portrait"] = portrait_url
        await db["characters"].update_one(
            {"char_id": payload.char_id}, {"$set": {"char_portrait": portrait_url}}
        )

    return {"success": bool(portrait_url), "portrait_url": portrait_url or ""}
