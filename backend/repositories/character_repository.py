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

        # Validate against schema before saving
        try:
            validated = CharacterSchema(**char_data)
            char_data = validated.model_dump()
        except Exception as e:
            logger.warning(
                f"Character data failed validation during save: {e}. Attempting recovery/sanitization."
            )
            try:
                from backend.core.state_manager import (
                    get_default_character,
                    CHARACTER_FIELDS,
                )

                fallback_data = get_default_character()
                for key in CHARACTER_FIELDS:
                    if key in char_data and char_data[key] is not None:
                        fallback_data[key] = char_data[key]
                validated = CharacterSchema.model_validate(fallback_data, strict=False)
                char_data = validated.model_dump()
            except Exception as rec_err:
                # Fail fast — do NOT persist corrupt data to MongoDB.
                raise ValueError(
                    f"Cannot save '{char_data.get('char_name', 'unknown')}': "
                    f"validation failed and recovery was unsuccessful. "
                    f"Original error: {e} | Recovery error: {rec_err}"
                ) from rec_err

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
        """Load a character from MongoDB. Note: 'filename' is now treated as 'char_id_filename' to match legacy logic."""
        if self.collection is None:
            return None

        # Extract char_id from the legacy filename format (e.g., willow_whisperwind_3029a9f1.json)
        # Or just use it directly if it's already an ID
        char_id = filename.replace(".json", "").split("_")[-1]

        try:
            data = self.collection.find_one({"char_id": char_id})
            if data:
                if "_id" in data:
                    del data["_id"]  # Remove mongo internal ID

                # Perform auto-healing/validation on load to clean any legacy or corrupted fields
                try:
                    validated = CharacterSchema(**data)
                    return validated.model_dump()
                except Exception as val_err:
                    logger.warning(
                        f"Loaded character failed validation, running fallback cleaning: {val_err}"
                    )
                    try:
                        from backend.core.state_manager import (
                            get_default_character,
                            CHARACTER_FIELDS,
                        )

                        fallback_data = get_default_character()
                        for key in CHARACTER_FIELDS:
                            if key in data and data[key] is not None:
                                fallback_data[key] = data[key]
                        validated = CharacterSchema.model_validate(
                            fallback_data, strict=False
                        )
                        return validated.model_dump()
                    except Exception as fallback_err:
                        logger.error(
                            f"Fallback validation failed on load: {fallback_err}. Returning raw data."
                        )
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
