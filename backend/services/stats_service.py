import copy
import functools
import logging
import math
from typing import Any, Dict, List, Tuple, Union

from backend.services.dice_service import rebuild_damage_formula

logger = logging.getLogger("DnDAssistant.StatsService")

_ITEM_TYPES = ("item", "armor", "shield", "weapon")
_FEAT_TYPES = ("feat", "feature")


def _merge_homebrew_items(
    base_items: List[Dict[str, Any]], homebrew_content: List[Dict[str, Any]] | None
) -> List[Dict[str, Any]]:
    """Merge homebrew items/armor/shields/weapons into the static item list."""
    if not homebrew_content:
        return base_items
    return base_items + [i for i in homebrew_content if i.get("homebrew_type") in _ITEM_TYPES]


def _merge_homebrew_weapons(
    base_weapons: List[Dict[str, Any]], homebrew_content: List[Dict[str, Any]] | None
) -> List[Dict[str, Any]]:
    """Merge homebrew weapons into the static weapon list."""
    if not homebrew_content:
        return base_weapons
    return base_weapons + [w for w in homebrew_content if w.get("homebrew_type") == "weapon"]


def _merge_homebrew_feats(
    base_feats: List[Dict[str, Any]], homebrew_content: List[Dict[str, Any]] | None
) -> List[Dict[str, Any]]:
    """Merge homebrew feats/features into the static feat list."""
    if not homebrew_content:
        return base_feats
    return base_feats + [f for f in homebrew_content if f.get("homebrew_type") in _FEAT_TYPES]


@functools.lru_cache(maxsize=128)
def get_modifier(score: int) -> int:
    """Calculates the D&D ability modifier from a score."""
    return math.floor((score - 10) / 2)


@functools.lru_cache(maxsize=2)
def _get_known_cantrips_for_edition(edition: str) -> set:
    from backend.repositories.rules_repository import RulesRepository

    repo = RulesRepository()
    spells = repo.get_all_spells(edition)
    return frozenset(
        s.get("name", "").strip().lower()
        for s in spells
        if str(s.get("level", "")).lower() in ["0", "cantrip"]
    )


def calculate_proficiency_bonus(level: int, class_data: Dict[str, Any] = None) -> int:
    """Calculates proficiency bonus."""
    if class_data:
        progression = class_data.get("progression", {})
        level_data = progression.get(str(level), {})
        if "proficiency_bonus" in level_data:
            return level_data["proficiency_bonus"]
    return math.ceil(level / 4) + 1


