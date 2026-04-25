import urllib.parse
import hashlib


def generate_portrait_url(char_data: dict) -> str:
    """
    Generates a character portrait URL using image.pollinations.ai,
    incorporating character-specific details for a more accurate result.
    """
    race = char_data.get("race", "Human")
    char_class = char_data.get("char_class", "Warrior")
    background = char_data.get("background", "")
    backstory = char_data.get("backstory", "")
    alignment = char_data.get("alignment", "")
    gender = char_data.get("gender", "")

    # Extract keywords from backstory (first 150 chars) to avoid prompt bloat
    visual_hooks = backstory[:150] if backstory else ""

    # Construct a rich, descriptive prompt
    prompt = f"High fantasy D&D portrait of a {gender} {race} {char_class}. "
    if background:
        prompt += f"Background: {background}. "
    if alignment:
        prompt += f"Aura: {alignment}. "
    if visual_hooks:
        prompt += f"Details: {visual_hooks}. "

    prompt += "Cinematic lighting, detailed face, digital art masterpiece, high resolution, professional concept art."

    # URL encode the full prompt
    encoded_prompt = urllib.parse.quote(prompt)

    # Use a stable seed based on char_id to keep the URL consistent
    char_id = char_data.get("char_id", "default")
    seed = int(hashlib.md5(char_id.encode()).hexdigest(), 16) % 999999

    # More stable endpoint
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&seed={seed}&nologo=true"
