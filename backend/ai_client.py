import os
import json
import logging
import streamlit as st
from google import genai
from backend.constants import (
    EDITION_2014,
    RACES_2014,
    CLASSES_2014,
    BACKGROUNDS_2014,
    SPECIES_2024,
    CLASSES_2024,
    BACKGROUNDS_2024,
    GENDERS,
)

from backend.config_loader import load_config

logger = logging.getLogger("DnDAssistant.AIClient")

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
    """Selects the best available Flash model based on config preferences."""
    config = load_config()
    ai_settings = config.get("ai_settings", {})
    preferred = ai_settings.get("preferred_model", "models/gemini-1.5-flash")
    fallback = ai_settings.get("fallback_model", "models/gemini-1.5-flash")

    try:
        # gemini-flash-latest is the most stable auto-updating identifier in 2026
        stable_default = "gemini-flash-latest"

        models = list(client.models.list())
        model_names = [m.name.lower() for m in models]

        # 1. Try the preferred model from config
        for name in model_names:
            if preferred.lower() in name:
                target = name[7:] if name.startswith("models/") else name
                return target

        # 2. Try the stable default
        for name in model_names:
            if stable_default in name:
                target = name[7:] if name.startswith("models/") else name
                return target

        # 3. Fallback to whatever is in the config
        return fallback[7:] if fallback.startswith("models/") else fallback
    except Exception as e:
        logger.warning(
            f"Failed to fetch model list, defaulting to {fallback}. Error: {e}"
        )
        return fallback[7:] if fallback.startswith("models/") else fallback


def generate_ai_response(prompt: str) -> str:
    """Helper function to call Gemini and return standard text."""
    logger.info("Generating standard AI text response...")
    logger.debug(f"Prompt sent: {prompt[:100]}...")  # Log only the first 100 chars

    client = get_ai_client()
    if not client:
        logger.error("Cannot generate response: AI Client is None.")
        return "❌ Error: GEMINI_API_KEY is missing in your .env file."

    try:
        # Load temperature from config
        config = load_config()
        ai_settings = config.get("ai_settings", {})
        temp = ai_settings.get("temperature")

        model = get_flash_model(client)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=temp,
            ),
        )
        logger.info("Successfully received standard response from Gemini.")
        return response.text
    except Exception as e:
        error_msg = str(e)
        if "503" in error_msg or "high demand" in error_msg.lower():
            return "⚠️ The AI is currently experiencing high demand. Please wait a few seconds and try again."
        logger.error(f"Failed to generate response: {e}", exc_info=True)
        return f"❌ Failed to generate response: {error_msg}"


def generate_ai_json(prompt: str) -> dict:
    """Helper function to force Gemini to return structured JSON data."""
    logger.info("Generating structured AI JSON response...")
    logger.debug(f"JSON Prompt sent: {prompt[:100]}...")

    client = get_ai_client()
    if not client:
        logger.error("Cannot generate JSON: AI Client is None.")
        return None

    try:
        # Load temperature from config
        config = load_config()
        ai_settings = config.get("ai_settings", {})
        temp = ai_settings.get("temperature")

        prompt += "\n\nIMPORTANT: Return ONLY a valid JSON object. Do not include markdown blocks or any other text."
        model = get_flash_model(client)

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temp,
            ),
        )
        if not response or not response.text:
            logger.error("Gemini returned an empty or null response text.")
            return None

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
        error_msg = str(e)
        if "503" in error_msg or "high demand" in error_msg.lower():
            st.error(
                "⚠️ The AI is currently experiencing high demand. Please try again in a moment."
            )
            return None
        logger.error(f"Failed to parse JSON response from Gemini: {e}", exc_info=True)
        return None


# ==========================================
# Specialized AI Methods
# ==========================================


