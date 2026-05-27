import logging
import os
from backend.repositories.character_repository import CharacterRepository
from backend.repositories.campaign_repository import CampaignRepository

logger = logging.getLogger("DnDAssistant.Storage")

# Initialize repositories
_char_repo = CharacterRepository()
_camp_repo = CampaignRepository()


def save_character(char_data: dict) -> bool:
    return _char_repo.save(char_data)


def load_character(filename: str) -> dict:
    return _char_repo.load(filename)


def list_characters() -> list:
    return _char_repo.list_all()


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

    return _char_repo.delete(filename)


def save_campaign(
    campaign_name: str, notes: str, party: list = None, dnd_edition: str = None
) -> bool:
    return _camp_repo.save(campaign_name, notes, party, dnd_edition)


def load_campaign(name: str) -> dict:
    return _camp_repo.load(name)


def list_campaigns(edition: str = None) -> list:
    return _camp_repo.list_all(edition)


def delete_campaign(campaign_name: str) -> bool:
    return _camp_repo.delete(campaign_name)


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
