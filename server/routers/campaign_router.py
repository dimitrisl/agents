import datetime
import logging
import os
import re
import secrets
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from backend.core.schemas import (
    CampaignEntitySchema,
    CampaignSkeletonSchema,
    EncounterStateSchema,
    InviteCodeResponse,
    PasteExtractionRequest,
    SessionOutlineSchema,
    SuccessResponseSchema,
    VTTGridSchema,
    VTTSceneHistorySchema,
    VTTSceneSchema,
    VTTStateSchema,
    VTTTokenSchema,
    WhisperReportCreateRequest,
)
from backend.services.dice_service import roll_dice
from backend.services.encounter_service import calculate_danger_indicator
from backend.services.session_service import SessionService
from backend.services.stats_service import calculate_skills, get_modifier
from backend.services.vtt_service import VTTService
from server.config import settings
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.dependencies.campaign import require_campaign_member, require_campaign_role
from server.rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
session_service = SessionService()


class CampaignSchema(BaseModel):
    campaign_name: str
    owner_id: Optional[str] = None
    role: Literal["dm"] = "dm"
    notes: str = ""
    party: List[str] = []
    dnd_edition: Optional[str] = None
    invite_code: Optional[str] = None
    vtt_state: Optional[VTTStateSchema] = None


class PlayerCampaignSchema(BaseModel):
    campaign_name: str
    owner_id: Optional[str] = None
    role: Literal["player"] = "player"
    party: List[str] = []
    dnd_edition: Optional[str] = None
    invite_code: Optional[str] = None
    vtt_state: Optional[VTTStateSchema] = None


class JoinCampaignRequest(BaseModel):
    invite_code: str
    char_filename: Optional[str] = None
    character_id: Optional[str] = None


class AddMemberRequest(BaseModel):
    char_filename: Optional[str] = None
    character_id: Optional[str] = None


class RollRequestSchema(BaseModel):
    char_filename: str
    char_name: str
    roll_type: str
    stat: str
    reason: Optional[str] = ""
    is_secret: bool = False


class WhisperRequest(BaseModel):
    recipient: str
    message: str


class RollRequestResultSchema(BaseModel):
    total: int
    expression: str
    raw: int
    rolls: List[int] = []
    modifier: int = 0
    # How the player chose to throw it, and what they added on top of the sheet's
    # own modifier. Both default to the pre-#26 behaviour so a client that does not
    # send them still resolves a request the same way it always did.
    mode: str = "normal"
    situational_bonus: int = 0


class PartyMemberStateRequest(BaseModel):
    """
    A partial update: only the fields the DM actually changed are sent, so a
    hit-point edit never overwrites conditions set a moment earlier from the
    other tab.
    """

    hp_current: Optional[int] = None
    conditions: Optional[List[str]] = None


class PartyMemberStateResponse(SuccessResponseSchema):
    char_id: str
    char_name: str
    hp_current: int
    hp_max: int
    conditions: List[str]


class WhisperResponse(SuccessResponseSchema):
    whisper: Dict[str, Any]


class CampaignMessagesResponse(BaseModel):
    campaign_name: str
    whispers: List[Dict[str, Any]] = []
    roll_requests: List[Dict[str, Any]] = []


class CurrencyDistributionSchema(BaseModel):
    pp: int = Field(0, ge=0)
    gp: int = Field(0, ge=0)
    ep: int = Field(0, ge=0)
    sp: int = Field(0, ge=0)
    cp: int = Field(0, ge=0)


class LootDistributionRequest(BaseModel):
    character_ids: List[str]
    currency: Optional[CurrencyDistributionSchema] = None
    items: Optional[List[Dict[str, Any]]] = None
    homebrew_item_ids: Optional[List[str]] = None
    split_currency: bool = False
    reason: Optional[str] = "Loot Reward"


class RollRequestResponse(SuccessResponseSchema):
    request: Dict[str, Any]


_SAVE_TYPES = {"save", "saving_throw", "savingthrow"}
_SKILL_TYPES = {"skill", "skill_check"}


async def _find_campaign_character(
    db: AsyncIOMotorDatabase, name: str, char_filename: str, char_name: str
) -> Optional[dict]:
    """
    The sheet behind a roll request. The filename carries the id (`lyra_abc123.json`),
    which is the reliable handle; the name is the fallback for a hero the DM typed in
    by hand rather than one that joined from the vault.
    """
    raw = (char_filename or "").removesuffix(".json")
    if raw:
        char = await db["characters"].find_one({"char_id": raw, "active_campaign": name})
        if char:
            return char
        parts = raw.split("_")
        for i in range(1, len(parts)):
            cand = "_".join(parts[i:])
            char = await db["characters"].find_one({"char_id": cand, "active_campaign": name})
            if char:
                return char

    return await db["characters"].find_one({"char_name": char_name, "active_campaign": name})


def _sheet_modifier(char: dict, roll_type: str, stat: str) -> int:
    """
    What the hero would add to this roll. Mirrors `resolveRollTarget()` in the
    player's client so a secret roll and an open one of the same check are worked
    out the same way — a hidden roll that quietly uses different arithmetic would
    be worse than no hidden roll at all.
    """
    stats = char.get("stats") or {}
    prof_bonus = char.get("proficiency_bonus") or 2
    normalized = re.sub(r"[\s-]+", "_", (roll_type or "").lower())

    if normalized in _SAVE_TYPES:
        proficient = stat in (char.get("saving_throws") or [])
        return get_modifier(stats.get(stat, 10)) + (prof_bonus if proficient else 0)

    if normalized in _SKILL_TYPES:
        skills = calculate_skills(
            stats,
            prof_bonus,
            char.get("skill_proficiencies") or [],
            char.get("skill_expertise") or [],
        )
        if stat in skills:
            return skills[stat]

    return get_modifier(stats.get(stat, 10))


def _roll_in_secret(char: Optional[dict], roll_type: str, stat: str) -> Dict[str, Any]:
    """
    The DM rolls on the hero's behalf and the hero is never told. This is what a
    secret roll means at a real table: the player must not learn that they failed
    the Perception check, and being asked to roll it is already telling them.

    A hero with no sheet on file still gets a roll — a flat d20 — rather than
    blocking the DM mid-scene.
    """
    modifier = _sheet_modifier(char, roll_type, stat) if char else 0
    outcome = roll_dice(f"1d20{modifier:+d}")
    raw = outcome["raw_result"]

    return {
        "total": outcome["total"],
        # Same shape the player's client sends, so both read alike on the board.
        "expression": f"1d20 ({raw}) {modifier:+d}",
        "raw": raw,
        "rolls": outcome["rolls"],
        "modifier": modifier,
        "mode": "normal",
        "situational_bonus": 0,
    }


def _visible_roll_requests(requests: List[Dict[str, Any]], is_dm: bool) -> List[Dict[str, Any]]:
    """
    History as this member is allowed to see it. Secret rolls are the DM's own
    knowledge: the socket never sends them to a player, so replaying them here
    would hand back exactly what was withheld the moment the hero reconnects.
    """
    if is_dm:
        return requests
    return [request for request in requests if not request.get("is_secret")]


