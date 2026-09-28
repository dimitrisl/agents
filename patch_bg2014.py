import json

with open("data/rules/backgrounds_2014.json", "r") as f:
    data = json.load(f)

data.append(
    {
        "name": "Custom Background",
        "description": "A custom background with tailored proficiencies.",
        "skills": ["Any Two Skills"],
        "tools": ["Any Two Tools or Languages"],
        "equipment": "15 GP",
    }
)

with open("data/rules/backgrounds_2014.json", "w") as f:
    json.dump(data, f, indent=4)
