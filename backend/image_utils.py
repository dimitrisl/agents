import urllib.parse


def generate_portrait_url(char_data: dict) -> str:
    """
    Generates a character portrait URL using pollinations.ai.
    Constructs a detailed visual prompt from character data.
    """
    name = char_data.get("char_name", "Adventurer")
    race = char_data.get("race", "Human")
    char_class = char_data.get("char_class", "Warrior")
    backstory = char_data.get("backstory", "")

    # Construct a visual-focused prompt
    # We want a high-quality, D&D style portrait
    base_prompt = (
        f"Dungeons and Dragons character portrait, {race} {char_class}, {name}. "
    )

    # Add flavor from backstory if available (first 100 chars)
    if backstory:
        flavor = backstory[:150].replace("\n", " ")
        base_prompt += f"Background details: {flavor}. "

    base_prompt += "High fantasy art style, detailed face, cinematic lighting, masterpiece, oil painting style."

    # URL encode the prompt
    encoded_prompt = urllib.parse.quote(base_prompt)

    # Pollinations AI URL format
    # We add seeds/parameters to make it look consistent
    return f"https://pollinations.ai/p/{encoded_prompt}?width=512&height=512&seed=42&model=flux"
