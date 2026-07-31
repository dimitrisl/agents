import copy
import functools
import logging
import math
from typing import Any, Dict, List

from backend.services.dice_service import rebuild_damage_formula

logger = logging.getLogger("DnDAssistant.StatsService")


@functools.lru_cache(maxsize=128)
def get_modifier(score: int) -> int:
    """Calculates the D&D ability modifier from a score."""
    return math.floor((score - 10) / 2)


def calculate_proficiency_bonus(level: int, class_data: Dict[str, Any] = None) -> int:
    """Calculates proficiency bonus."""
    if class_data:
        progression = class_data.get("progression", {})
        level_data = progression.get(str(level), {})
        if "proficiency_bonus" in level_data:
            return level_data["proficiency_bonus"]
    return math.ceil(level / 4) + 1


def calculate_hp(class_hit_die: str, level: int, con_score: int, existing_hp: int = None) -> int:
    """Calculates HP Max, preserving existing manual rolls if provided."""
    try:
        parts = str(class_hit_die).lower().split("d")
        die_size = int(parts[-1])
    except (ValueError, AttributeError, IndexError):
        logger.warning(f"Invalid hit die format: {class_hit_die}. Defaulting to 8.")
        die_size = 8

    con_mod = get_modifier(con_score)

    if existing_hp is None or existing_hp <= 0:
        std_hp = die_size + con_mod
        if level > 1:
            average_gain = (die_size // 2 + 1) + con_mod
            std_hp += average_gain * (level - 1)
        return max(1, std_hp)

    return existing_hp


def calculate_ac(
    dex_score: int,
    equipment: List[Dict[str, Any]],
    features: List[Dict[str, Any]] = None,
    wis_score: int = None,
    con_score: int = None,
) -> int:
    """Calculates AC based on DEX and equipped items from KB."""
    from backend.repositories.rules_repository import RulesRepository

    _rules_repo = RulesRepository()
    all_items = _rules_repo.get_all_items()

    dex_mod = get_modifier(dex_score)
    base_ac = 10
    bonus_ac = 0
    max_dex = 10

    has_armor = False
    has_shield = False

    for equip in equipment:
        if isinstance(equip, str):
            equip = {"name": equip, "equipped": True}
        if not equip or not equip.get("equipped", False):
            continue

        item_name = (equip.get("name") or "").lower()
        if "shield" in item_name:
            has_shield = True

        item_data = next((i for i in all_items if i.get("name", "").lower() == item_name), None)
        try:
            val = int(equip.get("ac_bonus", 0) or 0)
        except (ValueError, TypeError):
            val = 0

        if item_data:
            if (item_data.get("type") or "").endswith("Armor") or "ac_base" in item_data:
                has_armor = True
        else:
            if val >= 10:
                has_armor = True

    has_monk_unarmored = False
    has_barbarian_unarmored = False
    has_draconic_resilience = False
    has_mage_armor = False

    if features:
        for f in features:
            if not f or not isinstance(f, dict):
                continue
            f_name = (f.get("name") or "").lower()
            if "unarmored defense" in f_name:
                source = (f.get("source") or "").lower()
                desc = (f.get("description") or "").lower()
                if "monk" in source or "wisdom" in desc:
                    has_monk_unarmored = True
                elif "barbarian" in source or "constitution" in desc:
                    has_barbarian_unarmored = True
            elif "draconic resilience" in f_name:
                has_draconic_resilience = True
            elif "mage armor" in f_name:
                has_mage_armor = True

    if not has_armor:
        unarmored_bases = [10]
        if has_monk_unarmored and not has_shield and wis_score is not None:
            unarmored_bases.append(10 + get_modifier(wis_score))
        if has_barbarian_unarmored and con_score is not None:
            unarmored_bases.append(10 + get_modifier(con_score))
        if has_draconic_resilience:
            unarmored_bases.append(13)
        if has_mage_armor:
            unarmored_bases.append(13)
        base_ac = max(base_ac, max(unarmored_bases))

    for equip in equipment:
        if isinstance(equip, str):
            equip = {"name": equip, "equipped": True}
        if not equip or not equip.get("equipped", False):
            continue

        item_name = (equip.get("name") or "").lower()
        item_data = next((i for i in all_items if i.get("name", "").lower() == item_name), None)

        try:
            val = int(equip.get("ac_bonus", 0) or 0)
        except (ValueError, TypeError):
            val = 0

        if item_data:
            if (item_data.get("type") or "").endswith("Armor") or "ac_base" in item_data:
                item_base = val if val >= 10 else item_data.get("ac_base", 10)
                base_ac = max(base_ac, item_base)

                if "dex_limit" in item_data:
                    max_dex = min(max_dex, item_data["dex_limit"])

                if val != 0 and val < 10:
                    bonus_ac += val
            else:
                item_bonus = val if val != 0 else item_data.get("ac_bonus", 0)
                bonus_ac += item_bonus
        else:
            if val >= 10:
                base_ac = max(base_ac, val)
                if "heavy" in item_name or "plate" in item_name or "chain mail" in item_name:
                    max_dex = min(max_dex, 0)
                elif "medium" in item_name or "scale" in item_name or "breastplate" in item_name:
                    max_dex = min(max_dex, 2)
            else:
                bonus_ac += val

    if features:
        for f in features:
            if not f or not isinstance(f, dict):
                continue
            if "integrated protection" in (f.get("name") or "").lower():
                bonus_ac += 1

    if features and base_ac > 10:
        for f in features:
            if not f or not isinstance(f, dict):
                continue
            name_lower = (f.get("name") or "").lower()
            if "defense" in name_lower and (
                "fighting style" in name_lower or name_lower.strip() == "defense"
            ):
                bonus_ac += 1
                break

    applied_dex = min(dex_mod, max_dex)
    return base_ac + applied_dex + bonus_ac


def calculate_passive_perception(
    wis_score: int,
    proficiency_bonus: int,
    skills: List[str],
    expertise: List[str] = None,
) -> int:
    """Calculates Passive Perception, accounting for proficiency and expertise."""
    wis_mod = get_modifier(wis_score)
    bonus = 0
    if "Perception" in (expertise or []):
        bonus = proficiency_bonus * 2
    elif "Perception" in skills:
        bonus = proficiency_bonus
    return 10 + wis_mod + bonus


def calculate_skills(
    stats: Dict[str, int],
    proficiency_bonus: int,
    proficiencies: List[str],
    expertise: List[str] = None,
) -> Dict[str, int]:
    """Calculates all skill modifiers based on ability scores and proficiencies."""
    from backend.core.constants import SKILLS_BY_ABILITY

    skills = {}
    expertise_list = expertise or []

    for ability, skill_list in SKILLS_BY_ABILITY.items():
        mod = get_modifier(stats.get(ability, 10))
        for skill in skill_list:
            bonus = mod
            if skill in expertise_list:
                bonus += proficiency_bonus * 2
            elif skill in proficiencies:
                bonus += proficiency_bonus
            skills[skill] = bonus
    return skills


def calculate_saving_throws(
    stats: Dict[str, int], proficiency_bonus: int, proficient_saves: List[str]
) -> Dict[str, int]:
    """Calculates all saving throw modifiers."""
    saves = {}
    stat_map = {
        "strength": "STR",
        "dexterity": "DEX",
        "constitution": "CON",
        "intelligence": "INT",
        "wisdom": "WIS",
        "charisma": "CHA",
    }
    normalized_prof_saves = []
    for s in proficient_saves or []:
        s_clean = str(s).strip().lower()
        if s_clean in stat_map:
            normalized_prof_saves.append(stat_map[s_clean])
        else:
            normalized_prof_saves.append(str(s).upper())

    for stat in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        base_mod = get_modifier(stats.get(stat, 10))
        bonus = proficiency_bonus if stat in normalized_prof_saves else 0
        saves[stat] = base_mod + bonus
    return saves


def calculate_spell_stats(
    ability: str, stats: Dict[str, int], proficiency_bonus: int
) -> Dict[str, Any]:
    """Calculates Spell Save DC and Spell Attack Bonus."""
    ability_mod = get_modifier(stats.get(ability, 10))
    dc = 8 + proficiency_bonus + ability_mod
    atk = proficiency_bonus + ability_mod
    return {
        "spell_save_dc": dc,
        "spell_attack_bonus": f"+{atk}" if atk >= 0 else str(atk),
    }


def calculate_max_spell_slots(char_class: str, level: int, subclass: str = None) -> Dict[str, int]:
    """Calculates maximum spell slots per level based on class, level, and subclass."""
    char_class = (char_class or "").lower()
    subclass_lower = (subclass or "").lower()
    full_casters = {"bard", "cleric", "druid", "sorcerer", "wizard"}
    half_casters = {"paladin", "ranger"}

    full_caster_slots = {
        1: [2, 0, 0, 0, 0, 0, 0, 0, 0],
        2: [3, 0, 0, 0, 0, 0, 0, 0, 0],
        3: [4, 2, 0, 0, 0, 0, 0, 0, 0],
        4: [4, 3, 0, 0, 0, 0, 0, 0, 0],
        5: [4, 3, 2, 0, 0, 0, 0, 0, 0],
        6: [4, 3, 3, 0, 0, 0, 0, 0, 0],
        7: [4, 3, 3, 1, 0, 0, 0, 0, 0],
        8: [4, 3, 3, 2, 0, 0, 0, 0, 0],
        9: [4, 3, 3, 3, 1, 0, 0, 0, 0],
        10: [4, 3, 3, 3, 2, 0, 0, 0, 0],
        11: [4, 3, 3, 3, 2, 1, 0, 0, 0],
        12: [4, 3, 3, 3, 2, 1, 0, 0, 0],
        13: [4, 3, 3, 3, 2, 1, 1, 0, 0],
        14: [4, 3, 3, 3, 2, 1, 1, 0, 0],
        15: [4, 3, 3, 3, 2, 1, 1, 1, 0],
        16: [4, 3, 3, 3, 2, 1, 1, 1, 0],
        17: [4, 3, 3, 3, 2, 1, 1, 1, 1],
        18: [4, 3, 3, 3, 3, 1, 1, 1, 1],
        19: [4, 3, 3, 3, 3, 2, 1, 1, 1],
        20: [4, 3, 3, 3, 3, 2, 2, 1, 1],
    }

    warlock_slots = {
        1: (1, 1),
        2: (2, 1),
        3: (2, 2),
        4: (2, 2),
        5: (2, 3),
        6: (2, 3),
        7: (2, 4),
        8: (2, 4),
        9: (2, 5),
        10: (2, 5),
        11: (3, 5),
        12: (3, 5),
        13: (3, 5),
        14: (3, 5),
        15: (3, 5),
        16: (3, 5),
        17: (4, 5),
        18: (4, 5),
        19: (4, 5),
        20: (4, 5),
    }

    slots = {}
    if char_class in full_casters:
        caster_level = level
    elif char_class in half_casters:
        caster_level = (level + 1) // 2 if level >= 2 else 0
    elif char_class == "artificer":
        caster_level = (level + 1) // 2
    elif char_class == "warlock":
        if level in warlock_slots:
            count, slot_lvl = warlock_slots[level]
            slots[f"level_{slot_lvl}"] = count
        return slots
    elif (
        "eldritch knight" in subclass_lower
        or "arcane trickster" in subclass_lower
        or (char_class in ["fighter", "rogue"] and level >= 3 and subclass_lower)
    ):
        # Third-caster progression (Eldritch Knight / Arcane Trickster)
        # Level 3: 2 1st lvl slots (Caster Level 1 equivalent)
        # Level 4-6: 3 1st lvl slots (Caster Level 2 equivalent)
        # Level 7-9: 4 1st lvl slots, 2 2nd lvl slots (Caster Level 3 equivalent)
        if level >= 3:
            caster_level = max(1, math.floor((level + 1) / 3))
        else:
            caster_level = 0
    else:
        caster_level = 0

    if caster_level > 0 and caster_level <= 20:
        prog = full_caster_slots[caster_level]
        for idx, count in enumerate(prog):
            if count > 0:
                slots[f"level_{idx + 1}"] = count

    return slots


def calculate_weapon_stats(
    weapon: Dict[str, Any], stats: Dict[str, int], proficiency_bonus: int
) -> Dict[str, Any]:
    """Calculates attack bonus and damage modifier for a weapon."""
    weapon = copy.copy(weapon)
    import re

    is_custom_flag = weapon.get("is_custom", False)
    if is_custom_flag is True or str(is_custom_flag).lower() == "true":
        if not weapon.get("damage_dice"):
            damage_raw = weapon.get("damage") or "1d4"
            dice_match = re.match(r"^\s*(\d*d\d+)", str(damage_raw), re.I)
            if dice_match:
                dice_part = dice_match.group(1)
                type_match = re.search(r"([a-zA-Z][a-zA-Z\s]*)$", str(damage_raw))
                dmg_type = type_match.group(1).strip() if type_match else ""
                weapon["damage_dice"] = f"{dice_part} {dmg_type}".strip()

                if weapon.get("damage_bonus", "+0") in ["+0", "", 0, "+ 0", "-0"]:
                    bonus_match = re.search(r"([+-]\s*\d+)", str(damage_raw))
                    if bonus_match:
                        weapon["damage_bonus"] = bonus_match.group(1).replace(" ", "")
                    else:
                        weapon["damage_bonus"] = "+0"

        weapon["damage"] = rebuild_damage_formula(
            weapon.get("damage_dice"), weapon.get("damage_bonus")
        )
        return weapon

    str_mod = get_modifier(stats.get("STR", 10))
    dex_mod = get_modifier(stats.get("DEX", 10))

    ability_override = weapon.get("ability_modifier")
    if ability_override:
        ability_override = ability_override.upper()
        if ability_override in stats:
            mod = get_modifier(stats[ability_override])
        else:
            mod = str_mod
    else:
        name = weapon.get("name", "").lower()
        is_ranged = any(word in name for word in ["bow", "crossbow", "sling", "dart"])
        is_finesse = any(word in name for word in ["rapier", "dagger", "scimitar", "shortsword"])

        if is_ranged:
            mod = dex_mod
        elif is_finesse:
            mod = max(str_mod, dex_mod)
        else:
            mod = str_mod

    magic_bonus = int(weapon.get("magic_bonus", 0))

    attack_bonus = mod + proficiency_bonus + magic_bonus
    weapon["attack_bonus"] = f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)

    damage_raw = weapon.get("damage") or rebuild_damage_formula(
        weapon.get("damage_dice"), weapon.get("damage_bonus")
    )
    dice_match = re.match(r"^\s*(\d+d\d+)", damage_raw, re.I)
    if dice_match:
        dice_part = dice_match.group(1)
        type_match = re.search(r"([a-zA-Z][a-zA-Z\s]*)$", damage_raw)
        dmg_type = type_match.group(1).strip() if type_match else ""

        total_dmg_mod = mod + magic_bonus
        if total_dmg_mod < 0:
            total_dmg_mod = 0

        weapon["damage_dice"] = f"{dice_part} {dmg_type}".strip()
        weapon["damage_bonus"] = f"+{total_dmg_mod}"
        weapon["damage"] = rebuild_damage_formula(weapon["damage_dice"], weapon["damage_bonus"])

    return weapon


