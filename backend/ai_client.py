import os
import json
import logging
import streamlit as st
from google import genai
from backend.constants import (
    ALLOWED_RACES,
    ALLOWED_CLASSES,
    ALLOWED_BACKGROUNDS,
    GENDERS,
)

logger = logging.getLogger("DnDAssistant.AIClient")


# ==========================================
# AI Constants & Config
# ==========================================
DEFAULT_TEMPERATURE = 0.9


# ==========================================
# AI Helper Functions
# ==========================================
def get_ai_client():
    """Initializes the Gemini AI Client. Not cached if it fails to find the API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is missing from environment variables.")
        return None

    # We use a local cache-like behavior only on success to avoid re-initializing every time
    if not hasattr(st, "_genai_client"):
        logger.info("Attempting to initialize Gemini AI Client.")
        st._genai_client = genai.Client(api_key=api_key)
        logger.info("Gemini AI Client successfully initialized.")

    return st._genai_client


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
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=DEFAULT_TEMPERATURE,
            ),
        )
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
                temperature=DEFAULT_TEMPERATURE,
            ),
        )
        logger.info("Received JSON response from Gemini. Attempting to parse...")
        cleaned_text = response.text.strip()
        if cleaned_text.startswith("```"):
            first_newline = cleaned_text.find("\n")
            if first_newline != -1:
                cleaned_text = cleaned_text[first_newline:].strip()
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3].strip()

        parsed_data = json.loads(cleaned_text)
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
    Stats: STR {stats.get("STR")}, DEX {stats.get("DEX")}, CON {stats.get("CON")},
    INT {stats.get("INT")}, WIS {stats.get("WIS")}, CHA {stats.get("CHA")}.
    Give me a very short, 2-sentence creative build or multiclass suggestion for my next level up based on these specific stats.
    """
    return generate_ai_response(prompt)


def forge_character(
    target_level,
    forge_race,
    forge_class,
    forge_background,
    concept,
    gender="AI Choice",
    stats_mode="standard",
    char_name=None,
) -> dict:
    race_prompt = (
        forge_race
        if forge_race != "AI Choice"
        else f"Choose one from: {', '.join(ALLOWED_RACES)}"
    )
    class_prompt = (
        forge_class
        if forge_class != "AI Choice"
        else f"Choose one from: {', '.join(ALLOWED_CLASSES)}"
    )
    bg_prompt = (
        forge_background
        if forge_background != "AI Choice"
        else f"Choose one from: {', '.join(ALLOWED_BACKGROUNDS)}"
    )
    gender_prompt = (
        gender if gender != "AI Choice" else f"Choose from: {', '.join(GENDERS)}"
    )

    name_instruction = (
        f"Character Name: {char_name}"
        if char_name
        else "Assign them a creative and thematic name."
    )

    if stats_mode == "standard":
        stats_instruction = "You MUST use the Standard Array (15, 14, 13, 12, 10, 8) for their base ability scores, distributed optimally for their class/race."
    else:
        stats_instruction = "You must assign them a balanced, high-quality array of 6 ability scores (equivalent to rolling 4d6 drop lowest)."

    prompt = f"""
    Create a fully fleshed out level {target_level} D&D 5e (2014 edition) character.
    {name_instruction}
    Gender: {gender_prompt}
    Race: {race_prompt}
    Class: {class_prompt}
    Background: {bg_prompt}
    Flavor/Concept: {concept}

    STRICT RULES:
    1. Race MUST be one of: {ALLOWED_RACES}
    2. Class MUST be one of: {ALLOWED_CLASSES}
    3. Background MUST be one of: {ALLOWED_BACKGROUNDS}

    {stats_instruction}

    Calculate their HP, AC, Proficiency Bonus, and choose appropriate skills, weapons, equipment, features/traits, and spells (if applicable) for a level {target_level} character.

    Output the character strictly as a JSON object with exactly the following schema:
    {{
        "char_name": "Name of the character",
        "gender": "{gender_prompt if gender != "AI Choice" else "Male/Female"}",
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
        "spells": {{"cantrips": ["Fire Bolt"], "level_1": ["Shield"]}},
        "spell_ability": "INT",
        "spell_save_dc": 15,
        "spell_attack_bonus": "+7",
        "hit_dice": "1d10",
        "passive_perception": 12,
        "personality_traits": "...",
        "ideals": "...",
        "bonds": "...",
        "flaws": "..."
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


def generate_session_prep(campaign_notes, party_info) -> str:
    prompt = f"""
    I am a Dungeon Master preparing for my next D&D 5e session.
    Here are my current campaign notes:
    ---
    {campaign_notes}
    ---
    Here is the current party composition:
    {party_info}

    Based on the notes and the party, generate 3 creative plot hooks, twists, or developments for the next session.
    Format your response with markdown, using clear headings for each hook.
    Keep the total response under 250 words.
    """
    return generate_ai_response(prompt)
