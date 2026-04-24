import os
import json
import logging
import streamlit as st
from google import genai

logger = logging.getLogger("DnDAssistant.AIClient")


# ==========================================
# AI Helper Functions
# ==========================================
@st.cache_resource
def get_ai_client():
    logger.info("Attempting to initialize Gemini AI Client.")
    if not os.getenv("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY is missing from environment variables.")
        return None
    logger.info("Gemini AI Client successfully initialized.")
    return genai.Client()


def get_flash_model(client):
    try:
        models = list(client.models.list())
        flash_models = [m.name for m in models if "flash" in m.name.lower()]
        model_to_use = flash_models[0] if flash_models else "gemini-1.5-flash"
        if model_to_use.startswith("models/"):
            model_to_use = model_to_use[7:]
        logger.debug(f"Selected Gemini model: {model_to_use}")
        return model_to_use
    except Exception as e:
        logger.warning(
            f"Failed to fetch model list, defaulting to gemini-1.5-flash. Error: {e}"
        )
        return "gemini-1.5-flash"


def generate_ai_response(prompt: str) -> str:
    """Helper function to call Gemini and return standard text."""
    logger.info("Generating standard AI text response...")
    logger.debug(f"Prompt sent: {prompt[:100]}...")  # Log only the first 100 chars

    client = get_ai_client()
    if not client:
        logger.error("Cannot generate response: AI Client is None.")
        return "❌ Error: GEMINI_API_KEY is missing in your .env file."

    try:
        model = get_flash_model(client)
        response = client.models.generate_content(model=model, contents=prompt)
        logger.info("Successfully received standard response from Gemini.")
        return response.text
    except Exception as e:
        logger.error(f"Failed to generate response: {e}", exc_info=True)
        return f"❌ Failed to generate response: {e}"


def generate_ai_json(prompt: str) -> dict:
    """Helper function to force Gemini to return structured JSON data."""
    logger.info("Generating structured AI JSON response...")
    logger.debug(f"JSON Prompt sent: {prompt[:100]}...")

    client = get_ai_client()
    if not client:
        logger.error("Cannot generate JSON: AI Client is None.")
        return None

    try:
        prompt += "\n\nIMPORTANT: Return ONLY a valid JSON object. Do not include markdown blocks or any other text."
        model = get_flash_model(client)

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        logger.info("Received JSON response from Gemini. Attempting to parse...")
        parsed_data = json.loads(response.text)
        logger.info("Successfully parsed JSON data from Gemini.")
        return parsed_data
    except json.JSONDecodeError:
        logger.error(
            f"Failed to parse JSON from Gemini response. Raw response: {response.text}",
            exc_info=True,
        )
        return None
    except Exception as e:
        logger.error(f"Failed to generate JSON response: {e}", exc_info=True)
        return None

def get_build_suggestion(char_level, char_class, char_name, stats) -> str:
    prompt = f"""
    I am playing a Level {char_level} {char_class} in D&D 5e (2014 edition) named {char_name}.
    Stats: STR {stats.get('STR')}, DEX {stats.get('DEX')}, CON {stats.get('CON')},
    INT {stats.get('INT')}, WIS {stats.get('WIS')}, CHA {stats.get('CHA')}.
    Give me a very short, 2-sentence creative build or multiclass suggestion for my next level up based on these specific stats.
    """
    return generate_ai_response(prompt)

def forge_character(target_level, forge_race, forge_class, forge_background, concept) -> dict:
    race_prompt = forge_race if forge_race != "AI Choice" else "Choose an optimal race"
    class_prompt = forge_class if forge_class != "AI Choice" else "Choose an optimal class"
    bg_prompt = forge_background if forge_background != "AI Choice" else "Choose an optimal background"
    
    prompt = f"""
    Create a fully fleshed out level {target_level} D&D 5e (2014 edition) character.
    Race: {race_prompt}
    Class: {class_prompt}
    Background: {bg_prompt}
    Flavor/Concept: {concept}
    
    You must assign them a balanced array of 6 ability scores, calculate their HP, AC, Proficiency Bonus, and choose appropriate skills, weapons, equipment, features/traits, and spells (if applicable) for a level {target_level} character.

    Output the character strictly as a JSON object with exactly the following schema:
    {{
        "char_name": "Name of the character",
        "char_class": "Class (e.g., Fighter, Wizard)",
        "char_level": {target_level},
        "race": "Race",
        "background": "Background",
        "alignment": "Alignment",
        "backstory": "A short, 2-3 sentence backstory.",
        "armor_class": 16,
        "hp_max": 45,
        "speed": 30,
        "proficiency_bonus": 3,
        "stats": {{
            "STR": 15, "DEX": 10, "CON": 14, "INT": 8, "WIS": 12, "CHA": 10
        }},
        "saving_throws": ["STR", "CON"],
        "skills": {{"Athletics": 5, "Intimidation": 2}},
        "weapons": [{{"name": "Warhammer", "attack_bonus": "+5", "damage": "1d8+3 bludgeoning"}}],
        "equipment": ["Chain mail", "Backpack"],
        "features_traits": [{{"name": "Action Surge", "description": "Push yourself..."}}],
        "spells": {{"cantrips": ["Fire Bolt"], "level_1": ["Shield"]}}
    }}
    """
    return generate_ai_json(prompt)

def generate_random_encounter(party_size, avg_level, location) -> str:
    prompt = f"""
    Generate a short, flavorful random encounter for a D&D 5e (2014 edition) party of {party_size} level {avg_level} characters.
    The setting is {location}.
    Include the monsters, a brief description of the environment, and a small twist.
    Format it nicely using markdown. Keep it under 150 words.
    """
    return generate_ai_response(prompt)

def generate_npc(npc_concept) -> str:
    prompt = f"""
    Create a D&D 5e (2014 edition) NPC based on: "{npc_concept}".
    Include their Name, Race, Appearance, Personality Trait, and a secret they are hiding.
    Format nicely with Markdown. Keep it brief and punchy.
    """
    return generate_ai_response(prompt)
