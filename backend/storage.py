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


def save_campaign(campaign_name: str, notes: str) -> bool:
    """Save campaign notes to a local JSON file."""
    _ensure_dirs()
    if not campaign_name:
        return False

    filename = f"{campaign_name.replace(' ', '_').lower()}.json"
    filepath = os.path.join(CAMP_DIR, filename)

    try:
        with open(filepath, "w") as f:
            json.dump({"campaign_name": campaign_name, "notes": notes}, f, indent=4)
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
