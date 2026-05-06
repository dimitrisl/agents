import json
import os
import logging

logger = logging.getLogger("DnDAssistant.Storage")

DATA_DIR = "data"
CHAR_DIR = os.path.join(DATA_DIR, "characters")
CAMP_DIR = os.path.join(DATA_DIR, "campaigns")


def _ensure_dirs():
    """Ensure the data directories exist."""
    os.makedirs(CHAR_DIR, exist_ok=True)
    os.makedirs(CAMP_DIR, exist_ok=True)


def save_character(char_data: dict) -> bool:
    """Save a character dictionary to a local JSON file."""
    _ensure_dirs()
    if "char_name" not in char_data:
        logger.error("Cannot save character without a name.")
        return False

    char_id = char_data.get("char_id", "unknown_id")
    filename = f"{char_data['char_name'].replace(' ', '_').lower()}_{char_id}.json"
    filepath = os.path.join(CHAR_DIR, filename)

    try:
        with open(filepath, "w") as f:
            json.dump(char_data, f, indent=4)
        logger.info(f"Successfully saved character to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save character: {e}", exc_info=True)
        return False


def load_character(filename: str) -> dict:
    """Load a character dictionary from a local JSON file using the filename."""
    filepath = os.path.join(CHAR_DIR, filename)

    if not os.path.exists(filepath):
        logger.warning(f"Character file not found: {filepath}")
        return None

    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        logger.info(f"Successfully loaded character from {filepath}")
        return data
    except Exception as e:
        logger.error(f"Failed to load character: {e}", exc_info=True)
        return None


def list_characters() -> list:
    """Return a list of available character filenames."""
    _ensure_dirs()
    chars = []
    for f in os.listdir(CHAR_DIR):
        if f.endswith(".json"):
            chars.append(f)
    return chars


def delete_character(filename: str) -> bool:
    """Delete a character JSON file and its associated portrait."""
    filepath = os.path.join(CHAR_DIR, filename)

    # Attempt to delete the portrait first
    try:
        # Filename is usually name_id.json
        char_id = filename.split("_")[-1].replace(".json", "")
        portrait_path = os.path.join(DATA_DIR, "portraits", f"{char_id}.png")
        if os.path.exists(portrait_path):
            os.remove(portrait_path)
            logger.info(f"Successfully deleted portrait: {portrait_path}")
    except Exception as e:
        logger.warning(f"Failed to delete portrait during character deletion: {e}")

    if os.path.exists(filepath):
        try:
            # Check if character is in a campaign and remove them from it
            char_data = load_character(filename)
            if char_data and char_data.get("active_campaign"):
                remove_from_campaign(char_data["active_campaign"], filename)

            os.remove(filepath)
            logger.info(f"Successfully deleted character: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete character: {e}")
            return False
    return False


def save_campaign(campaign_name: str, notes: str, party: list = None) -> bool:
    """Save campaign notes and party list to a local JSON file."""
    _ensure_dirs()
    if not campaign_name:
        return False

    filename = f"{campaign_name.replace(' ', '_').lower()}.json"
    filepath = os.path.join(CAMP_DIR, filename)

    # If party is not provided, try to load existing party to avoid wiping it
    if party is None:
        existing_data = load_campaign(campaign_name)
        if existing_data:
            party = existing_data.get("party", [])
        else:
            party = []

    data = {
        "campaign_name": campaign_name,
        "notes": notes,
        "party": party,
    }

    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
        logger.info(f"Successfully saved campaign to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save campaign: {e}", exc_info=True)
        return False


def load_campaign(name: str) -> dict:
    """Load a campaign dictionary from a local JSON file."""
    filename = f"{name.replace(' ', '_').lower()}.json"
    filepath = os.path.join(CAMP_DIR, filename)

    if not os.path.exists(filepath):
        logger.warning(f"Campaign file not found: {filepath}")
        return None

    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        logger.info(f"Successfully loaded campaign from {filepath}")
        return data
    except Exception as e:
        logger.error(f"Failed to load campaign: {e}", exc_info=True)
        return None


def list_campaigns() -> list:
    """Return a list of available campaign names."""
    _ensure_dirs()
    camps = []
    for f in os.listdir(CAMP_DIR):
        if f.endswith(".json"):
            camps.append(f.replace(".json", "").replace("_", " ").title())
    return camps


def join_campaign(campaign_name: str, char_filename: str) -> bool:
    """Add a character filename to a campaign's party list and update character data."""
    data = load_campaign(campaign_name)
    if not data:
        return False

    party = data.get("party", [])
    if char_filename not in party:
        party.append(char_filename)
        if not save_campaign(campaign_name, data.get("notes", ""), party):
            return False

    # Also update the character file to remember the campaign
    char_data = load_character(char_filename)
    if char_data:
        char_data["active_campaign"] = campaign_name
        save_character(char_data)

    return True


def remove_from_campaign(campaign_name: str, char_filename: str) -> bool:
    """Remove a character from a campaign and update character data."""
    data = load_campaign(campaign_name)
    if not data:
        return False

    party = data.get("party", [])
    if char_filename in party:
        party.remove(char_filename)
        if not save_campaign(campaign_name, data.get("notes", ""), party):
            return False

    # Also update the character file to forget the campaign
    char_data = load_character(char_filename)
    if char_data and char_data.get("active_campaign") == campaign_name:
        char_data["active_campaign"] = None
        save_character(char_data)

    return True
