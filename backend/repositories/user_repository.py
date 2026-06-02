import logging
from typing import Optional, List
from backend.core.db import get_db

logger = logging.getLogger("DnDAssistant.UserRepository")


class UserRepository:
    def __init__(self):
        self.db = get_db()
        self.collection = self.db["users"] if self.db is not None else None

    def list_all(self) -> List[dict]:
        if self.collection is None:
            return []
        try:
            users = list(self.collection.find({}, {"password_hash": 0}))
            for user in users:
                if "_id" in user:
                    user["_id"] = str(user["_id"])
            return users
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []

    def get_by_username(self, username: str) -> Optional[dict]:
        if self.collection is None:
            return None
        return self.collection.find_one({"username": username.strip().lower()})

    def delete(self, username: str) -> bool:
        if self.collection is None:
            return False
        try:
            result = self.collection.delete_one({"username": username.strip().lower()})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete user {username}: {e}")
            return False

    def update(self, username: str, update_data: dict) -> bool:
        if self.collection is None:
            return False
        try:
            result = self.collection.update_one(
                {"username": username.strip().lower()}, {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update user {username}: {e}")
            return False

    def count_all(self) -> int:
        if self.collection is None:
            return 0
        return self.collection.count_documents({})
