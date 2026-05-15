def convert_to_vtt_format(char_dict: dict) -> dict:
    """
    Converts the internal character representation into a Foundry VTT compatible JSON format (dnd5e system).
    This allows players to easily import their characters into popular virtual tabletops.
    """
    stats = char_dict.get("stats", {})

    # Map internal skills to Foundry VTT standard abbreviations
    skill_mapping = {
        "Acrobatics": "acr",
        "Animal Handling": "ani",
        "Arcana": "arc",
        "Athletics": "ath",
        "Deception": "dec",
        "History": "his",
        "Insight": "ins",
        "Intimidation": "itm",
        "Investigation": "inv",
        "Medicine": "med",
        "Nature": "nat",
        "Perception": "prc",
        "Performance": "prf",
        "Persuasion": "per",
        "Religion": "rel",
        "Sleight of Hand": "slt",
        "Stealth": "ste",
        "Survival": "sur",
    }

    proficiencies = char_dict.get("skill_proficiencies", [])
    expertise = char_dict.get("skill_expertise", [])

    skills_data = {}
    for skill_name, short_code in skill_mapping.items():
        prof_val = 0
        if skill_name in expertise:
            prof_val = 2
        elif skill_name in proficiencies:
            prof_val = 1

        skills_data[short_code] = {"value": prof_val}

    vtt_char = {
        "name": char_dict.get("char_name", "Unknown Hero"),
        "type": "character",
        "system": {
            "abilities": {
                "str": {"value": stats.get("STR", 10)},
                "dex": {"value": stats.get("DEX", 10)},
                "con": {"value": stats.get("CON", 10)},
                "int": {"value": stats.get("INT", 10)},
                "wis": {"value": stats.get("WIS", 10)},
                "cha": {"value": stats.get("CHA", 10)},
            },
            "attributes": {
                "hp": {
                    "value": char_dict.get("hp_max", 10),
                    "max": char_dict.get("hp_max", 10),
                },
                "ac": {"value": char_dict.get("armor_class", 10), "calc": "default"},
                "movement": {"walk": char_dict.get("speed", 30)},
                "prof": char_dict.get("proficiency_bonus", 2),
                "init": {"bonus": char_dict.get("initiative_modifier", 0)},
            },
            "details": {
                "level": char_dict.get("char_level", 1),
                "race": char_dict.get("race", ""),
                "background": char_dict.get("background", ""),
                "alignment": char_dict.get("alignment", ""),
                "biography": {"value": char_dict.get("backstory", "")},
            },
            "skills": skills_data,
            "traits": {
                "languages": {"custom": "; ".join(char_dict.get("languages", []))}
            },
        },
        "items": [],
    }

    # Add items, weapons, and features
    for weapon in char_dict.get("weapons", []):
        vtt_char["items"].append(
            {
                "name": weapon.get("name", "Unknown Weapon"),
                "type": "weapon",
                "system": {
                    "description": {"value": weapon.get("damage", "")},
                    "equipped": True,
                },
            }
        )

    for item in char_dict.get("equipment", []):
        vtt_char["items"].append(
            {
                "name": item.get("name", "Unknown Item")
                if isinstance(item, dict)
                else item,
                "type": "equipment",
                "system": {
                    "equipped": item.get("equipped", False)
                    if isinstance(item, dict)
                    else True
                },
            }
        )

    for feature in char_dict.get("features_traits", []):
        vtt_char["items"].append(
            {
                "name": feature.get("name", "Unknown Feature")
                if isinstance(feature, dict)
                else feature,
                "type": "feat",
                "system": {
                    "description": {
                        "value": feature.get("description", "")
                        if isinstance(feature, dict)
                        else ""
                    }
                },
            }
        )

    return vtt_char
