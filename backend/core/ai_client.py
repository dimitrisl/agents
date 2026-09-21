import logging

from backend.core.providers.factory import get_llm_provider

logger = logging.getLogger("DnDAssistant.AIClient")


def generate_ai_response(prompt: str) -> str:
    """Helper function to call the configured LLM and return standard text."""
    logger.info("Generating standard AI text response...")
    logger.debug(f"Prompt sent: {prompt[:100]}...")
    provider = get_llm_provider()
    return provider.generate_text(prompt)


def generate_ai_json(prompt: str) -> dict:
    """Helper function to force the configured LLM to return structured JSON data."""
    logger.info("Generating structured AI JSON response...")
    logger.debug(f"JSON Prompt sent: {prompt[:100]}...")
    provider = get_llm_provider()
    return provider.generate_json(prompt)


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
        clean_resp = resp.strip().upper()
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


def generate_session_prep(module_file_name: str, previous_recap: str, dm_ideas: str) -> str:
    """Generates DM session prep based on the module, recap, and new ideas."""
    logger.info("Generating session prep using uploaded module context...")

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

    file_ids = [module_file_name] if module_file_name else []
    provider = get_llm_provider()
    return provider.generate_from_files(file_ids, prompt)
