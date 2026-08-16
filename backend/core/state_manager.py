def get_default_character() -> dict:
    """Returns a valid default character dictionary to be used as a fallback."""
    return {
        "char_name": "Unknown Hero",
        "char_class": "Fighter",
        "race": "Human",
        "background": "Soldier",
        "stats": {"STR": 15, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8}
    }