def sync_character_stats(
    char_data: Dict[str, Any],
    class_data: Dict[str, Any] = None,
    weapon_deltas: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Synchronizes all derived character stats."""
    from backend.repositories.rules_repository import RulesRepository

    char_data = copy.deepcopy(char_data)
    repo = RulesRepository()

    stats_raw = char_data.get("stats", {})
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

    if "saving_throw_values" not in char_data or char_data["saving_throw_values"] is None:
        char_data["saving_throw_values"] = {}

    level = char_data.get("char_level", 1)
    edition = char_data.get("dnd_edition", "2014 Edition")
    char_class = char_data.get("char_class", "Fighter")

    if not class_data:
        class_data = repo.get_class_progression(char_class, edition)

    prof_bonus = calculate_proficiency_bonus(level, class_data)
    char_data["proficiency_bonus"] = prof_bonus

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

    for equip in char_data["equipment"]:
        if not equip.get("equipped", False):
            continue

        for i in [1, 2]:
            raw_mod = equip.get(f"mod{i}")
            if not raw_mod:
                continue

            attr_key = str(raw_mod).upper().strip()
            bonus_val = int(equip.get(f"val{i}", 0))

            if not attr_key or attr_key == "NONE" or bonus_val == 0:
                continue

            if attr_key in stats:
                stats[attr_key] += bonus_val
            elif attr_key == "HP":
                char_data["hp_max"] = char_data.get("hp_max", 0) + bonus_val
            elif attr_key in ["SPD", "SPEED"]:
                char_data["speed"] = char_data.get("speed", 30) + bonus_val
            elif attr_key in ["INIT", "INITIATIVE"]:
                char_data["initiative_bonus"] = char_data.get("initiative_bonus", 0) + bonus_val
            elif attr_key in ["ATK", "HIT", "ATTACK"]:
                char_data["global_attack_bonus"] = (
                    char_data.get("global_attack_bonus", 0) + bonus_val
                )
            elif attr_key in ["DMG", "DAMAGE"]:
                char_data["global_damage_bonus"] = (
                    char_data.get("global_damage_bonus", 0) + bonus_val
                )
            elif attr_key in ["SAVES", "SAVE"]:
                for s in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
                    char_data["saving_throw_values"][s] = (
                        char_data["saving_throw_values"].get(s, 0) + bonus_val
                    )

        item_name = equip.get("name", "").lower()
        all_items = repo.get_all_items()
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

    prof_bonus = calculate_proficiency_bonus(level, class_data)
    char_data["proficiency_bonus"] = prof_bonus

    if not char_data.get("saving_throws"):
        class_saves = {
            "barbarian": ["STR", "CON"],
            "bard": ["DEX", "CHA"],
            "cleric": ["WIS", "CHA"],
            "druid": ["INT", "WIS"],
            "fighter": ["STR", "CON"],
            "monk": ["STR", "DEX"],
            "paladin": ["WIS", "CHA"],
            "ranger": ["STR", "DEX"],
            "rogue": ["DEX", "INT"],
            "sorcerer": ["CON", "CHA"],
            "warlock": ["WIS", "CHA"],
            "wizard": ["INT", "WIS"],
            "artificer": ["CON", "INT"],
        }
        char_class_lower = char_class.lower() if char_class else ""
        if char_class_lower in class_saves:
            char_data["saving_throws"] = class_saves[char_class_lower]
        elif class_data:
            raw_saves = class_data.get("primary_ability", [])
            clean_saves = []
            abbr_map = {
                "strength": "STR",
                "dexterity": "DEX",
                "constitution": "CON",
                "intelligence": "INT",
                "wisdom": "WIS",
                "charisma": "CHA",
                "str": "STR",
                "dex": "DEX",
                "con": "CON",
                "int": "INT",
                "wis": "WIS",
                "cha": "CHA",
            }
            for s in raw_saves:
                s_clean = str(s).strip().lower()
                if s_clean in abbr_map:
                    clean_saves.append(abbr_map[s_clean])
            char_data["saving_throws"] = clean_saves
    else:
        abbr_map = {
            "strength": "STR",
            "dexterity": "DEX",
            "constitution": "CON",
            "intelligence": "INT",
            "wisdom": "WIS",
            "charisma": "CHA",
            "str": "STR",
            "dex": "DEX",
            "con": "CON",
            "int": "INT",
            "wis": "WIS",
            "cha": "CHA",
        }
        clean_saves = []
        for s in char_data.get("saving_throws", []):
            s_clean = str(s).strip().lower()
            if s_clean in abbr_map:
                clean_saves.append(abbr_map[s_clean])
            elif s in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
                clean_saves.append(s)
        char_data["saving_throws"] = clean_saves

    from backend.services.progression_service import get_hit_die_for_class

    hit_die_size = get_hit_die_for_class(char_class, edition)
    if class_data and "hit_die" in class_data:
        raw_die = class_data["hit_die"]
        hit_die_size = raw_die[1:] if raw_die.startswith("1d") else raw_die

    char_data["hit_dice"] = f"{level}{hit_die_size}"

    hp_bonus_per_level = 0
    features = char_data.get("features_traits", [])

    feat_library = repo.get_all_feats(edition)
    feat_lookup = {f["name"].lower(): f for f in feat_library} if feat_library else {}

    for f in features:
        feat_name = f.get("name", "").lower()
        clean_name = feat_name.replace("feat: ", "").strip()

        feat_data = feat_lookup.get(clean_name)
        if not feat_data:
            for k, v in feat_lookup.items():
                if k in clean_name or clean_name in k:
                    feat_data = v
                    break
        if feat_data and feat_data.get("hp_bonus_per_level", 0) > 0:
            hp_bonus_per_level += feat_data["hp_bonus_per_level"]
        else:
            desc = f.get("description", "").lower()
            if "dwarven toughness" in desc:
                hp_bonus_per_level += 1

    existing_hp = char_data.get("hp_max")
    if existing_hp is not None and existing_hp > 0:
        base_existing_hp = existing_hp - (hp_bonus_per_level * level)
    else:
        base_existing_hp = None

    base_hp = calculate_hp(hit_die_size, level, con_score, existing_hp=base_existing_hp)
    char_data["hp_max"] = base_hp + (hp_bonus_per_level * level)

    char_data["armor_class"] = calculate_ac(
        dex_score,
        char_data.get("equipment", []),
        char_data.get("features_traits", []),
        wis_score=wis_score,
        con_score=con_score,
    )

    # Skill Proficiencies Synchronization: Ensure skill_proficiencies contains Perception if Passive Perception or Perception skill has proficiency bonus
    skill_profs = list(char_data.get("skill_proficiencies", []))
    wis_mod = get_modifier(wis_score)
    pass_perc = char_data.get("passive_perception", 10)

    if pass_perc >= 10 + wis_mod + prof_bonus and "Perception" not in skill_profs:
        skill_profs.append("Perception")

    temp_skills = calculate_skills(
        stats, prof_bonus, skill_profs, char_data.get("skill_expertise", [])
    )
    for skill_name, skill_val in temp_skills.items():
        from backend.core.constants import SKILLS_BY_ABILITY

        ability_for_skill = next(
            (ab for ab, s_list in SKILLS_BY_ABILITY.items() if skill_name in s_list), None
        )
        if ability_for_skill:
            ab_mod = get_modifier(stats.get(ability_for_skill, 10))
            if skill_val >= ab_mod + prof_bonus and skill_name not in skill_profs:
                skill_profs.append(skill_name)

    char_data["skill_proficiencies"] = list(dict.fromkeys(skill_profs))

    char_data["passive_perception"] = calculate_passive_perception(
        wis_score,
        prof_bonus,
        char_data["skill_proficiencies"],
        char_data.get("skill_expertise", []),
    )

    char_data["skills"] = calculate_skills(
        stats,
        prof_bonus,
        char_data["skill_proficiencies"],
        char_data.get("skill_expertise", []),
    )

    char_data["saving_throw_values"] = calculate_saving_throws(
        stats, prof_bonus, char_data.get("saving_throws", [])
    )

    init_bonus = 0
    for f in features:
        feat_name = f.get("name", "").lower().replace("feat: ", "").strip()
        feat_data = feat_lookup.get(feat_name)
        if not feat_data:
            for k, v in feat_lookup.items():
                if k in feat_name or feat_name in k:
                    feat_data = v
                    break
        if feat_data:
            init_bonus += feat_data.get("initiative_bonus", 0)
            if feat_data.get("initiative_proficiency", False):
                init_bonus += prof_bonus

    char_data["initiative_modifier"] = get_modifier(dex_score) + init_bonus

    weapons = char_data.get("weapons", [])
    updated_weapons = []
    edited_weapon_rows = weapon_deltas.get("edited_rows", {}) if weapon_deltas else {}
    from backend.core.schemas import Weapon

    for idx, w in enumerate(weapons):
        w_dict = (
            w
            if isinstance(w, dict)
            else (w.model_dump() if hasattr(w, "model_dump") else {"name": str(w)})
        )

        idx_str = str(idx)
        if idx_str in edited_weapon_rows:
            changes = edited_weapon_rows[idx_str]
            normalized_changes = Weapon.normalize_dict(changes)
            w_dict.update(normalized_changes)

            combat_keys = {"attack_bonus", "damage_dice", "damage_bonus"}
            if (
                any(k in combat_keys for k in normalized_changes)
                and "is_custom" not in normalized_changes
            ):
                w_dict["is_custom"] = True

            if any(k in ["damage_dice", "damage_bonus"] for k in normalized_changes):
                w_dict["damage"] = rebuild_damage_formula(
                    w_dict.get("damage_dice"), w_dict.get("damage_bonus")
                )

        updated_weapons.append(calculate_weapon_stats(w_dict, stats, prof_bonus))

    if weapon_deltas and "deleted_rows" in weapon_deltas:
        deleted_indices = sorted(weapon_deltas["deleted_rows"], reverse=True)
        for idx in deleted_indices:
            if idx < len(updated_weapons):
                updated_weapons.pop(idx)

    if weapon_deltas and "added_rows" in weapon_deltas:
        for row in weapon_deltas["added_rows"]:
            new_w_data = Weapon.normalize_dict(row)
            new_w = {
                "name": new_w_data.get("name", "New Weapon"),
                "magic_bonus": int(new_w_data.get("magic_bonus", 0)),
                "attack_bonus": new_w_data.get("attack_bonus", "+0"),
                "damage_dice": new_w_data.get("damage_dice", "1d4"),
                "damage_bonus": new_w_data.get("damage_bonus", "+0"),
                "properties": new_w_data.get("properties", ""),
                "range": new_w_data.get("range", ""),
                "is_custom": new_w_data.get("is_custom", False),
            }
            new_w = calculate_weapon_stats(new_w, stats, prof_bonus)
            updated_weapons.append(new_w)

    char_data["weapons"] = updated_weapons

    # Infer & Calculate Spellcasting Stats (DC & Attack Bonus)
    spell_ability = char_data.get("spell_ability")
    if not spell_ability or spell_ability == "None":
        class_lower = (char_class or "").lower()
        subclass_lower = (char_data.get("subclass") or "").lower()
        feats_str = str(char_data.get("features_traits", [])).lower()
        if (
            class_lower in ["wizard", "artificer"]
            or "eldritch knight" in subclass_lower
            or "arcane trickster" in subclass_lower
            or "eldritch knight" in feats_str
            or "arcane trickster" in feats_str
            or (class_lower == "fighter" and (char_data.get("spell_slots") or char_data.get("spells")))
        ):
            spell_ability = "INT"
        elif class_lower in ["cleric", "druid", "ranger"]:
            spell_ability = "WIS"
        elif class_lower in ["paladin", "sorcerer", "warlock", "bard"]:
            spell_ability = "CHA"
        elif char_data.get("spells") or char_data.get("prepared_spells") or char_data.get("spell_slots"):
            mental_stats = {
                "INT": stats.get("INT", 10),
                "WIS": stats.get("WIS", 10),
                "CHA": stats.get("CHA", 10),
            }
            spell_ability = max(mental_stats, key=mental_stats.get)

    if spell_ability and spell_ability != "None":
        char_data["spell_ability"] = spell_ability
        spell_stats = calculate_spell_stats(spell_ability, stats, prof_bonus)
        char_data["spell_save_dc"] = spell_stats["spell_save_dc"]
        char_data["spell_attack_bonus"] = spell_stats["spell_attack_bonus"]

    subclass = char_data.get("subclass")
    max_slots = calculate_max_spell_slots(char_class, level, subclass=subclass)
    if "spell_slots" not in char_data or not char_data["spell_slots"]:
        char_data["spell_slots"] = {}

    for slot_lvl, max_val in max_slots.items():
        existing = char_data["spell_slots"].get(slot_lvl)
        if isinstance(existing, dict):
            existing["max"] = max_val
        elif isinstance(existing, int):
            char_data["spell_slots"][slot_lvl] = {"max": max_val, "used": min(existing, max_val)}
        else:
            char_data["spell_slots"][slot_lvl] = {"max": max_val, "used": 0}

    if max_slots:
        keys_to_remove = [k for k in char_data["spell_slots"] if k not in max_slots]
        for k in keys_to_remove:
            del char_data["spell_slots"][k]

    # Ensure Passive Perception and Skill Proficiencies alignment
    skill_profs = char_data.get("skill_proficiencies") or []
    wis_mod = math.floor((stats.get("WIS", 10) - 10) / 2)
    passive_percep = char_data.get("passive_perception") or (10 + wis_mod)
    if passive_percep >= 10 + wis_mod + prof_bonus:
        if "Perception" not in skill_profs:
            skill_profs.append("Perception")
            char_data["skill_proficiencies"] = skill_profs

    if char_class.lower() == "rogue":
        sneak_attack_dice = (level + 1) // 2
        sneak_attack_str = f"{sneak_attack_dice}d6"
        for ft in char_data.get("features_traits", []):
            if ft.get("name") == "Sneak Attack":
                desc = ft.get("description", "")
                if "extra 1d6 damage" in desc:
                    ft["description"] = desc.replace(
                        "extra 1d6 damage", f"extra {sneak_attack_str} damage"
                    )
                elif "extra" in desc and "damage" in desc:
                    import re

                    ft["description"] = re.sub(
                        r"extra \d+d6 damage", f"extra {sneak_attack_str} damage", desc
                    )

    # ----------------------------------------------------
    # 2024 Edition Rules (5.5e) Enhancements: Masteries, Origin Feats, Fighter Features
    # ----------------------------------------------------
    is_2024 = "2024" in str(edition) or "2024" in str(char_data.get("dnd_edition", ""))

    if is_2024:
        # Filter out legacy 2014 background combat/roleplay traits
        legacy_bg_features = {
            "stand your ground",
            "military rank",
            "shelter of the faithful",
            "rustic hospitality",
            "criminal contact",
            "guild membership",
            "position of privilege",
            "researcher",
            "watcher's eye",
            "by popular demand",
            "false identity",
        }
        if char_data.get("features_traits"):
            char_data["features_traits"] = [
                f
                for f in char_data["features_traits"]
                if not (
                    isinstance(f, dict)
                    and (f.get("name") or "").lower() in legacy_bg_features
                )
            ]

        # A. Weapon Masteries (Fighter Lvl 1-3 = 3, Lvl 4+ = 4 masteries)
        martial_classes = ["fighter", "barbarian", "paladin", "ranger", "rogue"]
        if (char_class or "").lower() in martial_classes:
            target_masteries_count = 4 if (char_class or "").lower() == "fighter" and level >= 4 else (3 if level >= 4 else 2)
            existing_masteries = list(char_data.get("weapon_masteries") or [])

            # Prioritize masteries matching equipped weapons
            equipped_weapon_masteries = []
            for w in char_data.get("weapons", []):
                if isinstance(w, dict):
                    w_name = (w.get("name") or "").lower()
                    if "longsword" in w_name and "Sap (Longsword)" not in equipped_weapon_masteries:
                        equipped_weapon_masteries.append("Sap (Longsword)")
                    elif "crossbow" in w_name and "Slow (Light Crossbow)" not in equipped_weapon_masteries:
                        equipped_weapon_masteries.append("Slow (Light Crossbow)")
                    elif "greatsword" in w_name and "Graze (Greatsword)" not in equipped_weapon_masteries:
                        equipped_weapon_masteries.append("Graze (Greatsword)")
                    elif "warhammer" in w_name and "Topple (Warhammer)" not in equipped_weapon_masteries:
                        equipped_weapon_masteries.append("Topple (Warhammer)")

            for m in equipped_weapon_masteries:
                if m not in existing_masteries:
                    existing_masteries.insert(0, m)

            mastery_pool = [
                "Sap (Longsword)",
                "Slow (Light Crossbow)",
                "Graze (Greatsword)",
                "Nick (Dagger)",
                "Topple (Warhammer)",
                "Vex (Shortsword)",
                "Push (Pike)",
                "Cleave (Greataxe)",
            ]
            for m in mastery_pool:
                if len(existing_masteries) >= target_masteries_count:
                    break
                if m not in existing_masteries:
                    existing_masteries.append(m)

            char_data["weapon_masteries"] = existing_masteries[:target_masteries_count]

            for w in char_data.get("weapons", []):
                if isinstance(w, dict):
                    w_name = (w.get("name") or "").lower()
                    props = w.get("properties") or ""
                    if "mastery" not in props.lower():
                        if "longsword" in w_name:
                            w["properties"] = f"{props}, Mastery: Sap".strip(", ")
                        elif "crossbow" in w_name:
                            w["properties"] = f"{props}, Mastery: Slow".strip(", ")

        # B. Background Origin Feat
        bg = (char_data.get("background") or "").lower()
        origin_feat_map = {
            "guard": {
                "name": "Origin Feat: Alert",
                "description": "2024 Origin Feat: Add Proficiency Bonus (+3) to Initiative rolls and swap initiative with a willing ally.",
            },
            "soldier": {
                "name": "Origin Feat: Savage Attacker",
                "description": "2024 Origin Feat: Reroll weapon damage dice once per turn.",
            },
            "farmer": {
                "name": "Origin Feat: Tough",
                "description": "2024 Origin Feat: Gain +2 HP per level.",
            },
            "acolyte": {
                "name": "Origin Feat: Magic Initiate (Cleric)",
                "description": "2024 Origin Feat: Learn 2 Cleric cantrips and one 1st-level Cleric spell.",
            },
            "criminal": {
                "name": "Origin Feat: Alert",
                "description": "2024 Origin Feat: Add Proficiency Bonus to Initiative rolls.",
            },
            "guide": {
                "name": "Origin Feat: Magic Initiate (Druid)",
                "description": "2024 Origin Feat: Learn 2 Druid cantrips and one 1st-level Druid spell.",
            },
            "sage": {
                "name": "Origin Feat: Magic Initiate (Wizard)",
                "description": "2024 Origin Feat: Learn 2 Wizard cantrips and one 1st-level Wizard spell.",
            },
            "noble": {
                "name": "Origin Feat: Skilled",
                "description": "2024 Origin Feat: Gain proficiency in 3 skills of your choice.",
            },
            "sailor": {
                "name": "Origin Feat: Tavern Brawler",
                "description": "2024 Origin Feat: Re-roll 1s on unarmed strikes and shove as bonus action.",
            },
        }

        has_origin_feat = any(
            "origin feat" in f.get("name", "").lower()
            or "alert" in f.get("name", "").lower()
            or "savage attacker" in f.get("name", "").lower()
            for f in char_data.get("features_traits", [])
        )
        if not has_origin_feat:
            origin_info = origin_feat_map.get(bg, origin_feat_map["guard"])
            char_data.setdefault("features_traits", []).append(origin_info)

            if "alert" in origin_info["name"].lower():
                char_data["initiative_modifier"] = get_modifier(dex_score) + prof_bonus

        # C. 2024 Fighter Class Features (Tactical Mind & Tactical Shift)
        if (char_class or "").lower() == "fighter":
            ft_names = [f.get("name", "").lower() for f in char_data.get("features_traits", [])]
            if level >= 2 and not any("tactical mind" in n for n in ft_names):
                char_data.setdefault("features_traits", []).append(
                    {
                        "name": "Tactical Mind (2024)",
                        "description": "When you fail an Ability Check, you can spend 1 use of Second Wind to roll 1d10 and add it to the check. If you still fail, the Second Wind use is not expended.",
                    }
                )
            if level >= 5 and not any("tactical shift" in n for n in ft_names):
                char_data.setdefault("features_traits", []).append(
                    {
                        "name": "Tactical Shift (2024)",
                        "description": "As part of the Bonus Action you take to use Second Wind, you can move up to half your Speed without provoking Opportunity Attacks.",
                    }
                )

        # D. Eldritch Knight / Arcane Trickster Cantrip Limit (2 cantrips at level 5)
        subclass_clean = (char_data.get("subclass") or "").lower()
        if ("eldritch knight" in subclass_clean or "arcane trickster" in subclass_clean) and level < 10:
            spells_dict = char_data.get("spells")
            if isinstance(spells_dict, dict) and "cantrips" in spells_dict:
                cantrips = spells_dict.get("cantrips", [])
                if isinstance(cantrips, list) and len(cantrips) > 2:
                    spells_dict["cantrips"] = cantrips[:2]

    return char_data
