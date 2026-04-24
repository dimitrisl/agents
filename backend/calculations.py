def calculate_modifier(score: int) -> int:
    """Calculates the D&D 5e ability modifier for a given ability score."""
    return (score - 10) // 2
