import os
import json
import logging
import streamlit as st
from google import genai

from backend.core.config_loader import load_config

logger = logging.getLogger("DnDAssistant.AIClient")

# ==========================================
# AI Core Communication
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
    preferred = ai_settings.get("preferred_model", "models/gemini-2.5-flash")
    fallback = ai_settings.get("fallback_model", "models/gemini-2.5-flash")

    try:
        # Stable default to use if preferred is not available
        stable_default = "gemini-2.5-flash"

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
        # More robust cleaning of markdown blocks
        if "```json" in cleaned_text:
            cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned_text:
            cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()

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


def parse_user_intent(query: str) -> str:
    """Uses a fast model to classify the user's intent into a predefined category."""
    prompt = f"""
    Analyze the following user query and classify it into exactly one of the following categories:
    1. GENERAL_RULES
    2. COMBAT_ADVICE
    3. ROLEPLAY_ADVICE
    4. ITEM_PRICING
    5. UNKNOWN

    Return ONLY the category name.

    User Query: "{query}"
    """

    try:
        resp = generate_ai_response(prompt)
        # Clean up response
        clean_resp = resp.strip().upper()
        # Find if it contains any of the known intents
        for intent in [
            "GENERAL_RULES",
            "COMBAT_ADVICE",
            "ROLEPLAY_ADVICE",
            "ITEM_PRICING",
        ]:
            if intent in clean_resp:
                return intent
        return "UNKNOWN"
    except Exception as e:
        logger.error(f"Failed to parse user intent: {e}")
        return "UNKNOWN"


def generate_session_prep(
    module_file_name: str, previous_recap: str, dm_ideas: str
) -> str:
    """Generates DM session prep based on the module, recap, and new ideas."""
    logger.info("Generating session prep using uploaded module context...")

    client = get_ai_client()
    if not client:
        return "❌ Error: AI Client not initialized."

    prompt = f"""
    You are an expert Dungeon Master assistant. I am running an official D&D adventure module.
    You have access to the entire module PDF attached.

    Here is what happened in the previous session (Reality Recap):
    {previous_recap if previous_recap else "This is the first session. The campaign is just starting."}

    Here are my ideas for the next session:
    {dm_ideas}

    Using the module's contents, the recap, and my ideas, please generate comprehensive Session Prep notes for the NEXT session.
    Include:
    1. Recap of where the players are.
    2. Key NPCs they might encounter (with page references from the module).
    3. Potential encounters (combat/social/exploration) that logically follow the module and the DM's ideas.
    4. Important lore or secrets to reveal.

    Format the output in clean Markdown.
    """

    try:
        contents = []
        if module_file_name:
            try:
                # Fetch the file object using its name
                file_obj = client.files.get(name=module_file_name)
                contents.append(file_obj)
            except Exception as e:
                logger.error(f"Could not retrieve file {module_file_name}: {e}")

        contents.append(prompt)

        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=contents,
        )
        return response.text
    except Exception as e:
        logger.error(f"Failed to generate session prep: {e}")
        return f"❌ Failed to generate session prep: {str(e)}"
