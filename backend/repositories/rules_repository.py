import os
import json
import logging
from typing import Optional
from functools import lru_cache
from backend.core.constants import EDITION_2014, EDITION_2024

logger = logging.getLogger("DnDAssistant.RulesRepo")

DATA_DIR = "data"
RULES_DIR = os.path.join(DATA_DIR, "rules", "classes")


def _load_json(filepath: str):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON from {filepath}: {e}")
        return []


class RulesRepository:
    def __init__(self):
        # Ensure directories exist
        os.makedirs(os.path.join(RULES_DIR, "2014"), exist_ok=True)
        os.makedirs(os.path.join(RULES_DIR, "2024"), exist_ok=True)

    @lru_cache(maxsize=32)
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

        return _load_json(filepath)

    @lru_cache(maxsize=2)
    def get_available_classes(self, edition: str = EDITION_2014) -> list:
        """
        Lists all available classes for the specified edition based on JSON files.
        """
        edition_dir = "2014" if edition == EDITION_2014 else "2024"
        dir_path = os.path.join(RULES_DIR, edition_dir)
        if not os.path.exists(dir_path):
            return []

        classes = []
        for filename in os.listdir(dir_path):
            if filename.endswith(".json"):
                class_name = filename.replace(".json", "").replace("_", " ").title()
                classes.append(class_name)
        return sorted(classes)

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

    @lru_cache(maxsize=8)
    def get_all_feats(self, edition: str = EDITION_2014) -> list:
        """
        Loads all feats for the specified edition.
        """
        filename = f"feats_{'2024' if edition == EDITION_2024 else '2014'}.json"
        filepath = os.path.join(DATA_DIR, "rules", filename)
        return _load_json(filepath)

    def search_feats(self, query: str, edition: str = EDITION_2014) -> list:
        """
        Searches for feats by name.
        """
        feats = self.get_all_feats(edition)
        query = query.lower()
        return [f for f in feats if query in f["name"].lower()]

    @lru_cache(maxsize=1)
    def get_all_items(self) -> list:
        """
        Loads all items from the master items KB.
        """
        filepath = os.path.join(DATA_DIR, "rules", "items.json")
        return _load_json(filepath)
