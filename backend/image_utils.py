import urllib.parse
import random


def generate_portrait_url(char_data: dict) -> str:
    """
    Generates a character portrait URL using image.pollinations.ai.
    """
    race = char_data.get("race", "Human")
    char_class = char_data.get("char_class", "Warrior")

    # Simple, high-quality prompt
    prompt = f"High fantasy D&D portrait of a {race} {char_class}, detailed face, cinematic lighting, digital art"

    # URL encode only the prompt
    encoded_prompt = urllib.parse.quote(prompt)

    # Use a random seed to avoid cached broken images
    seed = random.randint(1, 999999)

    # More stable endpoint
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&seed={seed}&nologo=true"
