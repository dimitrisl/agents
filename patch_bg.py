import json

with open("data/rules/backgrounds_2024.json", "r") as f:
    data = json.load(f)

data.append(
    {
        "name": "Custom Background",
        "description": "A custom background with tailored proficiencies and origin feat.",
        "ability_scores": {
            "options": [["STR", "DEX", "CON", "INT", "WIS", "CHA"]],
            "description": "Increase three different scores by 1, or one by 2 and another by 1.",
        },
        "feat": "Any Origin Feat",
        "skills": ["Any Two Skills"],
        "tools": ["Any Tool"],
        "equipment": "50 GP",
    }
)

with open("data/rules/backgrounds_2024.json", "w") as f:
    json.dump(data, f, indent=4)
