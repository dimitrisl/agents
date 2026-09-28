import logging

from backend.core.ai_client import generate_ai_json

logger = logging.getLogger("DnDAssistant.LoreService")


def extract_entity_from_text(raw_text: str, campaign_name: str) -> dict:
    """
    Takes raw, unstructured text (like a stat block copied from a website or random notes)
    and parses it into a structured entity format suitable for CampaignEntitySchema.
    """
    logger.info("Extracting entity from raw text using AI...")

    prompt = f"""
    You are an expert Dungeon Master assistant for Dungeons & Dragons 5e.
    The user has pasted some raw text. It could be an NPC stat block, monster details,
    faction lore, a location description, or random campaign notes.

    Analyze the text and extract the information into the following JSON structure:
    {{
        "name": "The extracted name of the entity",
        "type": "Classify as ONE of: npc, villain, faction, location, lore, monster",
        "content": "A detailed Markdown description of the lore, history, or notes extracted.",
        "tags": ["list", "of", "relevant", "tags"],
        "stats": {{
             // If it's a monster/NPC with stats (like AC, HP, STR, DEX, Actions),
             // extract those stats into key-value pairs here. Otherwise, leave empty.
        }}
    }}

    Raw text to analyze:
    {raw_text}
    """

    try:
        extracted_data = generate_ai_json(prompt)

        # Ensure base fields are present
        entity_dict = {
            "campaign_name": campaign_name,
            "name": extracted_data.get("name", "Unknown Entity"),
            "type": extracted_data.get("type", "lore").lower(),
            "content": extracted_data.get("content", raw_text),
            "tags": extracted_data.get("tags", []),
            "stats": extracted_data.get("stats", {}),
        }

        return entity_dict
    except Exception as e:
        logger.error(f"Failed to extract entity: {e}")
        # Fallback to basic lore note if AI parsing fails
        return {
            "campaign_name": campaign_name,
            "name": "Extracted Note",
            "type": "lore",
            "content": raw_text,
            "tags": ["auto-extracted", "parsing-failed"],
            "stats": {},
        }
