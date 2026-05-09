import os
import logging
import requests
import io
import json
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from backend.calculations import calculate_modifier
from backend.constants import (
    PDF_PORTRAIT_X,
    PDF_PORTRAIT_Y,
    PDF_PORTRAIT_WIDTH,
    PDF_PORTRAIT_HEIGHT,
)

logger = logging.getLogger("DnDAssistant.PDFExporter")


def format_mod(mod: int) -> str:
    return f"+{mod}" if mod >= 0 else str(mod)


class PDFMappingProvider:
    """Loads and provides PDF field mappings from JSON files."""

    def __init__(self, mapping_name: str = "standard_5e"):
        self.mapping_path = os.path.join("data", "pdf_mappings", f"{mapping_name}.json")
        self.mapping = self._load_mapping()

    def _load_mapping(self) -> dict:
        try:
            if not os.path.exists(self.mapping_path):
                logger.error(f"Mapping file not found: {self.mapping_path}")
                return {}
            with open(self.mapping_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load PDF mapping: {e}")
            return {}

    def get_field_data(self, char_data: dict) -> dict:
        """Translates character data into PDF form fields based on the mapping."""
        if not self.mapping:
            return {}

        field_data = {}
        stats = char_data.get("stats", {})
        prof_bonus = char_data.get("proficiency_bonus", 2)

        # 1. Identity
        for pdf_key, data_key in self.mapping.get("identity", {}).items():
            if data_key == "char_class_level":
                field_data[pdf_key] = (
                    f"{char_data.get('char_class', '')} {char_data.get('char_level', '')}"
                )
            elif data_key == "proficiency_bonus_mod":
                field_data[pdf_key] = format_mod(prof_bonus)
            else:
                field_data[pdf_key] = str(char_data.get(data_key, ""))

        # 2. Stats & Mods
        for stat, pdf_key in self.mapping.get("stats", {}).items():
            val = stats.get(stat, 10)
            field_data[pdf_key] = str(val)

            mod_pdf_key = self.mapping.get("stat_mods", {}).get(stat)
            if mod_pdf_key:
                field_data[mod_pdf_key] = format_mod(calculate_modifier(val))

        # 3. Combat
        combat_map = self.mapping.get("combat", {})
        if "Initiative" in combat_map:
            dex_mod = calculate_modifier(stats.get("DEX", 10))
            field_data["Initiative"] = format_mod(dex_mod)

        # 4. Skills
        char_skills = char_data.get("skills", {})
        skill_profs = char_data.get("skill_proficiencies", [])
        skill_exps = char_data.get("skill_expertise", [])

        for skill_name, pdf_key in self.mapping.get("skills", {}).items():
            if skill_name in char_skills:
                field_data[pdf_key] = str(char_skills[skill_name])

            check_pdf_key = self.mapping.get("skill_checks", {}).get(skill_name)
            if check_pdf_key:
                field_data[check_pdf_key] = (
                    "/Yes"
                    if (skill_name in skill_profs or skill_name in skill_exps)
                    else "/No"
                )

        # 5. Saving Throws
        char_saves = char_data.get("saving_throws", [])
        for stat, pdf_key in self.mapping.get("saving_throws", {}).items():
            if stat in char_saves:
                val = stats.get(stat, 10)
                mod = calculate_modifier(val) + prof_bonus
                field_data[pdf_key] = format_mod(mod)

            check_pdf_key = self.mapping.get("save_checks", {}).get(stat)
            if check_pdf_key:
                field_data[check_pdf_key] = "/Yes" if stat in char_saves else "/No"

        # 6. Personality
        for pdf_key, data_key in self.mapping.get("personality", {}).items():
            field_data[pdf_key] = str(char_data.get(data_key, ""))

        # 7. Weapons
        weapons = char_data.get("weapons", [])
        weapon_mappings = self.mapping.get("weapons", [])
        for i, w_map in enumerate(weapon_mappings):
            if i < len(weapons):
                w = weapons[i]
                field_data[w_map["name"]] = w.get("name", "")
                field_data[w_map["atk"]] = w.get("attack_bonus", "")
                field_data[w_map["dmg"]] = w.get("damage", "")

        # 8. Equipment & Features
        blocks = self.mapping.get("blocks", {})
        if "Equipment" in blocks:
            field_data[blocks["Equipment"]] = "\n".join(char_data.get("equipment", []))

        if "Features and Traits" in blocks:
            feats = char_data.get("features_traits", [])
            field_data[blocks["Features and Traits"]] = "\n".join(
                [f"{f.get('name', '')}: {f.get('description', '')}" for f in feats]
            )

        if "Proficiencies and Languages" in blocks:
            langs = char_data.get("languages", [])
            tools = char_data.get("tool_proficiencies", [])
            combined = []
            if langs:
                combined.append(f"Languages: {', '.join(langs)}")
            if tools:
                combined.append(f"Tools: {', '.join(tools)}")

            field_data[blocks["Proficiencies and Languages"]] = "\n".join(combined)

        # 9. Spells
        char_spells = char_data.get("spells", {})
        spell_mapping = self.mapping.get("spells", {})
        for lvl, pdf_keys in spell_mapping.items():
            if lvl in char_spells:
                for i, spell in enumerate(char_spells[lvl]):
                    if i < len(pdf_keys):
                        field_data[pdf_keys[i]] = spell

        # 10. Spellcasting Stats
        char_class = char_data.get("char_class", "")
        spellcasting = self.mapping.get("spellcasting", {})
        spell_ability_map = {
            "Wizard": "INT",
            "Artificer": "INT",
            "Cleric": "WIS",
            "Druid": "WIS",
            "Ranger": "WIS",
            "Paladin": "CHA",
            "Sorcerer": "CHA",
            "Warlock": "CHA",
            "Bard": "CHA",
        }
        spell_stat = char_data.get(
            "spell_ability", spell_ability_map.get(char_class, "INT")
        )
        spell_mod = calculate_modifier(stats.get(spell_stat, 10))

        field_data[spellcasting["class"]] = char_class
        field_data[spellcasting["ability"]] = spell_stat
        field_data[spellcasting["dc"]] = str(
            char_data.get("spell_save_dc", 8 + spell_mod + prof_bonus)
        )
        field_data[spellcasting["bonus"]] = char_data.get(
            "spell_attack_bonus", format_mod(spell_mod + prof_bonus)
        )

        return field_data


def create_image_overlay(image_url: str) -> io.BytesIO:
    """Creates a transparent PDF page with the image at specific coordinates."""
    try:
        if os.path.exists(image_url):
            with open(image_url, "rb") as f:
                img_data = io.BytesIO(f.read())
        else:
            resp = requests.get(image_url, timeout=10)
            if resp.status_code != 200:
                return None
            img_data = io.BytesIO(resp.content)
        overlay_stream = io.BytesIO()

        # Create a canvas for a Letter size page
        from reportlab.lib.pagesizes import letter

        can = canvas.Canvas(overlay_stream, pagesize=letter)

        can.drawImage(
            ImageReader(img_data),
            PDF_PORTRAIT_X,
            PDF_PORTRAIT_Y,
            width=PDF_PORTRAIT_WIDTH,
            height=PDF_PORTRAIT_HEIGHT,
            mask="auto",
        )
        can.showPage()
        can.save()

        overlay_stream.seek(0)
        return overlay_stream
    except Exception as e:
        logger.error(f"Failed to create image overlay: {e}")
        return None


def export_character_to_pdf(char_data: dict, template_path: str) -> bytes:
    """Read template_path, fill fields with char_data, and return PDF bytes."""
    logger.info(f"Exporting character {char_data.get('char_name')} to PDF.")

    if not os.path.exists(template_path):
        logger.error(f"Template PDF not found: {template_path}")
        return None

    try:
        reader = PdfReader(template_path)
        writer = PdfWriter()
        writer.append(reader)

        # Load mapping and translate data
        edition = char_data.get("dnd_edition", "2014 Edition")
        mapping_name = "standard_5e"
        if "2024" in edition:
            mapping_name = "standard_2024"

        mapping_provider = PDFMappingProvider(mapping_name)
        field_data = mapping_provider.get_field_data(char_data)

        # Fill fields
        for page in writer.pages:
            writer.update_page_form_field_values(page, field_data)

        # Add portrait overlay
        portrait_url = char_data.get("char_portrait")
        if portrait_url:
            logger.info("Generating portrait overlay for PDF...")
            overlay_stream = create_image_overlay(portrait_url)
            if overlay_stream:
                overlay_reader = PdfReader(overlay_stream)
                overlay_page = overlay_reader.pages[0]
                if len(writer.pages) > 1:
                    writer.pages[1].merge_page(overlay_page)
                    logger.info("Merged portrait overlay onto page 2.")

        output_stream = io.BytesIO()
        writer.write(output_stream)
        pdf_bytes = output_stream.getvalue()
        output_stream.close()

        logger.info("PDF generation successful.")
        return pdf_bytes

    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}", exc_info=True)
        return None