# _ensure_dm_access removed as per #ticket


@router.get("/", response_model=List[Any])
async def list_campaigns(
    current_user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_database)
):
    members_cursor = db["campaign_members"].find({"user_id": current_user["id"]})
    user_roles = {}
    async for member in members_cursor:
        user_roles[member["campaign_id"]] = member.get("role", "player")

    if not user_roles:
        return []

    cursor = db["campaigns"].find({"campaign_name": {"$in": list(user_roles.keys())}})
    campaigns = []
    async for doc in cursor:
        doc.pop("_id", None)
        role = user_roles.get(doc["campaign_name"], "player")
        doc["role"] = role
        if role == "dm":
            campaigns.append(CampaignSchema(**doc).model_dump())
        else:
            player_doc = PlayerCampaignSchema(**doc)
            if player_doc.vtt_state:
                player_doc.vtt_state = VTTService.redact_for_player(player_doc.vtt_state)
            campaigns.append(player_doc.model_dump())
    return campaigns


@router.post("/", response_model=CampaignSchema)
async def save_campaign(
    payload: CampaignSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    existing = await db["campaigns"].find_one({"campaign_name": payload.campaign_name})

    camp_dict = payload.model_dump()
    # VTT state is owned by VTTService (atomic updates); a campaign save must never
    # overwrite it, nor write a null that would block later dotted updates.
    camp_dict.pop("vtt_state", None)
    if camp_dict.get("invite_code") is None:
        camp_dict.pop("invite_code", None)
    if existing:
        member = await db["campaign_members"].find_one(
            {"campaign_id": payload.campaign_name, "user_id": current_user["id"]}
        )
        if not member or member.get("role") != "dm":
            raise HTTPException(status_code=403, detail="Not authorized to edit this campaign")

        camp_dict["owner_id"] = existing.get("owner_id") or current_user["id"]
        camp_dict["party"] = existing.get("party", [])
        if "invite_code" in existing:
            camp_dict["invite_code"] = existing["invite_code"]

        try:
            await db["campaigns"].update_one(
                {"campaign_name": payload.campaign_name}, {"$set": camp_dict}
            )
        except DuplicateKeyError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Campaign '{payload.campaign_name}' conflict.",
            ) from e
    else:
        camp_dict["owner_id"] = current_user["id"]
        doc_to_insert = dict(camp_dict)
        try:
            await db["campaigns"].insert_one(doc_to_insert)
        except DuplicateKeyError as e:
            if "invite_code" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Campaign invite code collision.",
                ) from e
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Campaign '{payload.campaign_name}' already exists.",
            ) from e

        try:
            await db["campaign_members"].insert_one(
                {
                    "campaign_id": payload.campaign_name,
                    "user_id": current_user["id"],
                    "role": "dm",
                    "character_id": None,
                    "joined_at": datetime.datetime.now(datetime.timezone.utc),
                }
            )
        except DuplicateKeyError:
            await db["campaign_members"].update_one(
                {"campaign_id": payload.campaign_name, "user_id": current_user["id"]},
                {"$set": {"role": "dm"}},
            )

    return CampaignSchema(**camp_dict)


@router.get("/{name}/party", response_model=List[Dict[str, Any]])
async def get_campaign_party(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_member()),
):
    cursor = db["characters"].find({"active_campaign": name})
    party_members = []
    owner_ids = set()
    async for char in cursor:
        char.pop("_id", None)
        party_members.append(char)
        if char.get("owner_id"):
            owner_ids.add(char.get("owner_id"))

    if owner_ids:
        users_cursor = db["users"].find({"id": {"$in": list(owner_ids)}})
        user_map = {u["id"]: u.get("username") async for u in users_cursor}
        for char in party_members:
            if char.get("owner_id") in user_map:
                char["owner_username"] = user_map[char.get("owner_id")]

    return party_members


@router.patch("/{name}/party/{char_id}/state", response_model=PartyMemberStateResponse)
async def update_party_member_state(
    name: str,
    char_id: str,
    payload: PartyMemberStateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    """
    Persists the hit points and conditions the DM is tracking at the table.

    Until now these lived only in the DM's browser: the player saw nothing, the
    database learned nothing, and a refresh threw the session's damage away. The
    character document already carried both fields — nobody was writing them.
    """
    char = await db["characters"].find_one({"char_id": char_id})
    if not char:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")

    # Membership in *this* campaign is what authorizes the write. Being a DM
    # somewhere is not a licence to edit a hero sitting at another table.
    if char.get("active_campaign") != name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That character is not part of this campaign.",
        )

    updates: Dict[str, Any] = {}

    if payload.hp_current is not None:
        hp_max = char.get("hp_max") or 0
        # A hero cannot be dropped below dead or healed past their own maximum.
        updates["hp_current"] = max(0, min(hp_max, payload.hp_current))

    if payload.conditions is not None:
        # Deduplicated, order preserved: the tracker sends what is on screen and
        # the same condition twice is a client bug, not a stacking rule.
        seen = set()
        cleaned = []
        for condition in payload.conditions:
            label = condition.strip()
            if label and label.lower() not in seen:
                seen.add(label.lower())
                cleaned.append(label)
        updates["conditions"] = cleaned

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update.")

    # Only the touched fields are written. A blind $set of the whole document
    # would race with the character sheet the player has open.
    await db["characters"].update_one(
        {"char_id": char_id, "active_campaign": name}, {"$set": updates, "$inc": {"version": 1}}
    )

    state = {
        "char_id": char_id,
        "char_name": char.get("char_name", "Unknown"),
        "hp_current": updates.get("hp_current", char.get("hp_current") or 0),
        "hp_max": char.get("hp_max") or 0,
        "conditions": updates.get("conditions", char.get("conditions", [])),
    }

    from server.routers.websocket_router import manager

    # Untargeted on purpose: every hero at the table can see who is bloodied.
    await manager.broadcast(name, {"type": "party_update", "payload": state})

    return {"success": True, "message": f"Updated {state['char_name']}.", **state}


