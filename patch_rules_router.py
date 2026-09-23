path = "server/routers/rules_router.py"
with open(path, "r") as f:
    code = f.read()

# Replace response_model
code = code.replace(
    '@router.get("/classes/{class_name}/scaling", response_model=List[Dict[str, Any]])',
    '@router.get("/classes/{class_name}/scaling", response_model=Dict[str, Any])',
)

# Replace the loop and return
target = """    resolved_actions = []

    for action_id, action_def in scaling_dict.items():"""

replacement = """    resolved_actions = []
    cantripTier = 4 if level >= 17 else 3 if level >= 11 else 2 if level >= 5 else 1
    extraCritDice = 0
    critThreshold = 20

    for action_id, action_def in scaling_dict.items():"""

code = code.replace(target, replacement)


target2 = """        if "options" in action_def:
            action_payload["options"] = action_def["options"]

        resolved_actions.append(action_payload)

    return resolved_actions"""

replacement2 = """        if "options" in action_def:
            action_payload["options"] = action_def["options"]

        if action_def.get("extraCritDice"):
            extraCritDice = active_step.get("value", 0)

        if action_id == "improved_critical":
            critThreshold = active_step.get("value", 20)

        resolved_actions.append(action_payload)

    return {
        "actions": resolved_actions,
        "cantripTier": cantripTier,
        "extraCritDice": extraCritDice,
        "critThreshold": critThreshold
    }"""

code = code.replace(target2, replacement2)

with open(path, "w") as f:
    f.write(code)
