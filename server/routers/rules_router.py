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
    corrected = deterministic_validate_build(payload.character)
    return {
        "validation_result": {
            "is_valid": True,
            "issues": [],
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
