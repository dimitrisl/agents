import logging
import os
import re
import json
from typing import Dict, Any, List
import pdfplumber
from google import genai
from google.genai import types

logger = logging.getLogger("DnDAssistant.ModuleParser")

# Ensure images directory exists
MODULE_PICS_DIR = "data/module_pics"
os.makedirs(MODULE_PICS_DIR, exist_ok=True)


class ModuleParserService:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found. Module Parser disabled.")
            self.client = None
        else:
            self.client = genai.Client(api_key=self.api_key)

    def upload_pdf_to_gemini(self, pdf_path: str):
        """Uploads a PDF module to Gemini File API and returns the file object."""
        if not self.client:
            raise ValueError("Gemini Client not initialized.")

        logger.info(f"Uploading {pdf_path} to Gemini...")
        # Upload the file
        uploaded_file = self.client.files.upload(
            file=pdf_path, config={"mime_type": "application/pdf"}
        )
        logger.info(f"Uploaded successfully. URI: {uploaded_file.uri}")
        return uploaded_file

    def extract_npcs(self, uploaded_file) -> List[Dict[str, Any]]:
        """Asks Gemini to extract all NPCs and their page numbers."""
        if not self.client:
            return []

        prompt = """
        You are a D&D Assistant reading an official Adventure Module.
        Extract all named NPCs and notable unique monsters found in this module.
        For each NPC, provide a comprehensive statblock mapping to a character sheet format.
        Provide:
        - name: The name of the NPC
        - role: Their role or brief description (1-2 sentences)
        - ac: Armor Class (integer)
        - hp_max: Hit Points (integer)
        - char_level: Challenge Rating or estimated level (integer, default 1)
        - speed: Speed in feet (integer, default 30)
        - stats: An object containing STR, DEX, CON, INT, WIS, CHA (all integers)
        - features_traits: An array of objects, each with "name" and "description" (for their special traits and abilities)
        - weapons: An array of objects for their attacks, each with "name" (e.g. Longsword), "attack_bonus" (e.g. "+5"), and "damage_dice" (e.g. "1d8+3"). Set is_custom to true for monster attacks.
        - page_number_for_art: The integer page number (1-indexed based on the PDF file) where their primary artwork is located. 0 if none.

        Respond ONLY with a valid JSON array of objects. Example:
        [
          {
             "name": "Klarg",
             "role": "Bugbear boss",
             "ac": 16,
             "hp_max": 27,
             "char_level": 2,
             "speed": 30,
             "stats": {"STR": 15, "DEX": 14, "CON": 13, "INT": 8, "WIS": 11, "CHA": 9},
             "features_traits": [{"name": "Brute", "description": "Melee damage deals one extra die"}],
             "weapons": [{"name": "Morningstar", "attack_bonus": "+4", "damage_dice": "2d8+2", "is_custom": true}],
             "page_number_for_art": 12
          }
        ]
        """

        try:
            # We must use gemini-1.5-pro or flash for large context and files
            response = self.client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[uploaded_file, prompt],
                config=types.GenerateContentConfig(
                    temperature=0.0, response_mime_type="application/json"
                ),
            )

            # The response text should be valid JSON
            npcs = json.loads(response.text)
            return npcs
        except Exception as e:
            logger.error(f"Failed to extract NPCs: {e}")
            return []

    def extract_image_from_page(
        self, pdf_path: str, page_num: int, npc_name: str
    ) -> str:
        """
        Extracts the largest image from a specific page using pdfplumber.
        Returns the path to the saved image.
        """
        if page_num <= 0:
            return None

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Page numbers are 1-indexed, pdfplumber is 0-indexed
                if page_num > len(pdf.pages):
                    return None

                page = pdf.pages[page_num - 1]
                images = page.images

                if not images:
                    return None

                # Find the largest image by area (width * height)
                largest_image = max(
                    images, key=lambda img: img["width"] * img["height"]
                )

                # Extract the image
                # In pdfplumber, you can crop the page to the image bounding box and save it as an image
                bbox = (
                    largest_image["x0"],
                    largest_image["top"],
                    largest_image["x1"],
                    largest_image["bottom"],
                )
                cropped_page = page.crop(bbox)
                pil_image = cropped_page.to_image(resolution=150).original

                # Save it
                safe_name = re.sub(r"[^a-zA-Z0-9]", "_", npc_name).lower()
                image_filename = f"{safe_name}_{page_num}.png"
                image_path = os.path.join(MODULE_PICS_DIR, image_filename)

                pil_image.save(image_path)
                return image_path

        except Exception as e:
            logger.error(
                f"Failed to extract image for {npc_name} from page {page_num}: {e}"
            )
            return None
