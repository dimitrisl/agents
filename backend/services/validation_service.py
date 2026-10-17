import copy
import logging
from typing import Any, Dict

from backend.repositories.rules_repository import RulesRepository

logger = logging.getLogger("DnDAssistant.ValidationService")

SUBCLASS_MIN_LEVEL = 3


def get_character_armor_proficiencies(char_data: Dict[str, Any], class_data: Dict[str, Any]) -> set:
    """Extracts all armor proficiencies granted by class, multiclass entries, subclass, and features."""
    proficiencies = set()
    edition = char_data.get("dnd_edition", "2014 Edition")
    repo = RulesRepository()

    class_datas = [class_data] if class_data else []
    for cls in char_data.get("classes", []):
        c_dict = (
            cls
            if isinstance(cls, dict)
            else (cls.model_dump() if hasattr(cls, "model_dump") else {})
        )
        cname = c_dict.get("class_name")
        if cname:
            c_prog = repo.get_class_progression(cname, edition)
            if c_prog and c_prog not in class_datas:
                class_datas.append(c_prog)

    # 1. Base & Multiclass Proficiencies
    for cd in class_datas:
        if cd and "starting_proficiencies" in cd:
            armor_profs = cd["starting_proficiencies"].get("armor", [])
            for p in armor_profs:
                p_lower = p.lower()
                if p_lower != "none":
                    if p_lower in ["light", "medium", "heavy"]:
                        proficiencies.add(f"{p_lower} armor")
                    else:
                        proficiencies.add(p_lower)

    # 2. Features and Traits
    # e.g., "Bonus Proficiency: Heavy Armor" or "Training in War and Song" (Light armor)
    for feat in char_data.get("features_traits", []):
        if not isinstance(feat, dict):
            continue
        desc = (feat.get("description", "") + " " + feat.get("name", "")).lower()
        if "light armor" in desc and ("proficien" in desc or "training" in desc):
            proficiencies.add("light armor")
        if "medium armor" in desc and ("proficien" in desc or "training" in desc):
            proficiencies.add("medium armor")
        if "heavy armor" in desc and ("proficien" in desc or "training" in desc):
            proficiencies.add("heavy armor")
        if "shields" in desc and ("proficien" in desc or "training" in desc):
            proficiencies.add("shields")

    # "All armor" covers everything
    if "all armor" in proficiencies:
        proficiencies.update(["light armor", "medium armor", "heavy armor", "shields"])

    return proficiencies


