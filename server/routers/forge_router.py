from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from backend.core.schemas import (
    CharacterSchema,
    LevelUpAnalysisSchema,
    LevelUpApplyRequest,
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


@router.post("/level-up-apply", response_model=CharacterSchema)
async def apply_level_up(
    payload: LevelUpApplyRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    char_doc = await db["characters"].find_one(
        {"char_id": payload.character_id, "owner_id": current_user["id"]}
    )
    if not char_doc:
        raise HTTPException(status_code=404, detail="Character not found or access denied")

    # Increment level
    char_doc["char_level"] = char_doc.get("char_level", 1) + 1

    # Update HP
    char_doc["hp_max"] = payload.analysis.new_total_hp
    char_doc["hp_current"] = payload.analysis.new_total_hp  # heal on level up

    # Append automatic features
    existing_features = {
        f.get("name") for f in char_doc.get("features_traits", []) if isinstance(f, dict)
    }
    for feature in payload.analysis.automatic_changes:
        if feature.name not in existing_features:
            char_doc.setdefault("features_traits", []).append(feature.model_dump())
            existing_features.add(feature.name)

    # Process user choices (Subclass, etc)
    if payload.user_choices:
        for choice_key, choice_val in payload.user_choices.items():
            if (
                not choice_val
                or choice_key == "custom_hp_increase"
                or "_stat1_" in choice_key
                or "_stat2_" in choice_key
            ):
                continue

            # choice_key is now something like "subclass_0", "spell_1", "other_2"
            base_type = choice_key.rsplit("_", 1)[0] if "_" in choice_key else choice_key

            if base_type == "subclass":
                char_doc["subclass"] = choice_val
                continue

            # Check the type of choice from the analysis to know how to apply it
            choice_type = base_type
            choice_label = choice_key

            # Extract index if present to get the exact label
            if "_" in choice_key:
                try:
                    idx = int(choice_key.rsplit("_", 1)[1])
                    if idx < len(payload.analysis.choices_required):
                        req = payload.analysis.choices_required[idx]
                        choice_label = req.label
                except ValueError:
                    pass

            if choice_type == "spell" or "spell" in choice_label.lower():
                from backend.repositories.rules_repository import RulesRepository

                rules_repo = RulesRepository()
                edition = char_doc.get("dnd_edition", "2014 Edition")
                all_spells = rules_repo.get_all_spells(edition)

                spell_level = next(
                    (s.get("level") for s in all_spells if s.get("name") == choice_val), None
                )
                spells_dict = char_doc.setdefault("spells", {})

                target_list = None
                if spell_level == 0 or spell_level is None:
                    target_list = spells_dict.setdefault("cantrips", [])
                else:
                    target_list = spells_dict.setdefault(f"level_{spell_level}", [])

                if choice_val not in target_list:
                    target_list.append(choice_val)
            elif choice_type == "feat" or "feat" in choice_label.lower():
                if choice_val == "+2 to one Stat":
                    # Reconstruct the stat keys (e.g. feat_stat1_0)
                    parts = choice_key.rsplit("_", 1)
                    idx_suffix = f"_{parts[1]}" if len(parts) > 1 else ""
                    base = parts[0] if len(parts) > 1 else choice_key
                    stat1_key = f"{base}_stat1{idx_suffix}"

                    stat1 = payload.user_choices.get(stat1_key)
                    if stat1 and stat1 in char_doc.get("stats", {}):
                        char_doc["stats"][stat1] += 2
                elif choice_val == "+1 to two Stats":
                    parts = choice_key.rsplit("_", 1)
                    idx_suffix = f"_{parts[1]}" if len(parts) > 1 else ""
                    base = parts[0] if len(parts) > 1 else choice_key
                    stat1_key = f"{base}_stat1{idx_suffix}"
                    stat2_key = f"{base}_stat2{idx_suffix}"

                    stat1 = payload.user_choices.get(stat1_key)
                    stat2 = payload.user_choices.get(stat2_key)
                    if stat1 and stat1 in char_doc.get("stats", {}):
                        char_doc["stats"][stat1] += 1
                    if stat2 and stat2 in char_doc.get("stats", {}):
                        char_doc["stats"][stat2] += 1
                else:
                    char_doc.setdefault("features_traits", []).append(
                        {"name": choice_val, "description": "Selected via Level Up."}
                    )
            elif "expertise" in choice_label.lower():
                char_doc.setdefault("skill_expertise", []).append(choice_val)
            elif "skill" in choice_label.lower() or "proficiency" in choice_label.lower():
                char_doc.setdefault("skill_proficiencies", []).append(choice_val)
            else:
                # Fallback: just add it as a feature
                char_doc.setdefault("features_traits", []).append(
                    {"name": choice_val, "description": f"Selected for {choice_label}"}
                )

    # Sync stats deterministically
    from backend.services.mechanics_service import sync_character_stats

    synced_char = sync_character_stats(char_doc)

    # Ensure nested _id is not updated
    if "_id" in synced_char:
        del synced_char["_id"]

    await db["characters"].update_one({"char_id": payload.character_id}, {"$set": synced_char})

    return CharacterSchema.model_validate(synced_char, strict=False)