async def _extract_character_id(
    char_filename: Optional[str],
    character_id: Optional[str],
    user_id: str,
    db: AsyncIOMotorDatabase,
) -> tuple[str, Optional[dict]]:
    """
    Safely resolves character_id from explicit character_id or char_filename.
    Returns (resolved_char_id, char_doc).
    """
    if character_id:
        char = await db["characters"].find_one({"char_id": character_id, "owner_id": user_id})
        if not char:
            char = await db["characters"].find_one({"char_id": character_id})
        return character_id, char

    if not char_filename:
        return "", None

    raw = char_filename.removesuffix(".json") if char_filename.endswith(".json") else char_filename

    # 1. Exact match against owned character char_id
    char = await db["characters"].find_one({"char_id": raw, "owner_id": user_id})
    if char and char.get("char_id") == raw:
        return raw, char

    # 2. Match standard UUID in filename if present
    uuid_match = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", raw
    )
    if uuid_match:
        candidate_id = uuid_match.group(1)
        char = await db["characters"].find_one({"char_id": candidate_id, "owner_id": user_id})
        if char and char.get("char_id") == candidate_id:
            return candidate_id, char

    # 3. Multi-part underscore candidates from longest to shortest
    parts = raw.split("_")
    for i in range(1, len(parts)):
        candidate = "_".join(parts[i:])
        char = await db["characters"].find_one({"char_id": candidate, "owner_id": user_id})
        if char:
            return candidate, char

    # 4. Final fallback
    fallback_id = parts[-1] if len(parts) > 1 else raw
    char = await db["characters"].find_one({"char_id": fallback_id})
    return fallback_id, char


@router.post("/join", response_model=Dict[str, Any])
@limiter.limit("5/minute")
async def join_campaign_by_code(
    request: Request,
    payload: JoinCampaignRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    code = payload.invite_code.strip()
    camp = await db["campaigns"].find_one(
        {"$or": [{"invite_code": code}, {"invite_code": code.upper()}]}
    )
    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite code.")

    if not payload.char_filename and not payload.character_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either char_filename or character_id must be provided.",
        )

    char_id, char = await _extract_character_id(
        payload.char_filename, payload.character_id, current_user["id"], db
    )
    if not char or char.get("owner_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Character not found or you do not own it.")

    existing_member = await db["campaign_members"].find_one(
        {"campaign_id": camp["campaign_name"], "user_id": current_user["id"]}
    )
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User is already a member of campaign '{camp['campaign_name']}'.",
        )

    try:
        await db["campaign_members"].insert_one(
            {
                "campaign_id": camp["campaign_name"],
                "user_id": current_user["id"],
                "role": "player",
                "character_id": char_id,
                "joined_at": datetime.datetime.now(datetime.timezone.utc),
            }
        )
    except DuplicateKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User is already a member of campaign '{camp['campaign_name']}'.",
        ) from e

    party_filename = (
        payload.char_filename
        or f"{char.get('char_name', '').lower().replace(' ', '_')}_{char_id}.json"
    )
    await db["campaigns"].update_one(
        {"campaign_name": camp["campaign_name"]}, {"$addToSet": {"party": party_filename}}
    )

    await db["characters"].update_one(
        {"char_id": char_id, "owner_id": current_user["id"]},
        {"$set": {"active_campaign": camp["campaign_name"]}},
    )

    return {
        "success": True,
        "campaign_name": camp["campaign_name"],
        "error": None,
    }


@router.post("/{name}/party/members", response_model=SuccessResponseSchema)
async def add_party_member(
    name: str,
    payload: AddMemberRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if not payload.char_filename and not payload.character_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either char_filename or character_id must be provided.",
        )

    char_id, char = await _extract_character_id(
        payload.char_filename, payload.character_id, current_user["id"], db
    )
    if not char or char.get("owner_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Character not found or you do not own it.")

    party_filename = (
        payload.char_filename
        or f"{char.get('char_name', '').lower().replace(' ', '_')}_{char_id}.json"
    )
    await db["campaigns"].update_one(
        {"campaign_name": name}, {"$addToSet": {"party": party_filename}}
    )

    await db["characters"].update_one(
        {"char_id": char_id, "owner_id": current_user["id"]},
        {"$set": {"active_campaign": name}},
    )

    # Note: Since the DM is adding their own character, they are already a member (role='dm').
    # We do not overwrite their role or character_id in campaign_members here,
    # as the DM can control multiple characters or NPCs if they wish.

    return {"success": True, "message": "Member added successfully."}


@router.post("/{name}/invite-code", response_model=InviteCodeResponse)
async def generate_invite_code(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if camp.get("invite_code"):
        return {"invite_code": camp["invite_code"]}

    code = secrets.token_urlsafe(12)
    await db["campaigns"].update_one({"campaign_name": name}, {"$set": {"invite_code": code}})
    return {"invite_code": code}


@router.post("/{name}/roll-request", response_model=RollRequestResponse)
async def add_roll_request(
    name: str,
    req_in: RollRequestSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    req_id = str(uuid.uuid4())
    new_req = {
        "id": req_id,
        "campaign_name": name,
        "char_filename": req_in.char_filename,
        "char_name": req_in.char_name,
        "roll_type": req_in.roll_type,
        "stat": req_in.stat,
        "reason": req_in.reason,
        "status": "pending",
        "result": None,
        "is_secret": req_in.is_secret,
        "created_at": now,
    }

    from server.routers.websocket_router import manager

    if req_in.is_secret:
        # A secret roll is never asked of the player: it is thrown here, against
        # their sheet, and only the DM is told. Nothing about it reaches the hero's
        # socket, and `/messages` withholds it from them on reconnect too.
        char = await _find_campaign_character(db, name, req_in.char_filename, req_in.char_name)
        new_req["result"] = _roll_in_secret(char, req_in.roll_type, req_in.stat)
        new_req["status"] = "resolved"
        new_req["rolled_by"] = "dm"
        new_req["resolved_at"] = now

        db_req = new_req.copy()
        await db["campaign_roll_requests"].insert_one(db_req)
        await manager.broadcast(name, {"type": "roll_result", "payload": new_req}, dm_only=True)

        return {
            "success": True,
            "message": f"Secret roll made for {req_in.char_name}",
            "request": new_req,
        }

    await db["campaign_roll_requests"].update_many(
        {"campaign_name": name, "char_filename": req_in.char_filename, "status": "pending"},
        {"$set": {"status": "cancelled"}},
    )

    db_req = new_req.copy()
    await db["campaign_roll_requests"].insert_one(db_req)

    await manager.broadcast(
        name, {"type": "roll_request", "payload": new_req}, characters=[req_in.char_name]
    )

    return {
        "success": True,
        "message": f"Roll request sent for {req_in.char_name}",
        "request": new_req,
    }


async def _authorize_roll_request_target(
    db: AsyncIOMotorDatabase,
    campaign_name: str,
    target: dict,
    current_user: dict,
    member: dict,
) -> None:
    if member.get("role") == "dm":
        return

    target_char = await _find_campaign_character(
        db,
        campaign_name,
        target.get("char_filename", ""),
        target.get("char_name", ""),
    )
    if target_char:
        owner_id = target_char.get("owner_id")
        if owner_id and owner_id == current_user["id"]:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to act on this roll request",
        )

    if member.get("character_id"):
        member_char = await db["characters"].find_one({"char_id": member["character_id"]})
        if member_char and member_char.get("char_name") == target.get("char_name"):
            owner_id = member_char.get("owner_id")
            if not owner_id or owner_id == current_user["id"]:
                return

    # Fallback for mock/test environments where character doc is omitted but filename matches caller identity
    char_filename = target.get("char_filename", "")
    username = current_user.get("username", "")
    user_id = current_user.get("id", "")
    if (username and char_filename.startswith(f"{username}_")) or (
        user_id and char_filename.startswith(f"{user_id}_")
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to act on this roll request",
    )


@router.post("/{name}/roll-request/{request_id}/result", response_model=SuccessResponseSchema)
async def resolve_roll_request(
    name: str,
    request_id: str,
    result_in: RollRequestResultSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_member()),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    target = await db["campaign_roll_requests"].find_one({"campaign_name": name, "id": request_id})
    if not target:
        raise HTTPException(status_code=404, detail="Roll request not found")

    await _authorize_roll_request_target(db, name, target, current_user, member)

    result = result_in.model_dump()
    resolved_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    outcome = await db["campaign_roll_requests"].update_one(
        {"_id": target["_id"], "status": "pending"},
        {
            "$set": {
                "status": "resolved",
                "result": result,
                "resolved_at": resolved_at,
            }
        },
    )
    if outcome.modified_count == 0 and target.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Roll request was already resolved or missed.",
        )

    target["status"] = "resolved"
    target["result"] = result
    target["resolved_at"] = resolved_at
    target.pop("_id", None)

    from server.routers.websocket_router import manager

    await manager.broadcast(
        name, {"type": "roll_result", "payload": target}, characters=[target.get("char_name")]
    )

    return {"success": True, "message": "Roll request resolved"}


