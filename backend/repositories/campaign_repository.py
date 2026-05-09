import os
import json
import logging
from typing import List, Optional

logger = logging.getLogger("DnDAssistant.CampaignRepo")

DATA_DIR = "data"
CAMP_DIR = os.path.join(DATA_DIR, "campaigns")


class CampaignRepository:
    def __init__(self):
        os.makedirs(CAMP_DIR, exist_ok=True)

    def save(self, campaign_name: str, notes: str, party: List[str] = None) -> bool:
        """Save campaign notes and party list."""
        if not campaign_name:
            return False

        filename = f"{campaign_name.replace(' ', '_').lower()}.json"
        filepath = os.path.join(CAMP_DIR, filename)

        if party is None:
            existing = self.load(campaign_name)
            party = existing.get("party", []) if existing else []

        data = {
            "campaign_name": campaign_name,
            "notes": notes,
            "party": party,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Failed to save campaign: {e}")
            return False

    def load(self, name: str) -> Optional[dict]:
        """Load a campaign dictionary."""
        filename = f"{name.replace(' ', '_').lower()}.json"
        filepath = os.path.join(CAMP_DIR, filename)

        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load campaign: {e}")
            return None

    def list_all(self) -> List[str]:
        """Return a list of available campaign names."""
        os.makedirs(CAMP_DIR, exist_ok=True)
        camps = []
        for f in os.listdir(CAMP_DIR):
            if f.endswith(".json"):
                camps.append(f.replace(".json", "").replace("_", " ").title())
        return camps
