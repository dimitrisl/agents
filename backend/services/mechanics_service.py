import math
import logging
from typing import Dict, Any, List

logger = logging.getLogger("DnDAssistant.MechanicsService")


def get_modifier(score: int) -> int:
    """Calculates the D&D ability modifier from a score."""
    return math.floor((score - 10) / 2)


def get_hit_die_for_class(char_class: str, edition: str = "2014 Edition") -> str:
    """
    Returns the hit die string (e.g. 'd10') for a given class.
    Exclusively uses the RulesRepository (JSON files) as the source of truth.
    """
    from backend.repositories.rules_repository import RulesRepository

    repo = RulesRepository()
    progression = repo.get_class_progression(char_class, edition)

    if progression and "hit_die" in progression:
        # Standardize format: "1d10" or "d10" -> "d10"
        die = str(progression["hit_die"]).lower()
        return f"d{die.split('d')[-1]}"

    logger.warning(
        f"Could not find hit die for {char_class} in {edition} rules. Falling back to d8."
    )
    return "d8"


def calculate_proficiency_bonus(level: int, class_data: Dict[str, Any] = None) -> int:
    """
    Calculates proficiency bonus.
    Prioritizes JSON data from the class progression if available.
    """
    if class_data:
        progression = class_data.get("progression", {})
        level_data = progression.get(str(level), {})
        if "proficiency_bonus" in level_data:
            return level_data["proficiency_bonus"]

    # Fallback to standard D&D formula
    return math.ceil(level / 4) + 1


