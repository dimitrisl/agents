def calculate_ability_modifier(score: int) -> int:
    if score <= 0:
        raise ValueError("unacceptable score")
    return (score - 10) // 2
