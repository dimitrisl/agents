import logging
import math
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.core.schemas import CharacterSchema, ClassEntry
from backend.services.stats_service import get_modifier, sync_character_stats

logger = logging.getLogger("DnDAssistant.CharacterImportService")

DDB_URL_REGEX = re.compile(r"(?:https?://)?(?:www\.)?dndbeyond\.com/characters/(\d+)")

DDB_STAT_MAP = {
    1: "STR",
    2: "DEX",
    3: "CON",
    4: "INT",
    5: "WIS",
    6: "CHA",
}

ALIGNMENT_MAP = {
    1: "Lawful Good",
    2: "Neutral Good",
    3: "Chaotic Good",
    4: "Lawful Neutral",
    5: "Neutral",
    6: "Chaotic Neutral",
    7: "Lawful Evil",
    8: "Neutral Evil",
    9: "Chaotic Evil",
}

SKILL_NAME_MAP = {
    "acrobatics": "Acrobatics",
    "animal-handling": "Animal Handling",
    "arcana": "Arcana",
    "athletics": "Athletics",
    "deception": "Deception",
    "history": "History",
    "insight": "Insight",
    "intimidation": "Intimidation",
    "investigation": "Investigation",
    "medicine": "Medicine",
    "nature": "Nature",
    "perception": "Perception",
    "performance": "Performance",
    "persuasion": "Persuasion",
    "religion": "Religion",
    "sleight-of-hand": "Sleight of Hand",
    "stealth": "Stealth",
    "survival": "Survival",
}


class DndBeyondImportError(ValueError):
    """Raised when D&D Beyond fetch or parse fails."""

    pass


