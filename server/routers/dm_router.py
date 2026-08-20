from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.core.schemas import (
    EncounterSchema,
    NpcResponse,
    RiddleResponse,
    SessionPrepResponse,
)
from backend.services.dm_service import (
    generate_npc,
    generate_random_encounter,
    generate_riddle,
    generate_session_prep,
)
from server.dependencies.auth import get_current_user

router = APIRouter(prefix="/dm", tags=["DM Tools"])


class EncounterRequest(BaseModel):
    # Bounded rather than free-form: these go straight into the prompt, and a
    # party of 0 (or a difficulty the model has never heard of) only ever
    # produces a nonsense encounter that looks legitimate.
    party_size: int = Field(4, ge=1, le=20)
    avg_level: int = Field(5, ge=1, le=20)
    location: str = "Dungeon"
    edition: str = "2014 Edition"
    difficulty: Literal["Easy", "Medium", "Hard", "Deadly"] = "Medium"


class NpcRequest(BaseModel):
    npc_concept: str
    edition: str = "2014 Edition"


class RiddleRequest(BaseModel):
    location: str
    edition: str = "2014 Edition"


class SessionPrepRequest(BaseModel):
    campaign_notes: str
    party_info: str


@router.post("/encounter", response_model=EncounterSchema)
async def create_encounter(
    payload: EncounterRequest, current_user: dict = Depends(get_current_user)
):
    result = generate_random_encounter(
        party_size=payload.party_size,
        avg_level=payload.avg_level,
        location=payload.location,
        edition=payload.edition,
        difficulty=payload.difficulty,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate encounter",
        )
    return EncounterSchema.model_validate(result, strict=False)


@router.post("/npc", response_model=NpcResponse)
async def create_npc(payload: NpcRequest, current_user: dict = Depends(get_current_user)):
    npc_text = generate_npc(payload.npc_concept, payload.edition)
    return {"npc_markdown": npc_text}


@router.post("/riddle", response_model=RiddleResponse)
async def create_riddle(payload: RiddleRequest, current_user: dict = Depends(get_current_user)):
    riddle_text = generate_riddle(payload.location, payload.edition)
    return {"riddle_markdown": riddle_text}


@router.post("/session-prep", response_model=SessionPrepResponse)
async def create_session_prep(
    payload: SessionPrepRequest, current_user: dict = Depends(get_current_user)
):
    prep_text = generate_session_prep(payload.campaign_notes, payload.party_info)
    return {"session_markdown": prep_text}
