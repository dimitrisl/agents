import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from backend.core.schemas import (
    CharacterSchema,
    LevelUpAnalysisSchema,
    LevelUpApplyRequest,
    LevelUpRecommendationsRequest,
    LevelUpRecommendationsResponse,
    PlaystyleGuideResponse,
    PortraitResponse,
)
from backend.repositories.rules_repository import RulesRepository
from backend.services.forge_service import (
    analyze_level_up,
    forge_character,
    forge_character_manual,
    generate_level_up_build_recommendations,
    generate_playstyle_guide,
)
from backend.utils.image_utils import generate_portrait_url, prune_unreferenced_preview_portraits
from server.config import settings
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.rate_limiter import limiter

router = APIRouter(prefix="/forge", tags=["Forge (AI)"])
logger = logging.getLogger(__name__)


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
    chosen_spells: Optional[list] = None
    chosen_feats: Optional[list] = None
    chosen_equipment: Optional[list] = None


class LevelUpRequest(BaseModel):
    character: CharacterSchema
    user_choices: Optional[Dict[str, Any]] = None


class PortraitRequest(BaseModel):
    char_id: str
    force: bool = True
    prompt: Optional[str] = None
    character_data: Optional[Dict[str, Any]] = None


@router.post("/generate", response_model=CharacterSchema)
@limiter.limit(settings.AI_RATE_LIMIT)
async def generate_forge_character(
    request: Request,
    payload: ForgeCharacterRequest,
    current_user: dict = Depends(get_current_user),
):
    char_dict = await run_in_threadpool(
        forge_character,
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
@limiter.limit(settings.AI_RATE_LIMIT)
async def enrich_manual_character(
    request: Request,
    payload: ManualEnrichRequest,
    current_user: dict = Depends(get_current_user),
):
    char_dict = await run_in_threadpool(
        forge_character_manual,
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
        chosen_spells=payload.chosen_spells,
        chosen_feats=payload.chosen_feats,
        chosen_equipment=payload.chosen_equipment,
    )
    if not char_dict:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enrich character",
        )
    char_dict["owner_id"] = current_user["id"]
    return CharacterSchema.model_validate(char_dict, strict=False)


@router.post("/level-up-analysis", response_model=LevelUpAnalysisSchema)
@limiter.limit(settings.AI_RATE_LIMIT)
async def get_level_up_analysis(
    request: Request,
    payload: LevelUpRequest,
    current_user: dict = Depends(get_current_user),
):
    char_data = payload.character.model_dump()
    try:
        analysis = await run_in_threadpool(analyze_level_up, char_data, payload.user_choices)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze level up options",
        )
    return LevelUpAnalysisSchema.model_validate(analysis, strict=False)


@router.post("/level-up-recommendations", response_model=LevelUpRecommendationsResponse)
@limiter.limit(settings.AI_RATE_LIMIT)
async def get_level_up_recommendations(
    request: Request,
    payload: LevelUpRecommendationsRequest,
    current_user: dict = Depends(get_current_user),
):
    char_data = payload.character.model_dump()
    try:
        recommendations = await run_in_threadpool(
            generate_level_up_build_recommendations,
            char_data=char_data,
            target_class=payload.target_class,
            target_level=payload.target_level,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate level up recommendations: {e}"
        )

    return LevelUpRecommendationsResponse.model_validate(recommendations, strict=False)


@router.post("/playstyle-guide", response_model=PlaystyleGuideResponse)
@limiter.limit(settings.AI_RATE_LIMIT)
async def get_playstyle_guide(
    request: Request,
    character: CharacterSchema,
    current_user: dict = Depends(get_current_user),
):
    char_data = character.model_dump()
    guide_text = await run_in_threadpool(generate_playstyle_guide, char_data)
    return {"guide_markdown": guide_text}


