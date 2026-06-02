import logging
import os
import streamlit as st
from backend.repositories.character_repository import CharacterRepository
from backend.repositories.campaign_repository import CampaignRepository

logger = logging.getLogger("DnDAssistant.Storage")

# Initialize repositories
_char_repo = CharacterRepository()
_camp_repo = CampaignRepository()


def _get_owner_id():
    try:
        import streamlit as st

        user = st.session_state.get("user")
        return user.get("id") if user else None
    except Exception:
        return None


@st.cache_data(ttl=60)
def _cached_list_characters(owner_id: str):
    return _char_repo.list_all(owner_id=owner_id)


@st.cache_data(ttl=3600)
def _cached_load_campaign(name: str):
    return _camp_repo.load(name)


@st.cache_data(ttl=3600)
def _cached_list_campaigns(edition: str, owner_id: str):
    return _camp_repo.list_all(edition=edition, owner_id=owner_id)


def clear_character_cache():
    """Force-clear the character list cache. Call on login/logout."""
    _cached_list_characters.clear()


def save_character(char_data: dict) -> bool:
    try:
        owner_id = _get_owner_id()
        # Only assign owner_id if the character doesn't already have one
        # This prevents overwriting another player's character when saving
        if owner_id and not char_data.get("owner_id"):
            char_data["owner_id"] = owner_id
        res = _char_repo.save(char_data)
        if res:
            try:
                import streamlit as st

                if "char_cache" in st.session_state:
                    char_id = char_data.get("char_id")
                    for k in list(st.session_state.char_cache.keys()):
                        if char_id and char_id in k:
                            st.session_state.char_cache[k] = dict(char_data)
            except Exception:
                pass
            _cached_list_characters.clear()
        return res
    except ValueError as e:
        logger.error(f"save_character rejected due to validation failure: {e}")
        return False


def load_character(filename: str) -> dict:
    try:
        try:
            import streamlit as st

            if "char_cache" not in st.session_state:
                st.session_state.char_cache = {}
            if filename not in st.session_state.char_cache:
                st.session_state.char_cache[filename] = _char_repo.load(filename)
            data = (
                dict(st.session_state.char_cache[filename])
                if st.session_state.char_cache[filename]
                else None
            )
        except Exception:
            data = _char_repo.load(filename)

        if data:
            owner_id = _get_owner_id()
            char_owner = data.get("owner_id")
            if char_owner and char_owner != owner_id:
                # Check if the character is part of any campaign owned by the current user (e.g. DM loading party character)
                from backend.core.db import get_db

                db = get_db()
                if db is not None:
                    campaigns_col = db["campaigns"]
                    campaign = campaigns_col.find_one(
                        {"owner_id": owner_id, "party": filename}
                    )
                    if campaign:
                        return data
                logger.warning(
                    f"Unauthorized access attempt to character {filename} by user {owner_id}"
                )
                return None
        return data
    except ValueError as e:
        logger.error(f"load_character failed due to validation failure: {e}")
        return None


def list_characters() -> list:
    return _cached_list_characters(_get_owner_id())


def delete_character(filename: str) -> bool:
    """Delete a character and clean up associations."""
    char_data = load_character(filename)
    if not char_data:
        logger.warning(
            f"Unauthorized or non-existent delete attempt for character {filename}"
        )
        return False

    # 1. Handle portrait
    try:
        char_id = filename.split("_")[-1].replace(".json", "")
        portrait_path = os.path.join("data", "portraits", f"{char_id}.png")
        if os.path.exists(portrait_path):
            os.remove(portrait_path)
    except Exception as e:
        logger.warning(f"Failed to delete portrait: {e}")

    # 2. Handle campaign removal
    if char_data.get("active_campaign"):
        remove_from_campaign(char_data["active_campaign"], filename)

    # 3. Finally delete the character
    res = _char_repo.delete(filename)
    if res:
        try:
            import streamlit as st

            if (
                "char_cache" in st.session_state
                and filename in st.session_state.char_cache
            ):
                del st.session_state.char_cache[filename]
        except Exception:
            pass
        _cached_list_characters.clear()
    return res


def save_campaign(
    campaign_name: str, notes: str, party: list = None, edition: str = None, **kwargs
) -> bool:
    # Preserve existing owner_id if it exists to prevent players from "stealing" ownership
    owner_id = kwargs.pop("owner_id", None)
    if not owner_id:
        existing = _camp_repo.load(campaign_name)
        if existing and existing.get("owner_id"):
            owner_id = existing.get("owner_id")
        else:
            owner_id = _get_owner_id()

    res = _camp_repo.save(
        campaign_name,
        notes,
        party,
        dnd_edition=edition,
        owner_id=owner_id,
        **kwargs,
    )
    if res:
        _cached_load_campaign.clear()
        _cached_list_campaigns.clear()
    return res


def load_campaign(name: str) -> dict:
    data = _cached_load_campaign(name)
    if data:
        owner_id = _get_owner_id()
        camp_owner = data.get("owner_id")
        if camp_owner and camp_owner != owner_id:
            # Check if current user is a player with a character in this campaign
            from backend.core.db import get_db

            db = get_db()
            if db is not None:
                characters_col = db["characters"]
                char = characters_col.find_one(
                    {"owner_id": owner_id, "active_campaign": name}
                )
                if char:
                    return data
            logger.warning(
                f"Unauthorized access attempt to campaign {name} by user {owner_id}"
            )
            return None
    return data