def get_build_suggestion(
    char_level, char_class, char_name, stats, edition="2014 Edition"
) -> str:
    prompt = f"""
    I am playing a Level {char_level} {char_class} in D&D {edition} named {char_name}.
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
    name="AI Choice",
    gender="AI Choice",
    stats_mode="standard",
    alignment="AI Choice",
    edition="2014 Edition",
    subclass=None,
) -> dict:
    # Determine which lists to use based on edition
    if edition == EDITION_2014:
        current_races = RACES_2014
        current_classes = CLASSES_2014
        current_backgrounds = BACKGROUNDS_2014
    else:
        current_races = SPECIES_2024
        current_classes = CLASSES_2024
        current_backgrounds = BACKGROUNDS_2024

    race_prompt = (
        forge_race
        if forge_race != "AI Choice"
        else f"Choose one from: {', '.join(current_races)}"
    )
    class_prompt = (
        forge_class
        if forge_class != "AI Choice"
        else f"Choose one from: {', '.join(current_classes)}"
    )
    bg_prompt = (
        forge_background
        if forge_background != "AI Choice"
        else f"Choose one from: {', '.join(current_backgrounds)}"
    )
    gender_prompt = (
        gender if gender != "AI Choice" else f"Choose from: {', '.join(GENDERS)}"
    )

    if name != "AI Choice":
        name_instruction = f"The character's name MUST be: {name}"
    else:
        name_instruction = "Assign them a creative and thematic name."

    if stats_mode == "standard":
        stats_instruction = "You MUST use the Standard Array (15, 14, 13, 12, 10, 8) for their base ability scores, distributed optimally for their class/race."
    else:
        stats_instruction = "You must assign them a balanced, high-quality array of 6 ability scores (equivalent to rolling 4d6 drop lowest)."

    prompt = f"""
    Create a fully fleshed out level {target_level} D&D {edition} character.
    {name_instruction}
    Gender: {gender_prompt}
    Race: {race_prompt}
    Class: {class_prompt}
    Background: {bg_prompt}
    Flavor/Concept: {concept}
    Subclass: {subclass if subclass else "AI Choice (if applicable for level)"}
    Alignment: {alignment}

    STRICT RULES:
    1. Race/Species MUST be one of: {current_races}
    2. Class MUST be one of: {current_classes}
    3. Background MUST be one of: {current_backgrounds}

    {stats_instruction}

    Calculate their HP, AC, Proficiency Bonus, and choose appropriate skills, weapons, equipment, features/traits, and spells (if applicable) for a level {target_level} character.
    If the level is 4 or higher (or 1 if 2024 edition), explicitly list their Feats and Ability Score Improvements (ASI) in the 'advancements' field.

    Output the character strictly as a JSON object with exactly the following schema:
    {{
        "char_name": "Name of the character",
        "gender": "{gender_prompt if gender != "AI Choice" else "Male/Female"}",
        "char_class": "Class (e.g., Fighter, Wizard)",
        "subclass": "Subclass name (if applicable)",
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
        "weapon_masteries": ["Slow", "Topple"],
        "weapons": [{{"name": "Warhammer", "attack_bonus": "+5", "damage": "1d8+3 bludgeoning"}}],
        "equipment": ["Chain mail", "Backpack"],
        "features_traits": [{{"name": "Action Surge", "description": "Push yourself..."}}],
        "spells": {{"cantrips": ["Fire Bolt"], "level_1": ["Shield"]}},
        "spell_ability": "INT",
        "spell_save_dc": 15,
        "spell_attack_bonus": "+7",
        "hit_dice": "1d10",
        "passive_perception": 12,
        "advancements": [
            {{"level": 1, "type": "Origin Feat", "name": "Tough", "description": "+2 HP per level"}},
            {{"level": 4, "type": "Feat", "name": "Great Weapon Master", "description": "Deal more damage..."}}
        ],
        "personality_traits": "...",
        "ideals": "...",
        "bonds": "...",
        "flaws": "..."
    }}
    """
    result = generate_ai_json(prompt)
    if result:
        result["dnd_edition"] = edition
    return result


def generate_random_encounter(
    party_size, avg_level, location, edition="2014 Edition"
) -> dict:
    prompt = f"""
    Generate a flavorful random encounter for a D&D {edition} party of {party_size} level {avg_level} characters.
    The setting is {location}.

    You must return a JSON object with the following structure:
    {{
        "encounter_text": "Markdown formatted description of the environment, encounter, and twist.",
        "monsters": [
            {{
                "name": "Monster Name",
                "hp": 45,
                "ac": 15,
                "dex": 12,
                "quantity": 3,
                "statblock_summary": "Brief summary of attacks and abilities"
            }}
        ]
    }}

    Make the encounter_text engaging and flavorful.
    Ensure the monster stats are balanced for the party level.
    """
    return generate_ai_json(prompt)


def generate_npc(npc_concept, edition="2014 Edition") -> str:
    prompt = f"""
    Create a D&D {edition} NPC based on: "{npc_concept}".
    Include their Name, Race/Species, Appearance, Personality Trait, and a secret they are hiding.
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


