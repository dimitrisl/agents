import copy
import datetime
import inspect
import logging
import os
import re
import secrets
import uuid
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field, field_validator
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.core.schemas import (
    CampaignEntitySchema,
    CampaignRollResponse,
    CampaignSkeletonSchema,
    EncounterStateSchema,
    EncounterSyncResponseSchema,
    InviteCodeResponse,
    PasteExtractionRequest,
    SessionOutlineSchema,
    SheetRollCreateRequest,
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
from backend.services.stats_service import (
    calculate_skills,
    get_modifier,
    has_jack_of_all_trades,
    has_remarkable_athlete,
    sync_character_stats,
)
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
    member_count: int = 1

    @field_validator("campaign_name")
    @classmethod
    def validate_campaign_name(cls, v: str) -> str:
        if "%" in v or "/" in v or "\\" in v:
            raise ValueError("Campaign name cannot contain '%', '/', or '\\'.")
        return v


class PlayerCampaignSchema(BaseModel):
    campaign_name: str
    owner_id: Optional[str] = None
    role: Literal["player"] = "player"
    party: List[str] = []
    dnd_edition: Optional[str] = None
    invite_code: Optional[str] = None
    vtt_state: Optional[VTTStateSchema] = None
    member_count: int = 1


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
    target_char_id: Optional[str] = None
    roll_type: str
    stat: str = ""
    reason: Optional[str] = ""
    is_secret: bool = False
    manual_roll: Optional[int] = None


class WhisperRequest(BaseModel):
    recipient: str
    message: str = Field(..., min_length=1, max_length=2000)
    sender_character_id: Optional[str] = None
    recipient_character_id: Optional[str] = None


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
    version: Optional[int] = None


class WhisperResponse(SuccessResponseSchema):
    whisper: Dict[str, Any]


class CampaignMessagesResponse(BaseModel):
    campaign_name: str
    whispers: List[Dict[str, Any]] = []
    roll_requests: List[Dict[str, Any]] = []
    roll_logs: List[Dict[str, Any]] = []


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
    item_recipient_id: Optional[str] = None
    reason: Optional[str] = "Loot Reward"


class RollRequestResponse(SuccessResponseSchema):
    request: Dict[str, Any]
    requests: Optional[List[Dict[str, Any]]] = None


_SAVE_TYPES = {"save", "saving_throw", "savingthrow"}
_SKILL_TYPES = {"skill", "skill_check"}


def _member_character_ids(member: Optional[dict]) -> List[str]:
    """Collect distinct character IDs tied to a campaign_members document."""
    if not member:
        return []
    ids: List[str] = []
    for cid in member.get("character_ids") or []:
        if cid and cid not in ids:
            ids.append(cid)
    single_id = member.get("character_id")
    if single_id and single_id not in ids:
        ids.append(single_id)
    return ids


async def _broadcast_roll_event(
    manager: Any,
    campaign_name: str,
    message: Dict[str, Any],
    *,
    characters: Optional[List[str]] = None,
    user_ids: Optional[List[str]] = None,
    dm_only: bool = False,
) -> None:
    """Broadcast roll requests/results with user_ids when the manager supports it."""
    kwargs: Dict[str, Any] = {}
    if dm_only:
        kwargs["dm_only"] = True
    if characters is not None:
        kwargs["characters"] = characters
    if user_ids:
        try:
            params = inspect.signature(manager.broadcast).parameters
            if "user_ids" in params or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
            ):
                kwargs["user_ids"] = user_ids
        except (TypeError, ValueError):
            pass
    await manager.broadcast(campaign_name, message, **kwargs)


async def _find_campaign_character(
    db: AsyncIOMotorDatabase,
    name: str,
    char_filename: str,
    char_name: str,
    target_char_id: Optional[str] = None,
) -> Optional[dict]:
    """
    The sheet behind a roll request. Explicit `target_char_id` or the id embedded
    in `char_filename` (`lyra_abc123.json`) are the reliable handles; `char_name` is
    the legacy fallback for a hero typed in by hand rather than joined from the vault.
    """
    if target_char_id:
        char = await db["characters"].find_one({"char_id": target_char_id, "active_campaign": name})
        if char:
            return char

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
    stat_clean = (stat or "").strip()
    stat_upper = stat_clean.upper()
    edition = char.get("ruleset_version") or char.get("dnd_edition")
    is_2024 = "2024" in str(edition or "")
    exh_level = max(0, min(6, int(char.get("exhaustion_level", 0) or 0)))
    exh_penalty = (2 * exh_level) if is_2024 else 0

    if normalized in _SAVE_TYPES:
        save_values = char.get("saving_throw_values") or {}
        for sv_k, sv_val in save_values.items():
            if sv_k.upper() == stat_upper:
                return int(sv_val)
        saving_throws = [s.upper() for s in (char.get("saving_throws") or [])]
        proficient = stat_upper in saving_throws
        stat_val = stats.get(stat_upper)
        if stat_val is None:
            stat_val = next((v for k, v in stats.items() if k.upper() == stat_upper), 10)
        return get_modifier(stat_val) + (prof_bonus if proficient else 0) - exh_penalty

    if normalized in _SKILL_TYPES:
        char_skills = char.get("skills") or {}
        for sk_name, sk_val in char_skills.items():
            if sk_name.lower() == stat_clean.lower():
                return int(sk_val)

        jack = has_jack_of_all_trades(char)
        remarkable = has_remarkable_athlete(char, edition=edition)

        skills = calculate_skills(
            stats,
            prof_bonus,
            char.get("skill_proficiencies") or [],
            char.get("skill_expertise") or [],
            half_prof_all=jack,
            half_prof_phys=(remarkable and not is_2024),
        )
        for sk_name, sk_val in skills.items():
            if sk_name.lower() == stat_clean.lower():
                return int(sk_val) - exh_penalty

    if normalized == "initiative" or stat_clean.lower() == "initiative":
        if "initiative_modifier" in char and char["initiative_modifier"] is not None:
            return int(char["initiative_modifier"])
        return get_modifier(stats.get("DEX", 10)) - exh_penalty

    if stat_upper in stats:
        return get_modifier(stats[stat_upper]) - exh_penalty

    for k, v in stats.items():
        if k.upper() == stat_upper:
            return get_modifier(v) - exh_penalty

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


