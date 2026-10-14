import logging
import random
import re
from typing import Any, Dict

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


def roll_dice(die_str: str, advantage: bool = False, disadvantage: bool = False) -> Dict[str, Any]:
    """
    Parses and rolls dice notation (e.g. '1d20+5', '2d6-1', 'd8', '2d6 + 1d4 + 3').
    Returns a dictionary with raw rolls, modifier, and total result.
    """
    raw_str = (die_str or "1d20").lower().strip()
    dice_matches = list(re.finditer(r"([+-]?)\s*(\d*)d(\d+)", raw_str))

    if not dice_matches:
        logger.warning(f"Invalid dice expression '{die_str}', defaulting to 1d20.")
        num_dice, sides, modifier = 1, 20, 0
        total_dice_count = 1
        raw_val = random.randint(1, 20)
        rolls = [raw_val]
    else:
        first_num_dice = int(dice_matches[0].group(2)) if dice_matches[0].group(2) else 1
        sides = int(dice_matches[0].group(3))
        total_dice_count = 0

        if advantage and disadvantage:
            advantage = False
            disadvantage = False

        if (
            sides == 20
            and len(dice_matches) == 1
            and first_num_dice == 1
            and (advantage or disadvantage)
        ):
            roll1 = random.randint(1, 20)
            roll2 = random.randint(1, 20)
            rolls = [roll1, roll2]
            raw_val = max(roll1, roll2) if advantage and not disadvantage else min(roll1, roll2)
            total_dice_count = 1
        else:
            rolls = []
            raw_val = 0
            for m in dice_matches:
                sign = -1 if m.group(1) == "-" else 1
                n = int(m.group(2)) if m.group(2) else 1
                s = int(m.group(3))
                total_dice_count += n
                for _ in range(n):
                    r = random.randint(1, s)
                    rolls.append(r)
                    raw_val += sign * r

        # Extract standalone modifiers
        remaining = re.sub(r"([+-]?)\s*(\d*)d(\d+)", "", raw_str)
        mod_matches = re.findall(r"([+-]?\s*\d+)", remaining)
        modifier = 0
        for mod_str in mod_matches:
            mod_clean = mod_str.replace(" ", "")
            if mod_clean:
                try:
                    modifier += int(mod_clean)
                except ValueError:
                    pass

        is_compound = len(dice_matches) > 1
        num_dice = total_dice_count if is_compound else first_num_dice

    total = raw_val + modifier

    return {
        "expression": die_str,
        "num_dice": num_dice,
        "sides": sides,
        "modifier": modifier,
        "rolls": rolls,
        "raw_result": raw_val,
        "total": total,
        "is_nat20": (sides == 20 and total_dice_count == 1 and raw_val == 20),
        "is_nat1": (sides == 20 and total_dice_count == 1 and raw_val == 1),
    }
