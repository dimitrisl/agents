import os
import logging
from typing import List, Optional
from backend.core.schemas import CharacterSchema
from backend.core.db import get_db

logger = logging.getLogger("DnDAssistant.CharacterRepo")

DATA_DIR = "data"
CHAR_DIR = os.path.join(DATA_DIR, "characters")


class CharacterRepository:
    def __init__(self):
        self.db = get_db()
        if self.db is not None:
            self.collection = self.db["characters"]
        else:
            self.collection = None

    def save(self, char_data: dict) -> bool:
        """Save a character dictionary to MongoDB."""
        if self.collection is None:
            logger.error("Database connection missing. Cannot save.")
            return False

        if "char_name" not in char_data:
            logger.error("Cannot save character without a name.")
            return False

        # Validate against schema before saving.
        # We use strict=False to allow for some flexibility in input types (e.g. models vs dicts)
        try:
            validated = CharacterSchema.model_validate(char_data, strict=False)
            char_data = validated.model_dump()
        except Exception as e:
            logger.error(
                f"Character data failed validation during save: {e}. Aborting save to prevent corruption."
            )
            # We no longer "auto-heal" during save to ensure the caller is aware of data issues.
            return False

        char_id = char_data.get("char_id", "unknown_id")

        # Upsert based on char_id
        try:
            self.collection.update_one(
                {"char_id": char_id}, {"$set": char_data}, upsert=True
            )
            logger.info(
                f"Successfully saved character {char_data['char_name']} to MongoDB"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save character to MongoDB: {e}", exc_info=True)
            return False

    def load(self, filename: str) -> Optional[dict]:
        """Load a character from MongoDB."""
        if self.collection is None:
            return None

        # Legacy filename extraction
        char_id = filename.replace(".json", "").split("_")[-1]

        try:
            data = self.collection.find_one({"char_id": char_id})
            if data:
                if "_id" in data:
                    del data["_id"]

                # Validate and return
                try:
                    validated = CharacterSchema.model_validate(data, strict=False)
                    return validated.model_dump()
                except Exception as val_err:
                    logger.error(
                        f"Loaded character '{char_id}' failed validation: {val_err}"
                    )
                    # In load, we might want to return the raw data if validation fails
                    # so the user can at least see/fix it, but we log the error prominently.
                    return data
            return data
        except Exception as e:
            logger.error(f"Failed to load character from MongoDB: {e}")
            return None

    def list_all(self) -> List[str]:
        """Return a list of available character 'filenames' (simulating legacy format) from MongoDB."""
        if self.collection is None:
            return []

        try:
            chars = self.collection.find({}, {"char_name": 1, "char_id": 1})
            result = []
            for c in chars:
                name = c.get("char_name", "unknown")
                cid = c.get("char_id", "unknown")
                # Format exactly like legacy files for UI compatibility
                result.append(f"{name.replace(' ', '_').lower()}_{cid}.json")
            return result
        except Exception as e:
            logger.error(f"Failed to list characters: {e}")
            return []

    def delete(self, filename: str) -> bool:
        """Delete a character from MongoDB."""
        if self.collection is None:
            return False

        char_id = filename.replace(".json", "").split("_")[-1]
        try:
            result = self.collection.delete_one({"char_id": char_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete character: {e}")
            return False
