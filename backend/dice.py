import random
import re


def roll_dice(dice_str: str):
    """
    Parses and rolls dice strings like '1d20+5' or '2d8-2'.
    Returns a dictionary with details.
    """
    # Clean string
    dice_str = dice_str.lower().replace(" ", "")

    # Regex to match X d Y (+/-) Z
    match = re.match(r"(\d+)d(\d+)([+-]\d+)?", dice_str)
    if not match:
        return {"error": "Invalid dice format. Use e.g., 1d20+5"}

    num_dice = int(match.group(1))
    sides = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0

    rolls = [random.randint(1, sides) for _ in range(num_dice)]
    total = sum(rolls) + modifier

    return {
        "rolls": rolls,
        "modifier": modifier,
        "total": total,
        "result_text": f"{rolls} + {modifier} = {total}"
        if modifier != 0
        else f"{rolls} = {total}",
    }


def quick_roll(sides: int, modifier: int = 0):
    """Simple 1dX+modifier roll."""
    res = random.randint(1, sides)
    return res + modifier, res