def generate_playstyle_guide(char_data: dict) -> str:
    """Generates a detailed strategic and roleplay guide for a character."""
    prompt = f"""
    Create a detailed D&D {char_data.get("dnd_edition", "2014 Edition")} Playstyle Guide for the following character:
    Name: {char_data.get("char_name")}
    Class: {char_data.get("char_class")} (Subclass: {char_data.get("subclass", "N/A")})
    Level: {char_data.get("char_level")}
    Race/Species: {char_data.get("race")}
    Background: {char_data.get("background")}
    Stats: {char_data.get("stats")}
    Features: {[f.get("name") for f in char_data.get("features_traits", [])]}

    The guide should include:
    1. **Combat Strategy**: How to use their actions, bonus actions, and features optimally.
    2. **Roleplay Tips**: How to portray their personality and background in the world.
    3. **Key Synergies**: How their features work together.

    Use beautiful markdown formatting with headings, bullet points, and emphasis.
    """
    return generate_ai_response(prompt)


def analyze_level_up(char_data: dict) -> dict:
    """Uses AI to determine what changes occur when leveling up."""
    current_level = char_data.get("char_level", 1)
    target_level = current_level + 1
    edition = char_data.get("dnd_edition", "2014 Edition")

    prompt = f"""
    Act as a D&D {edition} Rules Expert.
    Analyze the following character and determine EXACTLY what changes when they level up from Level {current_level} to Level {target_level}.

    Character Info:
    - Class: {char_data.get("char_class")}
    - Subclass: {char_data.get("subclass", "None")}
    - Race/Species: {char_data.get("race")}
    - Stats: {char_data.get("stats")}

    Return a JSON object with the following structure:
    {{
        "automatic_changes": [
            {{"name": "Feature Name", "description": "Brief description of the new feature"}}
        ],
        "hp_increase": 8, // The exact number to add to Max HP (Die Average + CON mod)
        "new_total_hp": 42, // The expected total Max HP after level up
        "choices_required": [
            {{
                "type": "subclass|feat|spell|other",
                "label": "Prompt for the user",
                "options": ["Option 1", "Option 2"],
                "ai_recommendation": "Recommendation text"
            }}
        ],
        "updated_proficiency_bonus": 3, // New total bonus or null
        "updated_spell_slots": {{ "level_1": 4, "level_2": 2 }} // Total slots or null
    }}

    Ruleset specific notes:
    - If 2024 Edition, remember that Subclasses are now ALWAYS chosen at Level 3.
    - If 2024 Edition, Fighter/Barbarian/etc might gain more Weapon Masteries.
    - If Level 4, 8, 12, 16, 19, there is always a Choice (Feat or ASI).

    Be precise and follow the {edition} rules strictly.
    """
    return generate_ai_json(prompt)


def validate_character_build(char_data: dict) -> dict:
    """Uses AI to validate a character's build based on their level, class, and edition."""
    prompt = f"""
    You are an expert Dungeon Master and Rules Arbiter for Dungeons & Dragons.
    Your task is to validate a character sheet to ensure it complies with the official rules.

    Character Data:
    {json.dumps(char_data, indent=2)}

    Validate the following aspects based on their edition ({char_data.get("dnd_edition", "2014")}):
    1. Are the Ability Scores possible? (e.g., standard array/point buy + racial bonuses, no score above 20 unless a specific feature allows it).
    2. Is the Max HP reasonable for their class, level, and CON modifier?
    3. Is the Proficiency Bonus correct for their level ({char_data.get("char_level")})?
    4. Do they have too many or too few features/traits for their level and class?
    5. Are their spell slots correct for their class and level?

    Return a JSON object with the following structure exactly:
    {{
        "is_valid": true, // false if there are any major violations
        "issues": ["List of any rules violations or discrepancies found (leave empty if none)"],
        "suggestions": ["List of suggestions to fix the issues (leave empty if none)"]
    }}
    """
    return generate_ai_json(prompt)