def _visible_roll_requests(
    requests: List[Dict[str, Any]],
    is_dm: bool,
    current_user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    History as this member is allowed to see it. Secret rolls are the DM's own
    knowledge, and targeted player roll requests are scoped to their owner.
    """
    if is_dm:
        return requests
    visible: List[Dict[str, Any]] = []
    for req in requests:
        if req.get("is_secret"):
            continue
        target_owner_id = req.get("target_owner_id")
        if current_user_id and target_owner_id and target_owner_id != current_user_id:
            continue
        visible.append(req)
    return visible


def _compute_health_status(hp: Optional[int], max_hp: Optional[int]) -> str:
    hp_val = int(hp or 0)
    max_val = int(max_hp or 0)
    if hp_val <= 0:
        return "down"
    if max_val > 0 and hp_val <= (max_val // 2):
        return "bloodied"
    return "healthy"


def _redact_encounter_for_player(enc: Dict[str, Any]) -> Dict[str, Any]:
    """Strip secret monster stats while preserving party state and visual health status."""
    redacted = copy.deepcopy(enc)
    combatants = redacted.get("combatants") or []
    for c in combatants:
        if not c.get("health_status"):
            c["health_status"] = _compute_health_status(c.get("hp"), c.get("max_hp"))
        if not c.get("is_player"):
            c["hp"] = None
            c["max_hp"] = None
            c["ac"] = None
            c["statblock"] = None
            c["stats"] = None
            c["traits"] = None
            c["actions"] = None
            c["legendary_actions"] = None
            c["cr"] = None
            c["xp"] = None
    return redacted


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

    campaign_names = list(user_roles.keys())
    member_counts: Dict[str, int] = {}
    all_members_cursor = db["campaign_members"].find({"campaign_id": {"$in": campaign_names}})
    async for m in all_members_cursor:
        cid = m.get("campaign_id")
        if cid:
            member_counts[cid] = member_counts.get(cid, 0) + 1

    cursor = db["campaigns"].find({"campaign_name": {"$in": campaign_names}})
    campaigns = []
    async for doc in cursor:
        doc.pop("_id", None)
        role = user_roles.get(doc["campaign_name"], "player")
        doc["role"] = role
        doc["member_count"] = member_counts.get(doc["campaign_name"], 1)
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
        # #233: Allowlist safe fields on creation instead of trusting client role/party/member_count
        camp_dict = {
            "campaign_name": payload.campaign_name,
            "owner_id": current_user["id"],
            "role": "dm",
            "notes": payload.notes,
            "party": [],
            "dnd_edition": payload.dnd_edition,
            "member_count": 1,
        }
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
        old_hp = char.get("hp_current", 0) or 0
        new_hp = max(0, min(hp_max, payload.hp_current))
        updates["hp_current"] = new_hp
        if old_hp == 0 and new_hp > 0:
            updates["death_saves"] = {"successes": 0, "failures": 0}

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
    new_version = int(char.get("version", 0) or 0) + 1
    await db["characters"].update_one(
        {"char_id": char_id, "active_campaign": name}, {"$set": updates, "$inc": {"version": 1}}
    )

    state = {
        "char_id": char_id,
        "char_name": char.get("char_name", "Unknown"),
        "hp_current": updates.get("hp_current", char.get("hp_current") or 0),
        "hp_max": char.get("hp_max") or 0,
        "hp_temp": char.get("hp_temp", 0) or 0,
        "conditions": updates.get("conditions", char.get("conditions", [])),
        "concentrating_on": char.get("concentrating_on"),
        "death_saves": updates.get("death_saves", char.get("death_saves")),
        "inspiration": bool(char.get("inspiration", False)),
        "exhaustion_level": int(char.get("exhaustion_level", 0) or 0),
        "version": new_version,
        "source": "dm",
    }

    from server.routers.websocket_router import manager

    # Untargeted on purpose: every hero at the table can see who is bloodied.
    await manager.broadcast(name, {"type": "party_update", "payload": state})

    return {"success": True, "message": f"Updated {state['char_name']}.", **state}


@router.post("/{name}/party/long-rest", response_model=SuccessResponseSchema)
async def long_rest_party(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    """DM Long Rest: restores HP, spell slots, hit dice, and reduces exhaustion for the party."""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    from server.routers.websocket_router import manager

    rested_count = 0
    cursor = db["characters"].find({"active_campaign": name})
    async for char in cursor:
        char_id = char.get("char_id")
        if not char_id:
            continue

        updated_doc = None
        current_char = char
        for attempt in range(2):
            edition = (
                current_char.get("dnd_edition")
                or current_char.get("ruleset_version")
                or camp.get("dnd_edition")
                or ""
            )
            is_2024_rest = "2024" in str(edition)
            old_exh = int(current_char.get("exhaustion_level", 0) or 0)
            new_exh = max(0, old_exh - 1)

            old_hd_used = max(0, int(current_char.get("hit_dice_used") or 0))
            if is_2024_rest:
                new_hd_used = 0
            else:
                total_hd = max(1, int(current_char.get("char_level") or 1))
                recovered_hd = max(1, total_hd // 2)
                new_hd_used = max(0, old_hd_used - recovered_hd)

            raw_slots = current_char.get("spell_slots") or {}
            reset_slots: Dict[str, Any] = {}
            if isinstance(raw_slots, dict):
                for k, slot_val in raw_slots.items():
                    if isinstance(slot_val, dict):
                        next_slot = {**slot_val, "used": 0}
                        if "pact_used" in next_slot:
                            next_slot["pact_used"] = 0
                        reset_slots[k] = next_slot
                    else:
                        reset_slots[k] = slot_val

            raw_resources = current_char.get("class_resources") or []
            recharged_resources: List[Dict[str, Any]] = []
            for res in raw_resources:
                if isinstance(res, dict):
                    res_max = res.get("max", res.get("current", 0))
                    recharged_resources.append({**res, "current": res_max})

            updates: Dict[str, Any] = {
                "hp_temp": 0,
                "hit_dice_used": new_hd_used,
                "concentrating_on": None,
                "death_saves": {"successes": 0, "failures": 0},
                "exhaustion_level": new_exh,
                "spell_slots": reset_slots,
                "class_resources": recharged_resources,
            }

            if current_char.get("stats"):
                working = copy.deepcopy({k: v for k, v in current_char.items() if k != "_id"})
                working.update(updates)
                if edition and not working.get("dnd_edition"):
                    working["dnd_edition"] = edition
                synced = sync_character_stats(working)
                for sync_key in (
                    "hp_max",
                    "base_hp_max",
                    "speed",
                    "base_speed",
                    "skills",
                    "saving_throw_values",
                    "initiative_modifier",
                    "weapons",
                    "spell_attack_bonus",
                    "spell_save_dc",
                ):
                    if sync_key in synced:
                        updates[sync_key] = synced[sync_key]
            else:
                if (not is_2024_rest) and new_exh < 4 and current_char.get("base_hp_max"):
                    updates["hp_max"] = current_char["base_hp_max"]
                else:
                    updates["hp_max"] = current_char.get("hp_max") or 0

            hp_max = updates.get("hp_max") or current_char.get("hp_max") or 0
            updates["hp_current"] = hp_max

            query_filter: Dict[str, Any] = {"char_id": char_id, "active_campaign": name}
            if "version" in current_char:
                query_filter["version"] = current_char["version"]

            if hasattr(db["characters"], "find_one_and_update"):
                updated_doc = await db["characters"].find_one_and_update(
                    query_filter,
                    {"$set": updates, "$inc": {"version": 1}},
                    return_document=ReturnDocument.AFTER,
                )
            else:
                await db["characters"].update_one(
                    query_filter,
                    {"$set": updates, "$inc": {"version": 1}},
                )
                updated_doc = {
                    **current_char,
                    **updates,
                    "version": int(current_char.get("version", 0) or 0) + 1,
                }

            if updated_doc is not None:
                break

            refetched = await db["characters"].find_one(
                {"char_id": char_id, "active_campaign": name}
            )
            if not refetched:
                break
            current_char = refetched

        if not updated_doc:
            continue

        new_version = int(updated_doc.get("version", int(current_char.get("version", 0) or 0) + 1))
        await manager.broadcast(
            name,
            {
                "type": "party_update",
                "payload": {
                    "char_id": char_id,
                    "char_name": updated_doc.get(
                        "char_name", current_char.get("char_name", "Unknown")
                    ),
                    "hp_current": updated_doc.get("hp_current", updates["hp_current"]),
                    "hp_max": updated_doc.get("hp_max", updates["hp_max"]),
                    "hp_temp": 0,
                    "speed": updated_doc.get("speed", current_char.get("speed")),
                    "conditions": updated_doc.get("conditions", []),
                    "concentrating_on": None,
                    "death_saves": {"successes": 0, "failures": 0},
                    "inspiration": bool(updated_doc.get("inspiration", False)),
                    "exhaustion_level": updated_doc.get(
                        "exhaustion_level", updates["exhaustion_level"]
                    ),
                    "hit_dice_used": updated_doc.get("hit_dice_used", updates["hit_dice_used"]),
                    "spell_slots": updated_doc.get("spell_slots", updates["spell_slots"]),
                    "class_resources": updated_doc.get(
                        "class_resources", updates["class_resources"]
                    ),
                    "version": new_version,
                    "source": "dm",
                    "action": "long_rest",
                },
            },
        )
        rested_count += 1

    return {"success": True, "message": f"Completed Long Rest for {rested_count} party member(s)."}


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
    char = await db["characters"].find_one({"char_id": fallback_id, "owner_id": user_id})
    return fallback_id, char


def _build_canonical_party_filename(
    char: dict, char_id: str, provided_filename: Optional[str]
) -> str:
    safe_name = re.sub(r"\s+", "_", (char.get("char_name") or "").strip().lower())
    canonical = f"{safe_name}_{char_id}.json" if safe_name else f"{char_id}.json"
    if not provided_filename:
        return canonical
    raw_fn = provided_filename.removesuffix(".json")
    if raw_fn == char_id or raw_fn.endswith(f"_{char_id}"):
        return f"{raw_fn}.json"
    return canonical


@router.post("/join", response_model=Dict[str, Any])
@limiter.limit("5/minute")
async def join_campaign_by_code(
    request: Request,
    payload: JoinCampaignRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    code = payload.invite_code.strip()
    camp = await db["campaigns"].find_one({"invite_code": code})
    if not camp and code:
        camp = await db["campaigns"].find_one(
            {"invite_code": re.compile(f"^{re.escape(code)}$", re.IGNORECASE)}
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

    party_filename = _build_canonical_party_filename(char, char_id, payload.char_filename)
    party_entries = camp.get("party") or []
    char_in_party = any(
        entry == party_filename
        or entry == char_id
        or entry == f"{char_id}.json"
        or entry.endswith(f"_{char_id}.json")
        for entry in party_entries
    )

    existing_member = await db["campaign_members"].find_one(
        {"campaign_id": camp["campaign_name"], "user_id": current_user["id"]}
    )
    if existing_member:
        member_char_ids = _member_character_ids(existing_member)
        if (
            char_id in member_char_ids
            or char.get("active_campaign") == camp["campaign_name"]
            or char_in_party
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Character '{char.get('char_name') or char_id}' is already a member "
                    f"of campaign '{camp['campaign_name']}'."
                ),
            )

        member_update: Dict[str, Any] = {"$addToSet": {"character_ids": char_id}}
        if not existing_member.get("character_id") and existing_member.get("role") != "dm":
            member_update["$set"] = {"character_id": char_id}
        await db["campaign_members"].update_one(
            {"campaign_id": camp["campaign_name"], "user_id": current_user["id"]},
            member_update,
        )
    else:
        try:
            await db["campaign_members"].insert_one(
                {
                    "campaign_id": camp["campaign_name"],
                    "user_id": current_user["id"],
                    "role": "player",
                    "character_id": char_id,
                    "character_ids": [char_id],
                    "joined_at": datetime.datetime.now(datetime.timezone.utc),
                }
            )
        except DuplicateKeyError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User is already a member of campaign '{camp['campaign_name']}'.",
            ) from e

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

    party_filename = _build_canonical_party_filename(char, char_id, payload.char_filename)
    await db["campaigns"].update_one(
        {"campaign_name": name}, {"$addToSet": {"party": party_filename}}
    )

    await db["characters"].update_one(
        {"char_id": char_id, "owner_id": current_user["id"]},
        {"$set": {"active_campaign": name}},
    )

    # Note: Since the DM is adding their own character, they are already a member (role='dm').
    # Keep character_ids updated without overwriting role='dm'.
    await db["campaign_members"].update_one(
        {"campaign_id": name, "user_id": current_user["id"]},
        {"$addToSet": {"character_ids": char_id}},
    )

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


@router.post("/{name}/invite-code/rotate", response_model=InviteCodeResponse)
async def rotate_invite_code(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

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
    from server.routers.websocket_router import manager

    is_group_roll = (req_in.char_name or "").strip().upper() in (
        "ALL",
        "ALL PARTY",
        "ALL_PARTY",
        "*",
    ) or (req_in.char_filename or "").strip().upper() in ("ALL", "ALL.JSON")

    if is_group_roll:
        if req_in.manual_roll is not None:
            raise HTTPException(
                status_code=422,
                detail="A manual roll applies to a single hero and cannot be used for a group roll request.",
            )
        party_files = camp.get("party") or []
        created_reqs: List[Dict[str, Any]] = []
        for pf in party_files:
            char_doc = await _find_campaign_character(db, name, pf, "")
            target_name = (
                char_doc.get("char_name")
                if char_doc
                else pf.removesuffix(".json").split("_")[0].title()
            )
            target_char_id = char_doc.get("char_id") if char_doc else None
            target_owner_id = char_doc.get("owner_id") if char_doc else None
            req_id = str(uuid.uuid4())
            item_req: Dict[str, Any] = {
                "id": req_id,
                "campaign_name": name,
                "char_filename": pf,
                "char_name": target_name,
                "target_char_id": target_char_id,
                "target_owner_id": target_owner_id,
                "roll_type": req_in.roll_type,
                "stat": req_in.stat,
                "reason": req_in.reason,
                "status": "pending",
                "result": None,
                "is_secret": req_in.is_secret,
                "created_at": now,
            }
            if req_in.is_secret:
                item_req["result"] = _roll_in_secret(char_doc, req_in.roll_type, req_in.stat)
                item_req["status"] = "resolved"
                item_req["rolled_by"] = "dm"
                item_req["resolved_at"] = now
                await db["campaign_roll_requests"].insert_one(item_req.copy())
                await manager.broadcast(
                    name, {"type": "roll_result", "payload": item_req}, dm_only=True
                )
            else:
                cancel_group_filter: Dict[str, Any] = {
                    "campaign_name": name,
                    "char_filename": pf,
                    "status": "pending",
                }
                if target_char_id:
                    cancel_group_filter = {
                        "campaign_name": name,
                        "status": "pending",
                        "$or": [
                            {"target_char_id": target_char_id},
                            {"char_filename": pf},
                        ],
                    }
                await db["campaign_roll_requests"].update_many(
                    cancel_group_filter,
                    {"$set": {"status": "cancelled"}},
                )
                await db["campaign_roll_requests"].insert_one(item_req.copy())
                await _broadcast_roll_event(
                    manager,
                    name,
                    {"type": "roll_request", "payload": item_req},
                    characters=[target_name],
                    user_ids=[target_owner_id] if target_owner_id else None,
                )
            created_reqs.append(item_req)

        if not created_reqs:
            raise HTTPException(
                status_code=400, detail="No active party members found for group roll request."
            )
        return {
            "success": True,
            "message": f"Roll request sent for {len(created_reqs)} party member(s)",
            "request": created_reqs[0],
            "requests": created_reqs,
        }

    char_doc = await _find_campaign_character(
        db, name, req_in.char_filename, req_in.char_name, target_char_id=req_in.target_char_id
    )
    resolved_target_char_id = (
        char_doc.get("char_id") if char_doc else None
    ) or req_in.target_char_id
    resolved_target_owner_id = char_doc.get("owner_id") if char_doc else None
    canonical_target_name = (char_doc.get("char_name") if char_doc else None) or req_in.char_name

    req_id = str(uuid.uuid4())
    new_req = {
        "id": req_id,
        "campaign_name": name,
        "char_filename": req_in.char_filename,
        "char_name": canonical_target_name,
        "target_char_id": resolved_target_char_id,
        "target_owner_id": resolved_target_owner_id,
        "roll_type": req_in.roll_type,
        "stat": req_in.stat,
        "reason": req_in.reason,
        "status": "pending",
        "result": None,
        "is_secret": req_in.is_secret,
        "created_at": now,
    }

    if req_in.manual_roll is not None:
        if req_in.manual_roll < 1 or req_in.manual_roll > 20:
            raise HTTPException(status_code=422, detail="Manual roll must be between 1 and 20")
        modifier = _sheet_modifier(char_doc, req_in.roll_type, req_in.stat) if char_doc else 0
        raw = req_in.manual_roll
        total = raw + modifier
        new_req["result"] = {
            "total": total,
            "expression": f"1d20 ({raw}) {modifier:+d}",
            "raw": raw,
            "rolls": [raw],
            "modifier": modifier,
            "mode": "normal",
            "situational_bonus": 0,
        }
        new_req["status"] = "resolved"
        new_req["rolled_by"] = "dm"
        new_req["resolved_at"] = now

        db_req = new_req.copy()
        await db["campaign_roll_requests"].insert_one(db_req)
        await _broadcast_roll_event(
            manager,
            name,
            {"type": "roll_result", "payload": new_req},
            dm_only=req_in.is_secret,
            characters=None if req_in.is_secret else [canonical_target_name],
            user_ids=(
                None
                if req_in.is_secret or not resolved_target_owner_id
                else [resolved_target_owner_id]
            ),
        )

        return {
            "success": True,
            "message": f"Manual roll recorded for {canonical_target_name}",
            "request": new_req,
        }

    if req_in.is_secret:
        # A secret roll is never asked of the player: it is thrown here, against
        # their sheet, and only the DM is told. Nothing about it reaches the hero's
        # socket, and `/messages` withholds it from them on reconnect too.
        new_req["result"] = _roll_in_secret(char_doc, req_in.roll_type, req_in.stat)
        new_req["status"] = "resolved"
        new_req["rolled_by"] = "dm"
        new_req["resolved_at"] = now

        db_req = new_req.copy()
        await db["campaign_roll_requests"].insert_one(db_req)
        await manager.broadcast(name, {"type": "roll_result", "payload": new_req}, dm_only=True)

        return {
            "success": True,
            "message": f"Secret roll made for {canonical_target_name}",
            "request": new_req,
        }

    cancel_single_filter: Dict[str, Any] = {
        "campaign_name": name,
        "char_filename": req_in.char_filename,
        "status": "pending",
    }
    if resolved_target_char_id:
        cancel_single_filter = {
            "campaign_name": name,
            "status": "pending",
            "$or": [
                {"target_char_id": resolved_target_char_id},
                {"char_filename": req_in.char_filename},
            ],
        }
    await db["campaign_roll_requests"].update_many(
        cancel_single_filter,
        {"$set": {"status": "cancelled"}},
    )

    db_req = new_req.copy()
    await db["campaign_roll_requests"].insert_one(db_req)

    await _broadcast_roll_event(
        manager,
        name,
        {"type": "roll_request", "payload": new_req},
        characters=[canonical_target_name],
        user_ids=[resolved_target_owner_id] if resolved_target_owner_id else None,
    )

    return {
        "success": True,
        "message": f"Roll request sent for {canonical_target_name}",
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
        target_char_id=target.get("target_char_id"),
    )
    if target_char:
        owner_id = target_char.get("owner_id")
        if owner_id and owner_id == current_user["id"]:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to act on this roll request",
        )

    for cid in _member_character_ids(member):
        if target.get("target_char_id") and target.get("target_char_id") != cid:
            continue
        member_char = await db["characters"].find_one({"char_id": cid})
        if member_char and member_char.get("char_name") == target.get("char_name"):
            owner_id = member_char.get("owner_id")
            if owner_id and owner_id == current_user["id"]:
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

    target_uid = target.get("target_owner_id")
    await _broadcast_roll_event(
        manager,
        name,
        {"type": "roll_result", "payload": target},
        characters=[target.get("char_name")],
        user_ids=[target_uid] if target_uid else None,
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

    target_uid = target.get("target_owner_id")
    await _broadcast_roll_event(
        manager,
        name,
        {"type": "roll_result", "payload": target},
        characters=[target.get("char_name")],
        user_ids=[target_uid] if target_uid else None,
    )

    return {"success": True, "message": "Roll request marked as missed"}


@router.post("/{name}/rolls", response_model=CampaignRollResponse)
@limiter.limit("60/minute")
async def publish_sheet_roll(
    request: Request,
    name: str,
    payload: SheetRollCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_member()),
):
    """Persist and broadcast a player character-sheet roll to the campaign roll log (#197)."""
    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    char_doc = None
    member_char_ids = _member_character_ids(member)
    if member.get("role") != "dm":
        if payload.char_id:
            char_doc = await db["characters"].find_one(
                {
                    "char_id": payload.char_id,
                    "owner_id": current_user["id"],
                    "active_campaign": name,
                }
            )
            if not char_doc and payload.char_id in member_char_ids:
                member_char = await db["characters"].find_one({"char_id": payload.char_id})
                if member_char and member_char.get("owner_id") in (None, current_user["id"]):
                    char_doc = member_char
        else:
            char_doc = await db["characters"].find_one(
                {
                    "char_name": {"$regex": f"^{re.escape(payload.char_name)}$", "$options": "i"},
                    "owner_id": current_user["id"],
                    "active_campaign": name,
                }
            )
            if not char_doc:
                for cid in member_char_ids:
                    member_char = await db["characters"].find_one({"char_id": cid})
                    if (
                        member_char
                        and member_char.get("owner_id") in (None, current_user["id"])
                        and (member_char.get("char_name") or "").strip().lower()
                        == payload.char_name.lower()
                    ):
                        char_doc = member_char
                        break

        if not char_doc:
            raise HTTPException(
                status_code=403,
                detail="You can only broadcast rolls for your own character in this campaign.",
            )
    elif payload.char_id:
        char_doc = await db["characters"].find_one(
            {"char_id": payload.char_id, "active_campaign": name}
        )

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    canonical_char_id = (char_doc.get("char_id") if char_doc else None) or payload.char_id
    canonical_char_name = (char_doc.get("char_name") if char_doc else None) or payload.char_name
    edition = (
        payload.dnd_edition
        or (char_doc.get("dnd_edition") if char_doc else None)
        or camp.get("dnd_edition")
    )
    roll_doc: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "campaign_name": name,
        "sender_user_id": current_user["id"],
        "sender_username": current_user.get("username"),
        "char_id": canonical_char_id,
        "char_name": canonical_char_name,
        "roll_label": payload.roll_label,
        "roll_type": payload.roll_type,
        "formula": payload.formula,
        "natural_roll": payload.natural_roll,
        "rolls": list(payload.rolls),
        "modifier": payload.modifier,
        "total": payload.total,
        "mode": payload.mode,
        "is_crit": payload.is_crit,
        "is_fumble": payload.is_fumble,
        "visibility": payload.visibility,
        "dnd_edition": edition,
        "created_at": now_iso,
    }

    await db["campaign_roll_logs"].insert_one(roll_doc.copy())

    from server.routers.websocket_router import manager

    await manager.broadcast(
        name,
        {"type": "campaign_roll", "payload": roll_doc},
        dm_only=(payload.visibility == "dm"),
    )

    return {
        "success": True,
        "message": f"Roll recorded for {canonical_char_name}",
        "roll": roll_doc,
    }


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

    whisper_filter: Dict[str, Any] = {"campaign_name": name, "archived_at": None}

    if member.get("role") == "player":
        my_char_ids: List[str] = list(_member_character_ids(member))
        my_char_names: List[str] = []

        for cid in list(my_char_ids):
            char_doc = await db["characters"].find_one({"char_id": cid})
            if char_doc and char_doc.get("char_name"):
                my_char_names.append(char_doc["char_name"])

        char_cursor = db["characters"].find(
            {"owner_id": current_user["id"], "active_campaign": name}
        )
        if hasattr(char_cursor, "__aiter__"):
            async for char_doc in char_cursor:
                cid = char_doc.get("char_id")
                cname = char_doc.get("char_name")
                if cid and cid not in my_char_ids:
                    my_char_ids.append(cid)
                if cname and cname not in my_char_names:
                    my_char_names.append(cname)

        player_conditions: List[Dict[str, Any]] = [
            {"recipient": "All"},
            {"sender_user_id": current_user["id"]},
            {"recipient_user_id": current_user["id"]},
        ]
        if my_char_ids:
            player_conditions.extend(
                [
                    {"sender_character_id": {"$in": my_char_ids}},
                    {"recipient_character_id": {"$in": my_char_ids}},
                ]
            )
        for cname in my_char_names:
            player_conditions.extend(
                [
                    {
                        "$and": [
                            {"sender": cname},
                            {"sender_user_id": None},
                            {"sender_character_id": None},
                        ]
                    },
                    {
                        "$and": [
                            {"recipient": cname},
                            {"recipient_user_id": None},
                            {"recipient_character_id": None},
                        ]
                    },
                ]
            )
        whisper_filter["$or"] = player_conditions

    cursor_w = db["campaign_whispers"].find(whisper_filter).sort("timestamp", -1).limit(100)
    all_whispers = []
    async for w in cursor_w:
        w.pop("_id", None)
        all_whispers.append(w)

    all_whispers.reverse()
    whispers = all_whispers

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

    is_dm = member.get("role") == "dm"
    roll_logs: List[Dict[str, Any]] = []
    if not isinstance(db, dict) or "campaign_roll_logs" in db:
        roll_log_filter: Dict[str, Any] = {"campaign_name": name}
        if not is_dm:
            roll_log_filter["$or"] = [
                {"visibility": "public"},
                {"sender_user_id": current_user["id"]},
            ]
        cursor_logs = (
            db["campaign_roll_logs"].find(roll_log_filter).sort("created_at", -1).limit(100)
        )
        if hasattr(cursor_logs, "__aiter__"):
            try:
                async for rl in cursor_logs:
                    rl.pop("_id", None)
                    if isinstance(rl.get("created_at"), datetime.datetime):
                        rl["created_at"] = rl["created_at"].isoformat()
                    roll_logs.append(rl)
                roll_logs.reverse()
            except TypeError:
                roll_logs = []

    return {
        "campaign_name": camp["campaign_name"],
        "whispers": whispers,
        "roll_requests": _visible_roll_requests(
            roll_requests, is_dm, current_user_id=current_user["id"]
        ),
        "roll_logs": roll_logs,
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
        char_doc = None
        member_char_ids = _member_character_ids(member)
        if payload.sender_character_id:
            char_doc = await db["characters"].find_one(
                {
                    "char_id": payload.sender_character_id,
                    "owner_id": current_user["id"],
                    "active_campaign": name,
                }
            )
            if not char_doc and payload.sender_character_id in member_char_ids:
                candidate = await db["characters"].find_one(
                    {"char_id": payload.sender_character_id}
                )
                if candidate and candidate.get("owner_id") in (None, current_user["id"]):
                    char_doc = candidate
            if not char_doc:
                raise HTTPException(
                    status_code=403,
                    detail="You can only whisper as your own character in this campaign.",
                )
        elif member_char_ids:
            for cid in member_char_ids:
                char_doc = await db["characters"].find_one({"char_id": cid})
                if char_doc:
                    break

        if char_doc:
            sender_character_id = char_doc.get("char_id")
            sender_character_name = char_doc.get("char_name")
            sender_name = sender_character_name or sender_username or "Player"
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
        target_char = None
        if payload.recipient_character_id:
            target_char = await db["characters"].find_one(
                {"active_campaign": name, "char_id": payload.recipient_character_id}
            )
        if not target_char:
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

    resolved_recipient = recipient_character_name or payload.recipient

    new_whisper = {
        "id": str(uuid.uuid4()),
        "campaign_name": name,
        "sender": sender_name,
        "recipient": resolved_recipient,
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

    existing_open = await db["whisper_reports"].find_one(
        {
            "campaign_name": name,
            "whisper_id": whisper_id,
            "reported_by_user_id": current_user["id"],
            "status": "open",
        }
    )
    if existing_open:
        return {"success": True, "message": "Whisper already reported."}

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
    for c in encounter.get("combatants") or []:
        if not c.get("health_status"):
            c["health_status"] = _compute_health_status(c.get("hp"), c.get("max_hp"))

    if member.get("role") != "dm":
        return _redact_encounter_for_player(encounter)
    return encounter


@router.post("/{name}/encounter", response_model=EncounterSyncResponseSchema)
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
    for c in enc_dict.get("combatants") or []:
        c["health_status"] = _compute_health_status(c.get("hp"), c.get("max_hp"))

    # Calculate Danger Indicator dynamically
    enc_dict["danger_indicator"] = await calculate_danger_indicator(
        enc_dict.get("combatants", []), db, edition=camp.get("dnd_edition", "2014 Edition")
    )

    enc_dict["campaign_name"] = name

    await db["campaign_encounters"].update_one(
        {"campaign_name": name}, {"$set": enc_dict}, upsert=True
    )

    from server.routers.websocket_router import manager

    params = inspect.signature(manager.broadcast).parameters
    if "dm_only" in params and "player_only" in params:
        await manager.broadcast(
            name, {"type": "encounter_update", "payload": enc_dict}, dm_only=True
        )
        await manager.broadcast(
            name,
            {"type": "encounter_update", "payload": _redact_encounter_for_player(enc_dict)},
            player_only=True,
        )
    else:
        await manager.broadcast(name, {"type": "encounter_update", "payload": enc_dict})

    return {
        "success": True,
        "message": "Encounter state updated",
        "danger_indicator": enc_dict.get("danger_indicator"),
    }


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

    # 3. Reconcile campaign_members record
    owner_id = char.get("owner_id")
    if owner_id:
        member_doc = await db["campaign_members"].find_one(
            {"campaign_id": name, "user_id": owner_id}
        )
        if member_doc:
            member_filter = (
                {"_id": member_doc["_id"]}
                if "_id" in member_doc
                else {"campaign_id": name, "user_id": owner_id}
            )
            if member_doc.get("role") != "dm":
                # Check if this user has any other active characters in this campaign
                other_active_chars = await db["characters"].count_documents(
                    {
                        "owner_id": owner_id,
                        "active_campaign": name,
                    }
                )

                if other_active_chars == 0:
                    await db["campaign_members"].delete_one(member_filter)
                else:
                    update_ops: Dict[str, Any] = {"$pull": {"character_ids": char_id}}
                    if member_doc.get("character_id") == char_id:
                        remaining = await db["characters"].find_one(
                            {
                                "owner_id": owner_id,
                                "active_campaign": name,
                                "char_id": {"$ne": char_id},
                            }
                        )
                        update_ops["$set"] = {
                            "character_id": remaining.get("char_id") if remaining else None
                        }
                    await db["campaign_members"].update_one(member_filter, update_ops)
            else:
                update_ops = {"$pull": {"character_ids": char_id}}
                if member_doc.get("character_id") == char_id:
                    update_ops["$set"] = {"character_id": None}
                await db["campaign_members"].update_one(member_filter, update_ops)

    from server.routers.websocket_router import manager

    kicked_user_id = None
    if owner_id:
        remaining_member = await db["campaign_members"].find_one(
            {"campaign_id": name, "user_id": owner_id}
        )
        if not remaining_member:
            kicked_user_id = owner_id

    if hasattr(manager, "disconnect_campaign_member"):
        await manager.disconnect_campaign_member(
            name,
            user_id=kicked_user_id,
            character_name=char.get("char_name"),
        )

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

    if member.get("role") != "dm":
        entities = [e for e in entities if e.get("is_revealed", False)]

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
    data["campaign_name"] = name
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
    encoded_name = quote(name, safe="")
    if f"/campaigns/{name}/assets/" in map_url or f"/campaigns/{encoded_name}/assets/" in map_url:
        filename = os.path.basename(map_url.rsplit("/", 1)[-1].split("?", 1)[0])
        other_scene = await db["campaign_scenes"].find_one(
            {
                "campaign_name": name,
                "scene_id": {"$ne": scene_id},
                "grid.background_image_url": {"$regex": f"/assets/{re.escape(filename)}$"},
            }
        )
        if filename and not other_scene:
            asset_owner = await db["campaign_assets"].find_one({"filename": filename})
            if not asset_owner or asset_owner.get("campaign_name") == name:
                uploads_base = os.path.abspath(os.path.join("data", "uploads"))
                file_path = os.path.abspath(os.path.join(uploads_base, filename))
                if os.path.commonpath([uploads_base, file_path]) == uploads_base and os.path.exists(
                    file_path
                ):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.warning("Failed removing map asset file %s: %s", file_path, e)
                await db["campaign_assets"].delete_one(
                    {"campaign_name": name, "filename": filename}
                )

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


def _resolve_item_recipient(
    raw_item: Dict[str, Any],
    default_recipient_id: Optional[str],
    fallback_first_char_id: Optional[str],
) -> Optional[str]:
    """Return the target char_id for an awarded loot item, or None for party-wide delivery."""
    explicit_id = raw_item.get("recipient_id") or raw_item.get("recipient_char_id")
    if isinstance(explicit_id, str) and explicit_id.strip():
        return explicit_id.strip()
    if default_recipient_id:
        return default_recipient_id
    if raw_item.get("requires_attunement") or raw_item.get("attuned") or raw_item.get("unique"):
        return fallback_first_char_id
    return None


@router.post("/{name}/loot/distribute")
async def distribute_loot(
    name: str,
    payload: LootDistributionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    member: dict = Depends(require_campaign_role("dm")),
):
    """Distribute currency and/or items to selected campaign characters and broadcast via WebSocket."""
    from pydantic import ValidationError

    from backend.core.schemas import EquipmentItem, FeatureTrait, SpellSchema, Weapon
    from backend.services.stats_service import calculate_weapon_stats

    camp = await db["campaigns"].find_one({"campaign_name": name})
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    unique_char_ids = list(dict.fromkeys(cid for cid in (payload.character_ids or []) if cid))
    if not unique_char_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one character must be selected to receive loot.",
        )

    raw_currency = {
        "pp": max(0, payload.currency.pp) if payload.currency else 0,
        "gp": max(0, payload.currency.gp) if payload.currency else 0,
        "ep": max(0, payload.currency.ep) if payload.currency else 0,
        "sp": max(0, payload.currency.sp) if payload.currency else 0,
        "cp": max(0, payload.currency.cp) if payload.currency else 0,
    }

    # Fetch and validate items
    awarded_items: List[Dict[str, Any]] = []
    if payload.items:
        for item in payload.items:
            if not isinstance(item, dict) or not str(item.get("name") or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="All distributed items must have a valid name.",
                )
            if item.get("homebrew_type") == "monster" or item.get("type") == "monster":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Monsters cannot be distributed as loot.",
                )
            awarded_items.append(item)

    if payload.homebrew_item_ids:
        from bson import ObjectId
        from bson.errors import InvalidId

        for hb_id in payload.homebrew_item_ids:
            try:
                oid = ObjectId(hb_id)
                hb_doc = await db["homebrew_content"].find_one({"_id": oid, "campaign_id": name})
                if hb_doc:
                    if hb_doc.get("homebrew_type") == "monster" or hb_doc.get("type") == "monster":
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Monsters cannot be distributed as loot.",
                        )
                    hb_doc["_id"] = str(hb_doc["_id"])
                    awarded_items.append(hb_doc)
            except InvalidId:
                continue

    if sum(raw_currency.values()) == 0 and not awarded_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one currency amount or item must be provided to distribute loot.",
        )

    # Validate and classify items by schema before writing, preserving raw recipient targeting
    classified_items: List[tuple[str, Any, Dict[str, Any]]] = []

    try:
        for item in awarded_items:
            htype = item.get("homebrew_type") or item.get("type") or "item"
            if htype == "weapon":
                classified_items.append(("weapon", Weapon.model_validate(item).model_dump(), item))
            elif htype == "spell":
                classified_items.append(("spell", SpellSchema.model_validate(item), item))
            elif htype in ("feat", "feature"):
                classified_items.append(
                    (
                        "feature",
                        FeatureTrait.model_validate(
                            {
                                "name": item["name"],
                                "description": item.get("description", ""),
                                "source": item.get("source") or "Homebrew",
                            }
                        ).model_dump(),
                        item,
                    )
                )
            else:
                classified_items.append(
                    ("equipment", EquipmentItem.model_validate(item).model_dump(), item)
                )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid loot item schema: {e.errors()}",
        ) from e

    # Resolve valid campaign characters first so currency split uses valid recipients
    valid_chars: List[dict] = []
    for char_id in unique_char_ids:
        char = await db["characters"].find_one({"char_id": char_id})
        if char and char.get("active_campaign") == name:
            valid_chars.append(char)

    divisor = len(valid_chars) if (payload.split_currency and len(valid_chars) > 1) else 1
    leftover_cp = 0
    if payload.currency:
        if divisor > 1:
            pp_each, pp_rem = divmod(raw_currency["pp"], divisor)
            gp_total = raw_currency["gp"] + (pp_rem * 10)
            gp_each, gp_rem = divmod(gp_total, divisor)
            ep_each, ep_rem = divmod(raw_currency["ep"], divisor)
            sp_total = raw_currency["sp"] + (gp_rem * 10) + (ep_rem * 5)
            sp_each, sp_rem = divmod(sp_total, divisor)
            cp_total = raw_currency["cp"] + (sp_rem * 10)
            cp_each, leftover_cp = divmod(cp_total, divisor)
            char_currency: Dict[str, int] = {
                "pp": pp_each,
                "gp": gp_each,
                "ep": ep_each,
                "sp": sp_each,
                "cp": cp_each,
            }
        else:
            char_currency = dict(raw_currency)
    else:
        char_currency = {}

    total_currency_given = sum(char_currency.values()) + leftover_cp

    if total_currency_given == 0 and not awarded_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one currency amount or item must be provided to distribute loot.",
        )

    fallback_first_char_id = valid_chars[0]["char_id"] if valid_chars else None

    updated_count = 0
    updated_character_ids: List[str] = []
    updated_character_names: List[str] = []

    for idx, char in enumerate(valid_chars):
        char_id = char["char_id"]
        update_ops: Dict[str, Any] = {}
        inc_ops: Dict[str, int] = {}

        # Handle currency
        if total_currency_given > 0:
            if not isinstance(char.get("currency"), dict):
                await db["characters"].update_one(
                    {"char_id": char_id},
                    {"$set": {"currency": {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 0}}},
                )
            for coin, amount in char_currency.items():
                bonus_cp = 1 if (coin == "cp" and idx < leftover_cp) else 0
                if amount + bonus_cp > 0:
                    inc_ops[f"currency.{coin}"] = amount + bonus_cp

        char_weapons_base: List[Dict[str, Any]] = []
        char_equip_to_push: List[Dict[str, Any]] = []
        char_feats_to_push: List[Dict[str, Any]] = []
        char_spells_to_push: List[SpellSchema] = []

        for kind, validated_data, raw_item in classified_items:
            item_target = _resolve_item_recipient(
                raw_item, payload.item_recipient_id, fallback_first_char_id
            )
            if item_target is not None and item_target != char_id:
                continue
            if kind == "weapon":
                char_weapons_base.append(validated_data)
            elif kind == "equipment":
                char_equip_to_push.append(validated_data)
            elif kind == "feature":
                char_feats_to_push.append(validated_data)
            elif kind == "spell":
                char_spells_to_push.append(validated_data)

        # Compute per-character weapon stats using character's ability scores & proficiency bonus
        char_weapons_to_push: List[Dict[str, Any]] = []
        if char_weapons_base:
            char_stats = char.get("stats") or {}
            char_prof = char.get("proficiency_bonus") or 2
            for w_base in char_weapons_base:
                w_calc = calculate_weapon_stats(
                    dict(w_base), char_stats, char_prof, homebrew_content=awarded_items
                )
                char_weapons_to_push.append(Weapon.model_validate(w_calc).model_dump())

        # Ensure arrays are initialized if missing or corrupted
        if char_weapons_to_push and not isinstance(char.get("weapons"), list):
            await db["characters"].update_one({"char_id": char_id}, {"$set": {"weapons": []}})
        if char_equip_to_push and not isinstance(char.get("equipment"), list):
            await db["characters"].update_one({"char_id": char_id}, {"$set": {"equipment": []}})
        if char_feats_to_push and not isinstance(char.get("features_traits"), list):
            await db["characters"].update_one(
                {"char_id": char_id}, {"$set": {"features_traits": []}}
            )

        push_ops: Dict[str, Any] = {}
        if char_weapons_to_push:
            push_ops["weapons"] = {"$each": char_weapons_to_push}
        if char_equip_to_push:
            push_ops["equipment"] = {"$each": char_equip_to_push}
        if char_feats_to_push:
            push_ops["features_traits"] = {"$each": char_feats_to_push}

        if push_ops:
            update_ops["$push"] = push_ops

        if char_spells_to_push:
            if not isinstance(char.get("spells"), dict):
                await db["characters"].update_one({"char_id": char_id}, {"$set": {"spells": {}}})
            if not isinstance(char.get("prepared_spells"), list):
                await db["characters"].update_one(
                    {"char_id": char_id}, {"$set": {"prepared_spells": []}}
                )
            add_to_set_ops: Dict[str, Any] = {}
            prep_names: List[str] = []
            for spell in char_spells_to_push:
                lvl_key = "cantrips" if spell.level == 0 else f"level_{spell.level}"
                add_to_set_ops.setdefault(f"spells.{lvl_key}", {"$each": []})["$each"].append(
                    spell.name
                )
                prep_names.append(spell.name)
            if prep_names:
                add_to_set_ops["prepared_spells"] = {"$each": prep_names}
            if add_to_set_ops:
                update_ops["$addToSet"] = add_to_set_ops

        if inc_ops or update_ops:
            inc_ops["version"] = 1
            update_ops["$inc"] = inc_ops
            await db["characters"].update_one({"char_id": char_id}, update_ops)
            updated_count += 1
            updated_character_ids.append(char_id)
            updated_character_names.append(char.get("char_name", char_id))

    item_names = [it.get("name", "Unknown Item") for it in awarded_items]

    # WebSocket broadcast only when at least one character was actually updated
    if updated_count > 0:
        from server.routers.websocket_router import manager

        await manager.broadcast(
            name,
            {
                "type": "loot_distributed",
                "payload": {
                    "character_ids": updated_character_ids,
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
