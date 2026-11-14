import copy
import json
import logging
import os
from typing import Any, Optional

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
_spells_cache: dict = {}
_features_level_cache: dict = {}
_races_cache: dict = {}
_backgrounds_cache: dict = {}
_weapons_cache: list | None = None
_weapon_masteries_cache: dict = {}
_subclasses_cache: dict = {}
_monsters_cache: dict = {}


def _norm_edition(edition: str) -> str:
    return "2024" if "2024" in str(edition) else "2014"


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

    def get_class_progression(self, class_name: str, edition: str = EDITION_2014) -> Optional[dict]:
        """
        Loads the progression data for a specific class and edition.
        Results are cached in module-level dict to avoid instance-level memory leaks.
        """
        edition_dir = _norm_edition(edition)
        cache_key = (class_name.lower(), edition_dir)
        if cache_key in _class_progression_cache:
            return _class_progression_cache[cache_key]

        filename = f"{class_name.lower().replace(' ', '_')}.json"
        filepath = os.path.join(RULES_DIR, edition_dir, filename)

        if not os.path.exists(filepath):
            logger.warning(f"No progression data found for {class_name} ({edition}) at {filepath}")
            _class_progression_cache[cache_key] = None
            return None

        result = _load_json(filepath)
        _class_progression_cache[cache_key] = result
        return result

    def get_available_classes(self, edition: str = EDITION_2014) -> list:
        """
        Lists all available classes for the specified edition based on JSON files.
        """
        edition_dir = _norm_edition(edition)
        if edition_dir in _available_classes_cache:
            return _available_classes_cache[edition_dir]

        dir_path = os.path.join(RULES_DIR, edition_dir)
        if not os.path.exists(dir_path):
            _available_classes_cache[edition_dir] = []
            return []

        classes = []
        for filename in os.listdir(dir_path):
            if filename.endswith(".json"):
                class_name = filename.replace(".json", "").replace("_", " ").title()
                classes.append(class_name)
        result = sorted(classes)
        _available_classes_cache[edition_dir] = result
        return result

    def get_features_at_level(
        self, class_name: str, level: int, edition: str = EDITION_2014
    ) -> list:
        """
        Helper to get specifically the features for a certain level.
        """
        if not class_name:
            return []
        edition_dir = _norm_edition(edition)
        cache_key = (class_name.lower(), level, edition_dir)
        if cache_key in _features_level_cache:
            return _features_level_cache[cache_key]

        progression = self.get_class_progression(class_name, edition)
        if not progression:
            _features_level_cache[cache_key] = []
            return []

        level_str = str(level)
        level_data = progression.get("progression", {}).get(level_str, {})
        result = level_data.get("features", [])
        _features_level_cache[cache_key] = result
        return result

    def get_all_feats(self, edition: str = EDITION_2014) -> list:
        """
        Loads all feats for the specified edition.
        """
        edition_val = _norm_edition(edition)
        if edition_val in _feats_cache:
            return _feats_cache[edition_val]

        filename = f"feats_{edition_val}.json"
        filepath = os.path.join(DATA_DIR, "rules", filename)
        result = _load_json(filepath)
        _feats_cache[edition_val] = result
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
        Loads all static spells for the specified edition from local JSON rules files.
        """
        edition_val = _norm_edition(edition)
        if edition_val in _spells_cache:
            return list(_spells_cache[edition_val])

        filename = f"spells_{edition_val}.json"
        filepath = os.path.join(DATA_DIR, "rules", filename)
        spells = _load_json(filepath)
        _spells_cache[edition_val] = spells
        return list(spells)

    def search_spells(self, query: str, edition: str = EDITION_2014) -> list:
        """
        Searches for spells by name.
        """
        spells = self.get_all_spells(edition)
        query = query.lower()
        return [s for s in spells if query in s["name"].lower()]

    def get_available_races(self, edition: str = EDITION_2014) -> list:
        """
        Loads all available races for the specified edition.
        """
        edition_val = _norm_edition(edition)
        if edition_val in _races_cache:
            return _races_cache[edition_val]

        filename = f"races_{edition_val}.json"
        filepath = os.path.join(DATA_DIR, "rules", filename)

        if not os.path.exists(filepath):
            return []

        data = _load_json(filepath)
        races = [r for r in data if "name" in r]
        _races_cache[edition_val] = races
        return races

    def get_race_data(self, race_name: str, edition: str = EDITION_2014) -> Optional[dict]:
        """
        Looks up canonical species/race data (traits, speed, size, mechanical_effects)
        for a given race name and edition, with subrace and cross-edition fallback.
        """
        if not race_name:
            return None
        clean = str(race_name).strip().lower()
        if clean == "variant human":
            clean = "human"

        primary_ed = _norm_edition(edition)
        fallback_ed = "2014" if primary_ed == "2024" else "2024"

        for ed in (primary_ed, fallback_ed):
            races = self.get_available_races(ed)
            for r in races:
                if r.get("name", "").strip().lower() == clean:
                    return r
            # Subrace fallback (check longer names like Half-Elf / Half-Orc before Elf / Orc)
            for r in sorted(races, key=lambda x: len(x.get("name", "")), reverse=True):
                r_name = r.get("name", "").strip().lower()
                if r_name and r_name in clean:
                    return r
        return None

    def get_subclasses(self, class_name: str, edition: str = EDITION_2014) -> list:
        filepath = os.path.join(DATA_DIR, "rules", "subclasses.json")
        if not os.path.exists(filepath):
            return []
        data = _load_json(filepath)
        target_key = "2024 Edition" if "2024" in str(edition) else EDITION_2014
        edition_data = data.get(target_key, data.get(EDITION_2014, {}))
        return edition_data.get(class_name, [])

    def get_subclass_mechanics(self, class_name: str, edition: str = EDITION_2014) -> dict:
        """
        Loads the rich mechanical data (like scaling tables) for a class's subclasses.
        """
        edition_dir = _norm_edition(edition)
        cache_key = (class_name.lower(), edition_dir)
        if cache_key in _subclasses_cache:
            return _subclasses_cache[cache_key]

        filename = f"{class_name.lower().replace(' ', '_')}.json"
        filepath = os.path.join(DATA_DIR, "rules", "subclasses", edition_dir, filename)

        if not os.path.exists(filepath):
            _subclasses_cache[cache_key] = {}
            return {}

        result = _load_json(filepath)
        _subclasses_cache[cache_key] = result
        return result

    def get_available_backgrounds(self, edition: str = EDITION_2014) -> list:
        """
        Loads all available backgrounds for the specified edition.
        """
        edition_val = _norm_edition(edition)
        if edition_val in _backgrounds_cache:
            return _backgrounds_cache[edition_val]

        filename = f"backgrounds_{edition_val}.json"
        filepath = os.path.join(DATA_DIR, "rules", filename)

        if not os.path.exists(filepath):
            return []

        data = _load_json(filepath)
        backgrounds = [b for b in data if "name" in b]
        _backgrounds_cache[edition_val] = backgrounds
        return backgrounds

    def get_background_data(
        self, background_name: str, edition: str = EDITION_2014
    ) -> Optional[dict]:
        """
        Looks up canonical background data (skills, tools, feat, feature, equipment)
        for a given background name and edition, with cross-edition fallback.
        """
        if not background_name:
            return None
        clean = str(background_name).strip().lower()
        primary_ed = _norm_edition(edition)
        fallback_ed = "2014" if primary_ed == "2024" else "2024"

        for ed in (primary_ed, fallback_ed):
            bgs = self.get_available_backgrounds(ed)
            for b in bgs:
                if b.get("name", "").strip().lower() == clean:
                    return b
        return None

    def get_all_weapons(self) -> list:
        """
        Loads all weapons from the master weapons JSON.
        """
        global _weapons_cache
        if _weapons_cache is not None:
            return _weapons_cache

        filepath = os.path.join(DATA_DIR, "rules", "weapons.json")
        _weapons_cache = _load_json(filepath)
        return _weapons_cache

    def get_all_weapon_masteries(self, edition: str = EDITION_2024) -> list:
        """
        Loads all weapon masteries.
        """
        edition_val = _norm_edition(edition)
        if edition_val in _weapon_masteries_cache:
            return _weapon_masteries_cache[edition_val]

        filename = f"weapon_masteries_{edition_val}.json"
        filepath = os.path.join(DATA_DIR, "rules", filename)

        if not os.path.exists(filepath):
            return []

        data = _load_json(filepath)
        _weapon_masteries_cache[edition_val] = data
        return data

    # ----------------------------------------------------------------------- #
    # Monsters (SRD Bestiary)                                                 #
    # ----------------------------------------------------------------------- #

    @staticmethod
    def _parse_cr_numeric(cr_val: Any) -> float:
        """
        Parses challenge rating expressions into numeric floats.
        Handles fractions ('1/8', '1/4', '1/2'), numeric strings ('0', '1', '24'),
        and integer/float values. Returns 0.0 for invalid or unparseable input.
        """
        if cr_val is None:
            return 0.0
        if isinstance(cr_val, (int, float)):
            return float(cr_val)
        cr_str = str(cr_val).strip()
        if "/" in cr_str:
            parts = cr_str.split("/", 1)
            try:
                return float(parts[0]) / float(parts[1])
            except (ValueError, ZeroDivisionError):
                return 0.0
        try:
            return float(cr_str)
        except ValueError:
            return 0.0

    def get_all_monsters(self, edition: str = "2014") -> list[dict]:
        """
        Loads all SRD monsters for the specified edition.
        Results are cached in module-level `_monsters_cache` to avoid repeated I/O.
        Returns a deep copy of the monster list to ensure strict cache immutability.
        Guarantees every monster record has origin="official", is_public=True,
        and id starting with 'srd_'.
        """
        edition_val = _norm_edition(edition)
        if edition_val in _monsters_cache:
            return copy.deepcopy(_monsters_cache[edition_val])

        filename = f"monsters_{edition_val}.json"
        filepath = os.path.join(DATA_DIR, "rules", filename)

        if not os.path.exists(filepath):
            logger.warning(f"No monsters dataset found for edition {edition_val} at {filepath}")
            _monsters_cache[edition_val] = []
            return []

        raw_data = _load_json(filepath)
        if not isinstance(raw_data, list):
            logger.error(f"Monsters dataset at {filepath} did not contain a JSON list")
            _monsters_cache[edition_val] = []
            return []

        sanitized: list[dict] = []
        for item in raw_data:
            if not isinstance(item, dict):
                continue
            monster = dict(item)
            monster["origin"] = "official"
            monster["is_public"] = True
            monster["edition"] = edition_val

            monster_id = str(monster.get("id") or "").strip()
            if not monster_id:
                slug = str(monster.get("name", "monster")).strip().lower().replace(" ", "_")
                monster_id = f"srd_{slug}_{edition_val}"
            elif not monster_id.startswith("srd_"):
                monster_id = f"srd_{monster_id}"
            monster["id"] = monster_id

            if "cr_numeric" not in monster or monster["cr_numeric"] is None:
                monster["cr_numeric"] = self._parse_cr_numeric(monster.get("cr"))
            else:
                try:
                    monster["cr_numeric"] = float(monster["cr_numeric"])
                except (ValueError, TypeError):
                    monster["cr_numeric"] = self._parse_cr_numeric(monster.get("cr"))

            sanitized.append(monster)

        _monsters_cache[edition_val] = sanitized
        return copy.deepcopy(sanitized)

    def search_monsters(
        self,
        query: str = "",
        edition: Optional[str] = None,
        cr: Optional[str] = None,
        monster_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Searches for official SRD monsters with filtering.
        - Case-insensitive query matches against name, type, and description.
        - If edition is None or 'all', searches across both 2014 and 2024 editions.
        - Supports filtering by CR (string or numeric equivalent) and monster_type.
        Returns deep copies of matching monster records.
        """
        if edition is not None and str(edition).strip().lower() not in ("", "all"):
            edition_val = _norm_edition(edition)
            monsters = self.get_all_monsters(edition_val)
        else:
            monsters = self.get_all_monsters("2014") + self.get_all_monsters("2024")

        results: list[dict] = []
        q = query.strip().lower() if query else ""
        cr_target = str(cr).strip().lower() if cr is not None and str(cr).strip() != "" else None
        t_target = (
            str(monster_type).strip().lower()
            if monster_type is not None and str(monster_type).strip() != ""
            else None
        )

        for m in monsters:
            if q:
                name_match = q in str(m.get("name", "")).lower()
                type_match = q in str(m.get("type", "")).lower()
                desc_match = q in str(m.get("description", "")).lower()
                if not (name_match or type_match or desc_match):
                    continue

            if cr_target is not None:
                m_cr = str(m.get("cr", "")).strip().lower()
                m_cr_num = m.get("cr_numeric")
                cr_matched = False
                if m_cr == cr_target:
                    cr_matched = True
                else:
                    target_num = self._parse_cr_numeric(cr_target)
                    if m_cr_num is not None and abs(m_cr_num - target_num) < 1e-4:
                        if cr_target in ("0", "0.0") or target_num > 0:
                            cr_matched = True
                if not cr_matched:
                    continue

            if t_target is not None:
                m_type = str(m.get("type", "")).strip().lower()
                if t_target not in m_type and m_type not in t_target:
                    continue

            results.append(m)

        return copy.deepcopy(results)

    def get_monster_by_id(self, monster_id: str) -> Optional[dict]:
        """
        Retrieves a single SRD monster by ID across available editions.
        Returns a deep copy if found, or None if not found.
        Supports exact matches, case-insensitive matches, and prefix/suffix tolerance.
        """
        if not monster_id or not isinstance(monster_id, str):
            return None

        clean_id = monster_id.strip()
        clean_id_lower = clean_id.lower()
        editions = ("2024", "2014") if "2024" in clean_id_lower else ("2014", "2024")

        for ed in editions:
            monsters = self.get_all_monsters(ed)
            for m in monsters:
                m_id = str(m.get("id", "")).strip()
                m_id_lower = m_id.lower()
                if m_id == clean_id or m_id_lower == clean_id_lower:
                    return copy.deepcopy(m)
                if not clean_id_lower.startswith("srd_"):
                    if m_id_lower == f"srd_{clean_id_lower}":
                        return copy.deepcopy(m)
                if m_id_lower in (f"srd_{clean_id_lower}_{ed}", f"{clean_id_lower}_{ed}"):
                    return copy.deepcopy(m)

        return None