def query_rules(query: str, edition: str = "2014 Edition") -> str:
    """Uses AI to answer questions about D&D rules, spells, and features."""
    prompt = f"""
    You are the 'Phyrexian Oracle', an expert on Dungeons & Dragons {edition} rules.
    Answer the following question clearly and concisely.
    The answer MUST BE no more than 5 sentences long.
    If the rule changed between 2014 and 2024, and the user is asking about {edition}, make sure to provide the version-accurate answer.

    Question: {query}

    Answer (be helpful, use markdown for formatting):
    """
    return generate_ai_response(prompt)


def parse_character_from_text(sheet_text: str, edition: str = "2014 Edition") -> dict:
    """
    Parses raw text extracted from a D&D Character Sheet PDF into the app's JSON structure.
    Uses a 2-step chained process for maximum precision.
    """
    logger.info("Starting Chained Character Parsing (Step 1: Core Stats)...")

    # STEP 1: Core Statistics & Identity
    step1_prompt = f"""
    Act as an expert D&D {edition} parser.
    Analyze the following raw text from a character sheet and extract the CORE identity and statistics.

    IMPORTANT: The text may contain labels in languages other than English (e.g., Italian like 'Classe e livello', 'Nome', 'Forza', 'Destrezza').
    Identify these fields by their context and map them correctly.

    The input text is organized into two primary sections for clarity:
    1. '--- FORM FIELDS ---': Contains raw key-value pairs from PDF form fields. These are often high-fidelity but may have cryptic names (e.g. 'STR' or 'Check Box 11').
    2. '--- VISUAL LAYOUT TEXT ---': Contains text extracted directly from the page, preserving the visual alignment. Use this to cross-reference field names with their nearby labels.

    Raw PDF Text:
    {sheet_text}

    Return a JSON object with this exact structure:
    {{
        "char_name": "string",
        "char_class": "string",
        "char_level": integer,
        "race": "string",
        "background": "string",
        "alignment": "string",
        "armor_class": integer,
        "hp_max": integer,
        "speed": integer,
        "proficiency_bonus": integer,
        "stats": {{
            "STR": integer, "DEX": integer, "CON": integer, "INT": integer, "WIS": integer, "CHA": integer
        }},
        "saving_throws": ["string"],
        "skills": {{"SkillName": BonusInteger}},
        "skill_proficiencies": ["string"],
        "skill_expertise": ["string"]
    }}
    """
    core_data = generate_ai_json(step1_prompt)
    if not core_data:
        logger.error("Step 1 of chained parsing failed.")
        return None

    logger.info(
        f"Step 1 Complete (Name: {core_data.get('char_name')}). Starting Step 2 (Combat & Features)..."
    )

    # STEP 2: Combat, Equipment, Spells & Lore
    # We provide the AI with the Core Data found in Step 1 to give it context.
    step2_prompt = f"""
    Act as an expert D&D {edition} parser.
    I have already extracted some core data for this character: {json.dumps(core_data)}.
    Now, focus on extracting the following details from the same raw text:
    - Weapons & Attacks
    - Equipment & Inventory
    - Spells (by level)
    - Features, Traits, and Lore (Backstory, Personality)

    The input text is organized into two primary sections for clarity:
    1. '--- FORM FIELDS ---': Contains raw key-value pairs from PDF form fields.
    2. '--- VISUAL LAYOUT TEXT ---': Contains text extracted directly from the page, preserving the visual alignment.

    Raw PDF Text:
    {sheet_text}

    Return a JSON object with this exact structure (combine with core data if necessary):
    {{
        "backstory": "string (summarize if too long, max 500 chars)",
        "personality_traits": "string",
        "ideals": "string",
        "bonds": "string",
        "flaws": "string",
        "weapons": [
            {{
                "name": "string",
                "attack_bonus": "string",
                "damage": "string",
                "range": "string (optional)",
                "properties": "string (optional)"
            }}
        ],
        "equipment": ["string"],
        "spells": {{
            "cantrips": ["string"],
            "level_1": ["string"],
            "level_2": ["string"],
            "level_3": ["string"],
            "level_4": ["string"],
            "level_5": ["string"]
        }},
        "features_traits": [
            {{
                "name": "string",
                "source": "string",
                "description": "string"
            }}
        ]
    }}
    """
    combat_data = generate_ai_json(step2_prompt)
    if not combat_data:
        logger.warning("Step 2 of chained parsing failed. Returning core data only.")
        return core_data

    # Merge the results
    final_data = {**core_data, **combat_data}
    logger.info("Chained parsing successfully completed.")
    return final_data
