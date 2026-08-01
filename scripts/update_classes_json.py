import glob
import json
import os

# Hardcoded data to move to JSON
class_data = {
    "artificer": {
        "caster_type": "half",
        "spellcasting_ability": "INT",
        "saving_throws": ["Constitution", "Intelligence"],
    },
    "barbarian": {"saving_throws": ["Strength", "Constitution"]},
    "bard": {
        "caster_type": "full",
        "spellcasting_ability": "CHA",
        "saving_throws": ["Dexterity", "Charisma"],
    },
    "cleric": {
        "caster_type": "full",
        "spellcasting_ability": "WIS",
        "saving_throws": ["Wisdom", "Charisma"],
    },
    "druid": {
        "caster_type": "full",
        "spellcasting_ability": "WIS",
        "saving_throws": ["Intelligence", "Wisdom"],
    },
    "fighter": {"saving_throws": ["Strength", "Constitution"]},
    "monk": {"saving_throws": ["Strength", "Dexterity"]},
    "paladin": {
        "caster_type": "half",
        "spellcasting_ability": "CHA",
        "saving_throws": ["Wisdom", "Charisma"],
    },
    "ranger": {
        "caster_type": "half",
        "spellcasting_ability": "WIS",
        "saving_throws": ["Strength", "Dexterity"],
    },
    "rogue": {"saving_throws": ["Dexterity", "Intelligence"]},
    "sorcerer": {
        "caster_type": "full",
        "spellcasting_ability": "CHA",
        "saving_throws": ["Constitution", "Charisma"],
    },
    "warlock": {
        "caster_type": "pact",
        "spellcasting_ability": "CHA",
        "saving_throws": ["Wisdom", "Charisma"],
    },
    "wizard": {
        "caster_type": "full",
        "spellcasting_ability": "INT",
        "saving_throws": ["Intelligence", "Wisdom"],
    },
}


def update_json_files(base_path):
    for year in ["2014", "2024"]:
        pattern = os.path.join(base_path, year, "*.json")
        for filepath in glob.glob(pattern):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            classname = data.get("class_name", "").lower()
            if classname in class_data:
                info = class_data[classname]

                # Add caster info
                if "caster_type" in info:
                    data["caster_type"] = info["caster_type"]
                if "spellcasting_ability" in info:
                    data["spellcasting_ability"] = info["spellcasting_ability"]

                # Add starting_proficiencies if missing
                if "starting_proficiencies" not in data:
                    data["starting_proficiencies"] = {}

                # Update saving throws
                if "saving_throws" not in data["starting_proficiencies"]:
                    data["starting_proficiencies"]["saving_throws"] = info["saving_throws"]

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            print(f"Updated {filepath}")


if __name__ == "__main__":
    update_json_files("data/rules/classes")
