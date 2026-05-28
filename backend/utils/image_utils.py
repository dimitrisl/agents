import urllib.parse
import hashlib
import os
import requests
import uuid
import logging
from backend.core.prompts import PORTRAIT_PROMPT

logger = logging.getLogger("DnDAssistant.ImageUtils")

PORTRAIT_DIR = os.path.join("data", "portraits")


def _ensure_dir():
    os.makedirs(PORTRAIT_DIR, exist_ok=True)


def generate_portrait_url(char_data: dict) -> str:
    """
    Generates a character portrait using image.pollinations.ai,
    downloads it, saves it to a local folder, and returns the local path.
    """
    _ensure_dir()

    # If the character already has a local portrait that exists, just return it.
    existing_portrait = char_data.get("char_portrait")
    if (
        existing_portrait
        and existing_portrait.startswith("data/portraits/")
        and os.path.exists(existing_portrait)
    ):
        return existing_portrait

    race = char_data.get("race", "Human")
    char_class = char_data.get("char_class", "Warrior")
    background = char_data.get("background", "")
    backstory = char_data.get("backstory", "")
    alignment = char_data.get("alignment", "")
    gender = char_data.get("gender", "")

    # Extract keywords from backstory (first 150 chars) to avoid prompt bloat
    visual_hooks = backstory[:150] if backstory else ""

    # Construct a rich, descriptive prompt
    prompt = PORTRAIT_PROMPT.format(
        gender=gender,
        race=race,
        char_class=char_class,
        background=background if background else "N/A",
        alignment=alignment if alignment else "N/A",
        visual_hooks=visual_hooks if visual_hooks else "N/A",
    )

    # URL encode the full prompt
    encoded_prompt = urllib.parse.quote(prompt)

    # Use a stable seed based on char_id to keep the URL consistent
    char_id = char_data.get("char_id") or str(uuid.uuid4())[:8]
    seed = int(hashlib.md5(char_id.encode()).hexdigest(), 16) % 999999

    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&seed={seed}&nologo=true"

    try:
        response = requests.get(image_url, timeout=15)
        response.raise_for_status()

        # Save locally
        filename = f"{char_id}.png"
        filepath = os.path.join(PORTRAIT_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(response.content)

        logger.info(f"Successfully downloaded and saved portrait to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to generate and download portrait: {e}")
        return None


def save_custom_portrait(image_bytes: bytes, filename: str) -> str:
    """Saves custom uploaded portrait bytes to data/portraits/ and returns the local file path."""
    _ensure_dir()
    filepath = os.path.join(PORTRAIT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return filepath
