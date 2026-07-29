import datetime
import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

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


@router.get("/", response_model=List[CampaignSchema])
async def list_campaigns(current_user: dict = Depends(get_current_user)):
    db = get_database()
    cursor = db["campaigns"].find(
        {"$or": [{"owner_id": current_user["id"]}, {"party": {"$exists": True}}]}
    )
    campaigns = []
    async for doc in cursor:
        doc.pop("_id", None)
        campaigns.append(CampaignSchema(**doc))
    return campaigns


@router.post("/", response_model=CampaignSchema)
async def save_campaign(payload: CampaignSchema, current_user: dict = Depends(get_current_user)):
    db = get_database()
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


@router.post("/join", response_model=Dict[str, Any])
async def join_campaign_by_code(
    payload: JoinCampaignRequest, current_user: dict = Depends(get_current_user)
):
    db = get_database()
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


@router.post("/{name}/invite-code")
async def generate_invite_code(name: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    camp = await db["campaigns"].find_one({"campaign_name": name})

    if not camp:
        raw = f"{name}-{time.time()}"
        code = hashlib.md5(raw.encode()).hexdigest()[:6].upper()
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

    raw = f"{name}-{time.time()}"
    code = hashlib.md5(raw.encode()).hexdigest()[:6].upper()
    await db["campaigns"].update_one({"campaign_name": name}, {"$set": {"invite_code": code}})
    return {"invite_code": code}


@router.post("/{name}/roll-request")
async def add_roll_request(
    name: str,
    req_in: RollRequestSchema,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
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
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    requests = camp.get("roll_requests", [])
    for r in requests:
        if r.get("char_filename") == req_in.char_filename and r.get("status") == "pending":
            r["status"] = "cancelled"

    requests.append(new_req)
    await db["campaigns"].update_one({"campaign_name": name}, {"$set": {"roll_requests": requests}})
    return {"success": True, "request": new_req}
