from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.services.rules_service import compare_rules, query_rules, validate_character_build
from server.dependencies.auth import get_current_user

router = APIRouter(prefix="/rules", tags=["Rules & Oracle"])


class RulesQueryRequest(BaseModel):
    query: str
    edition: str = "2014 Edition"


class RulesCompareRequest(BaseModel):
    query: str


class CharacterValidationRequest(BaseModel):
    character: Dict[str, Any]


@router.post("/query")
async def ask_rules_oracle(
    payload: RulesQueryRequest, current_user: dict = Depends(get_current_user)
):
    answer = query_rules(payload.query, payload.edition)
    return {"answer_markdown": answer}


@router.post("/compare")
async def compare_rule_editions(
    payload: RulesCompareRequest, current_user: dict = Depends(get_current_user)
):
    comparison = compare_rules(payload.query)
    return {"comparison_markdown": comparison}


@router.post("/validate")
async def validate_rules(
    payload: CharacterValidationRequest, current_user: dict = Depends(get_current_user)
):
    result = validate_character_build(payload.character)
    return {"validation_result": result}
