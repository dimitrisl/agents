import copy
import logging
from typing import Any, Dict

from backend.repositories.rules_repository import RulesRepository

logger = logging.getLogger("DnDAssistant.ValidationService")


def get_character_armor_proficiencies(char_data: Dict[str, Any], class_data: Dict[str, Any]) -> set:
    """Extracts all armor proficiencies granted by class, subclass, and features."""
    proficiencies = set()

    # 1. Base Class Proficiencies
    if class_data and "starting_proficiencies" in class_data:
        armor_profs = class_data["starting_proficiencies"].get("armor", [])
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


def deterministic_validate_build(char_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies deterministic rules validation to the character.
    Returns the corrected character data.
    """
    corrected_char = copy.deepcopy(char_data)
    repo = RulesRepository()

    char_class = corrected_char.get("char_class", "")
    edition = corrected_char.get("dnd_edition", "2014 Edition")

    class_data = repo.get_class_progression(char_class, edition)

    # 1. Ability Score Caps
    # We removed the hard cap of 20 because magic items (like Belt of Giant Strength)
    # or homebrew rules allow stats > 20, and the validation service does not differentiate
    # between base stats and final item-boosted stats.
    # The stat calculation engine will handle bounds naturally.
    # 2. Armor Proficiency Validation
    # If the character has equipped armor they are not proficient in, unequip it.
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
                        logger.warning(
                            f"Character lacks proficiency for {item_name} ({req_prof}). Unequipping."
                        )
                        equip["equipped"] = False

    # 3. Weapon Proficiency Validation (Basic)
    # Weapons can be used without proficiency, but it shouldn't have proficiency bonus applied.
    # Our sync_character_stats adds proficiency bonus automatically, so we'll just flag it for now
    # or remove custom non-proficient items if AI hallucinated them.
    # We will leave weapons equipped, as using weapons without proficiency is legal (unlike spellcasting in unproficient armor).

    return corrected_char
