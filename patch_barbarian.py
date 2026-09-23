import json
import os

for path in ["data/rules/classes/2014/barbarian.json", "data/rules/classes/2024/barbarian.json"]:
    if not os.path.exists(path):
        continue
    with open(path, "r") as f:
        data = json.load(f)

    if "scaling" in data and "brutal_critical" in data["scaling"]:
        steps = data["scaling"]["brutal_critical"]["steps"]
        for s in steps:
            if s["level"] == 9:
                s["value"] = 1
            elif s["level"] == 13:
                s["value"] = 2
            elif s["level"] == 17:
                s["value"] = 3
    elif "scaling" in data and "brutal_strike" in data["scaling"]:
        # Wait, does Barbarian 2024 have brutal critical or brutal strike?
        pass

    with open(path, "w") as f:
        json.dump(data, f, indent=4)