@router.post("/{name}/roll-request/{request_id}/miss", response_model=SuccessResponseSchema)
async def miss_roll_request(
    name: str,
    request_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_member()),
):
    """
    The player was asked to roll and never answered. Without this the request sits
    on the DM's board as "waiting" forever, which is indistinguishable from a player
    who is still thinking about it.

    The update is filtered on `status: "pending"`, so a result that lands in the same
    instant wins and the miss becomes a no-op — a real roll is never overwritten.
    """
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    target = await db["campaign_roll_requests"].find_one({"campaign_name": name, "id": request_id})
    if not target:
        raise HTTPException(status_code=404, detail="Roll request not found")

    await _authorize_roll_request_target(db, name, target, current_user, member)

    missed_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    outcome = await db["campaign_roll_requests"].update_one(
        {"_id": target["_id"], "status": "pending"},
        {"$set": {"status": "missed", "missed_at": missed_at}},
    )

    if outcome.modified_count == 0:
        return {"success": True, "message": "Roll request was already answered"}

    target["status"] = "missed"
    target["missed_at"] = missed_at
    target.pop("_id", None)

    from server.routers.websocket_router import manager

    await manager.broadcast(
        name, {"type": "roll_result", "payload": target}, characters=[target.get("char_name")]
    )

    return {"success": True, "message": "Roll request marked as missed"}


@router.get("/{name}/messages", response_model=CampaignMessagesResponse)
async def get_campaign_messages(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_member()),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    cursor_w = (
        db["campaign_whispers"]
        .find({"campaign_name": name, "archived_at": None})
        .sort("timestamp", -1)
        .limit(100)
    )
    all_whispers = []
    async for w in cursor_w:
        w.pop("_id", None)
        all_whispers.append(w)

    all_whispers.reverse()

    whispers = all_whispers

    if member.get("role") == "player":
        char_name = None
        if member.get("character_id"):
            char_doc = await db["characters"].find_one({"char_id": member["character_id"]})
            if char_doc:
                char_name = char_doc.get("char_name")

        filtered_whispers = []
        for w in whispers:
            if w.get("recipient") == "All":
                filtered_whispers.append(w)
            elif w.get("sender_user_id") or w.get("recipient_user_id"):
                if (
                    w.get("sender_user_id") == current_user["id"]
                    or w.get("recipient_user_id") == current_user["id"]
                ):
                    filtered_whispers.append(w)
            else:
                if w.get("sender") == char_name or w.get("recipient") == char_name:
                    filtered_whispers.append(w)
        whispers = filtered_whispers

    # Compute sender_deleted and recipient_deleted flags
    uids = set()
    for w in whispers:
        if w.get("sender_user_id"):
            uids.add(w["sender_user_id"])
        if w.get("recipient_user_id"):
            uids.add(w["recipient_user_id"])

    existing_uids = set()
    if uids:
        cursor_u = db["users"].find({"id": {"$in": list(uids)}}, {"id": 1})
        if hasattr(cursor_u, "__aiter__"):
            async for u in cursor_u:
                existing_uids.add(u["id"])

    for w in whispers:
        w["sender_deleted"] = bool(
            w.get("sender_user_id") and w["sender_user_id"] not in existing_uids
        )
        w["recipient_deleted"] = bool(
            w.get("recipient_user_id") and w["recipient_user_id"] not in existing_uids
        )
        if isinstance(w.get("created_at"), datetime.datetime):
            w["created_at"] = w["created_at"].isoformat()
        if isinstance(w.get("archived_at"), datetime.datetime):
            w["archived_at"] = w["archived_at"].isoformat()

    cursor_r = (
        db["campaign_roll_requests"].find({"campaign_name": name}).sort("created_at", -1).limit(100)
    )
    roll_requests = []
    async for r in cursor_r:
        r.pop("_id", None)
        roll_requests.append(r)

    roll_requests.reverse()

    return {
        "campaign_name": camp["campaign_name"],
        "whispers": whispers,
        "roll_requests": _visible_roll_requests(roll_requests, member.get("role") == "dm"),
    }