def calculate_hp(
    class_hit_die: str,
    level: int,
    con_score: int,
    existing_hp: int = None,
    hit_dice_list: list = None,
) -> int:
    """Calculates HP Max, preserving existing manual rolls if provided. Supports multiclassing via hit_dice_list."""
    con_mod = get_modifier(con_score)

    if existing_hp is not None and existing_hp > 0:
        return existing_hp

    if not hit_dice_list:
        hit_dice_list = [f"{level}d{str(class_hit_die).lower().split('d')[-1]}"]

    total_hp = 0
    first_level_added = False

    for hd_str in hit_dice_list:
        try:
            parts = hd_str.lower().split("d")
            count = int(parts[0])
            die_size = int(parts[1])
        except (ValueError, IndexError):
            continue

        for i in range(count):
            if not first_level_added:
                total_hp += die_size + con_mod
                first_level_added = True
            else:
                total_hp += (die_size // 2 + 1) + con_mod

    if not first_level_added:
        # Fallback if list was empty or invalid
        total_hp = 8 + con_mod

    return total_hp


def calculate_ac(
    dex_score: int,
    equipment: List[Dict[str, Any]],
    features: List[Dict[str, Any]] = None,
    wis_score: int = None,
    con_score: int = None,
    homebrew_content: List[Dict[str, Any]] = None,
    return_breakdown: bool = False,
) -> Union[int, Tuple[int, Dict[str, Any]]]:
    """Calculates AC based on DEX and equipped items from KB, optionally returning breakdown."""
    from backend.repositories.rules_repository import RulesRepository

    _rules_repo = RulesRepository()
    all_items = _merge_homebrew_items(_rules_repo.get_all_items(), homebrew_content)

    dex_mod = get_modifier(dex_score)
    base_ac = 10
    bonus_ac = 0
    max_dex = 10

    has_armor = False
    has_shield = False
    armor_name = None
    armor_type = "unarmored"

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

    base_source = "Base (10)"
    if not has_armor:
        if has_monk_unarmored and not has_shield and wis_score is not None:
            monk_val = 10 + get_modifier(wis_score)
            if monk_val > base_ac:
                base_ac = monk_val
                base_source = f"Unarmored Defense (Monk: 10 + WIS {get_modifier(wis_score):+d})"
        if has_barbarian_unarmored and con_score is not None:
            barb_val = 10 + get_modifier(con_score)
            if barb_val > base_ac:
                base_ac = barb_val
                base_source = (
                    f"Unarmored Defense (Barbarian: 10 + CON {get_modifier(con_score):+d})"
                )
        if has_draconic_resilience:
            if 13 > base_ac:
                base_ac = 13
                base_source = "Draconic Resilience (13)"
        if has_mage_armor:
            if 13 > base_ac:
                base_ac = 13
                base_source = "Mage Armor (13)"

    shield_bonus_applied = False
    shield_name = None
    shield_bonus = 0
    other_bonuses = []

    for equip in equipment:
        if isinstance(equip, str):
            equip = {"name": equip, "equipped": True}
        if not equip or not equip.get("equipped", False):
            continue

        raw_item_name = equip.get("name") or ""
        item_name = raw_item_name.lower()
        item_data = next((i for i in all_items if i.get("name", "").lower() == item_name), None)

        try:
            val = int(equip.get("ac_bonus", 0) or 0)
        except (ValueError, TypeError):
            val = 0

        is_shield = "shield" in item_name or (
            item_data and (item_data.get("type") or "").lower() == "shield"
        )
        if is_shield:
            if shield_bonus_applied:
                continue
            shield_bonus_applied = True
            shield_name = raw_item_name or "Shield"
            s_val = val if val != 0 else (item_data.get("ac_bonus", 2) if item_data else 2)
            shield_bonus = s_val
            bonus_ac += s_val
            continue

        if item_data:
            if (item_data.get("type") or "").endswith("Armor") or "ac_base" in item_data:
                item_base = val if val >= 10 else item_data.get("ac_base", 10)
                if item_base >= base_ac:
                    base_ac = item_base
                    armor_name = item_data.get("name", raw_item_name)
                    armor_type = item_data.get("type", "Armor")
                    base_source = f"{armor_name} ({base_ac})"

                if "dex_limit" in item_data:
                    max_dex = min(max_dex, item_data["dex_limit"])

                if val != 0 and val < 10:
                    bonus_ac += val
                    other_bonuses.append((f"{raw_item_name} bonus", val))
            else:
                item_bonus = val if val != 0 else item_data.get("ac_bonus", 0)
                if item_bonus != 0:
                    bonus_ac += item_bonus
                    other_bonuses.append((raw_item_name, item_bonus))
        else:
            if val >= 10:
                if val >= base_ac:
                    base_ac = val
                    armor_name = raw_item_name
                    base_source = f"{armor_name} ({base_ac})"
                if "heavy" in item_name or "plate" in item_name or "chain mail" in item_name:
                    max_dex = min(max_dex, 0)
                    armor_type = "Heavy Armor"
                elif "medium" in item_name or "scale" in item_name or "breastplate" in item_name:
                    max_dex = min(max_dex, 2)
                    armor_type = "Medium Armor"
                else:
                    armor_type = "Light Armor"
            elif val != 0:
                bonus_ac += val
                other_bonuses.append((raw_item_name, val))

    if features:
        for f in features:
            if not f or not isinstance(f, dict):
                continue
            if "integrated protection" in (f.get("name") or "").lower():
                bonus_ac += 1
                other_bonuses.append(("Warforged Integrated Protection", 1))

    defense_bonus = 0
    if features and has_armor:
        for f in features:
            if not f or not isinstance(f, dict):
                continue
            name_lower = (f.get("name") or "").lower()
            if "defense" in name_lower and (
                "fighting style" in name_lower or name_lower.strip() == "defense"
            ):
                defense_bonus = 1
                bonus_ac += 1
                break

    applied_dex = 0 if max_dex == 0 else min(dex_mod, max_dex)
    total_ac = base_ac + applied_dex + bonus_ac

    if not return_breakdown:
        return total_ac

    formula_parts = [base_source]
    if max_dex == 0:
        if dex_mod != 0:
            formula_parts.append("DEX (+0, heavy armor)")
    else:
        dex_label = f"DEX ({applied_dex:+d})"
        if max_dex < 10 and dex_mod > max_dex:
            dex_label = f"DEX ({applied_dex:+d} max)"
        formula_parts.append(dex_label)

    if shield_bonus > 0:
        formula_parts.append(f"{shield_name or 'Shield'} (+{shield_bonus})")

    if defense_bonus > 0:
        formula_parts.append(f"Defense Style (+{defense_bonus})")

    for ob_name, ob_val in other_bonuses:
        formula_parts.append(f"{ob_name} (+{ob_val})")

    formula_text = " + ".join(formula_parts) + f" = {total_ac}"

    breakdown = {
        "base": base_ac,
        "base_source": base_source,
        "armor_type": armor_type,
        "dex_mod": dex_mod,
        "dex_applied": applied_dex,
        "dex_cap": max_dex if max_dex < 10 else None,
        "shield_bonus": shield_bonus,
        "shield_name": shield_name,
        "defense_bonus": defense_bonus,
        "other_bonuses": [{"name": ob[0], "bonus": ob[1]} for ob in other_bonuses],
        "total": total_ac,
        "formula_text": formula_text,
    }

    return total_ac, breakdown


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


def calculate_max_spell_slots(
    char_class: str,
    level: int,
    subclass: str = None,
    caster_type: str = None,
    classes: list = None,
    edition: str = "2014 Edition",
) -> Dict[str, int]:
    """Calculates maximum spell slots per level based on class, level, subclass, and caster type.
    If 'classes' is provided, it calculates total multiclass slots."""
    import math

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

    if not classes:
        classes = [
            {
                "class_name": char_class,
                "level": level,
                "subclass": subclass,
                "caster_type": caster_type,
            }
        ]

    full_casters = {"bard", "cleric", "druid", "sorcerer", "wizard"}
    half_casters = {"paladin", "ranger", "artificer"}

    def _infer_ctype(cname: str, sub: str, raw_ctype: Any) -> str | None:
        if raw_ctype:
            return str(raw_ctype).lower()
        if cname == "warlock":
            return "pact"
        if cname in full_casters:
            return "full"
        if cname in half_casters:
            return "half"
        if "eldritch knight" in sub or "arcane trickster" in sub:
            return "third"
        return None

    total_caster_level = 0
    warlock_level = 0
    spellcasting_classes = 0
    single_caster_cls = None

    for cls in classes:
        cname = (cls.get("class_name") or "").lower()
        sub = (cls.get("subclass") or "").lower()
        lvl = cls.get("level", 1)
        ctype = _infer_ctype(cname, sub, cls.get("caster_type"))

        if ctype == "pact" or cname == "warlock":
            warlock_level += lvl
            continue

        cls_caster_level = 0
        if ctype == "full":
            cls_caster_level = lvl
        elif ctype == "half":
            is_2024 = "2024" in str(edition)
            if cname == "artificer" or (is_2024 and cname in ["paladin", "ranger"]):
                cls_caster_level = math.ceil(lvl / 2)
            else:
                cls_caster_level = math.floor(lvl / 2)
        elif ctype == "third" or "eldritch knight" in sub or "arcane trickster" in sub:
            cls_caster_level = math.floor(lvl / 3)

        if cls_caster_level > 0:
            spellcasting_classes += 1
            single_caster_cls = cls

        total_caster_level += cls_caster_level

    slots = {}

    if spellcasting_classes <= 1:
        target_cls = single_caster_cls
        if not target_cls and len(classes) > 0:
            target_cls = classes[0]

        if target_cls:
            cname = (target_cls.get("class_name") or "").lower()
            sub = (target_cls.get("subclass") or "").lower()
            lvl = target_cls.get("level", 1)
            ctype = _infer_ctype(cname, sub, target_cls.get("caster_type"))

            if ctype == "pact" or cname == "warlock":
                if warlock_level in warlock_slots:
                    count, slot_lvl = warlock_slots[warlock_level]
                    slots[f"level_{slot_lvl}"] = count
                return slots

            if ctype == "full":
                caster_level = lvl
            elif ctype == "half":
                is_2024 = "2024" in str(edition)
                if cname == "artificer" or (is_2024 and cname in ["paladin", "ranger"]):
                    caster_level = (lvl + 1) // 2
                else:
                    caster_level = (lvl + 1) // 2 if lvl >= 2 else 0
            elif ctype == "third" or "eldritch knight" in sub or "arcane trickster" in sub:
                if lvl >= 3:
                    caster_level = max(1, (lvl + 2) // 3)
                else:
                    caster_level = 0
            else:
                caster_level = 0

            if caster_level > 0 and caster_level <= 20:
                prog = full_caster_slots[caster_level]
                for idx, count in enumerate(prog):
                    if count > 0:
                        slots[f"level_{idx + 1}"] = count

    elif total_caster_level > 0 and total_caster_level <= 20:
        prog = full_caster_slots[total_caster_level]
        for idx, count in enumerate(prog):
            if count > 0:
                slots[f"level_{idx + 1}"] = count
    elif total_caster_level > 20:
        prog = full_caster_slots[20]
        for idx, count in enumerate(prog):
            if count > 0:
                slots[f"level_{idx + 1}"] = count

    if warlock_level > 0 and warlock_level <= 20:
        count, slot_lvl = warlock_slots[warlock_level]
        key = f"level_{slot_lvl}"
        slots[key] = slots.get(key, 0) + count

    return slots


def get_base_weapon(name: str, all_weapons: list) -> dict:
    import re

    name = (name or "").lower()
    weapon_data = next((w for w in all_weapons if w.get("name", "").lower() == name), None)
    if not weapon_data:
        sorted_weapons = sorted(all_weapons, key=lambda x: len(x.get("name", "")), reverse=True)
        for w in sorted_weapons:
            w_name = w.get("name", "").lower()
            if w_name and re.search(rf"\b{re.escape(w_name)}\b", name):
                return w
    return weapon_data


def calculate_weapon_stats(
    weapon: Dict[str, Any],
    stats: Dict[str, int],
    proficiency_bonus: int,
    homebrew_content: List[Dict[str, Any]] = None,
    features_traits: List[Any] = None,
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
        is_ranged = False
    else:
        from backend.repositories.rules_repository import RulesRepository

        repo = RulesRepository()
        all_weapons = _merge_homebrew_weapons(repo.get_all_weapons(), homebrew_content)
        name = weapon.get("name", "").lower()

        weapon_data = get_base_weapon(name, all_weapons)

        if weapon_data:
            category = (weapon_data.get("category") or "").lower()
            props = [p.lower() for p in weapon_data.get("properties", [])]
            is_ranged = "ranged" in category
            is_finesse = any("finesse" in p for p in props)
        else:
            is_ranged = any(
                word in name for word in ["bow", "crossbow", "sling", "dart", "blowgun"]
            )
            is_finesse = any(
                word in name for word in ["rapier", "dagger", "scimitar", "shortsword", "whip"]
            )

        if is_ranged:
            mod = dex_mod
        elif is_finesse:
            mod = max(str_mod, dex_mod)
        else:
            mod = str_mod

    # Extract magic bonus from weapon or weapon name (e.g. "Longbow +1")
    magic_bonus_raw = weapon.get("magic_bonus")
    if magic_bonus_raw is not None and str(magic_bonus_raw).strip() != "":
        try:
            magic_bonus = int(magic_bonus_raw)
        except (ValueError, TypeError):
            magic_bonus = 0
    else:
        name_match = re.search(r"\+([1-9])\b", weapon.get("name", ""))
        magic_bonus = int(name_match.group(1)) if name_match else 0

    # Fighting styles & proficiency
    has_archery = False
    has_dueling = False
    if features_traits:
        for f in features_traits:
            f_name = (f if isinstance(f, str) else f.get("name", "")).lower()
            f_desc = ("" if isinstance(f, str) else f.get("description", "")).lower()
            if (
                "archery" in f_name
                or "+2 bonus to attack rolls you make with ranged weapons" in f_desc
            ):
                has_archery = True
            if "dueling" in f_name or "+2 bonus to damage rolls with that weapon" in f_desc:
                has_dueling = True

    archery_bonus = 2 if (has_archery and is_ranged) else 0
    dueling_bonus = 2 if (has_dueling and not is_ranged) else 0

    is_proficient = weapon.get("proficient", True)
    prof_val = proficiency_bonus if is_proficient else 0

    misc_atk = int(weapon.get("misc_attack_bonus", 0) or 0)
    misc_dmg = int(weapon.get("misc_damage_bonus", 0) or 0)

    attack_bonus = mod + prof_val + magic_bonus + archery_bonus + misc_atk
    weapon["attack_bonus"] = f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)

    damage_raw = weapon.get("damage")
    if not damage_raw and weapon.get("damage_dice"):
        damage_raw = rebuild_damage_formula(weapon.get("damage_dice"), weapon.get("damage_bonus"))
    if not damage_raw:
        if "weapon_data" not in locals() or not weapon_data:
            from backend.repositories.rules_repository import RulesRepository

            repo = RulesRepository()
            all_weapons = _merge_homebrew_weapons(repo.get_all_weapons(), homebrew_content)
            name = weapon.get("name", "").lower()
            weapon_data = get_base_weapon(name, all_weapons)
        if weapon_data and weapon_data.get("damage"):
            damage_raw = weapon_data.get("damage")
    if not damage_raw:
        damage_raw = "1d4"
    dice_match = re.match(r"^\s*(\d+d\d+)", damage_raw or "", re.I)
    if dice_match:
        dice_part = dice_match.group(1)
        type_match = re.search(r"([a-zA-Z][a-zA-Z\s]*)$", damage_raw)
        dmg_type = type_match.group(1).strip() if type_match else ""

        total_dmg_mod = mod + magic_bonus + dueling_bonus + misc_dmg
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
    homebrew_content: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Synchronizes all derived character stats."""
    from backend.repositories.rules_repository import RulesRepository

    char_data = copy.deepcopy(char_data)
    repo = RulesRepository()

    is_initial_sync = char_data.get("base_stats") is None
    has_explicit_stats = "stats" in char_data and char_data["stats"] is not None
    stats_raw = char_data.get("stats", {})
    if hasattr(stats_raw, "model_dump"):
        input_stats = stats_raw.model_dump()
    elif isinstance(stats_raw, dict):
        input_stats = dict(stats_raw)
    else:
        input_stats = {
            "STR": getattr(stats_raw, "STR", 10),
            "DEX": getattr(stats_raw, "DEX", 10),
            "CON": getattr(stats_raw, "CON", 10),
            "INT": getattr(stats_raw, "INT", 10),
            "WIS": getattr(stats_raw, "WIS", 10),
            "CHA": getattr(stats_raw, "CHA", 10),
        }

    base_stats_raw = char_data.get("base_stats")
    if base_stats_raw is None:
        base_stats = dict(input_stats)
    else:
        if hasattr(base_stats_raw, "model_dump"):
            base_stats = base_stats_raw.model_dump()
        elif isinstance(base_stats_raw, dict):
            base_stats = dict(base_stats_raw)
        else:
            base_stats = {
                "STR": getattr(base_stats_raw, "STR", 10),
                "DEX": getattr(base_stats_raw, "DEX", 10),
                "CON": getattr(base_stats_raw, "CON", 10),
                "INT": getattr(base_stats_raw, "INT", 10),
                "WIS": getattr(base_stats_raw, "WIS", 10),
                "CHA": getattr(base_stats_raw, "CHA", 10),
            }
        prev_equip_bonuses = char_data.get("equip_stat_bonuses") or {}
        if has_explicit_stats:
            for k in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
                prev_bonus = int(prev_equip_bonuses.get(k, 0))
                expected_stat = base_stats.get(k, 10) + prev_bonus
                if k in input_stats and input_stats[k] != expected_stat:
                    base_stats[k] = input_stats[k] - prev_bonus

    char_data["base_stats"] = dict(base_stats)
    stats = dict(base_stats)
    char_data["stats"] = stats

    if "saving_throw_values" not in char_data or char_data["saving_throw_values"] is None:
        char_data["saving_throw_values"] = {}

    classes = char_data.get("classes", [])
    if not classes:
        # Pydantic models dump lists of ClassEntry to dicts, but just in case
        resolved_class = char_data.get("char_class") or char_data.get("class_name") or "Fighter"
        classes = [
            {
                "class_name": resolved_class,
                "level": char_data.get("char_level", 1),
                "subclass": char_data.get("subclass"),
            }
        ]
    else:
        # Convert pydantic ClassEntry to dict if it's not already
        classes = [c.model_dump() if hasattr(c, "model_dump") else c for c in classes]

    level = sum(c.get("level", 1) for c in classes)
    char_data["char_level"] = level

    edition = char_data.get("dnd_edition", "2014 Edition")
    char_class = classes[0].get("class_name", "Fighter")
    subclass = classes[0].get("subclass")

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
        entry = None
        if isinstance(ft, str):
            entry = {"name": ft, "description": "Imported feature"}
        elif hasattr(ft, "model_dump"):
            entry = ft.model_dump()
        elif isinstance(ft, dict):
            entry = dict(ft)

        if not entry:
            continue

        name_lower = str(entry.get("name") or "").strip().lower()
        desc_lower = str(entry.get("description") or "").strip().lower()

        # Discard invalid level-up metadata choices captured as traits
        if (
            name_lower in ("roll", "average", "manual")
            or "selected for level_up_class" in desc_lower
            or "selected for hp_method" in desc_lower
        ):
            continue

        normalized_ft.append(entry)
    char_data["features_traits"] = normalized_ft

    is_2024 = "2024" in str(edition) or "2024" in str(char_data.get("dnd_edition", ""))
    if is_2024:
        # Filter out legacy 2014 background combat/roleplay traits early
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
                if not (isinstance(f, dict) and (f.get("name") or "").lower() in legacy_bg_features)
            ]

        # Inject 2024 Background Origin Feat early so Tough (+2 HP/lvl) and Alert (+PB Init) apply during HP/Init calculation
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
            "custom": {
                "name": "Origin Feat: Skilled",
                "description": "2024 Origin Feat: Gain proficiency in 3 skills of your choice.",
            },
        }

        has_origin_feat = any(
            "origin feat" in f.get("name", "").lower()
            or "alert" in f.get("name", "").lower()
            or "savage attacker" in f.get("name", "").lower()
            or "skilled" in f.get("name", "").lower()
            or "tough" in f.get("name", "").lower()
            or "magic initiate" in f.get("name", "").lower()
            or "tavern brawler" in f.get("name", "").lower()
            or "musician" in f.get("name", "").lower()
            for f in char_data.get("features_traits", [])
            if isinstance(f, dict)
        )
        if not has_origin_feat:
            origin_info = origin_feat_map.get(bg, origin_feat_map["custom"])
            char_data.setdefault("features_traits", []).append(origin_info)

    # Pre-compute merged items list ONCE (not per equipment item)
    all_items = _merge_homebrew_items(repo.get_all_items(), homebrew_content)

    equip_hp_bonus = 0
    equip_speed_bonus = 0
    equip_init_bonus = 0
    equip_atk_bonus = 0
    equip_dmg_bonus = 0
    equip_save_bonus = 0
    equip_save_bonuses = {}

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
                equip_hp_bonus += bonus_val
            elif attr_key in ["SPD", "SPEED"]:
                equip_speed_bonus += bonus_val
            elif attr_key in ["INIT", "INITIATIVE"]:
                equip_init_bonus += bonus_val
            elif attr_key in ["ATK", "HIT", "ATTACK"]:
                equip_atk_bonus += bonus_val
            elif attr_key in ["DMG", "DAMAGE"]:
                equip_dmg_bonus += bonus_val
            elif attr_key in ["SAVES", "SAVE"]:
                equip_save_bonus += bonus_val
            elif attr_key.endswith("_SAVE"):
                stat_save = attr_key.split("_")[0]
                if stat_save in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
                    equip_save_bonuses[stat_save] = equip_save_bonuses.get(stat_save, 0) + bonus_val

        item_name = equip.get("name", "").lower()
        item_data = next((i for i in all_items if i["name"].lower() == item_name), None)

        if item_data and "stat_set" in item_data:
            for stat, val in item_data["stat_set"].items():
                stats[stat] = max(stats.get(stat, 10), val)
        if item_data and "stat_bonus" in item_data:
            for stat, val in item_data["stat_bonus"].items():
                stats[stat] = stats.get(stat, 10) + val

    char_data["equip_stat_bonuses"] = {
        k: stats.get(k, 10) - base_stats.get(k, 10)
        for k in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    }

    base_speed = char_data.get("base_speed")
    if base_speed is None:
        base_speed = char_data.get("speed", 30)
        char_data["base_speed"] = base_speed
    char_data["speed"] = base_speed + equip_speed_bonus
    char_data["global_attack_bonus"] = equip_atk_bonus
    char_data["global_damage_bonus"] = equip_dmg_bonus
    char_data["initiative_bonus"] = equip_init_bonus

    con_score = stats.get("CON", 10)
    dex_score = stats.get("DEX", 10)
    wis_score = stats.get("WIS", 10)

    prof_bonus = calculate_proficiency_bonus(level, class_data)
    char_data["proficiency_bonus"] = prof_bonus

    if not char_data.get("saving_throws"):
        saving_throws = []
        if class_data:
            sp = class_data.get("starting_proficiencies", {})
            raw_saves = sp.get("saving_throws", [])
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
                    saving_throws.append(abbr_map[s_clean])

        if saving_throws:
            char_data["saving_throws"] = saving_throws
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

    hit_dice_list = []
    for cls in classes:
        cname = cls.get("class_name", "Fighter")
        c_level = cls.get("level", 1)
        hd_size = get_hit_die_for_class(cname, edition)
        if cname == char_class and class_data and "hit_die" in class_data:
            raw_die = class_data["hit_die"]
            hd_size = raw_die[1:] if raw_die.startswith("1d") else raw_die
        if hd_size.startswith("d"):
            hd_size = hd_size[1:]
        hit_dice_list.append(f"{c_level}d{hd_size}")

    hd_counts = {}
    for hd in hit_dice_list:
        parts = hd.split("d")
        if len(parts) == 2:
            hd_counts[parts[1]] = hd_counts.get(parts[1], 0) + int(parts[0])

    char_data["hit_dice"] = ", ".join(
        f"{count}d{size}"
        for size, count in sorted(hd_counts.items(), key=lambda x: int(x[0]), reverse=True)
    )

    hp_bonus_per_level = 0
    features = char_data.get("features_traits", [])

    feat_library = _merge_homebrew_feats(repo.get_all_feats(edition), homebrew_content)
    feat_lookup = {f["name"].lower(): f for f in feat_library} if feat_library else {}

    import re

    for f in features:
        if not isinstance(f, dict):
            continue
        f_name = f.get("name", "")
        f_desc = f.get("description", "")
        full_text = f"{f_name} {f_desc}".lower()

        if "dwarven toughness" in full_text:
            hp_bonus_per_level += 1
            continue

        clean_name = f_name.lower().replace("origin feat: ", "").replace("feat: ", "").strip()
        if not clean_name:
            continue

        feat_data = feat_lookup.get(clean_name)
        if not feat_data:
            for k, v in feat_lookup.items():
                if k and re.search(rf"\b{re.escape(k)}\b", clean_name):
                    feat_data = v
                    break
        if feat_data and feat_data.get("hp_bonus_per_level", 0) > 0:
            hp_bonus_per_level += feat_data["hp_bonus_per_level"]

    existing_hp = char_data.get("hp_max")
    current_con_mod = get_modifier(con_score)
    con_mod_applied = char_data.get("con_mod_applied")
    if con_mod_applied is None:
        base_con = (
            base_stats_raw.get("CON", con_score) if isinstance(base_stats_raw, dict) else con_score
        )
        con_mod_applied = get_modifier(base_con)

    feat_hp_bonus = hp_bonus_per_level * level
    prev_feat_hp = char_data.get("feat_hp_bonus", 0)
    prev_equip_hp = char_data.get("equip_hp_bonus", 0)

    con_delta = 0
    if existing_hp is not None and existing_hp > 0:
        base_existing_hp = existing_hp - prev_feat_hp - prev_equip_hp
        if con_mod_applied is not None and con_mod_applied != current_con_mod:
            con_delta = current_con_mod - con_mod_applied
            base_existing_hp += con_delta * level
    else:
        base_existing_hp = None

    hit_die_size = hit_dice_list[0].split("d")[1] if hit_dice_list else "10"
    if not hit_die_size.startswith("d"):
        hit_die_size = "d" + hit_die_size

    base_hp = calculate_hp(
        hit_die_size, level, con_score, existing_hp=base_existing_hp, hit_dice_list=hit_dice_list
    )
    char_data["hp_max"] = base_hp + feat_hp_bonus + equip_hp_bonus
    char_data["feat_hp_bonus"] = feat_hp_bonus
    char_data["equip_hp_bonus"] = equip_hp_bonus
    char_data["con_mod_applied"] = current_con_mod

    feat_hp_delta = feat_hp_bonus - prev_feat_hp if existing_hp is not None else 0
    total_hp_delta = con_delta * level + feat_hp_delta
    if total_hp_delta != 0 and char_data.get("hp_current") is not None:
        char_data["hp_current"] = max(
            0, min(char_data["hp_max"], char_data["hp_current"] + total_hp_delta)
        )

    char_data["armor_class"], char_data["ac_breakdown"] = calculate_ac(
        dex_score,
        char_data.get("equipment", []),
        char_data.get("features_traits", []),
        wis_score=wis_score,
        con_score=con_score,
        homebrew_content=homebrew_content,
        return_breakdown=True,
    )

    # Skill Proficiencies Synchronization: Ensure skill_proficiencies contains Perception if Passive Perception or Perception skill has proficiency bonus on initial import/forge
    skill_profs = list(char_data.get("skill_proficiencies", []))
    wis_mod = get_modifier(wis_score)
    pass_perc = char_data.get("passive_perception")

    if (
        is_initial_sync
        and pass_perc is not None
        and pass_perc >= 10 + wis_mod + prof_bonus
        and "Perception" not in skill_profs
    ):
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
    if equip_save_bonus > 0 or equip_save_bonuses:
        for s in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
            bonus_to_add = equip_save_bonus + equip_save_bonuses.get(s, 0)
            if bonus_to_add:
                char_data["saving_throw_values"][s] = (
                    char_data["saving_throw_values"].get(s, 0) + bonus_to_add
                )

    init_bonus = 0
    for f in features:
        if not isinstance(f, dict):
            continue
        feat_name = (
            f.get("name", "").lower().replace("origin feat: ", "").replace("feat: ", "").strip()
        )
        if not feat_name:
            continue
        feat_data = feat_lookup.get(feat_name)
        if not feat_data:
            for k, v in feat_lookup.items():
                if k and re.search(rf"\b{re.escape(k)}\b", feat_name):
                    feat_data = v
                    break
        if feat_data:
            init_bonus += feat_data.get("initiative_bonus", 0)
            if feat_data.get("initiative_proficiency", False):
                init_bonus += prof_bonus

    char_data["initiative_modifier"] = (
        get_modifier(dex_score) + init_bonus + char_data.get("initiative_bonus", 0)
    )

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

        updated_weapons.append(
            calculate_weapon_stats(
                w_dict,
                stats,
                prof_bonus,
                homebrew_content,
                features_traits=char_data.get("features_traits", []),
            )
        )

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
            new_w = calculate_weapon_stats(
                new_w,
                stats,
                prof_bonus,
                homebrew_content,
                features_traits=char_data.get("features_traits", []),
            )
            updated_weapons.append(new_w)

    char_data["weapons"] = updated_weapons

    # Infer & Calculate Spellcasting Stats (DC & Attack Bonus)
    spell_ability = char_data.get("spell_ability")
    if not spell_ability or spell_ability == "None":
        if class_data and "spellcasting_ability" in class_data:
            spell_ability = class_data.get("spellcasting_ability")
        else:
            class_lower = (char_class or "").lower()
            subclass_lower = (char_data.get("subclass") or "").lower()
            feats_str = str(char_data.get("features_traits", [])).lower()
            standard_spell_abilities = {
                "wizard": "INT",
                "artificer": "INT",
                "cleric": "WIS",
                "druid": "WIS",
                "ranger": "WIS",
                "paladin": "CHA",
                "sorcerer": "CHA",
                "warlock": "CHA",
                "bard": "CHA",
            }
            if class_lower in standard_spell_abilities:
                spell_ability = standard_spell_abilities[class_lower]
            elif (
                "eldritch knight" in subclass_lower
                or "arcane trickster" in subclass_lower
                or "eldritch knight" in feats_str
                or "arcane trickster" in feats_str
                or (
                    class_lower == "fighter"
                    and (char_data.get("spell_slots") or char_data.get("spells"))
                )
            ):
                spell_ability = "INT"
            elif (
                char_data.get("spells")
                or char_data.get("prepared_spells")
                or char_data.get("spell_slots")
            ):
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
    if not subclass and char_class.lower() == "fighter" and char_data.get("spells"):
        subclass = "Eldritch Knight"
        char_data["subclass"] = subclass

    for cls in classes:
        cname = cls.get("class_name")
        cls_data = repo.get_class_progression(cname, edition)
        if cls_data and "caster_type" in cls_data:
            cls["caster_type"] = cls_data.get("caster_type")

    max_slots = calculate_max_spell_slots(
        char_class, level, subclass=subclass, caster_type=None, classes=classes, edition=edition
    )

    # Rebuild spell_slots cleanly according to class/level max slots rules
    new_spell_slots = {}
    for slot_lvl, max_val in max_slots.items():
        existing = (char_data.get("spell_slots") or {}).get(slot_lvl)
        used_val = 0
        if isinstance(existing, dict):
            used_val = min(existing.get("used", 0), max_val)
        elif isinstance(existing, int) and existing <= max_val:
            used_val = existing
        new_spell_slots[slot_lvl] = {"max": max_val, "used": used_val}
    char_data["spell_slots"] = new_spell_slots

    # Enforce Spell Level Caps (Stops AI from hallucinating spells higher than allowed)
    spells_dict = char_data.get("spells")
    if isinstance(spells_dict, dict):
        max_spell_level = 0
        for i in range(1, 10):
            if new_spell_slots.get(f"level_{i}", {}).get("max", 0) > 0:
                max_spell_level = i
        # Dynamically determine if the class progression grants high-level spells beyond basic slots (e.g., Mystic Arcanum)
        if class_data and "progression" in class_data:
            import re

            for lvl_idx in range(1, level + 1):
                lvl_data = class_data["progression"].get(str(lvl_idx), {})
                for feature in lvl_data.get("features", []):
                    f_name = feature.get("name", "")
                    # Look for explicit spell level grants in feature names (e.g. "Mystic Arcanum (6th level)")
                    match = re.search(r"\((\d)(?:st|nd|rd|th)\s+level\)", f_name, re.IGNORECASE)
                    if match:
                        max_spell_level = max(max_spell_level, int(match.group(1)))

        # Allow innate/racial spells (up to level 3) for characters with few/no slots
        max_spell_level = max(max_spell_level, min(3, math.ceil(level / 2)))

        for i in range(max_spell_level + 1, 10):
            lvl_key = f"level_{i}"
            if spells_dict.get(lvl_key):
                logger.info(
                    f"Removing hallucinated {lvl_key} spells (max allowed for this build is {max_spell_level})"
                )
                spells_dict[lvl_key] = []

        # Update prepared_spells as well to remove spells we just deleted
        valid_spell_names = set(spells_dict.get("cantrips", []))
        for i in range(1, max_spell_level + 1):
            valid_spell_names.update(spells_dict.get(f"level_{i}", []))

        if "prepared_spells" in char_data:
            char_data["prepared_spells"] = [
                ps for ps in char_data["prepared_spells"] if ps in valid_spell_names
            ]

    rogue_level = 0
    for cls in classes:
        c_dict = (
            cls
            if isinstance(cls, dict)
            else (cls.model_dump() if hasattr(cls, "model_dump") else {})
        )
        if (c_dict.get("class_name") or "").lower() == "rogue":
            rogue_level += c_dict.get("level", 1)

    if rogue_level == 0 and (char_class or "").lower() == "rogue":
        rogue_level = level

    if rogue_level > 0:
        sneak_attack_dice = (rogue_level + 1) // 2
        sneak_attack_str = f"{sneak_attack_dice}d6"
        for ft in char_data.get("features_traits", []):
            if isinstance(ft, dict) and ft.get("name") == "Sneak Attack":
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
    # 2024 Edition Rules (5.5e) Enhancements: Masteries, Fighter Features, Spell Cleanup
    # ----------------------------------------------------
    if is_2024:
        # A. Weapon Masteries (Fighter Lvl 1-3 = 3, Lvl 4+ = 4 masteries)
        martial_classes = ["fighter", "barbarian", "paladin", "ranger", "rogue"]
        if (char_class or "").lower() in martial_classes:
            c_low = (char_class or "").lower()
            if c_low == "fighter":
                target_masteries_count = (
                    6 if level >= 16 else (5 if level >= 10 else (4 if level >= 4 else 3))
                )
            elif c_low == "barbarian":
                target_masteries_count = 4 if level >= 10 else (3 if level >= 4 else 2)
            else:
                # Paladin, Ranger, Rogue strictly get 2 weapon masteries
                target_masteries_count = 2
            existing_masteries = list(char_data.get("weapon_masteries") or [])
            all_weapons = _merge_homebrew_weapons(repo.get_all_weapons(), homebrew_content)

            # Prioritize masteries matching equipped weapons
            equipped_weapon_masteries = []
            for w in char_data.get("weapons", []):
                if isinstance(w, dict):
                    w_name = (w.get("name") or "").lower()
                    w_data = get_base_weapon(w_name, all_weapons)
                    if w_data and "mastery" in w_data:
                        m_string = f"{w_data['mastery']} ({w_data['name']})"
                        if m_string not in equipped_weapon_masteries:
                            equipped_weapon_masteries.append(m_string)

            for m in equipped_weapon_masteries:
                if m not in existing_masteries:
                    existing_masteries.insert(0, m)

            # Popular defaults to ensure we have a good pool of different masteries
            default_weapon_names = [
                "Longsword",
                "Light Crossbow",
                "Greatsword",
                "Dagger",
                "Warhammer",
                "Shortsword",
                "Pike",
                "Greataxe",
            ]
            for def_name in default_weapon_names:
                w_data = next(
                    (x for x in all_weapons if x.get("name", "").lower() == def_name.lower()), None
                )
                if w_data and "mastery" in w_data:
                    m_string = f"{w_data['mastery']} ({w_data['name']})"
                    if len(existing_masteries) >= target_masteries_count:
                        break
                    if m_string not in existing_masteries:
                        existing_masteries.append(m_string)

            char_data["weapon_masteries"] = existing_masteries[:target_masteries_count]

            for w in char_data.get("weapons", []):
                if isinstance(w, dict):
                    w_name = (w.get("name") or "").lower()
                    props = w.get("properties") or ""
                    if "mastery" not in props.lower():
                        w_data = get_base_weapon(w_name, all_weapons)
                        if w_data and "mastery" in w_data:
                            w["properties"] = f"{props}, Mastery: {w_data['mastery']}".strip(", ")

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

        # D. Clean up miscategorized spells (move cantrips out of leveled slots)
        spells_dict = char_data.get("spells")
        if isinstance(spells_dict, dict):
            cantrips = spells_dict.get("cantrips", [])
            if not isinstance(cantrips, list):
                cantrips = []

            undeniable_cantrips = {
                "booming blade",
                "green-flame blade",
                "eldritch blast",
                "fire bolt",
                "mage hand",
                "prestidigitation",
                "minor illusion",
                "ray of frost",
                "shocking grasp",
            }
            edition_val = char_data.get("dnd_edition") or "2014 Edition"
            known_cantrips_lower = (
                set(_get_known_cantrips_for_edition(edition_val)) | undeniable_cantrips
            )

            for lvl in [f"level_{i}" for i in range(1, 10)]:
                lvl_spells = spells_dict.get(lvl, [])
                if isinstance(lvl_spells, list):
                    new_lvl_spells = []
                    for spell in lvl_spells:
                        spell_clean = str(spell).strip().lower()
                        is_cantrip = spell_clean in known_cantrips_lower
                        if not is_cantrip:
                            for uc in undeniable_cantrips:
                                if uc in spell_clean:
                                    is_cantrip = True
                                    break

                        if is_cantrip:
                            if spell not in cantrips:
                                cantrips.append(spell)
                        else:
                            new_lvl_spells.append(spell)
                    spells_dict[lvl] = new_lvl_spells

            spells_dict["cantrips"] = list(dict.fromkeys(cantrips))  # remove duplicates

        # E. (Removed) Eldritch Knight / Arcane Trickster Cantrip Limit
        # This was flawed as it did not account for racial cantrips (e.g. High Elf) or feats (Magic Initiate)

    return char_data