def list_campaigns(edition: str = None) -> list:
    return _cached_list_campaigns(edition, _get_owner_id())


def delete_campaign(campaign_name: str) -> bool:
    camp_data = load_campaign(campaign_name)
    if not camp_data:
        logger.warning(
            f"Unauthorized or non-existent delete attempt for campaign {campaign_name}"
        )
        return False
    res = _camp_repo.delete(campaign_name)
    if res:
        _cached_load_campaign.clear()
        _cached_list_campaigns.clear()
    return res


def join_campaign(campaign_name: str, char_filename: str) -> bool:
    data = load_campaign(campaign_name)
    if not data:
        return False

    party = data.get("party", [])
    if char_filename not in party:
        party.append(char_filename)
        if not save_campaign(campaign_name, data.get("notes", ""), party):
            return False

    char_data = load_character(char_filename)
    if char_data:
        char_data["active_campaign"] = campaign_name
        save_character(char_data)
    return True


def remove_from_campaign(campaign_name: str, char_filename: str) -> bool:
    data = load_campaign(campaign_name)
    if not data:
        return False

    party = data.get("party", [])
    if char_filename in party:
        party.remove(char_filename)
        if not save_campaign(campaign_name, data.get("notes", ""), party):
            return False

    char_data = load_character(char_filename)
    if char_data and char_data.get("active_campaign") == campaign_name:
        char_data["active_campaign"] = None
        save_character(char_data)
    return True


def add_roll_request(
    campaign_name: str,
    char_filename: str,
    char_name: str,
    roll_type: str,
    stat: str,
    reason: str = "",
) -> bool:
    camp = load_campaign(campaign_name)
    if not camp:
        return False

    import uuid
    import datetime

    req_id = str(uuid.uuid4())
    req = {
        "id": req_id,
        "char_filename": char_filename,
        "char_name": char_name,
        "roll_type": roll_type,
        "stat": stat,
        "reason": reason,
        "status": "pending",
        "result": None,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    requests = camp.get("roll_requests", [])

    # Ensure only one pending request per character by cancelling older ones
    for old_req in requests:
        if (
            old_req.get("char_filename") == char_filename
            and old_req.get("status") == "pending"
        ):
            old_req["status"] = "cancelled"

    requests.append(req)
    # Clear cache to ensure immediate load
    _cached_load_campaign.clear()
    return save_campaign(
        campaign_name,
        camp.get("notes", ""),
        camp.get("party", []),
        edition=camp.get("dnd_edition"),
        roll_requests=requests,
    )


def submit_roll_result(campaign_name: str, request_id: str, result_text: str) -> bool:
    camp = _camp_repo.load(campaign_name)
    if not camp:
        return False

    requests = camp.get("roll_requests", [])
    updated = False
    for req in requests:
        if req.get("id") == request_id:
            req["status"] = "completed"
            req["result"] = result_text
            updated = True
            break

    if updated:
        _cached_load_campaign.clear()
        return save_campaign(
            campaign_name,
            camp.get("notes", ""),
            camp.get("party", []),
            edition=camp.get("dnd_edition"),
            roll_requests=requests,
        )
    return False


def clear_roll_requests(campaign_name: str) -> bool:
    camp = _camp_repo.load(campaign_name)
    if not camp:
        return False
    _cached_load_campaign.clear()
    return save_campaign(
        campaign_name,
        camp.get("notes", ""),
        camp.get("party", []),
        edition=camp.get("dnd_edition"),
        roll_requests=[],
    )


def generate_invite_code(campaign_name: str) -> str | None:
    """Generate and persist a short invite code for a campaign. Returns the code."""
    camp = load_campaign(campaign_name)
    if not camp:
        return None

    # If already has a code, return it (idempotent)
    existing_code = camp.get("invite_code")
    if existing_code:
        return existing_code

    import hashlib
    import time

    raw = f"{campaign_name}-{time.time()}"
    code = hashlib.md5(raw.encode()).hexdigest()[:6].upper()

    _cached_load_campaign.clear()
    saved = save_campaign(
        campaign_name,
        camp.get("notes", ""),
        camp.get("party", []),
        edition=camp.get("dnd_edition"),
        invite_code=code,
    )
    return code if saved else None


def join_campaign_by_code(invite_code: str, char_filename: str) -> dict:
    """
    Player joins a campaign using an invite code.
    Returns a dict: {"success": bool, "campaign_name": str | None, "error": str | None}
    """
    camp = _camp_repo.find_by_invite_code(invite_code)
    if not camp:
        return {
            "success": False,
            "campaign_name": None,
            "error": "Invalid invite code.",
        }

    campaign_name = camp.get("campaign_name")
    party = camp.get("party", [])

    if char_filename in party:
        return {
            "success": True,
            "campaign_name": campaign_name,
            "error": None,
        }  # already in

    party.append(char_filename)
    _cached_load_campaign.clear()
    saved = save_campaign(
        campaign_name, camp.get("notes", ""), party, edition=camp.get("dnd_edition")
    )
    if not saved:
        return {
            "success": False,
            "campaign_name": None,
            "error": "Could not save campaign after joining.",
        }

    # Update character's active_campaign
    char_data = load_character(char_filename)
    if char_data:
        char_data["active_campaign"] = campaign_name
        save_character(char_data)

    return {"success": True, "campaign_name": campaign_name, "error": None}