def calculate_hp(
    class_hit_die: str, level: int, con_score: int, existing_hp: int = None
) -> int:
    """
    Calculates HP Max.
    If existing_hp is provided, it ONLY adjusts for CON modifier changes,
    preserving any manual rolls or edits.
    """
    try:
        parts = str(class_hit_die).lower().split("d")
        die_size = int(parts[-1])
    except (ValueError, AttributeError, IndexError):
        logger.warning(f"Invalid hit die format: {class_hit_die}. Defaulting to 8.")
        die_size = 8

    con_mod = get_modifier(con_score)

    # If no existing HP, calculate full "Standard/Average" HP
    if existing_hp is None or existing_hp <= 0:
        # 1st level: Max die + CON mod
        std_hp = die_size + con_mod
        # Subsequent levels: Average (die/2 + 1) + CON mod
        if level > 1:
            average_gain = (die_size // 2 + 1) + con_mod
            std_hp += average_gain * (level - 1)
        return max(1, std_hp)

    # If we HAVE existing HP, we trust it was built correctly
    # (either by this function previously or by a manual roll).
    # We don't have the "previous" con_mod, so we can't easily auto-adjust
    # unless we store base_rolled_hp.
    # For now, we return existing_hp and let the Level Up service handle increments.
    return existing_hp


def get_level_up_vitals(
    char_class: str, current_level: int, con_score: int, edition: str = "2014 Edition"
) -> dict:
    """
    Returns standard level-up vitals (hit die, average HP gain).
    Logic moved from view to backend.
    """
    hit_die_str = get_hit_die_for_class(char_class, edition)
    if not hit_die_str.startswith("1"):
        hit_die_str = f"1{hit_die_str}"

    try:
        die_size = int(hit_die_str.lower().split("d")[-1])
    except Exception:
        die_size = 8

    con_mod = get_modifier(con_score)
    avg_gain = (die_size // 2) + 1 + con_mod

    return {
        "hit_die": hit_die_str,
        "die_size": die_size,
        "con_mod": con_mod,
        "average_hp_gain": max(1, avg_gain),
    }


def calculate_ac(
    dex_score: int,
    equipment: List[Dict[str, Any]],
    features: List[Dict[str, Any]] = None,
) -> int:
    """
    Calculates AC based on DEX and equipped items from KB.
    """
    from backend.repositories.rules_repository import RulesRepository

    _rules_repo = RulesRepository()
    all_items = _rules_repo.get_all_items()

    dex_mod = get_modifier(dex_score)
    base_ac = 10
    bonus_ac = 0
    max_dex = 10

    for equip in equipment:
        # Normalize: accept both strings and dicts
        if isinstance(equip, str):
            equip = {"name": equip, "equipped": True}
        # Check if equipped
        if not equip.get("equipped", False):
            continue

        # 1. Manual Bonus (from user input in the table)
        bonus_ac += int(equip.get("ac_bonus", 0))

        # 2. KB Bonus
        item_name = equip.get("name", "").lower()
        item_data = next((i for i in all_items if i["name"].lower() == item_name), None)

        if item_data:
            if "ac_base" in item_data:
                base_ac = max(base_ac, item_data["ac_base"])
                if "dex_limit" in item_data:
                    max_dex = min(max_dex, item_data["dex_limit"])
            if "ac_bonus" in item_data:
                bonus_ac += item_data["ac_bonus"]

    # Warforged bonus
    if features:
        for f in features:
            if "integrated protection" in f.get("name", "").lower():
                bonus_ac += 1

    applied_dex = min(dex_mod, max_dex)
    return base_ac + applied_dex + bonus_ac


def calculate_passive_perception(
    wis_score: int, proficiency_bonus: int, skills: List[str]
) -> int:
    """Calculates Passive Perception."""
    wis_mod = get_modifier(wis_score)
    is_proficient = "Perception" in skills
    bonus = proficiency_bonus if is_proficient else 0
    return 10 + wis_mod + bonus


def calculate_saving_throws(
    stats: Dict[str, int], proficiency_bonus: int, proficient_saves: List[str]
) -> Dict[str, int]:
    """Calculates all saving throw modifiers."""
    saves = {}
    for stat in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        base_mod = get_modifier(stats.get(stat, 10))
        bonus = proficiency_bonus if stat in proficient_saves else 0
        saves[stat] = base_mod + bonus
    return saves


def calculate_weapon_stats(
    weapon: Dict[str, Any], stats: Dict[str, int], proficiency_bonus: int
) -> Dict[str, Any]:
    """
    Calculates attack bonus and damage modifier for a weapon.
    Simplified: uses STR for melee, DEX for ranged/finesse.
    """
    name = weapon.get("name", "").lower()
    # Basic logic: Ranged/Finesse detection
    is_ranged = any(
        word in name for word in ["bow", "crossbow", "sling", "dart", "javelin"]
    )
    is_finesse = any(
        word in name for word in ["rapier", "dagger", "scimitar", "shortsword"]
    )

    str_mod = get_modifier(stats.get("STR", 10))
    dex_mod = get_modifier(stats.get("DEX", 10))

    # Choose modifier
    if is_ranged:
        mod = dex_mod
    elif is_finesse:
        mod = max(str_mod, dex_mod)
    else:
        mod = str_mod

    attack_bonus = mod + proficiency_bonus
    weapon["attack_bonus"] = (
        f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)
    )

    # Update damage string (e.g., "1d8" -> "1d8 + 3")
    damage_base = weapon.get("damage", "1d4")
    if " + " in damage_base:
        damage_base = damage_base.split(" + ")[0]

    if mod != 0:
        op = "+" if mod > 0 else "-"
        weapon["damage"] = f"{damage_base} {op} {abs(mod)}"
    else:
        weapon["damage"] = damage_base

    return weapon


def sync_character_stats(
    char_data: Dict[str, Any], class_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Synchronizes derived stats based on base ability scores and level.
    """
    from backend.repositories.rules_repository import RulesRepository

    repo = RulesRepository()

    stats_raw = char_data.get("stats", {})
    # ... (existing stat handling)
    if hasattr(stats_raw, "model_dump"):
        stats = stats_raw.model_dump()
    elif isinstance(stats_raw, dict):
        stats = stats_raw
    else:
        stats = {
            "STR": getattr(stats_raw, "STR", 10),
            "DEX": getattr(stats_raw, "DEX", 10),
            "CON": getattr(stats_raw, "CON", 10),
            "INT": getattr(stats_raw, "INT", 10),
            "WIS": getattr(stats_raw, "WIS", 10),
            "CHA": getattr(stats_raw, "CHA", 10),
        }

    level = char_data.get("char_level", 1)
    edition = char_data.get("dnd_edition", "2014 Edition")
    char_class = char_data.get("char_class", "Fighter")

    # 1. Fetch Class Data if not provided
    if not class_data:
        class_data = repo.get_class_progression(char_class, edition)

    # 2. Apply Equipment Bonuses ...
    all_items = repo.get_all_items()

    # Normalize equipment and features to ensure they are dictionaries
    normalized_eq = []
    for item in char_data.get("equipment", []):
        if isinstance(item, str):
            normalized_eq.append({"name": item, "equipped": True})
        elif hasattr(item, "model_dump"):
            normalized_eq.append(item.model_dump())
        elif isinstance(item, dict):
            normalized_eq.append(item)
    char_data["equipment"] = normalized_eq

    normalized_ft = []
    for ft in char_data.get("features_traits", []):
        if isinstance(ft, str):
            normalized_ft.append({"name": ft, "description": "Imported feature"})
        elif hasattr(ft, "model_dump"):
            normalized_ft.append(ft.model_dump())
        elif isinstance(ft, dict):
            normalized_ft.append(ft)
    char_data["features_traits"] = normalized_ft

    equipment = char_data["equipment"]
    for equip in equipment:
        if not equip.get("equipped", False):
            continue

        # 1. Structured Attribute Bonuses (Mod1, Val1, Mod2, Val2)
        for i in [1, 2]:
            raw_mod = equip.get(f"mod{i}")
            if not raw_mod:
                continue

            attr_key = str(raw_mod).upper().strip()
            bonus_val = int(equip.get(f"val{i}", 0))

            if not attr_key or attr_key == "NONE" or bonus_val == 0:
                continue

            # Ability Scores
            if attr_key in stats:
                stats[attr_key] += bonus_val
            # HP
            elif attr_key == "HP":
                char_data["hp_max"] = char_data.get("hp_max", 0) + bonus_val
            # Speed
            elif attr_key in ["SPD", "SPEED"]:
                char_data["speed"] = char_data.get("speed", 30) + bonus_val
            # Initiative
            elif attr_key in ["INIT", "INITIATIVE"]:
                char_data["initiative_bonus"] = (
                    char_data.get("initiative_bonus", 0) + bonus_val
                )
            # Attack Bonus (Global)
            elif attr_key in ["ATK", "HIT", "ATTACK"]:
                char_data["global_attack_bonus"] = (
                    char_data.get("global_attack_bonus", 0) + bonus_val
                )
            # Damage Bonus (Global)
            elif attr_key in ["DMG", "DAMAGE"]:
                char_data["global_damage_bonus"] = (
                    char_data.get("global_damage_bonus", 0) + bonus_val
                )
            # Saving Throws (Global)
            elif attr_key in ["SAVES", "SAVE"]:
                for s in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
                    char_data["saving_throw_values"][s] = (
                        char_data["saving_throw_values"].get(s, 0) + bonus_val
                    )

        # 2. KB Data
        item_name = equip.get("name", "").lower()
        item_data = next((i for i in all_items if i["name"].lower() == item_name), None)

        if item_data and "stat_set" in item_data:
            for stat, val in item_data["stat_set"].items():
                stats[stat] = max(stats.get(stat, 10), val)
        if item_data and "stat_bonus" in item_data:
            for stat, val in item_data["stat_bonus"].items():
                stats[stat] = stats.get(stat, 10) + val

    con_score = stats.get("CON", 10)
    dex_score = stats.get("DEX", 10)
    wis_score = stats.get("WIS", 10)

    # Update Proficiency Bonus
    prof_bonus = calculate_proficiency_bonus(level, class_data)
    char_data["proficiency_bonus"] = prof_bonus

    # 3. Dynamic Proficiencies from JSON if missing
    if not char_data.get("saving_throws") and class_data:
        # Many JSONs use primary_ability for saves (simplified logic)
        char_data["saving_throws"] = class_data.get("primary_ability", [])

    # Update HP and Hit Dice
    hit_die_size = get_hit_die_for_class(char_class, edition)
    if class_data and "hit_die" in class_data:
        raw_die = class_data["hit_die"]
        hit_die_size = raw_die[1:] if raw_die.startswith("1d") else raw_die

    # Generate standard hit dice string (e.g. "5d8")
    char_data["hit_dice"] = f"{level}{hit_die_size}"

    # Check for HP bonuses per level (e.g. Tough feat, Hill Dwarf)
    hp_bonus_per_level = 0
    features = char_data.get("features_traits", [])
    for f in features:
        desc = f.get("description", "").lower()
        if "tough" in f.get("name", "").lower() or "toughness" in desc:
            hp_bonus_per_level += 2
        if "dwarven toughness" in desc:
            hp_bonus_per_level += 1

    # Calculate HP Max
    base_hp = calculate_hp(
        hit_die_size, level, con_score, existing_hp=char_data.get("hp_max")
    )
    char_data["hp_max"] = base_hp + (hp_bonus_per_level * level)

    # AC Calculation
    char_data["armor_class"] = calculate_ac(
        dex_score, char_data.get("equipment", []), char_data.get("features_traits", [])
    )

    # Passive Perception
    char_data["passive_perception"] = calculate_passive_perception(
        wis_score, prof_bonus, char_data.get("skill_proficiencies", [])
    )

    # Saving Throws
    char_data["saving_throw_values"] = calculate_saving_throws(
        stats, prof_bonus, char_data.get("saving_throws", [])
    )

    # Initiative
    init_bonus = 0
    for f in features:
        if "alert" in f.get("name", "").lower():
            init_bonus += 5

    char_data["initiative_modifier"] = get_modifier(dex_score) + init_bonus

    # Weapons
    weapons = char_data.get("weapons", [])
    updated_weapons = []
    for w in weapons:
        if isinstance(w, dict):
            updated_weapons.append(calculate_weapon_stats(w, stats, prof_bonus))
        else:
            # Pydantic model
            w_dict = w.model_dump()
            updated_weapons.append(calculate_weapon_stats(w_dict, stats, prof_bonus))
    char_data["weapons"] = updated_weapons

    return char_data


def check_progression_features(
    char_class: str, target_level: int, edition: str = "2014 Edition"
) -> dict:
    """
    Checks for ASI and other features at a specific level.
    Backend logic for level up wizard.
    """
    from backend.repositories.rules_repository import RulesRepository

    repo = RulesRepository()
    progression = repo.get_class_progression(char_class, edition)

    is_asi_level = False
    level_features = []

    if progression:
        level_data = progression.get("progression", {}).get(str(target_level), {})
        level_features = level_data.get("features", [])
        is_asi_level = any(
            "Ability Score Improvement" in f.get("name", "") for f in level_features
        )

    return {
        "is_asi_level": is_asi_level,
        "level_features": level_features,
        "has_progression_data": progression is not None,
    }
