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


@st.cache_data(ttl=3600)
def _cached_list_characters(owner_id: str):
    return _char_repo.list_all(owner_id=owner_id)


@st.cache_data(ttl=3600)
def _cached_load_campaign(name: str):
    return _camp_repo.load(name)


@st.cache_data(ttl=3600)
def _cached_list_campaigns(edition: str, owner_id: str):
    return _camp_repo.list_all(edition=edition, owner_id=owner_id)


def save_character(char_data: dict) -> bool:
    try:
        owner_id = _get_owner_id()
        if owner_id:
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
            return (
                dict(st.session_state.char_cache[filename])
                if st.session_state.char_cache[filename]
                else None
            )
        except Exception:
            return _char_repo.load(filename)
    except ValueError as e:
        logger.error(f"load_character failed due to validation failure: {e}")
        return None


def list_characters() -> list:
    return _cached_list_characters(_get_owner_id())


def delete_character(filename: str) -> bool:
    """Delete a character and clean up associations."""
    # 1. Handle portrait
    try:
        char_id = filename.split("_")[-1].replace(".json", "")
        portrait_path = os.path.join("data", "portraits", f"{char_id}.png")
        if os.path.exists(portrait_path):
            os.remove(portrait_path)
    except Exception as e:
        logger.warning(f"Failed to delete portrait: {e}")

    # 2. Handle campaign removal
    char_data = load_character(filename)
    if char_data and char_data.get("active_campaign"):
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
    res = _camp_repo.save(
        campaign_name,
        notes,
        party,
        dnd_edition=edition,
        owner_id=_get_owner_id(),
        **kwargs,
    )
    if res:
        _cached_load_campaign.clear()
        _cached_list_campaigns.clear()
    return res


def load_campaign(name: str) -> dict:
    return _cached_load_campaign(name)


def list_campaigns(edition: str = None) -> list:
    return _cached_list_campaigns(edition, _get_owner_id())


def delete_campaign(campaign_name: str) -> bool:
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
