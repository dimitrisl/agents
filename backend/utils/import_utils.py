import logging
from typing import Dict, Any

logger = logging.getLogger("DnDAssistant.ImportUtils")


def import_vtt_character(vtt_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses a Foundry VTT (dnd5e) exported JSON into our internal character schema.
    """
    try:
        system = vtt_data.get("system", {})

        # 1. Basic Info
        internal_data = {
            "char_name": vtt_data.get("name", "Imported Hero"),
            "char_class": "Unknown",  # Items will fill this if possible
            "race": "Unknown",
            "background": "Unknown",
            "alignment": "Neutral",
            "char_level": 1,
        }

        # 2. Details (Level, Race, etc)
        details = system.get("details", {})
        if details:
            internal_data["char_level"] = details.get("level", 1)
            internal_data["race"] = str(details.get("race", "Unknown"))
            internal_data["background"] = str(details.get("background", "Unknown"))
            internal_data["alignment"] = str(details.get("alignment", "Neutral"))
            internal_data["backstory"] = details.get("biography", {}).get("value", "")

        # 3. Abilities -> Stats
        abilities = system.get("abilities", {})
        if abilities:
            internal_data["stats"] = {
                "STR": abilities.get("str", {}).get("value", 10),
                "DEX": abilities.get("dex", {}).get("value", 10),
                "CON": abilities.get("con", {}).get("value", 10),
                "INT": abilities.get("int", {}).get("value", 10),
                "WIS": abilities.get("wis", {}).get("value", 10),
                "CHA": abilities.get("cha", {}).get("value", 10),
            }

        # 4. Attributes (HP, AC, Speed)
        attrs = system.get("attributes", {})
        if attrs:
            internal_data["hp_max"] = attrs.get("hp", {}).get("max", 10)
            internal_data["hp_current"] = attrs.get("hp", {}).get(
                "value", internal_data["hp_max"]
            )
            internal_data["armor_class"] = attrs.get("ac", {}).get("value", 10)
            internal_data["speed"] = attrs.get("movement", {}).get("walk", 30)
            internal_data["proficiency_bonus"] = attrs.get("prof", 2)
            internal_data["initiative_modifier"] = attrs.get("init", {}).get("bonus", 0)

        # 5. Skills
        # Reverse mapping for skills
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
        skill_profs = []
        skill_exp = []
        for code, data in vtt_skills.items():
            skill_name = vtt_skill_map.get(code)
            if skill_name:
                val = data.get("value", 0)
                if val == 1:
                    skill_profs.append(skill_name)
                elif val == 2:
                    skill_exp.append(skill_name)

        internal_data["skill_proficiencies"] = skill_profs
        internal_data["skill_expertise"] = skill_exp

        # 6. Items (Weapons, Equipment, Features, Spells)
        internal_data["weapons"] = []
        internal_data["equipment"] = []
        internal_data["features_traits"] = []
        internal_data["spells"] = {"cantrips": []}

        items = vtt_data.get("items", [])
        for item in items:
            item_type = item.get("type")
            item_name = item.get("name")
            item_sys = item.get("system", {})

            if item_type == "weapon":
                internal_data["weapons"].append(
                    {
                        "name": item_name,
                        "attack_bonus": "+0",  # Hard to derive perfectly from VTT without calculation
                        "damage_dice": "",
                        "damage_bonus": "+0",
                        "properties": item_sys.get("properties", []),
                    }
                )
            elif item_type == "equipment":
                internal_data["equipment"].append(
                    {
                        "name": item_name,
                        "equipped": item_sys.get("equipped", False),
                        "attuned": item_sys.get("attuned", False),
                    }
                )
            elif item_type == "feat" or item_type == "class":
                if item_type == "class":
                    internal_data["char_class"] = item_name

                internal_data["features_traits"].append(
                    {
                        "name": item_name,
                        "description": item_sys.get("description", {}).get("value", ""),
                        "source": "VTT Import",
                    }
                )
            elif item_type == "spell":
                lvl = item_sys.get("level", 0)
                lvl_key = "cantrips" if lvl == 0 else f"level_{lvl}"
                if lvl_key not in internal_data["spells"]:
                    internal_data["spells"][lvl_key] = []
                internal_data["spells"][lvl_key].append(item_name)

        return internal_data
    except Exception as e:
        logger.error(f"Failed to parse VTT character: {e}", exc_info=True)
        return None
