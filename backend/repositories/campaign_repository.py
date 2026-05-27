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

    def save(
        self,
        campaign_name: str,
        notes: str,
        party: List[str] = None,
        dnd_edition: str = None,
    ) -> bool:
        """Save campaign notes and party list to MongoDB with edition tracking."""
        if self.collection is None:
            logger.error("Database connection missing. Cannot save campaign.")
            return False

        if not campaign_name:
            return False

        if party is None:
            existing = self.load(campaign_name)
            party = existing.get("party", []) if existing else []

        if dnd_edition is None:
            # Fallback: check streamlit session state or load existing
            try:
                import streamlit as st

                dnd_edition = st.session_state.get("dnd_edition")
            except Exception:
                pass
            if not dnd_edition:
                existing = self.load(campaign_name)
                if existing:
                    dnd_edition = existing.get("dnd_edition")
            if not dnd_edition:
                dnd_edition = "2014 Edition"

        data = {
            "campaign_name": campaign_name,
            "notes": notes,
            "party": party,
            "dnd_edition": dnd_edition,
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

    def list_all(self, edition: str = None) -> List[str]:
        """Return a list of available campaign names from MongoDB, filtered by edition."""
        if self.collection is None:
            return []

        if edition is None:
            # Fallback to streamlit session state if available
            try:
                import streamlit as st

                edition = st.session_state.get("dnd_edition")
            except Exception:
                pass

        query = {}
        if edition:
            is_2024 = "2024" in edition
            if is_2024:
                query["dnd_edition"] = {"$regex": "2024", "$options": "i"}
            else:
                # 2014 maps to either explicit 2014 or documents missing the edition field (legacy)
                query["$or"] = [
                    {"dnd_edition": {"$regex": "2014", "$options": "i"}},
                    {"dnd_edition": {"$exists": False}},
                    {"dnd_edition": None},
                ]

        try:
            camps = self.collection.find(query, {"campaign_name": 1})
            result = []
            for c in camps:
                if "campaign_name" in c:
                    result.append(c["campaign_name"])
            return result
        except Exception as e:
            logger.error(f"Failed to list campaigns from MongoDB: {e}")
            return []
