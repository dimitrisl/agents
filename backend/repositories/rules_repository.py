import os
import json
import logging
from typing import Optional
from backend.core.constants import EDITION_2014, EDITION_2024

logger = logging.getLogger("DnDAssistant.RulesRepo")

DATA_DIR = "data"
RULES_DIR = os.path.join(DATA_DIR, "rules", "classes")

# --------------------------------------------------------------------------- #
# Module-level caches — keyed only by arguments (no `self`), so instances can #
# be garbage-collected normally without leaking through the cache.            #
# --------------------------------------------------------------------------- #
_class_progression_cache: dict = {}
_available_classes_cache: dict = {}
_feats_cache: dict = {}
_items_cache: list | None = None


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

    def get_class_progression(
        self, class_name: str, edition: str = EDITION_2014
    ) -> Optional[dict]:
        """
        Loads the progression data for a specific class and edition.
        Results are cached in module-level dict to avoid instance-level memory leaks.
        """
        cache_key = (class_name.lower(), edition)
        if cache_key in _class_progression_cache:
            return _class_progression_cache[cache_key]

        edition_dir = "2014" if edition == EDITION_2014 else "2024"
        filename = f"{class_name.lower().replace(' ', '_')}.json"
        filepath = os.path.join(RULES_DIR, edition_dir, filename)

        if not os.path.exists(filepath):
            logger.warning(
                f"No progression data found for {class_name} ({edition}) at {filepath}"
            )
            _class_progression_cache[cache_key] = None
            return None

        result = _load_json(filepath)
        _class_progression_cache[cache_key] = result
        return result

    def get_available_classes(self, edition: str = EDITION_2014) -> list:
        """
        Lists all available classes for the specified edition based on JSON files.
        """
        if edition in _available_classes_cache:
            return _available_classes_cache[edition]

        edition_dir = "2014" if edition == EDITION_2014 else "2024"
        dir_path = os.path.join(RULES_DIR, edition_dir)
        if not os.path.exists(dir_path):
            _available_classes_cache[edition] = []
            return []

        classes = []
        for filename in os.listdir(dir_path):
            if filename.endswith(".json"):
                class_name = filename.replace(".json", "").replace("_", " ").title()
                classes.append(class_name)
        result = sorted(classes)
        _available_classes_cache[edition] = result
        return result

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
        if edition in _feats_cache:
            return _feats_cache[edition]

        filename = f"feats_{'2024' if edition == EDITION_2024 else '2014'}.json"
        filepath = os.path.join(DATA_DIR, "rules", filename)
        result = _load_json(filepath)
        _feats_cache[edition] = result
        return result

    def search_feats(self, query: str, edition: str = EDITION_2014) -> list:
        """
        Searches for feats by name.
        """
        feats = self.get_all_feats(edition)
        query = query.lower()
        return [f for f in feats if query in f["name"].lower()]

    def get_all_items(self) -> list:
        """
        Loads all items from the master items KB.
        """
        global _items_cache
        if _items_cache is not None:
            return _items_cache

        filepath = os.path.join(DATA_DIR, "rules", "items.json")
        _items_cache = _load_json(filepath)
        return _items_cache

    def get_all_spells(self, edition: str = EDITION_2014) -> list:
        """
        Loads all spells for the specified edition, prioritizing MongoDB.
        """
        edition_val = "2014" if edition == EDITION_2014 else "2024"

        # Try database first
        try:
            from backend.core.db import get_db

            db = get_db()
            if db is not None:
                cursor = db["spells"].find({"edition": edition_val})
                spells = []
                for s in cursor:
                    if "_id" in s:
                        del s["_id"]
                    spells.append(s)
                if spells:
                    return spells
        except Exception as e:
            logger.error(f"Failed to load spells from MongoDB: {e}")

        # Fallback to local JSON files
        filename = f"spells_{edition_val}.json"
        filepath = os.path.join(DATA_DIR, "rules", filename)
        return _load_json(filepath)

    def search_spells(self, query: str, edition: str = EDITION_2014) -> list:
        """
        Searches for spells by name.
        """
        spells = self.get_all_spells(edition)
        query = query.lower()
        return [s for s in spells if query in s["name"].lower()]