class CharacterImportService:
    @staticmethod
    def extract_dndbeyond_character_id(url_or_id: str) -> str:
        """Extracts and validates character ID from a D&D Beyond URL or raw ID."""
        cleaned = url_or_id.strip()
        if cleaned.isdigit():
            return cleaned
        match = DDB_URL_REGEX.search(cleaned)
        if match:
            return match.group(1)
        raise DndBeyondImportError(
            f"Invalid D&D Beyond character URL or ID: '{url_or_id}'. "
            "Expected format: https://www.dndbeyond.com/characters/12345678 or numeric ID."
        )

    @classmethod
    async def fetch_dndbeyond_character(
        cls, url_or_id: str, timeout: float = 15.0
    ) -> Dict[str, Any]:
        """
        Fetches character JSON from D&D Beyond character service in an SSRF-safe manner.
        Only contacts character-service.dndbeyond.com with strict numeric character ID.
        """
        char_id = cls.extract_dndbeyond_character_id(url_or_id)
        api_url = f"https://character-service.dndbeyond.com/character/v5/character/{char_id}"

        headers = {
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            try:
                response = await client.get(api_url, headers=headers)
            except httpx.RequestError as exc:
                logger.error(f"D&D Beyond network error fetching {char_id}: {exc}")
                raise DndBeyondImportError(f"Network error contacting D&D Beyond: {exc}")

        if response.status_code == 404:
            raise DndBeyondImportError(
                "Character not found on D&D Beyond or character is set to Private. "
                "Please verify the ID and ensure character privacy is set to Public."
            )
        elif response.status_code == 403:
            raise DndBeyondImportError(
                "Access forbidden by D&D Beyond. The character is likely private. "
                "Please set the character visibility to Public on D&D Beyond and retry."
            )
        elif response.status_code == 429:
            raise DndBeyondImportError(
                "D&D Beyond rate limit reached. Please wait a few moments before retrying."
            )
        elif response.status_code != 200:
            raise DndBeyondImportError(
                f"D&D Beyond returned unexpected status HTTP {response.status_code}."
            )

        try:
            payload = response.json()
        except Exception as e:
            raise DndBeyondImportError(f"Failed to parse JSON response from D&D Beyond: {e}")

        if not isinstance(payload, dict) or not payload.get("success", True):
            msg = payload.get("message") if isinstance(payload, dict) else str(payload)
            raise DndBeyondImportError(f"D&D Beyond returned error: {msg}")

        return payload

    @classmethod
    def parse_dndbeyond_character(
        cls, ddb_payload: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Parses raw D&D Beyond payload (data wrapper or raw dict) into internal character schema.
        Returns (character_dict, warnings).
        """
        data = ddb_payload.get("data", ddb_payload)
        if not isinstance(data, dict):
            raise DndBeyondImportError("Invalid D&D Beyond data structure.")

        warnings: List[str] = []

        char_name = data.get("name") or "Imported Hero"
        gender = data.get("gender") or ""
        age = data.get("age") or ""
        hair = data.get("hair") or ""
        eyes = data.get("eyes") or ""
        skin = data.get("skin") or ""
        height = data.get("height") or ""
        weight = data.get("weight") or ""

        # Alignment
        align_id = data.get("alignmentId")
        alignment = ALIGNMENT_MAP.get(align_id, "Neutral")

        # Race
        race_data = data.get("race", {}) or {}
        race = race_data.get("fullName") or race_data.get("baseName") or "Unknown"

        # Background
        bg_data = data.get("background", {}) or {}
        bg_def = bg_data.get("definition", {}) or {}
        background = (
            bg_def.get("name") or bg_data.get("customBackground", {}).get("name") or "Unknown"
        )

        # Notes / traits
        traits = data.get("traits", {}) or {}
        notes = data.get("notes", {}) or {}
        personality_traits = traits.get("personalityTraits") or ""
        ideals = traits.get("ideals") or ""
        bonds = traits.get("bonds") or ""
        flaws = traits.get("flaws") or ""
        backstory = notes.get("backstory") or notes.get("personalPossessions") or ""

        # Classes
        raw_classes = data.get("classes", []) or []
        classes_list: List[Dict[str, Any]] = []
        hit_dice_parts: List[str] = []

        for c in raw_classes:
            c_def = c.get("definition", {}) or {}
            c_name = c_def.get("name", "Unknown Class")
            c_lvl = int(c.get("level", 1))
            subclass_def = c.get("subclassDefinition") or {}
            subclass_name = subclass_def.get("name") if subclass_def else None

            classes_list.append(
                {
                    "class_name": c_name,
                    "level": c_lvl,
                    "subclass": subclass_name,
                }
            )

            hd = c_def.get("hitDice", 8)
            hit_dice_parts.append(f"{c_lvl}d{hd}")

        if not classes_list:
            classes_list.append({"class_name": "Adventurer", "level": 1, "subclass": None})
            warnings.append("No classes found; assigned default Adventurer level 1.")

        char_level = sum(c["level"] for c in classes_list)
        char_class = " / ".join(f"{c['class_name']} {c['level']}" for c in classes_list)
        if len(classes_list) == 1:
            char_class = classes_list[0]["class_name"]

        hit_dice = " + ".join(hit_dice_parts) if hit_dice_parts else f"{char_level}d8"

        # Modifiers collection across all sources
        all_modifiers: List[Dict[str, Any]] = []
        mods_dict = data.get("modifiers", {}) or {}
        if isinstance(mods_dict, dict):
            for source_list in mods_dict.values():
                if isinstance(source_list, list):
                    all_modifiers.extend(source_list)

        # Stats calculation
        # Base stats
        base_stats_map: Dict[str, int] = {
            "STR": 10,
            "DEX": 10,
            "CON": 10,
            "INT": 10,
            "WIS": 10,
            "CHA": 10,
        }
        for s in data.get("stats", []) or []:
            stat_name = DDB_STAT_MAP.get(s.get("id"))
            if stat_name and s.get("value") is not None:
                base_stats_map[stat_name] = int(s.get("value"))

        # Bonus stats & overrides
        bonus_stats = {
            DDB_STAT_MAP.get(s.get("id")): s.get("value")
            for s in (data.get("bonusStats", []) or [])
            if s.get("id") in DDB_STAT_MAP and s.get("value") is not None
        }
        override_stats = {
            DDB_STAT_MAP.get(s.get("id")): s.get("value")
            for s in (data.get("overrideStats", []) or [])
            if s.get("id") in DDB_STAT_MAP and s.get("value") is not None
        }

        # Modifiers for ability scores
        stat_mods: Dict[str, int] = {k: 0 for k in base_stats_map}
        for m in all_modifiers:
            if m.get("type") == "bonus":
                sub_type = m.get("subType", "")
                for code, name in [
                    ("strength-score", "STR"),
                    ("dexterity-score", "DEX"),
                    ("constitution-score", "CON"),
                    ("intelligence-score", "INT"),
                    ("wisdom-score", "WIS"),
                    ("charisma-score", "CHA"),
                ]:
                    if sub_type == code:
                        val = m.get("value", 0) or m.get("fixedValue", 0)
                        if val is not None:
                            try:
                                stat_mods[name] += int(val)
                            except (ValueError, TypeError):
                                pass

        final_stats: Dict[str, int] = {}
        for stat_name in base_stats_map:
            if stat_name in override_stats and override_stats[stat_name] is not None:
                final_stats[stat_name] = int(override_stats[stat_name])
            else:
                base_v = base_stats_map[stat_name]
                bonus_v = int(bonus_stats.get(stat_name) or 0)
                mod_v = stat_mods.get(stat_name, 0)
                final_stats[stat_name] = base_v + bonus_v + mod_v

        # Saving throws & Skills proficiencies / expertise
        saving_throws: List[str] = []
        skill_proficiencies: List[str] = []
        skill_expertise: List[str] = []

        save_subtype_map = {
            "strength-saving-throws": "STR",
            "dexterity-saving-throws": "DEX",
            "constitution-saving-throws": "CON",
            "intelligence-saving-throws": "INT",
            "wisdom-saving-throws": "WIS",
            "charisma-saving-throws": "CHA",
        }

        for m in all_modifiers:
            m_type = m.get("type")
            sub_type = (m.get("subType") or "").lower()

            if m_type == "proficiency":
                if sub_type in save_subtype_map:
                    stat_code = save_subtype_map[sub_type]
                    if stat_code not in saving_throws:
                        saving_throws.append(stat_code)
                elif sub_type in SKILL_NAME_MAP:
                    sk_name = SKILL_NAME_MAP[sub_type]
                    if sk_name not in skill_proficiencies:
                        skill_proficiencies.append(sk_name)
            elif m_type in ("expertise", "half-proficiency"):
                if sub_type in SKILL_NAME_MAP:
                    sk_name = SKILL_NAME_MAP[sub_type]
                    if sk_name not in skill_expertise:
                        skill_expertise.append(sk_name)

        # Proficiency bonus
        prof_bonus = math.ceil(1 + (char_level / 4))

        # Speed
        speed = 30
        weight_speeds = (
            race_data.get("weightSpeeds", {}).get("normal", {})
            if isinstance(race_data, dict)
            else {}
        )
        if weight_speeds and weight_speeds.get("walk"):
            speed = int(weight_speeds.get("walk"))
        for m in all_modifiers:
            if m.get("type") == "set" and m.get("subType") == "innate-speed-walking":
                v = m.get("value") or m.get("fixedValue")
                if v:
                    speed = int(v)

        # HP calculation
        con_mod = get_modifier(final_stats["CON"])
        base_hp = int(data.get("baseHitPoints") or 0)
        bonus_hp = int(data.get("bonusHitPoints") or 0)
        removed_hp = int(data.get("removedHitPoints") or 0)
        temp_hp = int(data.get("temporaryHitPoints") or 0)

        # If baseHitPoints is populated, max HP is base_hp + bonus_hp + (con_mod * char_level)
        if base_hp > 0:
            hp_max = max(1, base_hp + bonus_hp + (con_mod * char_level))
        else:
            # Fallback estimation based on hit dice
            est_hd = 8
            if raw_classes:
                est_hd = raw_classes[0].get("definition", {}).get("hitDice", 8)
            first_lvl_hp = est_hd + con_mod
            other_lvl_hp = max(1, (est_hd // 2 + 1) + con_mod) * (char_level - 1)
            hp_max = max(1, first_lvl_hp + other_lvl_hp + bonus_hp)

        hp_current = max(0, hp_max - removed_hp)

        # Currency
        curr = data.get("currencies", {}) or {}
        currency = {
            "cp": int(curr.get("cp", 0)),
            "sp": int(curr.get("sp", 0)),
            "ep": int(curr.get("ep", 0)),
            "gp": int(curr.get("gp", 0)),
            "pp": int(curr.get("pp", 0)),
        }

        # Equipment & Weapons
        inventory = data.get("inventory", []) or []
        weapons: List[Dict[str, Any]] = []
        equipment: List[Dict[str, Any]] = []
        equipped_armor_ac: Optional[int] = None
        has_shield = False

        for item in inventory:
            idef = item.get("definition", {}) or {}
            iname = idef.get("name") or "Item"
            filter_type = (idef.get("filterType") or "").lower()
            is_equipped = bool(item.get("equipped", False))
            is_attuned = bool(item.get("isAttuned", False))

            if filter_type == "weapon":
                dmg_obj = idef.get("damage") or {}
                dmg_dice = dmg_obj.get("diceString") or ""
                dmg_type_name = (
                    (dmg_obj.get("damageType") or "")
                    if isinstance(dmg_obj.get("damageType"), str)
                    else ""
                )
                dmg_full = f"{dmg_dice} {dmg_type_name}".strip()

                raw_props = idef.get("properties") or []
                props_list = [
                    p.get("name") for p in raw_props if isinstance(p, dict) and p.get("name")
                ]

                weapons.append(
                    {
                        "name": iname,
                        "damage": dmg_full,
                        "attack_bonus": "+0",
                        "damage_dice": "",
                        "damage_bonus": "+0",
                        "properties": ", ".join(props_list),
                        "equipped": is_equipped,
                    }
                )
            else:
                armor_val = idef.get("armorClass")
                armor_type_id = idef.get("armorTypeId")  # 1=light, 2=medium, 3=heavy, 4=shield
                if is_equipped and armor_val is not None:
                    if armor_type_id == 4 or "shield" in iname.lower():
                        has_shield = True
                    else:
                        equipped_armor_ac = int(armor_val)

                equipment.append(
                    {
                        "name": iname,
                        "quantity": int(item.get("quantity", 1)),
                        "equipped": is_equipped,
                        "attuned": is_attuned,
                        "description": idef.get("description", "") or "",
                    }
                )

        # Armor class derivation
        dex_mod = get_modifier(final_stats["DEX"])
        if equipped_armor_ac is not None:
            # Base armor + dex (capped if medium, none if heavy)
            armor_class = equipped_armor_ac
        else:
            armor_class = 10 + dex_mod
        if has_shield:
            armor_class += 2

        # Features & Traits
        features_traits: List[Dict[str, Any]] = []

        # Racial traits
        for r_trait in race_data.get("racialTraits", []) or []:
            t_def = r_trait.get("definition", {}) or {}
            t_name = t_def.get("name")
            if t_name:
                features_traits.append(
                    {
                        "name": t_name,
                        "description": t_def.get("snippet") or t_def.get("description", ""),
                        "source": "Race",
                    }
                )

        # Class features
        for c in raw_classes:
            for feat in c.get("classFeatures", []) or []:
                f_def = feat.get("definition", {}) or {}
                f_name = f_def.get("name")
                if f_name:
                    features_traits.append(
                        {
                            "name": f_name,
                            "description": f_def.get("snippet") or f_def.get("description", ""),
                            "source": "Class",
                        }
                    )

        # Feats
        for f in data.get("feats", []) or []:
            f_def = f.get("definition", {}) or {}
            f_name = f_def.get("name")
            if f_name:
                features_traits.append(
                    {
                        "name": f_name,
                        "description": f_def.get("snippet") or f_def.get("description", ""),
                        "source": "Feat",
                    }
                )

        # Spells
        spells: Dict[str, List[Any]] = {"cantrips": []}
        all_raw_spells: List[Dict[str, Any]] = []

        for cs in data.get("classSpells", []) or []:
            all_raw_spells.extend(cs.get("spells", []) or [])

        raw_spells_dict = data.get("spells", {}) or {}
        if isinstance(raw_spells_dict, dict):
            for sp_list in raw_spells_dict.values():
                if isinstance(sp_list, list):
                    all_raw_spells.extend(sp_list)

        for sp in all_raw_spells:
            sdef = sp.get("definition", {}) or {}
            sname = sdef.get("name")
            if not sname:
                continue
            lvl = sdef.get("level", 0)
            lvl_key = "cantrips" if lvl == 0 else f"level_{lvl}"
            if lvl_key not in spells:
                spells[lvl_key] = []
            if sname not in spells[lvl_key]:
                spells[lvl_key].append(sname)

        character_dict: Dict[str, Any] = {
            "char_name": char_name,
            "char_class": char_class,
            "char_level": char_level,
            "classes": classes_list,
            "race": race,
            "background": background,
            "alignment": alignment,
            "gender": gender,
            "age": age,
            "hair": hair,
            "eyes": eyes,
            "skin": skin,
            "height": height,
            "weight": weight,
            "personality_traits": personality_traits,
            "ideals": ideals,
            "bonds": bonds,
            "flaws": flaws,
            "backstory": backstory,
            "stats": final_stats,
            "saving_throws": saving_throws,
            "skill_proficiencies": skill_proficiencies,
            "skill_expertise": skill_expertise,
            "armor_class": armor_class,
            "speed": speed,
            "proficiency_bonus": prof_bonus,
            "initiative_modifier": dex_mod,
            "hp_max": hp_max,
            "hp_current": hp_current,
            "temp_hp": temp_hp,
            "hit_dice": hit_dice,
            "currency": currency,
            "weapons": weapons,
            "equipment": equipment,
            "features_traits": features_traits,
            "spells": spells,
        }

        return character_dict, warnings

    @classmethod
    async def finalize_and_save_imported_character(
        cls,
        char_dict: Dict[str, Any],
        user_id: str,
        db: Any,
        sync_stats: bool = True,
    ) -> CharacterSchema:
        """
        Calculates weapon stats and class sync, validates against CharacterSchema,
        generates fresh char_id, and inserts into MongoDB.
        """
        # Assign fresh UUID
        new_char_id = str(uuid.uuid4())
        char_dict["char_id"] = new_char_id
        char_dict["owner_id"] = user_id
        char_dict["user_id"] = user_id

        # Normalize classes field to list of ClassEntry
        raw_classes = char_dict.get("classes", [])
        validated_classes: List[ClassEntry] = []
        for c in raw_classes:
            if isinstance(c, dict):
                validated_classes.append(
                    ClassEntry(
                        class_name=c.get("class_name", "Adventurer"),
                        level=int(c.get("level", 1)),
                        subclass=c.get("subclass"),
                    )
                )
            elif isinstance(c, ClassEntry):
                validated_classes.append(c)

        if not validated_classes:
            validated_classes.append(
                ClassEntry(
                    class_name=char_dict.get("char_class", "Adventurer").split()[0],
                    level=int(char_dict.get("char_level", 1)),
                    subclass=None,
                )
            )

        char_dict["classes"] = [c.model_dump() for c in validated_classes]

        # Sync character stats (weapon attack bonus, damage formula, spell DC, etc.)
        if sync_stats:
            char_dict = sync_character_stats(char_dict)

        # Validate with CharacterSchema
        character_obj = CharacterSchema(**char_dict)

        # Persist to database
        doc = character_obj.model_dump()
        if hasattr(db["characters"], "insert_one"):
            res = db["characters"].insert_one(doc)
            if hasattr(res, "__await__"):
                await res

        return character_obj