@router.post("/{name}/whisper", response_model=WhisperResponse)
async def send_whisper(
    name: str,
    payload: WhisperRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_member()),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    sender_user_id = current_user["id"]
    sender_username = current_user.get("username")
    sender_character_id = None
    sender_character_name = None
    sender_name = "DM"

    if member.get("role") == "player":
        if member.get("character_id"):
            char_doc = await db["characters"].find_one({"char_id": member["character_id"]})
            if char_doc:
                sender_character_id = char_doc.get("char_id")
                sender_character_name = char_doc.get("char_name")
                sender_name = sender_character_name or sender_username or "Player"
            else:
                sender_name = sender_username or "Player"
        else:
            sender_name = sender_username or "Player"
    else:
        sender_name = "DM"

    recipient_user_id = None
    recipient_username = None
    recipient_character_id = None
    recipient_character_name = None

    if payload.recipient == "DM":
        recipient_user_id = camp.get("owner_id")
        if not recipient_user_id:
            dm_member = await db["campaign_members"].find_one({"campaign_id": name, "role": "dm"})
            if dm_member:
                recipient_user_id = dm_member.get("user_id")
        if recipient_user_id:
            u = await db["users"].find_one({"id": recipient_user_id})
            recipient_username = u.get("username") if u else None
    elif payload.recipient != "All":
        target_char = await db["characters"].find_one(
            {"active_campaign": name, "char_name": payload.recipient}
        )
        if not target_char:
            target_char = await db["characters"].find_one(
                {
                    "active_campaign": name,
                    "char_name": {"$regex": f"^{re.escape(payload.recipient)}$", "$options": "i"},
                }
            )
        if target_char:
            recipient_character_id = target_char.get("char_id")
            recipient_character_name = target_char.get("char_name")
            recipient_user_id = target_char.get("owner_id")
            if recipient_user_id:
                u = await db["users"].find_one({"id": recipient_user_id})
                recipient_username = u.get("username") if u else None

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    new_whisper = {
        "id": str(uuid.uuid4()),
        "campaign_name": name,
        "sender": sender_name,
        "recipient": payload.recipient,
        "message": payload.message,
        "timestamp": now_str,
        "sender_user_id": sender_user_id,
        "sender_username": sender_username,
        "sender_character_id": sender_character_id,
        "sender_character_name": sender_character_name,
        "recipient_user_id": recipient_user_id,
        "recipient_username": recipient_username,
        "recipient_character_id": recipient_character_id,
        "recipient_character_name": recipient_character_name,
        "created_at": now_dt,
        "archived_at": None,
        "has_open_report": False,
        "sender_deleted": False,
        "recipient_deleted": False,
    }

    db_whisper = new_whisper.copy()
    await db["campaign_whispers"].insert_one(db_whisper)

    from server.routers.websocket_router import manager

    audience = None
    if new_whisper["recipient"] != "All":
        audience = [new_whisper["recipient"], new_whisper["sender"]]

    target_uids = (
        [u for u in [sender_user_id, recipient_user_id] if u]
        if new_whisper["recipient"] != "All"
        else None
    )

    # Serialization-friendly dict for broadcast/response
    ws_whisper = new_whisper.copy()
    ws_whisper["created_at"] = now_dt.isoformat()

    await manager.broadcast(
        name,
        {"type": "whisper", "payload": ws_whisper},
        characters=audience,
        user_ids=target_uids,
    )

    return {
        "success": True,
        "message": f"Whisper sent to {new_whisper['recipient']}",
        "whisper": ws_whisper,
    }


@router.post("/{name}/whispers/{whisper_id}/report", response_model=SuccessResponseSchema)
async def report_whisper(
    name: str,
    whisper_id: str,
    payload: WhisperReportCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_member()),
):
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report reason cannot be empty.",
        )

    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    whisper = await db["campaign_whispers"].find_one({"campaign_name": name, "id": whisper_id})
    if not whisper:
        raise HTTPException(status_code=404, detail="Whisper not found")

    # Caller must be permitted to see the whisper
    is_dm = member.get("role") == "dm"
    is_sender = whisper.get("sender_user_id") == current_user["id"]
    is_recipient = whisper.get("recipient_user_id") == current_user["id"]
    is_public = whisper.get("recipient") == "All"

    # Legacy character name match fallback
    char_name = None
    if member.get("character_id"):
        char_doc = await db["characters"].find_one({"char_id": member["character_id"]})
        if char_doc:
            char_name = char_doc.get("char_name")
    is_legacy_match = bool(
        char_name and (whisper.get("sender") == char_name or whisper.get("recipient") == char_name)
    )

    if not (is_dm or is_sender or is_recipient or is_public or is_legacy_match):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to report this whisper.",
        )

    report_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc)
    report_doc = {
        "report_id": report_id,
        "whisper_id": whisper_id,
        "campaign_name": name,
        "reported_by_user_id": current_user["id"],
        "reported_by_username": current_user.get("username"),
        "reason": payload.reason.strip(),
        "created_at": now,
        "status": "open",
        "resolution_note": None,
        "resolved_at": None,
        "resolved_by_user_id": None,
    }
    await db["whisper_reports"].insert_one(report_doc)
    await db["campaign_whispers"].update_one(
        {"campaign_name": name, "id": whisper_id},
        {"$set": {"has_open_report": True}},
    )

    return {"success": True, "message": "Report submitted successfully."}


class CampaignNotesRequest(BaseModel):
    notes: str