def deterministic_validate_build(char_data: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    """
    Applies deterministic rules validation to the character.
    Returns the corrected character data and a list of identified issues.
    """
    corrected_char = copy.deepcopy(char_data)
    repo = RulesRepository()
    issues = []

    char_class = corrected_char.get("char_class", "")
    edition = corrected_char.get("dnd_edition", "2014 Edition")

    class_data = repo.get_class_progression(char_class, edition)

    # 1. Ability Score Caps
    # We removed the hard cap of 20 because magic items (like Belt of Giant Strength)
    # or homebrew rules allow stats > 20, and the validation service does not differentiate
    # between base stats and final item-boosted stats.
    # The stat calculation engine will handle bounds naturally.
    # 1b. Multiclass Prerequisites
    stats = corrected_char.get("base_stats") or corrected_char.get("stats", {})
    if hasattr(stats, "model_dump"):
        stats = stats.model_dump()
    elif not isinstance(stats, dict):
        stats = {
            "STR": getattr(stats, "STR", 10),
            "DEX": getattr(stats, "DEX", 10),
            "CON": getattr(stats, "CON", 10),
            "INT": getattr(stats, "INT", 10),
            "WIS": getattr(stats, "WIS", 10),
            "CHA": getattr(stats, "CHA", 10),
        }

    classes = corrected_char.get("classes", [])
    if len(classes) > 1:
        prereqs = {
            "barbarian": lambda s: s.get("STR", 0) >= 13,
            "bard": lambda s: s.get("CHA", 0) >= 13,
            "cleric": lambda s: s.get("WIS", 0) >= 13,
            "druid": lambda s: s.get("WIS", 0) >= 13,
            "fighter": lambda s: s.get("STR", 0) >= 13 or s.get("DEX", 0) >= 13,
            "monk": lambda s: s.get("DEX", 0) >= 13 and s.get("WIS", 0) >= 13,
            "paladin": lambda s: s.get("STR", 0) >= 13 and s.get("CHA", 0) >= 13,
            "ranger": lambda s: s.get("DEX", 0) >= 13 and s.get("WIS", 0) >= 13,
            "rogue": lambda s: s.get("DEX", 0) >= 13,
            "sorcerer": lambda s: s.get("CHA", 0) >= 13,
            "warlock": lambda s: s.get("CHA", 0) >= 13,
            "wizard": lambda s: s.get("INT", 0) >= 13,
            "artificer": lambda s: s.get("INT", 0) >= 13,
        }
        for cls in classes:
            cname = cls.get("class_name", "").lower()
            if cname in prereqs and not prereqs[cname](stats):
                issue_msg = f"Character does not meet the multiclassing stat prerequisites for {cname.capitalize()}."
                logger.warning(issue_msg)
                issues.append(issue_msg)

    # 2. Armor Proficiency Validation
    # Check if the character has equipped armor they are not proficient in and issue a warning
    armor_profs = get_character_armor_proficiencies(corrected_char, class_data)
    all_items = repo.get_all_items()
    items_lookup = {i.get("name", "").lower(): i for i in all_items}

    equipment = corrected_char.get("equipment", [])
    for equip in equipment:
        if isinstance(equip, dict) and equip.get("equipped", False):
            item_name = equip.get("name", "").lower()
            item_db = items_lookup.get(item_name)
            if item_db:
                item_type = item_db.get("type", "").lower()

                # Check if it's armor
                req_prof = None
                if "light armor" in item_type:
                    req_prof = "light armor"
                elif "medium armor" in item_type:
                    req_prof = "medium armor"
                elif "heavy armor" in item_type:
                    req_prof = "heavy armor"
                elif "shield" in item_type:
                    req_prof = "shields"

                if req_prof:
                    if req_prof not in armor_profs and "all armor" not in armor_profs:
                        issue_msg = f"Character lacks proficiency for {item_name} ({req_prof}). Wearing it imposes disadvantage on STR/DEX checks, saves, and attacks, and prevents spellcasting."
                        logger.warning(issue_msg)
                        issues.append(issue_msg)

    # 3. Weapon Proficiency Validation (Basic)
    # Weapons can be used without proficiency, but it shouldn't have proficiency bonus applied.
    # Our sync_character_stats adds proficiency bonus automatically, so we'll just flag it for now
    # or remove custom non-proficient items if AI hallucinated them.
    # We will leave weapons equipped, as using weapons without proficiency is legal (unlike spellcasting in unproficient armor).

    # 4. Subclass Level Validation
    # Clear the subclass if the character has not yet reached the level where the class
    # grants a subclass choice. The threshold is read from the static JSON progression,
    # so no domain data is ever hardcoded here.
    subclass = corrected_char.get("subclass")
    level = corrected_char.get("char_level", 1)
    classes_list = corrected_char.get("classes", [])

    # In multiclass characters, verify the specific class level rather than total character level
    char_class_level = level
    for cls in classes_list:
        c_dict = (
            cls
            if isinstance(cls, dict)
            else (cls.model_dump() if hasattr(cls, "model_dump") else {})
        )
        if c_dict.get("class_name", "").lower() == char_class.lower():
            char_class_level = c_dict.get("level", level)
            break

    if subclass and class_data:
        subclass_min_level = _get_subclass_min_level(class_data)
        if subclass_min_level is None:
            # Fallback for parsing errors or older JSON
            subclass_min_level = SUBCLASS_MIN_LEVEL

        if char_class_level < subclass_min_level:
            issue_msg = f"Character is level {char_class_level} in '{char_class}' but subclass '{subclass}' requires level {subclass_min_level}. Clearing subclass."
            logger.warning(issue_msg)
            issues.append(issue_msg)
            corrected_char["subclass"] = None

    # Check any other classes in the multiclass list
    for cls in classes_list:
        c_dict = (
            cls
            if isinstance(cls, dict)
            else (cls.model_dump() if hasattr(cls, "model_dump") else {})
        )
        c_sub = c_dict.get("subclass")
        c_name = c_dict.get("class_name", "")
        c_lvl = c_dict.get("level", 1)
        if c_sub and c_name:
            c_data = (
                class_data
                if c_name.lower() == char_class.lower()
                else repo.get_class_progression(c_name, edition)
            )
            if c_data:
                c_min = _get_subclass_min_level(c_data)
                if c_min is None:
                    c_min = SUBCLASS_MIN_LEVEL
                if c_lvl < c_min:
                    issue_msg = f"Character has {c_lvl} level(s) in '{c_name}' but subclass '{c_sub}' requires level {c_min}. Clearing subclass."
                    logger.warning(issue_msg)
                    if issue_msg not in issues:
                        issues.append(issue_msg)
                    if isinstance(cls, dict):
                        cls["subclass"] = None
                    elif hasattr(cls, "subclass"):
                        cls.subclass = None
                    if c_name.lower() == char_class.lower():
                        corrected_char["subclass"] = None

    return corrected_char, issues


# Keywords that identify the "choose your subclass" feature in progression JSON.
_SUBCLASS_KEYWORDS = (
    "archetype",
    "subclass",
    "domain",
    "circle",
    "sacred oath",
    "patron",
    "monastic tradition",
    "primal path",
    "college",
    "roguish archetype",
    "ranger archetype",
    "arcane tradition",
    "sorcerous origin",
    "otherworldly patron",
    "artificer specialist",
)


def _get_subclass_min_level(class_data: Dict[str, Any]) -> int | None:
    """Returns the earliest level at which the class grants a subclass choice.

    Reads the static JSON progression and looks for feature names matching
    known subclass-granting keywords. Returns None if no such entry is found,
    which is treated as 'no restriction' by the caller.
    """
    progression = class_data.get("progression", {})
    for level_str, level_data in sorted(progression.items(), key=lambda x: int(x[0])):
        for feature in level_data.get("features", []):
            name = feature.get("name", "").lower()
            if any(kw in name for kw in _SUBCLASS_KEYWORDS):
                return int(level_str)
    return None
