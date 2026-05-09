import os
import json
import logging
from typing import List, Optional
from backend.schemas import CharacterSchema

logger = logging.getLogger("DnDAssistant.CharacterRepo")

DATA_DIR = "data"
CHAR_DIR = os.path.join(DATA_DIR, "characters")


class CharacterRepository:
    def __init__(self):
        os.makedirs(CHAR_DIR, exist_ok=True)

    def save(self, char_data: dict) -> bool:
        """Save a character dictionary to a local JSON file."""
        if "char_name" not in char_data:
            logger.error("Cannot save character without a name.")
            return False

        # Validate against schema before saving
        try:
            validated = CharacterSchema(**char_data)
            char_data = validated.model_dump()
        except Exception as e:
            logger.warning(f"Character data failed validation during save: {e}")

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

    def load(self, filename: str) -> Optional[dict]:
        """Load a character dictionary from a local JSON file."""
        filepath = os.path.join(CHAR_DIR, filename)
        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Failed to load character: {e}")
            return None

    def list_all(self) -> List[str]:
        """Return a list of available character filenames."""
        os.makedirs(CHAR_DIR, exist_ok=True)
        return [f for f in os.listdir(CHAR_DIR) if f.endswith(".json")]

    def delete(self, filename: str) -> bool:
        """Delete a character JSON file."""
        filepath = os.path.join(CHAR_DIR, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception as e:
                logger.error(f"Failed to delete character file: {e}")
                return False
        return False
