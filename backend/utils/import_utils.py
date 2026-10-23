import html
import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("DnDAssistant.ImportUtils")


class FoundryImportError(ValueError):
    """Raised when Foundry VTT JSON is malformed or invalid."""

    pass


def _strip_html(raw_html: str) -> str:
    """Strip basic HTML tags and unescape HTML entities."""
    if not raw_html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", raw_html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


def import_vtt_character(vtt_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parses a Foundry VTT (dnd5e) exported JSON into our internal character schema.
    Supports Foundry dnd5e system v2 and v3 schemas.
    Returns (character_dict, warnings).
    """
    if not isinstance(vtt_data, dict):
        raise FoundryImportError("Invalid Foundry export: root must be a JSON object")

    system = vtt_data.get("system")
    if system is None:
        # In very old or minimal exports, system might be missing
        if "name" not in vtt_data:
            raise FoundryImportError(
                "Invalid Foundry export: neither 'system' nor 'name' found in JSON."
            )
        system = {}

    warnings: List[str] = []

    # Check actor type
    actor_type = vtt_data.get("type")
    if actor_type and actor_type not in ("character", "npc"):
        warnings.append(
            f"Actor type '{actor_type}' is not a standard character; parsed with best effort."
        )

    # 1. Basic Info & Details
    char_name = vtt_data.get("name") or "Imported Hero"
    details = system.get("details", {})

    # Alignment
    raw_alignment = details.get("alignment")
    alignment = str(raw_alignment).strip() if raw_alignment else "Neutral"

    # Biography
    bio_raw = details.get("biography", {})
    if isinstance(bio_raw, dict):
        backstory = _strip_html(bio_raw.get("value", ""))
    else:
        backstory = _strip_html(str(bio_raw))

    # Race & Background (Support v2 strings and v3 objects/items)
    race = "Unknown"
    raw_race = details.get("race")
    if isinstance(raw_race, dict):
        race = raw_race.get("name", "Unknown")
    elif isinstance(raw_race, str) and raw_race.strip():
        race = raw_race.strip()

    background = "Unknown"
    raw_bg = details.get("background")
    if isinstance(raw_bg, dict):
        background = raw_bg.get("name", "Unknown")
    elif isinstance(raw_bg, str) and raw_bg.strip():
        background = raw_bg.strip()

    # 2. Abilities -> Stats & Saving Throws
    abilities = system.get("abilities", {})
    stats: Dict[str, int] = {
        "STR": 10,
        "DEX": 10,
        "CON": 10,
        "INT": 10,
        "WIS": 10,
        "CHA": 10,
    }
    saving_throws: List[str] = []

    stat_keys = {
        "str": "STR",
        "dex": "DEX",
        "con": "CON",
        "int": "INT",
        "wis": "WIS",
        "cha": "CHA",
    }
    for vtt_key, internal_key in stat_keys.items():
        ab_data = abilities.get(vtt_key, {})
        if isinstance(ab_data, dict):
            val = ab_data.get("value")
            if val is not None:
                try:
                    stats[internal_key] = int(val)
                except (ValueError, TypeError):
                    stats[internal_key] = 10
            # Saving throw proficiency
            prof = ab_data.get("proficient", 0)
            if prof and int(prof) > 0:
                saving_throws.append(internal_key)
        elif isinstance(ab_data, (int, float)):
            stats[internal_key] = int(ab_data)

    # 3. Attributes (HP, AC, Speed, Initiative, Death Saves)
    attrs = system.get("attributes", {})
    hp_data = attrs.get("hp", {})
    hp_max = hp_data.get("max", 10) if isinstance(hp_data, dict) else 10
    hp_current = hp_data.get("value", hp_max) if isinstance(hp_data, dict) else (hp_max or 10)
    temp_hp = hp_data.get("temp", 0) if isinstance(hp_data, dict) else 0

    ac_data = attrs.get("ac", {})
    if isinstance(ac_data, dict):
        armor_class = ac_data.get("value", 10)
    elif isinstance(ac_data, (int, float)):
        armor_class = int(ac_data)
    else:
        armor_class = 10

    mov_data = attrs.get("movement", {})
    if isinstance(mov_data, dict):
        speed = mov_data.get("walk", 30)
    elif isinstance(mov_data, (int, float)):
        speed = int(mov_data)
    else:
        speed = 30

    prof_bonus = attrs.get("prof", 2)
    init_data = attrs.get("init", {})
    if isinstance(init_data, dict):
        init_bonus = init_data.get("bonus", 0)
    elif isinstance(init_data, (int, float)):
        init_bonus = int(init_data)
    else:
        init_bonus = 0

    death_data = attrs.get("death", {})
    death_saves = {
        "successes": death_data.get("success", 0) if isinstance(death_data, dict) else 0,
        "failures": death_data.get("failure", 0) if isinstance(death_data, dict) else 0,
    }

    # 4. Skills
    vtt_skill_map = {
        "acr": "Acrobatics",
        "ani": "Animal Handling",
        "arc": "Arcana",
        "ath": "Athletics",
        "dec": "Deception",
        "his": "History",
        "ins": "Insight",
        "itm": "Intimidation",
        "inv": "Investigation",
        "med": "Medicine",
        "nat": "Nature",
        "prc": "Perception",
        "prf": "Performance",
        "per": "Persuasion",
        "rel": "Religion",
        "slt": "Sleight of Hand",
        "ste": "Stealth",
        "sur": "Survival",
    }

    vtt_skills = system.get("skills", {})
    skill_profs: List[str] = []
    skill_exp: List[str] = []

    for code, data in vtt_skills.items():
        skill_name = vtt_skill_map.get(code)
        if not skill_name:
            continue
        val = 0
        if isinstance(data, dict):
            val = data.get("value", 0)
        elif isinstance(data, (int, float)):
            val = data
        if val == 1:
            skill_profs.append(skill_name)
        elif val >= 2:
            skill_exp.append(skill_name)

    # 5. Currency
    curr = system.get("currency", {})
    currency = {
        "cp": int(curr.get("cp", 0)),
        "sp": int(curr.get("sp", 0)),
        "ep": int(curr.get("ep", 0)),
        "gp": int(curr.get("gp", 0)),
        "pp": int(curr.get("pp", 0)),
    }

    # 6. Items processing: Classes, Subclasses, Race, Background, Weapons, Equipment, Features, Spells
    items = vtt_data.get("items", [])
    classes: List[Dict[str, Any]] = []
    subclasses: Dict[str, str] = {}  # classIdentifier/class_name -> subclass name
    hit_dice_parts: List[str] = []
    weapons: List[Dict[str, Any]] = []
    equipment: List[Dict[str, Any]] = []
    features_traits: List[Dict[str, Any]] = []
    spells: Dict[str, List[Any]] = {"cantrips": []}

    # First pass: collect subclasses and items
    for item in items:
        itype = item.get("type")
        iname = item.get("name", "")
        isys = item.get("system", {})

        if itype == "subclass":
            class_id = isys.get("classIdentifier", "")
            if class_id:
                subclasses[class_id.lower()] = iname
            subclasses[iname.lower()] = iname
        elif itype == "race" and race == "Unknown":
            race = iname
        elif itype == "background" and background == "Unknown":
            background = iname

    # Second pass: classes, equipment, weapons, features, spells
    for item in items:
        itype = item.get("type")
        iname = item.get("name", "")
        isys = item.get("system", {})

        if itype == "class":
            c_name = iname
            c_level = isys.get("levels") or isys.get("level") or 1
            try:
                c_level = int(c_level)
            except (ValueError, TypeError):
                c_level = 1

            c_subclass = isys.get("subclass")
            if not c_subclass:
                # check identifier
                cid = isys.get("identifier", c_name).lower()
                c_subclass = subclasses.get(cid) or subclasses.get(c_name.lower())

            hd = isys.get("hitDice")
            if hd:
                hit_dice_parts.append(f"{c_level}{hd}")

            classes.append(
                {
                    "class_name": c_name,
                    "level": c_level,
                    "subclass": c_subclass if c_subclass else None,
                }
            )

        elif itype == "weapon":
            # Extract damage
            dmg_parts = isys.get("damage", {}).get("parts", [])
            damage_str = ""
            if dmg_parts and isinstance(dmg_parts, list) and len(dmg_parts) > 0:
                first_part = dmg_parts[0]
                if isinstance(first_part, list) and len(first_part) >= 1:
                    formula = first_part[0]
                    dmg_type = first_part[1] if len(first_part) > 1 else ""
                    damage_str = f"{formula} {dmg_type}".strip()

            raw_props = isys.get("properties", [])
            props: List[str] = []
            if isinstance(raw_props, list):
                props = [str(p) for p in raw_props]
            elif isinstance(raw_props, dict):
                props = [k for k, v in raw_props.items() if v]

            weapons.append(
                {
                    "name": iname,
                    "damage": damage_str,
                    "attack_bonus": "+0",
                    "damage_dice": "",
                    "damage_bonus": "+0",
                    "properties": ", ".join(props),
                }
            )

        elif itype in ("equipment", "loot", "consumable", "tool", "container"):
            equipment.append(
                {
                    "name": iname,
                    "quantity": isys.get("quantity", 1),
                    "equipped": isys.get("equipped", False),
                    "attuned": isys.get("attuned", False),
                    "description": _strip_html(isys.get("description", {}).get("value", "")),
                }
            )

        elif itype in ("feat", "feature"):
            features_traits.append(
                {
                    "name": iname,
                    "description": _strip_html(isys.get("description", {}).get("value", "")),
                    "source": "Foundry Import",
                }
            )

        elif itype == "spell":
            lvl = isys.get("level", 0)
            try:
                lvl = int(lvl)
            except (ValueError, TypeError):
                lvl = 0
            lvl_key = "cantrips" if lvl == 0 else f"level_{lvl}"
            if lvl_key not in spells:
                spells[lvl_key] = []
            spells[lvl_key].append(iname)

    # Resolve Character Classes & Level
    if not classes:
        # Fallback to system.details
        fallback_class = details.get("originalClass") or details.get("class")
        fallback_level = details.get("level", 1)
        try:
            fallback_level = int(fallback_level)
        except (ValueError, TypeError):
            fallback_level = 1
        classes.append(
            {
                "class_name": str(fallback_class) if fallback_class else "Fighter",
                "level": fallback_level,
                "subclass": None,
            }
        )
        warnings.append(
            "No class items found in Foundry export; defaulted class from character details."
        )

    char_level = sum(c["level"] for c in classes)
    char_class = " / ".join(f"{c['class_name']} {c['level']}" for c in classes)
    if len(classes) == 1:
        char_class = classes[0]["class_name"]

    hit_dice = " + ".join(hit_dice_parts) if hit_dice_parts else f"{char_level}d8"

    character_dict: Dict[str, Any] = {
        "char_name": char_name,
        "char_class": char_class,
        "char_level": char_level,
        "classes": classes,
        "race": race,
        "background": background,
        "alignment": alignment,
        "backstory": backstory,
        "base_stats": dict(stats),
        "stats": stats,
        "saving_throws": saving_throws,
        "skill_proficiencies": skill_profs,
        "skill_expertise": skill_exp,
        "armor_class": armor_class,
        "speed": speed,
        "proficiency_bonus": prof_bonus,
        "initiative_modifier": init_bonus,
        "hp_max": hp_max,
        "hp_current": hp_current,
        "temp_hp": temp_hp,
        "hit_dice": hit_dice,
        "death_saves": death_saves,
        "currency": currency,
        "weapons": weapons,
        "equipment": equipment,
        "features_traits": features_traits,
        "spells": spells,
    }

    return character_dict, warnings
