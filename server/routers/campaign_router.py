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
from server.dependencies.campaign import require_campaign_member, require_campaign_role

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
    recipient: str
    message: str


class RollRequestResultSchema(BaseModel):
    total: int
    expression: str
    raw: int
    rolls: List[int] = []
    modifier: int = 0


class WhisperResponse(SuccessResponseSchema):
    whisper: Dict[str, Any]


class CampaignMessagesResponse(BaseModel):
    campaign_name: str
    whispers: List[Dict[str, Any]] = []
    roll_requests: List[Dict[str, Any]] = []


class RollRequestResponse(SuccessResponseSchema):
    request: Dict[str, Any]


# _ensure_dm_access removed as per #ticket


@router.get("/", response_model=List[CampaignSchema])
async def list_campaigns(
    current_user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_database)
):
    members = db["campaign_members"].find({"user_id": current_user["id"]})
    campaign_names = []
    async for member in members:
        campaign_names.append(member["campaign_id"])

    cursor = db["campaigns"].find({"campaign_name": {"$in": campaign_names}})
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
    if existing:
        member = await db["campaign_members"].find_one(
            {"campaign_id": payload.campaign_name, "user_id": current_user["id"]}
        )
        if not member or member.get("role") != "dm":
            raise HTTPException(status_code=403, detail="Not authorized to edit this campaign")

        camp_dict["owner_id"] = existing.get("owner_id") or current_user["id"]
        camp_dict["whispers"] = existing.get("whispers", [])
        camp_dict["roll_requests"] = existing.get("roll_requests", [])
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

    await db["campaigns"].update_many(
        {"campaign_name": name},
        {"$set": {"roll_requests.$[elem].status": "cancelled"}},
        array_filters=[{"elem.char_filename": req_in.char_filename, "elem.status": "pending"}],
    )

    await db["campaigns"].update_one({"campaign_name": name}, {"$push": {"roll_requests": new_req}})

    from server.routers.websocket_router import manager

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

    requests = camp.get("roll_requests", [])
    target = None
    for request in requests:
        if request.get("id") == request_id:
            target = request
            break

    if not target:
        raise HTTPException(status_code=404, detail="Roll request not found")

    result = result_in.model_dump()
    resolved_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    await db["campaigns"].update_one(
        {"campaign_name": name, "roll_requests.id": request_id},
        {
            "$set": {
                "roll_requests.$.status": "resolved",
                "roll_requests.$.result": result,
                "roll_requests.$.resolved_at": resolved_at,
            }
        },
    )

    target["status"] = "resolved"
    target["result"] = result
    target["resolved_at"] = resolved_at

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
    member: dict = Depends(require_campaign_member()),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    whispers = camp.get("whispers", [])
    roll_requests = camp.get("roll_requests", [])

    if member.get("role") == "player":
        char_name = None
        if member.get("character_id"):
            char_doc = await db["characters"].find_one({"char_id": member["character_id"]})
            if char_doc:
                char_name = char_doc.get("name")

        filtered_whispers = []
        for w in whispers:
            if (
                w.get("recipient") == "All"
                or w.get("sender") == char_name
                or w.get("recipient") == char_name
            ):
                filtered_whispers.append(w)
        whispers = filtered_whispers

    return {
        "campaign_name": camp["campaign_name"],
        "whispers": whispers,
        "roll_requests": roll_requests,
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
                char_doc.get("name") if char_doc else current_user.get("username", "Player")
            )
        else:
            sender_name = current_user.get("username", "Player")

    new_whisper = {
        "id": str(uuid.uuid4()),
        "sender": sender_name,
        "recipient": payload.recipient,
        "message": payload.message,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }

    await db["campaigns"].update_one({"campaign_name": name}, {"$push": {"whispers": new_whisper}})

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
