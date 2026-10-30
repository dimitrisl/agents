import logging
from typing import List, Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from backend.core.config_loader import (
    AVAILABLE_MODELS,
    get_ai_settings,
    get_user_api_key,
    provider_for_model,
    set_user_ai_settings,
)
from backend.services.campaign_service import _maybe_await
from server.db_async import get_database
from server.dependencies.auth import get_current_user, user_ai_context
from server.secret_box import encrypt_secret

logger = logging.getLogger("PhyrexianForge.SettingsRouter")

router = APIRouter(prefix="/settings", tags=["Settings"])


class AIModelOption(BaseModel):
    id: str
    label: str
    provider: str
    free_tier: bool


class AISettingsResponse(BaseModel):
    preferred_model: str
    temperature: float
    available_models: List[AIModelOption]
    has_anthropic_key: bool
    # Last 4 characters only; the key itself never leaves the server.
    anthropic_key_hint: Optional[str] = None


class AISettingsUpdate(BaseModel):
    preferred_model: str
    temperature: float = Field(ge=0.0, le=1.0)
    # None = keep the stored key, "" = remove it, anything else = replace it.
    anthropic_api_key: Optional[str] = None


def _build_response(ai_settings: dict) -> AISettingsResponse:
    api_key = get_user_api_key("anthropic")
    return AISettingsResponse(
        preferred_model=ai_settings.get("preferred_model", "gemini-2.5-flash"),
        temperature=ai_settings.get("temperature", 0.7),
        available_models=[
            AIModelOption(
                id=model_id,
                label=meta["label"],
                provider=meta["provider"],
                free_tier=meta["free_tier"],
            )
            for model_id, meta in AVAILABLE_MODELS.items()
        ],
        has_anthropic_key=bool(api_key),
        anthropic_key_hint=api_key[-4:] if api_key else None,
    )


def _verify_anthropic_key(api_key: str) -> None:
    """Rejects keys Anthropic does not accept; listing models costs no tokens."""
    try:
        anthropic.Anthropic(api_key=api_key, max_retries=0).models.list(limit=1)
    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anthropic rejected this API key. Check it and try again.",
        )
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        # Don't block saving on a transient outage; a bad key still surfaces on first use.
        logger.warning(f"Could not verify Anthropic API key, saving anyway: {e}")


@router.get("/ai", response_model=AISettingsResponse)
async def read_ai_settings(current_user: dict = Depends(get_current_user)):
    # Auth dependency already loaded this user's overrides into the context.
    return _build_response(get_ai_settings())


@router.put("/ai", response_model=AISettingsResponse)
async def update_ai_settings(
    payload: AISettingsUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Saves the AI model, temperature and own API key for the calling user only."""
    if payload.preferred_model not in AVAILABLE_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown model '{payload.preferred_model}'.",
        )

    stored = dict(current_user.get("ai_settings") or {})
    stored["preferred_model"] = payload.preferred_model
    stored["temperature"] = payload.temperature

    if payload.anthropic_api_key is not None:
        new_key = payload.anthropic_api_key.strip()
        if new_key:
            await run_in_threadpool(_verify_anthropic_key, new_key)
            stored["anthropic_api_key_enc"] = encrypt_secret(new_key)
        else:
            stored.pop("anthropic_api_key_enc", None)

    context = user_ai_context(stored)
    if provider_for_model(payload.preferred_model) == "anthropic" and not context["api_keys"].get(
        "anthropic"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add your Anthropic API key to use Claude models.",
        )

    await _maybe_await(
        db["users"].update_one({"id": current_user["id"]}, {"$set": {"ai_settings": stored}})
    )
    set_user_ai_settings(context)

    logger.info(
        "AI settings updated for %s: model=%s temperature=%s",
        current_user.get("username"),
        payload.preferred_model,
        payload.temperature,
    )
    return _build_response(get_ai_settings())
