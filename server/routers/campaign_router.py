import datetime
import re
import secrets
import uuid
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from backend.core.schemas import InviteCodeResponse, SuccessResponseSchema, EncounterStateSchema
from backend.services.dice_service import roll_dice
from backend.services.stats_service import calculate_skills, get_modifier
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.dependencies.campaign import require_campaign_member, require_campaign_role

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


class CampaignSchema(BaseModel):
    campaign_name: str
    owner_id: Optional[str] = None
    notes: str = ""
    party: List[str] = []
    dnd_edition: Optional[str] = None
    invite_code: Optional[str] = None


class PlayerCampaignSchema(BaseModel):
    campaign_name: str
    owner_id: Optional[str] = None
    party: List[str] = []
    dnd_edition: Optional[str] = None
    invite_code: Optional[str] = None


class JoinCampaignRequest(BaseModel):
    invite_code: str
    char_filename: str


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
    char_id = (char_filename or "").replace(".json", "").split("_")[-1]
    if char_id:
        char = await db["characters"].find_one({"char_id": char_id})
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


@router.get("/", response_model=List[Union[CampaignSchema, PlayerCampaignSchema]])
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
        if role == "dm":
            campaigns.append(CampaignSchema(**doc))
        else:
            campaigns.append(PlayerCampaignSchema(**doc))
    return campaigns


@router.post("/", response_model=CampaignSchema)
async def save_campaign(
    payload: CampaignSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    existing = await db["campaigns"].find_one({"campaign_name": payload.campaign_name})

    camp_dict = payload.model_dump()
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
    else:
        camp_dict["owner_id"] = current_user["id"]
        await db["campaign_members"].insert_one(
            {
                "campaign_id": payload.campaign_name,
                "user_id": current_user["id"],
                "role": "dm",
                "character_id": None,
                "joined_at": datetime.datetime.now(datetime.timezone.utc),
            }
        )

    await db["campaigns"].update_one(
        {"campaign_name": payload.campaign_name}, {"$set": camp_dict}, upsert=True
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
    async for char in cursor:
        char.pop("_id", None)
        party_members.append(char)
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
    await db["characters"].update_one({"char_id": char_id}, {"$set": updates})

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


@router.post("/join", response_model=Dict[str, Any])
async def join_campaign_by_code(
    payload: JoinCampaignRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    camp = await db["campaigns"].find_one({"invite_code": payload.invite_code.upper()})
    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite code.")

    char_id = payload.char_filename.replace(".json", "").split("_")[-1]

    char = await db["characters"].find_one({"char_id": char_id})
    if not char or char.get("owner_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Character not found or you do not own it.")

    await db["campaigns"].update_one(
        {"campaign_name": camp["campaign_name"]}, {"$addToSet": {"party": payload.char_filename}}
    )

    await db["characters"].update_one(
        {"char_id": char_id},
        {"$set": {"active_campaign": camp["campaign_name"]}},
    )

    existing_member = await db["campaign_members"].find_one(
        {"campaign_id": camp["campaign_name"], "user_id": current_user["id"]}
    )
    if not existing_member:
        await db["campaign_members"].insert_one(
            {
                "campaign_id": camp["campaign_name"],
                "user_id": current_user["id"],
                "role": "player",
                "character_id": char_id,
                "joined_at": datetime.datetime.now(datetime.timezone.utc),
            }
        )
    else:
        await db["campaign_members"].update_one(
            {"_id": existing_member["_id"]}, {"$set": {"character_id": char_id}}
        )

    return {
        "success": True,
        "campaign_name": camp["campaign_name"],
        "error": None,
    }


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

    code = secrets.token_hex(3).upper()
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

    result = result_in.model_dump()
    resolved_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    await db["campaign_roll_requests"].update_one(
        {"_id": target["_id"]},
        {
            "$set": {
                "status": "resolved",
                "result": result,
                "resolved_at": resolved_at,
            }
        },
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

    cursor_w = db["campaign_whispers"].find({"campaign_name": name})
    all_whispers = []
    async for w in cursor_w:
        w.pop("_id", None)
        all_whispers.append(w)

    whispers = all_whispers

    if member.get("role") == "player":
        char_name = None
        if member.get("character_id"):
            char_doc = await db["characters"].find_one({"char_id": member["character_id"]})
            if char_doc:
                char_name = char_doc.get("char_name")

        filtered_whispers = []
        for w in whispers:
            if (
                w.get("recipient") == "All"
                or w.get("sender") == char_name
                or w.get("recipient") == char_name
            ):
                filtered_whispers.append(w)
        whispers = filtered_whispers

    cursor_r = db["campaign_roll_requests"].find({"campaign_name": name})
    roll_requests = []
    async for r in cursor_r:
        r.pop("_id", None)
        roll_requests.append(r)

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

    sender_name = "DM"
    if member.get("role") == "player":
        if member.get("character_id"):
            char_doc = await db["characters"].find_one({"char_id": member["character_id"]})
            sender_name = (
                char_doc.get("char_name") if char_doc else current_user.get("username", "Player")
            )
        else:
            sender_name = current_user.get("username", "Player")

    new_whisper = {
        "id": str(uuid.uuid4()),
        "campaign_name": name,
        "sender": sender_name,
        "recipient": payload.recipient,
        "message": payload.message,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }

    db_whisper = new_whisper.copy()
    await db["campaign_whispers"].insert_one(db_whisper)

    from server.routers.websocket_router import manager

    audience = None
    if new_whisper["recipient"] != "All":
        audience = [new_whisper["recipient"], new_whisper["sender"]]

    await manager.broadcast(name, {"type": "whisper", "payload": new_whisper}, characters=audience)

    return {
        "success": True,
        "message": f"Whisper sent to {new_whisper['recipient']}",
        "whisper": new_whisper,
    }


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
    enc_dict["campaign_name"] = name

    await db["campaign_encounters"].update_one(
        {"campaign_name": name}, {"$set": enc_dict}, upsert=True
    )

    from server.routers.websocket_router import manager
    
    # Broadcast the new state to all members so their tracker syncs immediately
    await manager.broadcast(
        name,
        {"type": "encounter_update", "payload": enc_dict}
    )

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
    await manager.broadcast(
        name,
        {"type": "encounter_update", "payload": None}
    )

    return {"success": True, "message": "Encounter state cleared"}
