import os
import logging
from typing import List, Optional
from backend.core.db import get_db

logger = logging.getLogger("DnDAssistant.CampaignRepo")

DATA_DIR = "data"
CAMP_DIR = os.path.join(DATA_DIR, "campaigns")


class CampaignRepository:
    def __init__(self):
        self.db = get_db()
        if self.db is not None:
            self.collection = self.db["campaigns"]
        else:
            self.collection = None

    def save(self, campaign_name: str, notes: str, party: List[str] = None) -> bool:
        """Save campaign notes and party list to MongoDB."""
        if self.collection is None:
            logger.error("Database connection missing. Cannot save campaign.")
            return False

        if not campaign_name:
            return False

        # In mongo we can just identify campaigns by name
        # We will use lowercased name as an internal key or just search by name
        if party is None:
            existing = self.load(campaign_name)
            party = existing.get("party", []) if existing else []

        data = {
            "campaign_name": campaign_name,
            "notes": notes,
            "party": party,
        }

        try:
            self.collection.update_one(
                {"campaign_name": campaign_name}, {"$set": data}, upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save campaign to MongoDB: {e}")
            return False

    def load(self, name: str) -> Optional[dict]:
        """Load a campaign dictionary from MongoDB."""
        if self.collection is None:
            return None

        # Clean the name if it was passed as a filename
        name = name.replace(".json", "").replace("_", " ").title()

        try:
            # Try to find by exact name (case-insensitive search would be better, but we assume exact for now)
            # Actually, let's do a case-insensitive regex search just in case
            data = self.collection.find_one(
                {"campaign_name": {"$regex": f"^{name}$", "$options": "i"}}
            )
            if data and "_id" in data:
                del data["_id"]
            return data
        except Exception as e:
            logger.error(f"Failed to load campaign from MongoDB: {e}")
            return None

    def list_all(self) -> List[str]:
        """Return a list of available campaign names from MongoDB."""
        if self.collection is None:
            return []

        try:
            camps = self.collection.find({}, {"campaign_name": 1})
            result = []
            for c in camps:
                if "campaign_name" in c:
                    result.append(c["campaign_name"])
            return result
        except Exception as e:
            logger.error(f"Failed to list campaigns from MongoDB: {e}")
            return []
