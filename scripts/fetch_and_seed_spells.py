import os
import json
import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("SpellsFetcher")

# Add project path to sys.path
sys.path.append(os.getcwd())

from backend.core.db import get_db  # noqa: E402

DATA_DIR = os.path.join("data", "rules")
os.makedirs(DATA_DIR, exist_ok=True)

SPELLS_2014_PATH = os.path.join(DATA_DIR, "spells_2014.json")
SPELLS_2024_PATH = os.path.join(DATA_DIR, "spells_2024.json")

# Source files from the brain directory
SRC_2014_PATH = "/home/dimitrisl/.gemini/antigravity/brain/126f0792-a258-4531-b029-13c6eea74525/.system_generated/steps/183/content.md"
SRC_2024_PATH = "/home/dimitrisl/.gemini/antigravity/brain/126f0792-a258-4531-b029-13c6eea74525/.system_generated/steps/155/content.md"


def load_json_from_step_file(filepath):
    logger.info(f"Loading raw content from {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find where the JSON starts (usually after "---" or with "[")
    json_lines = []
    started = False
    for line in lines:
        if not started:
            if line.strip() == "---" or line.strip().startswith("["):
                started = True
                if line.strip().startswith("["):
                    json_lines.append(line)
            continue
        json_lines.append(line)

    json_str = "".join(json_lines).strip()
    return json.loads(json_str)


def process_2014_spells():
    raw_spells = load_json_from_step_file(SRC_2014_PATH)
    logger.info(f"Normalizing {len(raw_spells)} spells from 2014 SRD data...")

    normalized_spells = []
    for spell in raw_spells:
        # Determine level
        lvl_str = str(spell.get("level", "0")).lower()
        level = 0 if "cantrip" in lvl_str else int(lvl_str) if lvl_str.isdigit() else 0

        # Casting time / Action type
        ct = spell.get("casting_time", "1 action").lower()
        if "bonus action" in ct:
            action_type = "bonusAction"
        elif "reaction" in ct:
            action_type = "reaction"
        else:
            action_type = "action"

        # Components
        comp_dict = spell.get("components", {})
        components = []
        if comp_dict.get("verbal"):
            components.append("v")
        if comp_dict.get("somatic"):
            components.append("s")
        if comp_dict.get("material"):
            components.append("m")

        materials = None
        if comp_dict.get("materials_needed"):
            materials = ", ".join(comp_dict.get("materials_needed", []))

        # Concentration
        duration = spell.get("duration", "Instantaneous")
        concentration = "concentration" in duration.lower()

        normalized = {
            "name": spell.get("name"),
            "level": level,
            "school": spell.get("school", "Unknown").lower(),
            "classes": [c.lower() for c in spell.get("classes", [])],
            "actionType": action_type,
            "concentration": concentration,
            "ritual": spell.get("ritual", False),
            "range": spell.get("range", "Touch"),
            "components": components,
            "material": materials,
            "duration": duration,
            "description": spell.get("description", ""),
            "higherLevelSlot": spell.get("higher_levels"),
            "castingTime": spell.get("casting_time", "1 action"),
            "edition": "2014",
        }
        normalized_spells.append(normalized)

    return normalized_spells


def process_2024_spells():
    raw_spells = load_json_from_step_file(SRC_2024_PATH)
    logger.info(f"Normalizing {len(raw_spells)} spells from 2024 Gist data...")

    normalized_spells = []
    for spell in raw_spells:
        normalized = {
            "name": spell.get("name"),
            "level": spell.get("level", 0),
            "school": spell.get("school", "Unknown").lower(),
            "classes": [c.lower() for c in spell.get("classes", [])],
            "actionType": spell.get("actionType", "action"),
            "concentration": spell.get("concentration", False),
            "ritual": spell.get("ritual", False),
            "range": spell.get("range", "Touch"),
            "components": [c.lower() for c in spell.get("components", [])],
            "material": spell.get("material"),
            "duration": spell.get("duration", "Instantaneous"),
            "description": spell.get("description", ""),
            "higherLevelSlot": spell.get("higherLevelSlot"),
            "castingTime": spell.get("castingTime", "1 action"),
            "edition": "2024",
        }
        normalized_spells.append(normalized)

    return normalized_spells


def seed_to_mongodb(spells_data):
    db = get_db()
    if db is None:
        logger.warning("MongoDB connection is not available. Skipping database seed.")
        return False

    collection = db["spells"]
    logger.info(f"Seeding {len(spells_data)} spells to MongoDB 'spells' collection...")

    inserted = 0
    updated = 0
    for spell in spells_data:
        try:
            result = collection.update_one(
                {"name": spell["name"], "edition": spell["edition"]},
                {"$set": spell},
                upsert=True,
            )
            if result.matched_count > 0:
                updated += 1
            else:
                inserted += 1
        except Exception as e:
            logger.error(f"Error seeding spell '{spell['name']}': {e}")

    logger.info(
        f"Seeding completed. Inserted: {inserted}, Updated/Upserted: {updated} spells."
    )
    return True


def main():
    # 1. 2014 spells
    spells_2014 = process_2014_spells()
    logger.info(f"Saving 2014 spells to {SPELLS_2014_PATH}...")
    with open(SPELLS_2014_PATH, "w", encoding="utf-8") as f:
        json.dump(spells_2014, f, indent=4)

    # 2. 2024 spells
    spells_2024 = process_2024_spells()
    logger.info(f"Saving 2024 spells to {SPELLS_2024_PATH}...")
    with open(SPELLS_2024_PATH, "w", encoding="utf-8") as f:
        json.dump(spells_2024, f, indent=4)

    # 3. Seed MongoDB
    all_spells = spells_2014 + spells_2024
    seed_to_mongodb(all_spells)
    logger.info("Spells processing and seeding complete!")


if __name__ == "__main__":
    main()
