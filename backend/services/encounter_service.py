from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

XP_THRESHOLDS = {
    1: {"easy": 25, "medium": 50, "hard": 75, "deadly": 100},
    2: {"easy": 50, "medium": 100, "hard": 150, "deadly": 200},
    3: {"easy": 75, "medium": 150, "hard": 225, "deadly": 400},
    4: {"easy": 125, "medium": 250, "hard": 375, "deadly": 500},
    5: {"easy": 250, "medium": 500, "hard": 750, "deadly": 1100},
    6: {"easy": 300, "medium": 600, "hard": 900, "deadly": 1400},
    7: {"easy": 350, "medium": 750, "hard": 1100, "deadly": 1700},
    8: {"easy": 450, "medium": 900, "hard": 1400, "deadly": 2100},
    9: {"easy": 500, "medium": 1050, "hard": 1600, "deadly": 2400},
    10: {"easy": 600, "medium": 1200, "hard": 1900, "deadly": 2800},
    11: {"easy": 800, "medium": 1600, "hard": 2400, "deadly": 3600},
    12: {"easy": 1000, "medium": 2000, "hard": 3000, "deadly": 4500},
    13: {"easy": 1100, "medium": 2200, "hard": 3400, "deadly": 5100},
    14: {"easy": 1250, "medium": 2500, "hard": 3800, "deadly": 5700},
    15: {"easy": 1400, "medium": 2800, "hard": 4300, "deadly": 6400},
    16: {"easy": 1600, "medium": 3200, "hard": 4800, "deadly": 7200},
    17: {"easy": 2000, "medium": 3900, "hard": 5900, "deadly": 8800},
    18: {"easy": 2100, "medium": 4200, "hard": 6300, "deadly": 9500},
    19: {"easy": 2400, "medium": 4900, "hard": 7300, "deadly": 10900},
    20: {"easy": 2800, "medium": 5700, "hard": 8500, "deadly": 12700},
}

CR_XP_MAP = {
    "0": 10,
    "1/8": 25,
    "1/4": 50,
    "1/2": 100,
    "1": 200,
    "2": 450,
    "3": 700,
    "4": 1100,
    "5": 1800,
    "6": 2300,
    "7": 2900,
    "8": 3900,
    "9": 5000,
    "10": 5900,
    "11": 7200,
    "12": 8400,
    "13": 10000,
    "14": 11500,
    "15": 13000,
    "16": 15000,
    "17": 18000,
    "18": 20000,
    "19": 22000,
    "20": 25000,
    "21": 33000,
    "22": 41000,
    "23": 50000,
    "24": 62000,
    "25": 75000,
    "26": 90000,
    "27": 105000,
    "28": 120000,
    "29": 135000,
    "30": 155000,
}


def estimate_cr_from_hp(hp: int) -> str:
    if hp <= 6:
        return "0"
    if hp <= 35:
        return "1/8"
    if hp <= 49:
        return "1/4"
    if hp <= 70:
        return "1/2"
    if hp <= 85:
        return "1"
    if hp <= 100:
        return "2"
    if hp <= 115:
        return "3"
    if hp <= 130:
        return "4"
    if hp <= 145:
        return "5"
    if hp <= 160:
        return "6"
    if hp <= 175:
        return "7"
    if hp <= 190:
        return "8"
    if hp <= 205:
        return "9"
    if hp <= 220:
        return "10"
    if hp <= 235:
        return "11"
    if hp <= 250:
        return "12"
    if hp <= 265:
        return "13"
    if hp <= 280:
        return "14"
    if hp <= 295:
        return "15"
    if hp <= 310:
        return "16"
    if hp <= 325:
        return "17"
    if hp <= 340:
        return "18"
    if hp <= 355:
        return "19"
    if hp <= 400:
        return "20"
    return "21"


def get_encounter_multiplier(num_monsters: int) -> float:
    if num_monsters <= 0:
        return 1.0
    if num_monsters == 1:
        return 1.0
    if num_monsters == 2:
        return 1.5
    if 3 <= num_monsters <= 6:
        return 2.0
    if 7 <= num_monsters <= 10:
        return 2.5
    if 11 <= num_monsters <= 14:
        return 3.0
    return 4.0


async def calculate_danger_indicator(
    combatants: List[Dict[str, Any]], db: AsyncIOMotorDatabase
) -> str:
    """
    Calculates the danger indicator for an encounter asynchronously by fetching character levels from DB.
    """
    if not combatants:
        return "Trivial"

    heroes = []
    enemies = []

    for combatant in combatants:
        # Check if they are dead. We only consider conscious/alive combatants for danger levels.
        # But wait, if someone is dead, the encounter shouldn't instantly become easy!
        # Actually, standard D&D calculates encounter difficulty BEFORE the fight starts, assuming all are max HP.
        # So we should include everyone.

        is_player = combatant.get("is_player", False)

        if is_player:
            heroes.append(combatant)
        else:
            enemies.append(combatant)

    if not heroes or not enemies:
        return "Trivial"

    party_thresholds = {"easy": 0, "medium": 0, "hard": 0, "deadly": 0}

    # Pre-fetch all heroes from DB to get their levels
    char_ids = [h.get("char_id") for h in heroes if h.get("char_id")]
    char_docs = []
    if char_ids:
        cursor = db["characters"].find({"char_id": {"$in": char_ids}})
        char_docs = await cursor.to_list(length=100)

    char_level_map = {doc["char_id"]: doc.get("char_level", 1) for doc in char_docs}

    for hero in heroes:
        char_id = hero.get("char_id")
        level = char_level_map.get(char_id, 1) if char_id else 1
        level = max(1, min(20, int(level)))

        for k in party_thresholds:
            party_thresholds[k] += XP_THRESHOLDS[level][k]

    enemy_base_xp = 0
    num_enemies = len(enemies)

    for enemy in enemies:
        # Estimate CR from Max HP
        max_hp = enemy.get("max_hp", 10)
        cr_str = estimate_cr_from_hp(max_hp)
        enemy_base_xp += CR_XP_MAP.get(cr_str, 50)

    multiplier = get_encounter_multiplier(num_enemies)

    if len(heroes) < 3:
        tiers = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
        try:
            idx = tiers.index(multiplier)
            multiplier = tiers[min(len(tiers) - 1, idx + 1)]
        except ValueError:
            pass
    elif len(heroes) > 5:
        tiers = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
        try:
            idx = tiers.index(multiplier)
            multiplier = tiers[max(0, idx - 1)]
        except ValueError:
            pass

    adjusted_enemy_xp = enemy_base_xp * multiplier

    if adjusted_enemy_xp < party_thresholds["easy"]:
        return "Trivial"
    elif adjusted_enemy_xp < party_thresholds["medium"]:
        return "Easy"
    elif adjusted_enemy_xp < party_thresholds["hard"]:
        return "Medium"
    elif adjusted_enemy_xp < party_thresholds["deadly"]:
        return "Hard"
    else:
        return "Deadly"
