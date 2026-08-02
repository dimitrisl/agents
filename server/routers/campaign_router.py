import datetime
import secrets
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from backend.core.schemas import InviteCodeResponse, SuccessResponseSchema
from server.db_async import get_database
from server.dependencies.auth import get_current_user

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


class CampaignSchema(BaseModel):
    campaign_name: str
    owner_id: Optional[str] = None
    notes: Optional[str] = ""
    party: List[str] = []
    dnd_edition: Optional[str] = "2014 Edition"
    invite_code: Optional[str] = None
    roll_requests: List[Dict[str, Any]] = []
    whispers: List[Dict[str, Any]] = []


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
    sender: str
    recipient: str
    message: str


class RollRequestResultSchema(BaseModel):
    total: int
    expression: str
    raw: int
    rolls: List[int] = []
    modifier: int = 0


class WhisperResponse(SuccessResponseSchema):
    """The stored whisper travels back so the sender can thread it immediately,
    without waiting for the WebSocket echo to arrive."""

    whisper: Dict[str, Any]


class CampaignMessagesResponse(BaseModel):
    campaign_name: str
    whispers: List[Dict[str, Any]] = []
    roll_requests: List[Dict[str, Any]] = []


@router.get("/", response_model=List[CampaignSchema])
async def list_campaigns(
    current_user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_database)
):
    user_chars = db["characters"].find({"owner_id": current_user["id"]})
    joined_campaigns = []
    async for char in user_chars:
        if char.get("active_campaign"):
            joined_campaigns.append(char["active_campaign"])

    cursor = db["campaigns"].find(
        {"$or": [{"owner_id": current_user["id"]}, {"campaign_name": {"$in": joined_campaigns}}]}
    )
    campaigns = []
    async for doc in cursor:
        doc.pop("_id", None)
        campaigns.append(CampaignSchema(**doc))
    return campaigns


@router.post("/", response_model=CampaignSchema)
async def save_campaign(
    payload: CampaignSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    existing = await db["campaigns"].find_one({"campaign_name": payload.campaign_name})

    camp_dict = payload.model_dump()
    if existing and existing.get("owner_id"):
        camp_dict["owner_id"] = existing["owner_id"]
    else:
        camp_dict["owner_id"] = current_user["id"]

    await db["campaigns"].update_one(
        {"campaign_name": payload.campaign_name}, {"$set": camp_dict}, upsert=True
    )
    return CampaignSchema(**camp_dict)


@router.get("/{name}/party", response_model=List[Dict[str, Any]])
async def get_campaign_party(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    # Find all characters that have joined this campaign
    cursor = db["characters"].find({"active_campaign": name})
    party_members = []
    async for char in cursor:
        char.pop("_id", None)
        party_members.append(char)
    return party_members


@router.post("/join", response_model=Dict[str, Any])
async def join_campaign_by_code(
    payload: JoinCampaignRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    camp = await db["campaigns"].find_one({"invite_code": payload.invite_code.upper()})
    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite code.")

    party = camp.get("party", [])
    if payload.char_filename not in party:
        party.append(payload.char_filename)
        await db["campaigns"].update_one(
            {"campaign_name": camp["campaign_name"]}, {"$set": {"party": party}}
        )

    # Update character active campaign
    char_id = payload.char_filename.replace(".json", "").split("_")[-1]
    await db["characters"].update_one(
        {"char_id": char_id},
        {"$set": {"active_campaign": camp["campaign_name"]}},
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
):
    camp = await db["campaigns"].find_one({"campaign_name": name})

    if not camp:
        code = secrets.token_hex(3).upper()
        camp_dict = {
            "campaign_name": name,
            "owner_id": current_user["id"],
            "invite_code": code,
            "party": [],
            "notes": "",
            "roll_requests": [],
            "whispers": [],
        }
        await db["campaigns"].insert_one(camp_dict)
        return {"invite_code": code}

    if camp.get("invite_code"):
        return {"invite_code": camp["invite_code"]}

    code = secrets.token_hex(3).upper()
    await db["campaigns"].update_one({"campaign_name": name}, {"$set": {"invite_code": code}})
    return {"invite_code": code}


@router.post("/{name}/roll-request", response_model=SuccessResponseSchema)
async def add_roll_request(
    name: str,
    req_in: RollRequestSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        camp = {
            "campaign_name": name,
            "owner_id": current_user["id"],
            "party": [],
            "notes": "",
            "roll_requests": [],
            "whispers": [],
        }
        await db["campaigns"].insert_one(camp)

    req_id = str(uuid.uuid4())
    new_req = {
        "id": req_id,
        "char_filename": req_in.char_filename,
        "char_name": req_in.char_name,
        "roll_type": req_in.roll_type,
        "stat": req_in.stat,
        "reason": req_in.reason,
        "status": "pending",
        "result": None,
        "is_secret": req_in.is_secret,
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }

    requests = camp.get("roll_requests", [])
    for r in requests:
        if r.get("char_filename") == req_in.char_filename and r.get("status") == "pending":
            r["status"] = "cancelled"

    requests.append(new_req)
    await db["campaigns"].update_one({"campaign_name": name}, {"$set": {"roll_requests": requests}})

    # Broadcast to campaign websocket channel — only the hero being asked to roll
    # needs it (the DM's own socket always receives, so their board stays live).
    from server.routers.websocket_router import manager

    await manager.broadcast(
        name, {"type": "roll_request", "payload": new_req}, characters=[req_in.char_name]
    )

    return {"success": True, "message": f"Roll request sent for {req_in.char_name}"}


@router.post("/{name}/roll-request/{request_id}/result", response_model=SuccessResponseSchema)
async def resolve_roll_request(
    name: str,
    request_id: str,
    result_in: RollRequestResultSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    requests = camp.get("roll_requests", [])
    target = None
    for request in requests:
        if request.get("id") == request_id:
            target = request
            break

    if not target:
        raise HTTPException(status_code=404, detail="Roll request not found")

    result = result_in.model_dump()
    target["status"] = "resolved"
    target["result"] = result
    target["resolved_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    await db["campaigns"].update_one({"campaign_name": name}, {"$set": {"roll_requests": requests}})

    from server.routers.websocket_router import manager

    await manager.broadcast(
        name, {"type": "roll_result", "payload": target}, characters=[target.get("char_name")]
    )

    return {"success": True, "message": "Roll request resolved"}


@router.get("/{name}/messages", response_model=CampaignMessagesResponse)
async def get_campaign_messages(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Whisper + roll-request history for one campaign.

    Both dashboards replay this on load so the live socket only ever has to carry
    what happens from that moment on.
    """
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {
        "campaign_name": camp["campaign_name"],
        "whispers": camp.get("whispers", []),
        "roll_requests": camp.get("roll_requests", []),
    }


@router.post("/{name}/whisper", response_model=WhisperResponse)
async def send_whisper(
    name: str,
    payload: WhisperRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    new_whisper = {
        "id": str(uuid.uuid4()),
        "sender": payload.sender,
        "recipient": payload.recipient,
        "message": payload.message,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }

    whispers = camp.get("whispers", [])
    whispers.append(new_whisper)
    await db["campaigns"].update_one({"campaign_name": name}, {"$set": {"whispers": whispers}})

    # Broadcast via WebSocket. A whisper addressed to one hero reaches that hero
    # and its sender only — "All" is the one case that goes out to the room.
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
):
    result = await db["campaigns"].update_one(
        {"campaign_name": name}, {"$set": {"notes": payload.notes}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"success": True, "message": "Notes saved successfully"}
