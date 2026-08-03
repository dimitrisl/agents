import json
import re

try:
    with open(
        "/home/dimitrisl/.gemini/antigravity/brain/c402d456-7d30-4080-b032-961e6926f46a/.system_generated/steps/247/content.md",
        "r",
    ) as f:
        content = f.read()

    # Find the JSON array part
    match = re.search(r"\[\{.*\}\]", content, re.DOTALL)
    if match:
        json_str = match.group(0)
        issues = json.loads(json_str)
        print(f"Found {len(issues)} issues:")
        for issue in issues:
            number = issue.get("number")
            title = issue.get("title")
            state = issue.get("state")
            labels = [label.get("name") for label in issue.get("labels", [])]
            print(f"#{number} - {title} [{state}] (Labels: {', '.join(labels)})")
    else:
        print("Could not find JSON array in the file.")
except Exception as e:
    print(f"Error: {e}")
