import random
import re
import logging
from typing import Dict, Any

logger = logging.getLogger("DnDAssistant.DiceService")


def rebuild_damage_formula(damage_dice: str, damage_bonus: str) -> str:
    """Reconstructs a clean damage formula string from dice and bonus inputs."""
    damage_dice = (damage_dice or "1d4").strip()
    damage_bonus = (damage_bonus or "+0").strip()

    # Match 1d8, 2d6, or just d20
    dice_match = re.match(r"^\s*(\d*d\d+)", damage_dice, re.I)
    if not dice_match:
        # If it doesn't look like dice at all, just return it combined
        if damage_bonus in ["+0", "0", ""]:
            return damage_dice
        connector = " + " if not damage_bonus.startswith(("-", "+")) else " "
        return f"{damage_dice}{connector}{damage_bonus}".strip()

    dice_part = dice_match.group(1)
    type_str = damage_dice[dice_match.end() :].replace("+", "").replace("-", "").strip()

    clean_bonus = damage_bonus.replace(" ", "")
    is_simple_bonus = re.match(r"^[+-]?\d+$", clean_bonus)

    if is_simple_bonus:
        try:
            bonus_val = int(clean_bonus)
        except ValueError:
            bonus_val = 0

        if bonus_val > 0:
            return f"{dice_part} + {bonus_val} {type_str}".strip()
        elif bonus_val < 0:
            return f"{dice_part} - {abs(bonus_val)} {type_str}".strip()
        else:
            return f"{dice_part} {type_str}".strip()
    else:
        if damage_bonus in ["+0", "0", ""]:
            return f"{dice_part} {type_str}".strip()
        connector = " + " if not damage_bonus.startswith(("-", "+")) else " "
        return f"{dice_part}{connector}{damage_bonus} {type_str}".strip()


def roll_dice(
    die_str: str, advantage: bool = False, disadvantage: bool = False
) -> Dict[str, Any]:
    """
    Parses and rolls dice notation (e.g. '1d20+5', '2d6-1', 'd8').
    Returns a dictionary with raw rolls, modifier, and total result.
    """
    clean_str = (die_str or "1d20").lower().strip().replace(" ", "")
    match = re.match(r"^(\d*)d(\d+)([+-]\d+)?$", clean_str)

    if not match:
        logger.warning(f"Invalid dice expression '{die_str}', defaulting to 1d20.")
        num_dice, sides, modifier = 1, 20, 0
    else:
        num_dice = int(match.group(1)) if match.group(1) else 1
        sides = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0

    rolls = []
    if sides == 20 and num_dice == 1 and (advantage or disadvantage):
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        rolls = [roll1, roll2]
        raw_val = (
            max(roll1, roll2) if advantage and not disadvantage else min(roll1, roll2)
        )
    else:
        rolls = [random.randint(1, sides) for _ in range(num_dice)]
        raw_val = sum(rolls)

    total = raw_val + modifier

    return {
        "expression": die_str,
        "num_dice": num_dice,
        "sides": sides,
        "modifier": modifier,
        "rolls": rolls,
        "raw_result": raw_val,
        "total": total,
        "is_nat20": (sides == 20 and raw_val == 20),
        "is_nat1": (sides == 20 and raw_val == 1),
    }