@router.post("/portrait", response_model=PortraitResponse)
@limiter.limit(settings.AI_RATE_LIMIT)
async def generate_ai_portrait(
    request: Request,
    payload: PortraitRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await db["characters"].find_one(
        {"char_id": payload.char_id, "owner_id": current_user["id"]}
    )
    if doc:
        char_dict = CharacterSchema.model_validate(doc, strict=False).model_dump()
    elif isinstance(payload.character_data, dict):
        existing_any = await db["characters"].find_one(
            {"char_id": payload.char_id}, {"owner_id": 1}
        )
        if existing_any and existing_any.get("owner_id") != current_user["id"]:
            raise HTTPException(status_code=404, detail="Character not found")
        raw = payload.character_data
        # Only prompt-descriptive fields are accepted for an unsaved Forge preview;
        # char_id is pinned to an isolated ephemeral id and char_portrait is ignored.
        char_dict = {
            key: str(raw[key])[:500]
            for key in (
                "race",
                "char_class",
                "background",
                "backstory",
                "alignment",
                "gender",
            )
            if raw.get(key) is not None
        }
        char_dict["char_id"] = f"preview_{uuid.uuid4().hex[:12]}"
    else:
        raise HTTPException(status_code=404, detail="Character not found")

    portrait_url = await generate_portrait_url(
        char_dict, force=payload.force, custom_prompt=payload.prompt
    )

    new_version = int(doc.get("version", 0) or 0) if doc else 0
    if doc and portrait_url:
        new_version += 1
        char_dict["char_portrait"] = portrait_url
        await db["characters"].update_one(
            {"char_id": payload.char_id, "owner_id": current_user["id"]},
            {"$set": {"char_portrait": portrait_url, "version": new_version}},
        )
    elif not doc and portrait_url:
        # Clean up stale unreferenced Forge preview files off the event loop, preserving DB-referenced portraits
        referenced_portraits = []
        distinct_fn = getattr(db["characters"], "distinct", None)
        if callable(distinct_fn):
            referenced_portraits = await distinct_fn("char_portrait")
        await run_in_threadpool(prune_unreferenced_preview_portraits, referenced_portraits)

    return {
        "success": bool(portrait_url),
        "portrait_url": portrait_url or "",
        "version": new_version,
    }


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

    # Increment level based on multiclass choice
    user_choices = payload.user_choices or {}
    target_class = user_choices.get("level_up_class", char_doc.get("char_class", "Fighter"))
    old_level = max(1, int(char_doc.get("char_level", 1) or 1))

    classes = char_doc.get("classes", [])
    if not classes:
        classes = [
            {
                "class_name": char_doc.get("char_class", "Fighter"),
                "level": char_doc.get("char_level", 1),
                "subclass": char_doc.get("subclass"),
            }
        ]

    class_found = False
    for cls in classes:
        if cls.get("class_name", "").lower() == target_class.lower():
            cls["level"] = cls.get("level", 0) + 1
            class_found = True
            break

    if not class_found:
        classes.append({"class_name": target_class, "level": 1, "subclass": None})

    char_doc["classes"] = classes
    char_doc["char_level"] = sum(c.get("level", 1) for c in classes)

    if char_doc["char_level"] > 20:
        raise HTTPException(status_code=400, detail="Character cannot exceed level 20.")

    # Note: if they change primary class logic, they will update it elsewhere, but we preserve primary char_class.

    # Compute legal level-up HP gain deterministically server-side
    from backend.services.forge_service import resolve_level_up_automatic_features
    from backend.services.progression_service import get_level_up_vitals
    from backend.services.stats_service import calculate_hp

    edition = char_doc.get("dnd_edition", "2014 Edition")
    is_2024_edition = "2024" in str(edition)
    target_class_entry = next(
        (c for c in classes if (c.get("class_name") or "").lower() == target_class.lower()),
        None,
    )
    new_class_level = int((target_class_entry or {}).get("level") or char_doc["char_level"])
    old_class_level = max(0, new_class_level - 1)
    pre_subclass = (
        target_class_entry.get("subclass") if target_class_entry else None
    ) or char_doc.get("subclass")
    # Resolve any newly selected subclass before computing HP vitals so unlocks (e.g. 2024 L3 Draconic) match analyze_level_up
    chosen_subclass = pre_subclass
    if payload.user_choices:
        for choice_key, choice_val in payload.user_choices.items():
            if not choice_val:
                continue
            base_type = choice_key.rsplit("_", 1)[0] if "_" in choice_key else choice_key
            if base_type == "subclass":
                chosen_subclass = choice_val
                for cls in char_doc["classes"]:
                    if cls.get("class_name", "").lower() == target_class.lower():
                        cls["subclass"] = choice_val
                        break
                if target_class.lower() == char_doc.get("char_class", "").lower():
                    char_doc["subclass"] = choice_val

    old_con = int((char_doc.get("stats") or {}).get("CON", 10) or 10)
    vitals = get_level_up_vitals(
        char_class=target_class,
        current_level=old_class_level,
        con_score=old_con,
        edition=edition,
        features=char_doc.get("features_traits", []),
        subclass=chosen_subclass,
    )
    hp_increase = vitals["average_hp_gain"]
    hp_method = str(user_choices.get("hp_method") or "").strip().lower()
    custom_hp = user_choices.get("custom_hp_increase")
    if custom_hp is not None and hp_method != "average":
        try:
            adjusted_hp = int(custom_hp)
            if hp_method == "roll" and "hp_bonus_included" in user_choices:
                try:
                    included = int(user_choices["hp_bonus_included"])
                    current_bonus = int(vitals.get("hp_bonus_per_level") or 0)
                    adjusted_hp += current_bonus - included
                except (ValueError, TypeError):
                    pass
            hp_increase = max(1, min(vitals["max_hp_gain"], adjusted_hp))
        except (ValueError, TypeError):
            pass

    old_hp_max = int(char_doc.get("hp_max") or 0)
    if old_hp_max <= 0:
        old_hp_max = calculate_hp(
            vitals["hit_die"],
            old_level,
            old_con,
        )

    char_doc["hp_max"] = old_hp_max + hp_increase
    char_doc["hp_current"] = char_doc["hp_max"]  # heal on level up
    # Compute the pre-existing feat/subclass HP already baked into old_hp_max (for legacy docs
    # that omit `feat_hp_bonus`) plus the +1 level increment included in `vitals["hp_bonus_per_level"]`
    # so sync_character_stats() adds retroactive levels (e.g. L1-L2 Draconic on 2024 L3 unlock) once.
    pre_bonus_per_lvl = int(vitals.get("hp_bonus_per_level") or 0)
    is_target_draconic_sorc = target_class.lower() == "sorcerer" and (
        "draconic" in str(chosen_subclass or "").lower()
        or any(
            isinstance(f, dict) and "draconic resilience" in (f.get("name") or "").lower()
            for f in char_doc.get("features_traits", [])
        )
    )

    if char_doc.get("feat_hp_bonus"):
        prev_baked_feat_hp = int(char_doc["feat_hp_bonus"])
    else:
        non_drac_per_lvl = pre_bonus_per_lvl - (1 if is_target_draconic_sorc else 0)
        non_drac_per_lvl = max(0, non_drac_per_lvl)
        pre_drac_levels = 0
        has_drac_trait = any(
            isinstance(f, dict) and "draconic resilience" in (f.get("name") or "").lower()
            for f in char_doc.get("features_traits", [])
        )
        for cls in classes:
            if (cls.get("class_name") or "").lower() == "sorcerer":
                c_sub = (cls.get("subclass") or char_doc.get("subclass") or "").lower()
                if "draconic" in c_sub or has_drac_trait:
                    pre_lvl = int(cls.get("level", 1) or 1)
                    if (cls.get("class_name") or "").lower() == target_class.lower():
                        pre_lvl = old_class_level
                    if not is_2024_edition or pre_lvl >= 3 or has_drac_trait:
                        pre_drac_levels += pre_lvl
        prev_baked_feat_hp = non_drac_per_lvl * old_level + pre_drac_levels

    char_doc["feat_hp_bonus"] = prev_baked_feat_hp + pre_bonus_per_lvl

    char_doc["con_mod_applied"] = (old_con - 10) // 2

    stat_cap = (
        30
        if (char_doc["char_level"] >= 19 and "2024" in str(char_doc.get("dnd_edition", "")))
        else 20
    )

    def _bump_stat(stat_key: str, amount: int) -> None:
        if stat_key and stat_key in char_doc.get("stats", {}):
            char_doc["stats"][stat_key] = min(stat_cap, int(char_doc["stats"][stat_key]) + amount)
            if isinstance(char_doc.get("base_stats"), dict) and stat_key in char_doc["base_stats"]:
                char_doc["base_stats"][stat_key] = min(
                    stat_cap, int(char_doc["base_stats"][stat_key]) + amount
                )

    # Inject authoritative automatic features from static RulesRepository only (never trust client list)
    static_auto_features = resolve_level_up_automatic_features(
        target_class, new_class_level, chosen_subclass, edition
    )
    existing_features = {
        f.get("name") for f in char_doc.get("features_traits", []) if isinstance(f, dict)
    }
    for feature in static_auto_features:
        f_name = feature.get("name")
        if f_name and f_name not in existing_features:
            char_doc.setdefault("features_traits", []).append(feature)
            existing_features.add(f_name)

    # Process user choices (feats, spells, skills — subclass already applied above)
    if payload.user_choices:
        for choice_key, choice_val in payload.user_choices.items():
            if (
                not choice_val
                or choice_key in ("custom_hp_increase", "hp_bonus_included")
                or "_stat1_" in choice_key
                or "_stat2_" in choice_key
            ):
                continue

            # choice_key is now something like "subclass_0", "spell_1", "other_2"
            base_type = choice_key.rsplit("_", 1)[0] if "_" in choice_key else choice_key

            if base_type == "subclass":
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
                clean_val = str(choice_val).strip()

                rules_repo = RulesRepository()
                edition = char_doc.get("dnd_edition", "2014 Edition")
                all_spells = rules_repo.get_all_spells(edition)

                matched_spell = next(
                    (
                        s
                        for s in all_spells
                        if str(s.get("name", "")).strip().lower() == clean_val.lower()
                    ),
                    None,
                )
                if matched_spell is None:
                    logger.warning(
                        "Ignoring unknown spell choice %r during level-up for %s",
                        clean_val,
                        payload.character_id,
                    )
                    continue

                spell_level = matched_spell.get("level")
                canonical_name = matched_spell.get("name") or clean_val
                spells_dict = char_doc.setdefault("spells", {})

                if spell_level == 0:
                    target_list = spells_dict.setdefault("cantrips", [])
                else:
                    target_list = spells_dict.setdefault(f"level_{spell_level}", [])

                if canonical_name not in target_list:
                    target_list.append(canonical_name)
            elif choice_type == "feat" or "feat" in choice_label.lower():
                if choice_val == "+2 to one Stat":
                    # Reconstruct the stat keys (e.g. feat_stat1_0)
                    parts = choice_key.rsplit("_", 1)
                    idx_suffix = f"_{parts[1]}" if len(parts) > 1 else ""
                    base = parts[0] if len(parts) > 1 else choice_key
                    stat1_key = f"{base}_stat1{idx_suffix}"

                    stat1 = payload.user_choices.get(stat1_key)
                    _bump_stat(stat1, 2)
                elif choice_val == "+1 to two Stats":
                    parts = choice_key.rsplit("_", 1)
                    idx_suffix = f"_{parts[1]}" if len(parts) > 1 else ""
                    base = parts[0] if len(parts) > 1 else choice_key
                    stat1_key = f"{base}_stat1{idx_suffix}"
                    stat2_key = f"{base}_stat2{idx_suffix}"

                    stat1 = payload.user_choices.get(stat1_key)
                    stat2 = payload.user_choices.get(stat2_key)
                    _bump_stat(stat1, 1)
                    _bump_stat(stat2, 1)
                else:
                    rules_repo = RulesRepository()
                    edition = char_doc.get("dnd_edition", "2014 Edition")
                    feat_data = next(
                        (
                            f
                            for f in rules_repo.get_all_feats(edition)
                            if f.get("name") == choice_val
                        ),
                        None,
                    )

                    feat_desc = "Selected via Level Up."
                    if feat_data:
                        feat_desc = feat_data.get("description", feat_desc)

                        # Apply static stat bonuses
                        stat_bonus = feat_data.get("stat_bonus", {})
                        if stat_bonus:
                            for stat, bonus in stat_bonus.items():
                                if bonus > 0:
                                    _bump_stat(stat, bonus)

                        # Handle stat choice for half-feats if user provided it
                        if feat_data.get("has_stat_choice"):
                            parts = choice_key.rsplit("_", 1)
                            idx_suffix = f"_{parts[1]}" if len(parts) > 1 else ""
                            base = parts[0] if len(parts) > 1 else choice_key
                            stat1_key = f"{base}_stat1{idx_suffix}"
                            stat1 = payload.user_choices.get(stat1_key)
                            _bump_stat(stat1, 1)

                    char_doc.setdefault("features_traits", []).append(
                        {"name": choice_val, "description": feat_desc}
                    )
            elif "expertise" in choice_label.lower():
                char_doc.setdefault("skill_expertise", []).append(choice_val)
            elif "skill" in choice_label.lower() or "proficiency" in choice_label.lower():
                char_doc.setdefault("skill_proficiencies", []).append(choice_val)
            elif (
                choice_key.startswith("level_up")
                or choice_key in ("hp_method", "hp_roll", "subclass", "hit_die_roll")
                or "level_up" in choice_label.lower()
                or "hp_method" in choice_label.lower()
                or str(choice_val).lower() in ("roll", "average", "manual")
            ):
                # Metadata / mechanical level-up choices: do not append to features_traits
                pass
            else:
                # Fallback: only add if it's a real feature
                if choice_val and str(choice_val).lower() not in ("roll", "average", "manual"):
                    char_doc.setdefault("features_traits", []).append(
                        {"name": choice_val, "description": f"Selected for {choice_label}"}
                    )

    # Sync stats deterministically
    from backend.services.homebrew_service import HomebrewService
    from backend.services.mechanics_service import sync_character_stats

    homebrew_service = HomebrewService()
    homebrew_items = await homebrew_service.get_campaign_homebrew(
        db, char_doc.get("active_campaign")
    )

    old_resource_state = {
        str(r.get("name")): (int(r.get("current", 0) or 0), int(r.get("max", 0) or 0))
        for r in (char_doc.get("class_resources") or [])
        if isinstance(r, dict) and r.get("name")
    }

    synced_char = sync_character_stats(char_doc, homebrew_content=homebrew_items)
    synced_char["hp_current"] = synced_char.get("hp_max", char_doc.get("hp_max", 10))

    # Grant newly gained resource capacity delta on level-up even when pool was partially spent
    for r in synced_char.get("class_resources") or []:
        if isinstance(r, dict) and r.get("name") in old_resource_state:
            old_cur, old_max = old_resource_state[str(r.get("name"))]
            new_max = int(r.get("max", 0) or 0)
            if 0 < old_cur < old_max and new_max > old_max:
                r["current"] = min(new_max, old_cur + (new_max - old_max))

    # Ensure nested _id is not updated
    if "_id" in synced_char:
        del synced_char["_id"]

    raw_version = char_doc.get("version")
    client_version = int(raw_version or 0)
    synced_char["version"] = client_version + 1
    version_filter = (
        {"$or": [{"version": 0}, {"version": None}, {"version": {"$exists": False}}]}
        if raw_version in (None, 0)
        else {"version": client_version}
    )

    result = await db["characters"].update_one(
        {"char_id": payload.character_id, **version_filter}, {"$set": synced_char}
    )
    if result.modified_count == 0 and result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict: Character was modified concurrently during level up. Please refresh.",
        )

    active_camp = synced_char.get("active_campaign")
    if active_camp:
        from backend.services.encounter_service import calculate_danger_indicator
        from server.routers.websocket_router import manager

        # Atomically update only this character's encounter combatant fields so DM reloads
        # see post-level-up HP/AC/danger without colliding on homonyms or overwriting concurrent edits.
        camp_doc = await db["campaigns"].find_one({"campaign_name": active_camp})
        camp_edition = (camp_doc or {}).get("dnd_edition", "2014 Edition")
        char_name_lower = str(synced_char.get("char_name") or "").strip().lower()
        new_hp = synced_char.get("hp_current") or 0
        new_hp_max = synced_char.get("hp_max") or 0
        new_ac = synced_char.get("armor_class", 10)

        for _attempt in range(2):
            enc_doc = await db["campaign_encounters"].find_one({"campaign_name": active_camp})
            if not enc_doc or not isinstance(enc_doc.get("combatants"), list):
                break
            filter_query: Dict[str, Any] = {"campaign_name": active_camp}
            set_fields: Dict[str, Any] = {}
            preview_combatants = []
            for idx, c in enumerate(enc_doc["combatants"]):
                if not isinstance(c, dict):
                    preview_combatants.append(c)
                    continue
                c_id = c.get("char_id")
                c_name_lower = str(c.get("name") or "").strip().lower()
                is_match = bool(c.get("is_player")) and (
                    c_id == payload.character_id
                    if c_id
                    else (bool(char_name_lower) and c_name_lower == char_name_lower)
                )
                if is_match:
                    if c.get("id") is not None:
                        filter_query[f"combatants.{idx}.id"] = c["id"]
                    if c_id:
                        filter_query[f"combatants.{idx}.char_id"] = c_id
                    else:
                        filter_query[f"combatants.{idx}.char_id"] = {"$in": [None, ""]}
                    set_fields[f"combatants.{idx}.hp"] = new_hp
                    set_fields[f"combatants.{idx}.max_hp"] = new_hp_max
                    set_fields[f"combatants.{idx}.ac"] = new_ac
                    set_fields[f"combatants.{idx}.health_status"] = "Healthy"
                    preview_combatants.append(
                        {**c, "hp": new_hp, "max_hp": new_hp_max, "ac": new_ac}
                    )
                else:
                    preview_combatants.append(c)

            if not set_fields:
                break

            set_fields["danger_indicator"] = await calculate_danger_indicator(
                preview_combatants, db, edition=camp_edition
            )
            enc_res = await db["campaign_encounters"].update_one(filter_query, {"$set": set_fields})
            if enc_res.matched_count > 0:
                break

        await manager.broadcast(
            active_camp,
            {
                "type": "party_update",
                "payload": {
                    "char_id": payload.character_id,
                    "char_name": synced_char.get("char_name", "Unknown"),
                    "hp_current": synced_char.get("hp_current") or 0,
                    "hp_max": synced_char.get("hp_max") or 0,
                    "ac": synced_char.get("armor_class", 10),
                    "level": synced_char.get("char_level", 1),
                    "conditions": synced_char.get("conditions", []),
                    "version": synced_char["version"],
                    "source": "player",
                },
            },
        )

    return CharacterSchema.model_validate(synced_char, strict=False)
