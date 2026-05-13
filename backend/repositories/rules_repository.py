import os
import json
import logging
from typing import Optional
from backend.constants import EDITION_2014

logger = logging.getLogger("DnDAssistant.RulesRepo")

DATA_DIR = "data"
RULES_DIR = os.path.join(DATA_DIR, "rules", "classes")


class RulesRepository:
    def __init__(self):
        # Ensure directories exist
        os.makedirs(os.path.join(RULES_DIR, "2014"), exist_ok=True)
        os.makedirs(os.path.join(RULES_DIR, "2024"), exist_ok=True)

    def get_class_progression(
        self, class_name: str, edition: str = EDITION_2014
    ) -> Optional[dict]:
        """
        Loads the progression data for a specific class and edition.
        """
        edition_dir = "2014" if edition == EDITION_2014 else "2024"
        filename = f"{class_name.lower().replace(' ', '_')}.json"
        filepath = os.path.join(RULES_DIR, edition_dir, filename)

        if not os.path.exists(filepath):
            logger.warning(
                f"No progression data found for {class_name} ({edition}) at {filepath}"
            )
            return None

        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Failed to load class progression for {class_name}: {e}")
            return None

    def get_features_at_level(
        self, class_name: str, level: int, edition: str = EDITION_2014
    ) -> list:
        """
        Helper to get specifically the features for a certain level.
        """
        progression = self.get_class_progression(class_name, edition)
        if not progression:
            return []

        level_str = str(level)
        level_data = progression.get("progression", {}).get(level_str, {})
        return level_data.get("features", [])

    def get_all_feats(self, edition: str = EDITION_2014) -> list:
        """
        Loads all feats for the specified edition.
        """
        filename = "feats_2014.json" if edition == EDITION_2014 else "feats_2024.json"
        filepath = os.path.join(DATA_DIR, "rules", filename)

        if not os.path.exists(filepath):
            logger.warning(f"No feats data found for {edition} at {filepath}")
            return []

        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load feats for {edition}: {e}")
            return []

    def search_feats(self, query: str, edition: str = EDITION_2014) -> list:
        """
        Searches for feats by name.
        """
        feats = self.get_all_feats(edition)
        query = query.lower()
        return [f for f in feats if query in f["name"].lower()]
