import os
import logging
from pypdf import PdfReader, PdfWriter
from backend.calculations import calculate_modifier

logger = logging.getLogger("DnDAssistant.PDFExporter")

def format_mod(mod: int) -> str:
    return f"+{mod}" if mod >= 0 else str(mod)

def export_character_to_pdf(char_data: dict, template_path: str, output_path: str) -> bool:
    """Read template_path, fill fields with char_data, write to output_path."""
    logger.info(f"Exporting character {char_data.get('char_name')} to PDF.")
    
    if not os.path.exists(template_path):
        logger.error(f"Template PDF not found: {template_path}")
        return False
        
    try:
        reader = PdfReader(template_path)
        writer = PdfWriter()
        
        # Append the reader to the writer to preserve the AcroForm structure
        writer.append(reader)

        stats = char_data.get("stats", {})
        
        # 1. Base Core Fields
        field_data = {
            "CharacterName": char_data.get("char_name", ""),
            "ClassLevel": f"{char_data.get('char_class', '')} {char_data.get('char_level', '')}",
            "Race ": char_data.get("race", ""),
            "Background": char_data.get("background", ""),
            "Alignment": char_data.get("alignment", ""),
            "Backstory": char_data.get("backstory", ""),
            "AC": str(char_data.get("armor_class", "")),
            "Speed": str(char_data.get("speed", "")),
            "HPMax": str(char_data.get("hp_max", "")),
            "HPCurrent": str(char_data.get("hp_max", "")),
            "ProfBonus": format_mod(char_data.get("proficiency_bonus", 2)),
        }
        
        # 2. Ability Scores & Modifiers
        stat_keys = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
        mod_keys = {
            "STR": "STRmod", "DEX": "DEXmod ", "CON": "CONmod",
            "INT": "INTmod", "WIS": "WISmod", "CHA": "CHamod"
        }
        
        for st in stat_keys:
            val = stats.get(st, 10)
            mod = calculate_modifier(val)
            field_data[st] = str(val)
            field_data[mod_keys[st]] = format_mod(mod)
            
        # Initiative is usually DEX mod
        dex_mod = calculate_modifier(stats.get("DEX", 10))
        field_data["Initiative"] = format_mod(dex_mod)
        
        # 3. Skills Mapping
        skill_map = {
            "Acrobatics": "Acrobatics", "Animal Handling": "Animal", "Arcana": "Arcana",
            "Athletics": "Athletics", "Deception": "Deception ", "History": "History ",
            "Insight": "Insight", "Intimidation": "Intimidation", "Investigation": "Investigation ",
            "Medicine": "Medicine", "Nature": "Nature", "Perception": "Perception ",
            "Performance": "Performance", "Persuasion": "Persuasion", "Religion": "Religion",
            "Sleight of Hand": "SleightofHand", "Stealth": "Stealth ", "Survival": "Survival"
        }
        
        char_skills = char_data.get("skills", {})
        for sk_name, sk_val in char_skills.items():
            if sk_name in skill_map:
                field_data[skill_map[sk_name]] = str(sk_val)
                
        # 4. Saving Throws
        save_map = {
            "STR": "ST Strength", "DEX": "ST Dexterity", "CON": "ST Constitution",
            "INT": "ST Intelligence", "WIS": "ST Wisdom", "CHA": "ST Charisma"
        }
        for sv in char_data.get("saving_throws", []):
            if sv in save_map:
                val = stats.get(sv, 10)
                mod = calculate_modifier(val) + char_data.get("proficiency_bonus", 2)
                field_data[save_map[sv]] = format_mod(mod)
                
        # 5. Weapons (up to 3)
        weapons = char_data.get("weapons", [])
        if len(weapons) > 0:
            field_data["Wpn Name"] = weapons[0].get("name", "")
            field_data["Wpn1 AtkBonus"] = weapons[0].get("attack_bonus", "")
            field_data["Wpn1 Damage"] = weapons[0].get("damage", "")
        if len(weapons) > 1:
            field_data["Wpn Name 2"] = weapons[1].get("name", "")
            field_data["Wpn2 AtkBonus "] = weapons[1].get("attack_bonus", "")
            field_data["Wpn2 Damage "] = weapons[1].get("damage", "")
        if len(weapons) > 2:
            field_data["Wpn Name 3"] = weapons[2].get("name", "")
            field_data["Wpn3 AtkBonus  "] = weapons[2].get("attack_bonus", "")
            field_data["Wpn3 Damage "] = weapons[2].get("damage", "")
            
        # 6. Equipment & Features
        equip_text = "\\n".join(char_data.get("equipment", []))
        field_data["Equipment"] = equip_text
        
        feats = char_data.get("features_traits", [])
        feat_text = "\\n".join([f"{f.get('name', '')}: {f.get('description', '')}" for f in feats])
        
        # Append spells to correct spell fields
        spells = char_data.get("spells", {})
        if spells:
            spell_field_map = {
                "cantrips": [f"Spells 10{i}" for i in range(14, 23)],
                "level_1": [f"Spells 10{i}" for i in range(23, 34)],
                "level_2": [f"Spells 10{i}" for i in range(34, 47)],
                "level_3": [f"Spells 10{i}" for i in range(47, 60)],
                "level_4": [f"Spells 10{i}" for i in range(60, 73)],
                "level_5": [f"Spells 10{i}" for i in range(73, 82)],
                "level_6": [f"Spells 10{i}" for i in range(82, 91)],
                "level_7": [f"Spells 10{i}" for i in range(91, 100)],
                "level_8": [f"Spells 1010{i}" for i in range(0, 7)],
                "level_9": [f"Spells 1010{i}" for i in range(7, 14)]
            }
            for lvl, spell_list in spells.items():
                if lvl in spell_field_map:
                    target_fields = spell_field_map[lvl]
                    for i, spell in enumerate(spell_list):
                        if i < len(target_fields):
                            field_data[target_fields[i]] = spell
                    
        field_data["Features and Traits"] = feat_text

        # Update all fields
        writer.update_page_form_field_values(
            writer.pages[0], field_data
        )

        with open(output_path, "wb") as output_stream:
            writer.write(output_stream)
            
        logger.info("PDF generation successful.")
        return True
        
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}", exc_info=True)
        return False
