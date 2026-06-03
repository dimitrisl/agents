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
        owner_id: str = None,
        sessions: List[dict] = None,
        module_pdf_uri: str = None,
        extracted_npcs: List[dict] = None,
        vault_npcs: List[str] = None,
        roll_requests: List[dict] = None,
        invite_code: str = None,
        module_lore: str = None,
        whispers: List[dict] = None,
        google_doc_id: str = None,
        google_credentials_json: str = None,
    ) -> bool:
        """Save campaign notes and party list to MongoDB with edition tracking."""
        if self.collection is None:
            logger.error("Database connection missing. Cannot save campaign.")
            return False

        if not campaign_name:
            return False

        # Always try to load existing once if we need defaults
        existing = None
        needs_existing = (
            party is None
            or dnd_edition is None
            or sessions is None
            or extracted_npcs is None
            or module_pdf_uri is None
            or vault_npcs is None
            or roll_requests is None
            or invite_code is None
            or whispers is None
            or google_doc_id is None
            or google_credentials_json is None
        )
        if needs_existing:
            existing = self.load(campaign_name)

        if party is None:
            party = existing.get("party", []) if existing else []

        if dnd_edition is None:
            try:
                import streamlit as st

                dnd_edition = st.session_state.get("dnd_edition")
            except Exception:
                pass
            if not dnd_edition:
                dnd_edition = existing.get("dnd_edition") if existing else None
            if not dnd_edition:
                dnd_edition = "2014 Edition"

        if sessions is None:
            sessions = existing.get("sessions", []) if existing else []

        if extracted_npcs is None:
            extracted_npcs = existing.get("extracted_npcs", []) if existing else []

        if module_pdf_uri is None:
            module_pdf_uri = existing.get("module_pdf_uri") if existing else None

        if vault_npcs is None:
            vault_npcs = existing.get("vault_npcs", []) if existing else []

        if roll_requests is None:
            roll_requests = existing.get("roll_requests", []) if existing else []

        if invite_code is None:
            invite_code = existing.get("invite_code") if existing else None

        if module_lore is None:
            module_lore = existing.get("module_lore") if existing else None

        if whispers is None:
            whispers = existing.get("whispers", []) if existing else []

        if google_doc_id is None:
            google_doc_id = existing.get("google_doc_id") if existing else None

        if google_credentials_json is None:
            google_credentials_json = (
                existing.get("google_credentials_json") if existing else None
            )

        data = {
            "campaign_name": campaign_name,
            "notes": notes,
            "party": party,
            "dnd_edition": dnd_edition,
            "sessions": sessions,
            "module_pdf_uri": module_pdf_uri,
            "extracted_npcs": extracted_npcs,
            "vault_npcs": vault_npcs,
            "roll_requests": roll_requests,
            "invite_code": invite_code,
            "module_lore": module_lore,
            "whispers": whispers,
            "google_doc_id": google_doc_id,
            "google_credentials_json": google_credentials_json,
        }
        if owner_id:
            data["owner_id"] = owner_id

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

    def list_all(self, edition: str = None, owner_id: str = None) -> List[str]:
        """Return a list of available campaign names from MongoDB, filtered by edition and owner_id."""
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

        if owner_id:
            query["owner_id"] = owner_id

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

    def delete(self, campaign_name: str) -> bool:
        """Delete a campaign from MongoDB."""
        if self.collection is None:
            logger.error("Database connection missing. Cannot delete campaign.")
            return False

        if not campaign_name:
            return False

        # Clean the name if it was passed as a filename
        name = campaign_name.replace(".json", "").replace("_", " ").title()

        try:
            result = self.collection.delete_one(
                {"campaign_name": {"$regex": f"^{name}$", "$options": "i"}}
            )
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete campaign from MongoDB: {e}")
            return False

    def find_by_invite_code(self, invite_code: str) -> Optional[dict]:
        """Find a campaign by its invite code."""
        if self.collection is None:
            return None
        try:
            result = self.collection.find_one(
                {"invite_code": invite_code.strip().upper()}
            )
            if result:
                result.pop("_id", None)
            return result
        except Exception as e:
            logger.error(f"Failed to find campaign by invite code: {e}")
            return None

    def count_all(self, owner_id: str = None) -> int:
        if self.collection is None:
            return 0
        query = {}
        if owner_id:
            query["owner_id"] = owner_id
        return self.collection.count_documents(query)
