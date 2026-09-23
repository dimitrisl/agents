import json

path = "data/rules/subclasses/2014/fighter.json"
with open(path, "r") as f:
    data = json.load(f)

steps = data["subclasses"]["Champion"]["scaling"]["improved_critical"]["steps"]
for s in steps:
    if s["level"] == 3:
        s["value"] = 19
    elif s["level"] == 15:
        s["value"] = 18

with open(path, "w") as f:
    json.dump(data, f, indent=4)
