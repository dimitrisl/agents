import functools
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.core.constants import EDITION_2014
from backend.core.schemas import (
    RulesAutofixResponse,
    RulesCompareResponse,
    RulesQueryResponse,
    RulesValidationResponse,
)
from backend.repositories.rules_repository import RulesRepository
from backend.services.rules_service import (
    autofix_character_build,
    compare_rules,
    query_rules,
)
from backend.services.validation_service import deterministic_validate_build
from server.dependencies.auth import get_current_user

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


@router.get("/classes")
async def get_classes(
    edition: str = Query(EDITION_2014, description="D&D Edition (2014 or 2024)"),
    current_user: dict = Depends(get_current_user),
):
    repo = get_rules_repo()
    return repo.get_available_classes(edition)


@router.get("/classes/{class_name}")
async def get_class_details(
    class_name: str,
    edition: str = Query(EDITION_2014),
    current_user: dict = Depends(get_current_user),
):
    repo = get_rules_repo()
    data = repo.get_class_progression(class_name, edition)
    if not data:
        raise HTTPException(status_code=404, detail=f"Class {class_name} not found in {edition}")
    return data


@router.get("/feats")
async def get_feats(
    edition: str = Query(EDITION_2014), current_user: dict = Depends(get_current_user)
):
    repo = get_rules_repo()
    return repo.get_all_feats(edition)


@router.get("/spells")
async def get_spells(
    edition: str = Query(EDITION_2014), current_user: dict = Depends(get_current_user)
):
    repo = get_rules_repo()
    return repo.get_all_spells(edition)


@router.get("/races")
async def get_races(
    edition: str = Query(EDITION_2014), current_user: dict = Depends(get_current_user)
):
    repo = get_rules_repo()
    return repo.get_available_races(edition)


@router.get("/backgrounds")
async def get_backgrounds(
    edition: str = Query(EDITION_2014), current_user: dict = Depends(get_current_user)
):
    repo = get_rules_repo()
    return repo.get_available_backgrounds(edition)