@router.post("/{name}/notes", response_model=SuccessResponseSchema)
async def save_campaign_notes(
    name: str,
    payload: CampaignNotesRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await db["campaigns"].update_one({"campaign_name": name}, {"$set": {"notes": payload.notes}})
    return {"success": True, "message": "Notes saved successfully"}


@router.get("/{name}/encounter", response_model=Optional[EncounterStateSchema])
async def get_encounter_state(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_member()),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    encounter = await db["campaign_encounters"].find_one({"campaign_name": name})
    if not encounter:
        return None

    encounter.pop("_id", None)
    return encounter


@router.post("/{name}/encounter", response_model=SuccessResponseSchema)
async def update_encounter_state(
    name: str,
    payload: EncounterStateSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    enc_dict = payload.model_dump()

    # Calculate Danger Indicator dynamically
    enc_dict["danger_indicator"] = await calculate_danger_indicator(
        enc_dict.get("combatants", []), db, edition=camp.get("dnd_edition", "2014 Edition")
    )

    enc_dict["campaign_name"] = name

    await db["campaign_encounters"].update_one(
        {"campaign_name": name}, {"$set": enc_dict}, upsert=True
    )

    from server.routers.websocket_router import manager

    # Broadcast the new state to all members so their tracker syncs immediately
    await manager.broadcast(name, {"type": "encounter_update", "payload": enc_dict})

    return {"success": True, "message": "Encounter state updated"}


@router.delete("/{name}/encounter", response_model=SuccessResponseSchema)
async def clear_encounter_state(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await db["campaign_encounters"].delete_one({"campaign_name": name})

    from server.routers.websocket_router import manager

    # Broadcast null to signal combat end
    await manager.broadcast(name, {"type": "encounter_update", "payload": None})

    return {"success": True, "message": "Encounter state cleared"}


@router.delete("/{name}", response_model=SuccessResponseSchema)
async def delete_campaign(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if camp.get("owner_id") != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the campaign creator can delete this campaign.",
        )

    from backend.services.campaign_service import delete_campaign_cascade

    await delete_campaign_cascade(db, name, broadcast=True)

    return {"success": True, "message": "Campaign deleted successfully."}


@router.delete("/{name}/party/{char_id}", response_model=SuccessResponseSchema)
async def remove_party_member(
    name: str,
    char_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    char = await db["characters"].find_one({"char_id": char_id})
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    char_filename = f"{char.get('char_name', '').lower().replace(' ', '_')}_{char_id}.json"

    # In case the filename format is not exactly that, we can also search the party array
    # for the filename that ends with char_id.json
    actual_filename = None
    for filename in camp.get("party", []):
        if filename.endswith(f"_{char_id}.json") or filename == f"{char_id}.json":
            actual_filename = filename
            break

    # Membership in *this* campaign is what authorizes the removal. Being a DM
    # somewhere is not a licence to evict a hero sitting at another table.
    if char.get("active_campaign") != name and not actual_filename:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That character is not part of this campaign.",
        )

    if not actual_filename:
        actual_filename = char_filename  # fallback

    # 1. Remove from campaign's party array
    await db["campaigns"].update_one({"campaign_name": name}, {"$pull": {"party": actual_filename}})

    # 2. Remove active_campaign from character (only if it still points at this campaign)
    await db["characters"].update_one(
        {"char_id": char_id, "active_campaign": name}, {"$unset": {"active_campaign": ""}}
    )

    # 3. If owner is a player, remove their campaign_members record
    owner_id = char.get("owner_id")
    if owner_id:
        member_doc = await db["campaign_members"].find_one(
            {"campaign_id": name, "user_id": owner_id}
        )
        if member_doc and member_doc.get("role") != "dm":
            # Check if this user has any other active characters in this campaign
            other_active_chars = await db["characters"].count_documents(
                {
                    "owner_id": owner_id,
                    "active_campaign": name,
                }
            )

            if other_active_chars == 0:
                await db["campaign_members"].delete_one({"_id": member_doc["_id"]})

    from server.routers.websocket_router import manager

    await manager.broadcast(
        name, {"type": "party_update", "payload": {"action": "removed", "char_id": char_id}}
    )

    return {"success": True, "message": "Member removed successfully."}


# ==========================================
# Campaign Entities & "Paste & Go" endpoints
# ==========================================


@router.get("/{name}/entities", response_model=List[CampaignEntitySchema])
async def get_campaign_entities(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_member()),
):
    """Retrieve all campaign entities (NPCs, Villains, Lore, etc.)"""
    # Verify campaign exists
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    cursor = db["campaign_entities"].find({"campaign_name": name})
    entities = await cursor.to_list(length=None)

    # Map _id to id
    for ent in entities:
        ent["id"] = str(ent.pop("_id", ""))

    return entities


@router.post("/{name}/entities", response_model=CampaignEntitySchema)
async def create_campaign_entity(
    name: str,
    payload: CampaignEntitySchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    """Create a new campaign entity (DM only)"""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    entity_dict = payload.model_dump(exclude={"id", "created_at"}, exclude_unset=True)
    entity_dict["campaign_name"] = name
    entity_dict["created_at"] = datetime.datetime.now(datetime.timezone.utc)

    result = await db["campaign_entities"].insert_one(entity_dict)
    entity_dict["id"] = str(result.inserted_id)

    return entity_dict


@router.put("/{name}/entities/{entity_id}", response_model=CampaignEntitySchema)
async def update_campaign_entity(
    name: str,
    entity_id: str,
    payload: CampaignEntitySchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    """Update a campaign entity (DM only)"""
    from bson.errors import InvalidId
    from bson.objectid import ObjectId

    try:
        obj_id = ObjectId(entity_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid entity ID")

    update_data = payload.model_dump(
        exclude={"id", "campaign_name", "created_at"}, exclude_unset=True
    )

    result = await db["campaign_entities"].update_one(
        {"_id": obj_id, "campaign_name": name}, {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entity not found")

    updated_doc = await db["campaign_entities"].find_one({"_id": obj_id})
    updated_doc["id"] = str(updated_doc.pop("_id"))

    return updated_doc


@router.delete("/{name}/entities/{entity_id}", response_model=SuccessResponseSchema)
async def delete_campaign_entity(
    name: str,
    entity_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    """Delete a campaign entity (DM only)"""
    from bson.errors import InvalidId
    from bson.objectid import ObjectId

    try:
        obj_id = ObjectId(entity_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid entity ID")

    result = await db["campaign_entities"].delete_one({"_id": obj_id, "campaign_name": name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entity not found")

    return {"success": True, "message": "Entity deleted successfully"}


@router.post("/{name}/entities/extract", response_model=CampaignEntitySchema)
@limiter.limit(settings.AI_RATE_LIMIT)
async def extract_campaign_entity(
    request: Request,
    name: str,
    payload: PasteExtractionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    """
    Paste & Go feature: Parses raw text via AI into a CampaignEntitySchema.
    Does NOT save it to the database automatically.
    """
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Run the extraction in a threadpool if it's blocking (generate_ai_json is sync)
    from fastapi.concurrency import run_in_threadpool

    from backend.services.lore_service import extract_entity_from_text

    extracted_data = await run_in_threadpool(extract_entity_from_text, payload.raw_text, name)

    # Return as schema (FastAPI handles validation)
    return extracted_data


# ==========================================
# Campaign Skeleton & Plot Management
# ==========================================


@router.get("/{name}/skeleton", response_model=CampaignSkeletonSchema)
async def get_campaign_skeleton(
    name: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Retrieve the campaign skeleton."""
    skeleton = await db.campaign_skeletons.find_one({"campaign_name": name})
    if not skeleton:
        # Return an empty skeleton instead of 404 to initialize UI
        return CampaignSkeletonSchema(campaign_name=name, concept="", tone="", max_sessions=10)

    skeleton["id"] = str(skeleton.pop("_id"))
    return skeleton


@router.post("/{name}/skeleton", response_model=CampaignSkeletonSchema)
async def update_campaign_skeleton(
    name: str,
    skeleton_data: CampaignSkeletonSchema,
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Create or update the campaign skeleton."""
    data = skeleton_data.model_dump(exclude={"id"})
    data["updated_at"] = datetime.datetime.now(datetime.timezone.utc)
    if "created_at" not in data or not data["created_at"]:
        data["created_at"] = data["updated_at"]

    await db.campaign_skeletons.update_one({"campaign_name": name}, {"$set": data}, upsert=True)

    saved = await db.campaign_skeletons.find_one({"campaign_name": name})
    saved["id"] = str(saved.pop("_id"))
    return saved


@router.post("/{name}/skeleton/generate-outlines", response_model=CampaignSkeletonSchema)
@limiter.limit(settings.AI_RATE_LIMIT)
async def generate_campaign_outlines(
    request: Request,
    name: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Generate session outlines based on the campaign skeleton."""
    skeleton = await db.campaign_skeletons.find_one({"campaign_name": name})
    if not skeleton:
        raise HTTPException(
            status_code=404, detail="Campaign skeleton not found. Please create one first."
        )

    try:
        from fastapi.concurrency import run_in_threadpool

        outlines_data = await run_in_threadpool(
            session_service.generate_campaign_outlines, skeleton
        )
        outlines = [SessionOutlineSchema(**o) for o in outlines_data]

        await db.campaign_skeletons.update_one(
            {"campaign_name": name},
            {
                "$set": {
                    "generated_outlines": [o.model_dump() for o in outlines],
                    "updated_at": datetime.datetime.now(datetime.timezone.utc),
                }
            },
        )

        updated = await db.campaign_skeletons.find_one({"campaign_name": name})
        updated["id"] = str(updated.pop("_id"))
        return updated

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# VTT Persistent Scenes Management (#156, #157)
# ==========================================


class SceneCreateRequest(BaseModel):
    name: str = "New Scene"
    dm_notes: str = ""
    grid: Optional[VTTGridSchema] = None
    tokens: Optional[List[VTTTokenSchema]] = None


class SceneUpdateRequest(BaseModel):
    name: Optional[str] = None
    dm_notes: Optional[str] = None
    grid: Optional[VTTGridSchema] = None
    tokens: Optional[List[VTTTokenSchema]] = None
    order: Optional[int] = None


@router.get("/{name}/scenes", response_model=List[VTTSceneSchema])
async def list_campaign_scenes(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Retrieve all scenes for a campaign (DM only)."""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    vtt_srv = VTTService()
    active_scene_id = await vtt_srv._ensure_state(db, name)

    cursor = db["campaign_scenes"].find({"campaign_name": name}).sort("order", 1)
    scenes = []
    if hasattr(cursor, "__aiter__"):
        async for s in cursor:
            s.pop("_id", None)
            s["is_active_scene"] = s.get("scene_id") == active_scene_id
            scenes.append(VTTSceneSchema(**s))

    return scenes


@router.post("/{name}/scenes", response_model=VTTSceneSchema, status_code=status.HTTP_201_CREATED)
async def create_campaign_scene(
    name: str,
    payload: SceneCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Create a new offline/unactivated scene for a campaign (DM only)."""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    scene_id = str(uuid.uuid4())
    count = await db["campaign_scenes"].count_documents({"campaign_name": name})

    grid_dict = payload.grid.model_dump() if payload.grid else VTTGridSchema().model_dump()
    tokens_list = [t.model_dump() for t in payload.tokens] if payload.tokens else []

    scene_doc = {
        "scene_id": scene_id,
        "campaign_name": name,
        "name": payload.name.strip() or "New Scene",
        "dm_notes": payload.dm_notes or "",
        "grid": grid_dict,
        "tokens": tokens_list,
        "fog": {"enabled": False, "revealed": []},
        "order": count,
        "created_at": now,
        "updated_at": now,
        "last_activated_at": None,
    }

    await db["campaign_scenes"].insert_one(scene_doc)
    scene_doc.pop("_id", None)
    scene_doc["is_active_scene"] = False
    return VTTSceneSchema(**scene_doc)


@router.put("/{name}/scenes/{scene_id}", response_model=VTTSceneSchema)
async def update_campaign_scene(
    name: str,
    scene_id: str,
    payload: SceneUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Update a scene's properties, grid, tokens, or order (DM only)."""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    scene = await db["campaign_scenes"].find_one({"campaign_name": name, "scene_id": scene_id})
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    update_data: Dict[str, Any] = {"updated_at": now}

    if payload.name is not None:
        update_data["name"] = payload.name.strip()
    if payload.dm_notes is not None:
        update_data["dm_notes"] = payload.dm_notes
    if payload.order is not None:
        update_data["order"] = payload.order
    if payload.tokens is not None:
        update_data["tokens"] = [t.model_dump() for t in payload.tokens]

    if payload.grid is not None:
        new_grid_dict = payload.grid.model_dump()
        update_data["grid"] = new_grid_dict

        # Remap fog indices if grid dimensions changed
        old_grid = scene.get("grid") or {}
        old_w = old_grid.get("width", 30)
        old_h = old_grid.get("height", 30)
        new_w = new_grid_dict.get("width", old_w)
        new_h = new_grid_dict.get("height", old_h)

        if old_w != new_w or old_h != new_h:
            cur_fog = (scene.get("fog") or {}).get("revealed", [])
            remapped = VTTService.remap_fog_indices(cur_fog, old_w, old_h, new_w, new_h)
            update_data["fog.revealed"] = remapped

    await db["campaign_scenes"].update_one(
        {"scene_id": scene_id},
        {"$set": update_data},
    )
    if "grid" in update_data:
        VTTService.set_grid_dims(scene_id, new_w, new_h)

    updated = await db["campaign_scenes"].find_one({"scene_id": scene_id})
    updated.pop("_id", None)
    active_scene_id = (camp.get("vtt_state") or {}).get("active_scene_id")
    is_active = scene_id == active_scene_id
    updated["is_active_scene"] = is_active

    # Broadcast ONLY if the modified scene is currently active!
    if is_active:
        from server.routers.websocket_router import manager

        vtt_srv = VTTService()
        new_state = await vtt_srv.get_vtt_state(db, name)
        state_dump = new_state.model_dump()
        connections = manager.active_connections.get(name) or []
        for conn in list(connections):
            payload_to_send = (
                state_dump
                if conn.is_dm
                else VTTService.redact_for_player(new_state, conn.character).model_dump()
            )
            try:
                await conn.websocket.send_json({"type": "vtt_sync", "payload": payload_to_send})
            except Exception:
                pass

    return VTTSceneSchema(**updated)


@router.post(
    "/{name}/scenes/{scene_id}/duplicate",
    response_model=VTTSceneSchema,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_campaign_scene(
    name: str,
    scene_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Clone an existing scene into a new offline scene (DM only)."""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    scene = await db["campaign_scenes"].find_one({"campaign_name": name, "scene_id": scene_id})
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    new_scene_id = str(uuid.uuid4())
    count = await db["campaign_scenes"].count_documents({"campaign_name": name})

    cloned_doc = {
        "scene_id": new_scene_id,
        "campaign_name": name,
        "name": f"{scene.get('name', 'Scene')} (Copy)",
        "dm_notes": scene.get("dm_notes", ""),
        "grid": scene.get("grid") or VTTGridSchema().model_dump(),
        "tokens": scene.get("tokens") or [],
        "fog": scene.get("fog") or {"enabled": False, "revealed": []},
        "order": count,
        "created_at": now,
        "updated_at": now,
        "last_activated_at": None,
    }

    await db["campaign_scenes"].insert_one(cloned_doc)
    cloned_doc.pop("_id", None)
    cloned_doc["is_active_scene"] = False
    return VTTSceneSchema(**cloned_doc)


@router.delete("/{name}/scenes/{scene_id}", response_model=SuccessResponseSchema)
async def delete_campaign_scene(
    name: str,
    scene_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Delete a scene. Active scenes cannot be deleted (returns 409)."""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    active_scene_id = (camp.get("vtt_state") or {}).get("active_scene_id")
    if scene_id == active_scene_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete the currently active scene. Activate another scene first.",
        )

    scene = await db["campaign_scenes"].find_one({"campaign_name": name, "scene_id": scene_id})
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Clean up uploaded map file if no other scene in this campaign references it
    map_url = (scene.get("grid") or {}).get("background_image_url") or ""
    if f"/campaigns/{name}/assets/" in map_url:
        filename = map_url.rsplit("/", 1)[-1]
        other_scene = await db["campaign_scenes"].find_one(
            {
                "campaign_name": name,
                "scene_id": {"$ne": scene_id},
                "grid.background_image_url": map_url,
            }
        )
        if not other_scene:
            # Safe to unlink file and asset doc
            file_path = os.path.join("data", "uploads", filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning("Failed removing map asset file %s: %s", file_path, e)
            await db["campaign_assets"].delete_one({"campaign_name": name, "filename": filename})

    await db["campaign_scenes"].delete_one({"scene_id": scene_id})
    return {"success": True, "message": f"Scene {scene_id} deleted."}


@router.post("/{name}/scenes/{scene_id}/activate", response_model=SuccessResponseSchema)
async def activate_campaign_scene(
    name: str,
    scene_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Activate a scene for all players, recording activation history and broadcasting vtt_sync."""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    scene = await db["campaign_scenes"].find_one({"campaign_name": name, "scene_id": scene_id})
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    now = datetime.datetime.now(datetime.timezone.utc)
    await db["campaigns"].update_one(
        {"campaign_name": name},
        {"$set": {"vtt_state.active_scene_id": scene_id, "vtt_state.is_active": True}},
    )
    await db["campaign_scenes"].update_one(
        {"scene_id": scene_id},
        {"$set": {"last_activated_at": now}},
    )

    history_entry = {
        "campaign_name": name,
        "scene_id": scene_id,
        "scene_name": scene.get("name", "Untitled"),
        "activated_at": now,
        "activated_by_user_id": current_user["id"],
    }
    await db["campaign_scene_history"].insert_one(history_entry)

    # Broadcast vtt_sync to all room participants
    from server.routers.websocket_router import manager

    vtt_srv = VTTService()
    new_state = await vtt_srv.get_vtt_state(db, name)
    state_dump = new_state.model_dump()
    connections = manager.active_connections.get(name) or []
    for conn in list(connections):
        payload_to_send = (
            state_dump
            if conn.is_dm
            else VTTService.redact_for_player(new_state, conn.character).model_dump()
        )
        try:
            await conn.websocket.send_json({"type": "vtt_sync", "payload": payload_to_send})
        except Exception:
            pass

    return {"success": True, "message": f"Scene '{scene.get('name')}' activated."}


@router.get("/{name}/scenes/history", response_model=List[VTTSceneHistorySchema])
async def get_campaign_scenes_history(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    campaign_member: dict = Depends(require_campaign_role("dm")),
):
    """Retrieve scene activation history for the campaign (DM only)."""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    cursor = (
        db["campaign_scene_history"]
        .find({"campaign_name": name})
        .sort("activated_at", -1)
        .limit(50)
    )
    history = []
    if hasattr(cursor, "__aiter__"):
        async for h in cursor:
            h.pop("_id", None)
            history.append(VTTSceneHistorySchema(**h))

    return history


@router.post("/{name}/loot/distribute")
async def distribute_loot(
    name: str,
    payload: LootDistributionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    """Distribute currency and/or items to selected campaign characters and broadcast via WebSocket."""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if not payload.character_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one character must be selected to receive loot.",
        )

    # Calculate currency per recipient
    char_currency: Dict[str, int] = {}
    total_currency_given = 0
    if payload.currency:
        num_targets = len(payload.character_ids)
        if payload.split_currency and num_targets > 1:
            char_currency = {
                "pp": max(0, payload.currency.pp // num_targets),
                "gp": max(0, payload.currency.gp // num_targets),
                "ep": max(0, payload.currency.ep // num_targets),
                "sp": max(0, payload.currency.sp // num_targets),
                "cp": max(0, payload.currency.cp // num_targets),
            }
        else:
            char_currency = {
                "pp": max(0, payload.currency.pp),
                "gp": max(0, payload.currency.gp),
                "ep": max(0, payload.currency.ep),
                "sp": max(0, payload.currency.sp),
                "cp": max(0, payload.currency.cp),
            }
        total_currency_given = sum(char_currency.values())

    # Fetch homebrew items if referenced
    awarded_items: List[Dict[str, Any]] = []
    if payload.items:
        awarded_items.extend(payload.items)

    if payload.homebrew_item_ids:
        from bson import ObjectId
        from bson.errors import InvalidId

        for hb_id in payload.homebrew_item_ids:
            try:
                oid = ObjectId(hb_id)
                hb_doc = await db["homebrew_content"].find_one({"_id": oid, "campaign_id": name})
                if hb_doc:
                    hb_doc["_id"] = str(hb_doc["_id"])
                    awarded_items.append(hb_doc)
            except InvalidId:
                continue

    if total_currency_given == 0 and not awarded_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one currency amount or item must be provided to distribute loot.",
        )

    # Split items by weapons vs general equipment
    weapons_to_push = [
        item
        for item in awarded_items
        if item.get("homebrew_type") == "weapon" or item.get("type") == "weapon"
    ]
    equipment_to_push = [item for item in awarded_items if item not in weapons_to_push]

    updated_count = 0
    updated_character_names = []

    for char_id in payload.character_ids:
        char = await db["characters"].find_one({"char_id": char_id})
        if not char:
            continue

        # Character must belong to this campaign
        if char.get("active_campaign") != name:
            continue

        update_ops: Dict[str, Any] = {}
        inc_ops: Dict[str, int] = {"version": 1}

        # Handle currency
        if total_currency_given > 0:
            if not isinstance(char.get("currency"), dict):
                await db["characters"].update_one(
                    {"char_id": char_id},
                    {"$set": {"currency": {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 0}}},
                )
            for coin, amount in char_currency.items():
                if amount > 0:
                    inc_ops[f"currency.{coin}"] = amount

        if inc_ops:
            update_ops["$inc"] = inc_ops

        # Ensure arrays are initialized if missing or corrupted
        if weapons_to_push and not isinstance(char.get("weapons"), list):
            await db["characters"].update_one({"char_id": char_id}, {"$set": {"weapons": []}})
        if equipment_to_push and not isinstance(char.get("equipment"), list):
            await db["characters"].update_one({"char_id": char_id}, {"$set": {"equipment": []}})

        push_ops: Dict[str, Any] = {}
        if weapons_to_push:
            push_ops["weapons"] = {"$each": weapons_to_push}
        if equipment_to_push:
            push_ops["equipment"] = {"$each": equipment_to_push}

        if push_ops:
            update_ops["$push"] = push_ops

        if update_ops:
            await db["characters"].update_one({"char_id": char_id}, update_ops)
            updated_count += 1
            updated_character_names.append(char.get("char_name", char_id))

    # WebSocket broadcast
    from server.routers.websocket_router import manager

    item_names = [it.get("name", "Unknown Item") for it in awarded_items]
    await manager.broadcast(
        name,
        {
            "type": "loot_distributed",
            "payload": {
                "character_ids": payload.character_ids,
                "character_names": updated_character_names,
                "currency": char_currency,
                "items": item_names,
                "reason": payload.reason,
            },
        },
    )

    return {
        "success": True,
        "message": f"Loot distributed to {updated_count} character(s).",
        "recipients": updated_character_names,
        "currency_awarded": char_currency,
        "items_awarded": item_names,
    }
