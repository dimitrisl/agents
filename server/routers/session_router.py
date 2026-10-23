from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from backend.core.schemas import CampaignEntitySchema, SessionLogSchema, SessionPrepSchema
from backend.services.session_service import SessionService
from backend.utils.audio_validator import format_file_size_limit, validate_audio_metadata
from server.config import settings
from server.db_async import get_database
from server.dependencies.campaign import require_campaign_member, require_campaign_role
from server.rate_limiter import limiter


class PrepRequest(BaseModel):
    dm_ideas: str = ""


class TextSessionRequest(BaseModel):
    session_number: int
    notes: str


router = APIRouter(tags=["sessions"])
session_service = SessionService()


@router.get("/campaigns/{name}/sessions", response_model=List[SessionLogSchema])
async def get_sessions(
    name: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm", "player")),
):
    """Get all session logs for a campaign."""
    cursor = db.session_logs.find({"campaign_name": name}).sort("session_number", -1)
    sessions = await cursor.to_list(length=100)

    # Map _id to id
    for s in sessions:
        s["id"] = str(s.pop("_id"))

    return sessions


@router.post("/campaigns/{name}/sessions/audio", response_model=SessionLogSchema)
@limiter.limit(settings.AUDIO_SESSION_RATE_LIMIT)
async def process_audio_session(
    request: Request,
    name: str,
    session_number: int = Form(...),
    audio_file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Upload an audio file, generate transcription and extract entities via AI."""
    # Fast reject if Content-Length header is present and exceeds max cap
    content_length_header = request.headers.get("content-length")
    if content_length_header:
        try:
            if int(content_length_header) > settings.MAX_AUDIO_FILE_SIZE_BYTES:
                limit_str = format_file_size_limit(settings.MAX_AUDIO_FILE_SIZE_BYTES)
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"File size exceeds the maximum allowed limit of {limit_str}.",
                )
        except ValueError:
            pass

    # Validate file extension and MIME type
    validate_audio_metadata(audio_file)

    try:
        # Process audio and extract data
        ai_result = await session_service.process_audio_session(
            campaign_name=name, session_number=session_number, audio_file=audio_file
        )

        extracted_entities = []
        # Save extracted entities to db
        docs_to_insert = []
        for ent_data in ai_result.get("extracted_entities", []):
            ent_schema = CampaignEntitySchema(
                campaign_name=name,
                name=ent_data.get("name", "Unknown Entity"),
                type=ent_data.get("type", "lore"),
                content=ent_data.get("content", ""),
                tags=ent_data.get("tags", []),
                created_at=datetime.now(timezone.utc),
            )
            extracted_entities.append(ent_schema)
            docs_to_insert.append(ent_schema.model_dump(exclude={"id"}))

        if docs_to_insert:
            result = await db.campaign_entities.insert_many(docs_to_insert)
            for schema, inserted_id in zip(extracted_entities, result.inserted_ids):
                schema.id = str(inserted_id)

        # Create session log
        session_log = SessionLogSchema(
            campaign_name=name,
            session_number=session_number,
            title=ai_result.get("title", f"Session {session_number}"),
            summary=ai_result.get("summary", ""),
            real_world_date=datetime.now(timezone.utc),
            extracted_entities=extracted_entities,
            audio_file_id=ai_result.get("audio_file_id"),
            created_at=datetime.now(timezone.utc),
        )

        result = await db.session_logs.insert_one(session_log.model_dump(exclude={"id"}))
        session_log.id = str(result.inserted_id)

        return session_log

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/{name}/sessions/text", response_model=SessionLogSchema)
@limiter.limit(settings.AI_RATE_LIMIT)
async def process_text_session(
    request: Request,
    name: str,
    payload: TextSessionRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Process raw text session notes, generate a structured log and extract entities via AI."""
    try:
        # Process text and extract data
        ai_result = await session_service.process_text_session(
            campaign_name=name, session_number=payload.session_number, notes=payload.notes
        )

        extracted_entities = []
        # Save extracted entities to db
        docs_to_insert = []
        for ent_data in ai_result.get("extracted_entities", []):
            ent_schema = CampaignEntitySchema(
                campaign_name=name,
                name=ent_data.get("name", "Unknown Entity"),
                type=ent_data.get("type", "lore"),
                content=ent_data.get("content", ""),
                tags=ent_data.get("tags", []),
                current_location_id=ent_data.get("current_location_id"),
                created_at=datetime.now(timezone.utc),
            )
            extracted_entities.append(ent_schema)
            docs_to_insert.append(ent_schema.model_dump(exclude={"id"}))

        if docs_to_insert:
            result = await db.campaign_entities.insert_many(docs_to_insert)
            for schema, inserted_id in zip(extracted_entities, result.inserted_ids):
                schema.id = str(inserted_id)

        # Create session log
        session_log = SessionLogSchema(
            campaign_name=name,
            session_number=payload.session_number,
            title=ai_result.get("title", f"Session {payload.session_number}"),
            session_type="text",
            summary=ai_result.get("summary", ""),
            real_world_date=datetime.now(timezone.utc),
            extracted_entities=extracted_entities,
            created_at=datetime.now(timezone.utc),
        )

        result = await db.session_logs.insert_one(session_log.model_dump(exclude={"id"}))
        session_log.id = str(result.inserted_id)

        return session_log

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/{name}/sessions/prep", response_model=SessionPrepSchema)
@limiter.limit(settings.AI_RATE_LIMIT)
async def generate_prep(
    request: Request,
    name: str,
    payload: PrepRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Generate session prep based on past sessions and active entities."""
    try:
        from fastapi.concurrency import run_in_threadpool

        # Fetch last 3 sessions
        cursor = db.session_logs.find({"campaign_name": name}).sort("session_number", -1).limit(3)
        past_sessions = await cursor.to_list(length=3)

        # Fetch key entities (villains, npcs)
        ent_cursor = db.campaign_entities.find(
            {"campaign_name": name, "type": {"$in": ["villain", "npc", "faction", "location"]}}
        ).limit(20)
        active_entities = await ent_cursor.to_list(length=20)

        prep_data = await run_in_threadpool(
            session_service.generate_session_forge_prep,
            past_sessions=past_sessions,
            active_entities=active_entities,
            dm_ideas=payload.dm_ideas,
        )

        return SessionPrepSchema(**prep_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns/{name}/sessions/journey", response_model=dict)
@limiter.limit(settings.AI_RATE_LIMIT)
async def generate_journey(
    request: Request,
    name: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_member()),
):
    """Generate a chronological graph of visited locations."""
    try:
        from fastapi.concurrency import run_in_threadpool

        # Fetch all sessions in chronological order (oldest first)
        cursor = db.session_logs.find({"campaign_name": name}).sort("session_number", 1)
        past_sessions = await cursor.to_list(length=100)

        if not past_sessions:
            return {"nodes": []}

        graph_data = await run_in_threadpool(session_service.generate_journey_graph, past_sessions)
        return graph_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
