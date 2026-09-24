import functools
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.core.schemas import (
    BackgroundSchema,
    FeatSchema,
    ItemSchema,
    RaceSchema,
    RulesAutofixResponse,
    RulesCompareResponse,
    RulesQueryResponse,
    RulesValidationResponse,
    SpellSchema,
)
from backend.repositories.rules_repository import RulesRepository
from backend.services.rules_service import (
    autofix_character_build,
    compare_rules,
    query_rules,
)
from backend.services.validation_service import deterministic_validate_build
from server.dependencies.auth import get_current_user


def parse_edition(
    edition: str = Query(EDITION_2014, description="D&D Edition (2014 or 2024)"),
) -> str:
    if edition in ["2014", EDITION_2014]:
        return EDITION_2014
    if edition in ["2024", EDITION_2024]:
        return EDITION_2024
    raise HTTPException(
        status_code=400, detail=f"Unknown edition: {edition}. Use '2014' or '2024'."
    )


router = APIRouter(prefix="/rules", tags=["Rules & Oracle"])


class RulesQueryRequest(BaseModel):
    query: str
    edition: str = "2014 Edition"


class RulesCompareRequest(BaseModel):
    query: str


class CharacterValidationRequest(BaseModel):
    character: Dict[str, Any]


@router.post("/query", response_model=RulesQueryResponse)
async def ask_rules_oracle(
    payload: RulesQueryRequest, current_user: dict = Depends(get_current_user)
):
    answer = query_rules(payload.query, payload.edition)
    return {"answer_markdown": answer}


@router.post("/compare", response_model=RulesCompareResponse)
async def compare_rule_editions(
    payload: RulesCompareRequest, current_user: dict = Depends(get_current_user)
):
    comparison = compare_rules(payload.query)
    return {"comparison_markdown": comparison}


@router.post("/validate", response_model=RulesValidationResponse)
async def validate_rules(
    payload: CharacterValidationRequest, current_user: dict = Depends(get_current_user)
):
    corrected, issues = deterministic_validate_build(payload.character)
    is_valid = len(issues) == 0
    return {
        "validation_result": {
            "is_valid": is_valid,
            "issues": issues,
            "suggestions": [],
            "corrections": corrected,
        }
    }


@router.post("/autofix", response_model=RulesAutofixResponse)
async def autofix_rules(
    payload: CharacterValidationRequest, current_user: dict = Depends(get_current_user)
):
    result = autofix_character_build(payload.character)
    return result


@functools.lru_cache(maxsize=1)
def get_rules_repo():
    return RulesRepository()


@router.get("/classes", response_model=List[str])
async def get_classes(
    edition: str = Depends(parse_edition),
    current_user: dict = Depends(get_current_user),
):
    repo = get_rules_repo()
    return repo.get_available_classes(edition)


@router.get("/classes/{class_name}", response_model=Dict[str, Any])
async def get_class_details(
    class_name: str,
    edition: str = Depends(parse_edition),
    current_user: dict = Depends(get_current_user),
):
    repo = get_rules_repo()
    data = repo.get_class_progression(class_name, edition)
    if not data:
        raise HTTPException(status_code=404, detail=f"Class {class_name} not found in {edition}")
    return data


@router.get("/classes/{class_name}/subclasses", response_model=List[str])
async def get_class_subclasses(
    class_name: str,
    edition: str = Depends(parse_edition),
    current_user: dict = Depends(get_current_user),
):
    repo = get_rules_repo()
    return repo.get_subclasses(class_name, edition)


@router.get("/classes/{class_name}/scaling", response_model=List[Dict[str, Any]])
async def get_class_scaling(
    class_name: str,
    level: int = Query(..., ge=1, le=20, description="Character level to resolve scaling for"),
    subclass: Optional[str] = Query(None, description="Optional subclass name"),
    edition: str = Depends(parse_edition),
    current_user: dict = Depends(get_current_user),
):
    repo = get_rules_repo()
    data = repo.get_class_progression(class_name, edition)
    if not data:
        raise HTTPException(status_code=404, detail=f"Class {class_name} not found in {edition}")

    scaling_dict = dict(data.get("scaling", {}))

    if subclass:
        subclass_data = repo.get_subclass_mechanics(class_name, edition)
        if subclass_data and "subclasses" in subclass_data:
            specific_subclass = subclass_data["subclasses"].get(subclass, {})
            subclass_scaling = specific_subclass.get("scaling", {})
            scaling_dict.update(subclass_scaling)

    resolved_actions = []

    for action_id, action_def in scaling_dict.items():
        steps = action_def.get("steps", [])
        valid_steps = [s for s in steps if s.get("level", 0) <= level]
        if not valid_steps:
            continue

        active_step = max(valid_steps, key=lambda s: s.get("level", 0))

        action_payload = {
            "id": action_id.replace("_", "-"),
            "name": action_def.get("name"),
            "kind": action_def.get("kind"),
            "hint": action_def.get("hint"),
            "notation": active_step.get("notation"),
            "rollable": action_def.get("rollable", True),
        }
        if "damage_type" in action_def:
            action_payload["damageType"] = action_def["damage_type"]
        if "options" in action_def:
            action_payload["options"] = action_def["options"]

        resolved_actions.append(action_payload)

    return resolved_actions


@router.get("/feats", response_model=List[FeatSchema])
async def get_feats(
    edition: str = Depends(parse_edition), current_user: dict = Depends(get_current_user)
):
    repo = get_rules_repo()
    return repo.get_all_feats(edition)


@router.get("/spells", response_model=List[SpellSchema])
async def get_spells(
    search: Optional[str] = Query(None, description="Search term for spell name"),
    level: Optional[int] = Query(None, description="Filter by spell level"),
    char_class: Optional[str] = Query(None, description="Filter by class name"),
    edition: str = Depends(parse_edition),
    current_user: dict = Depends(get_current_user),
):
    repo = get_rules_repo()
    if search:
        spells = repo.search_spells(search, edition)
    else:
        spells = repo.get_all_spells(edition)

    if level is not None:
        spells = [s for s in spells if s.get("level") == level]
    if char_class:
        cls_lower = char_class.lower()
        spells = [s for s in spells if cls_lower in [c.lower() for c in s.get("classes", [])]]

    return spells


@router.get("/races", response_model=List[RaceSchema])
async def get_races(
    edition: str = Depends(parse_edition), current_user: dict = Depends(get_current_user)
):
    repo = get_rules_repo()
    return repo.get_available_races(edition)


@router.get("/backgrounds", response_model=List[BackgroundSchema])
async def get_backgrounds(
    edition: str = Depends(parse_edition), current_user: dict = Depends(get_current_user)
):
    repo = get_rules_repo()
    return repo.get_available_backgrounds(edition)


@router.get("/items", response_model=List[ItemSchema])
async def get_items(current_user: dict = Depends(get_current_user)):
    repo = get_rules_repo()
    return repo.get_all_items()
