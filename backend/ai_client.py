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
