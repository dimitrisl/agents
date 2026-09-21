from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from backend.core.homebrew_schemas import (
    HomebrewFeat,
    HomebrewFeature,
    HomebrewItem,
    HomebrewSpell,
    HomebrewWeapon,
)
from backend.core.providers.factory import get_llm_provider


class HomebrewService:
    def __init__(self):
        self.provider = get_llm_provider()

    async def create_homebrew(
        self, db: AsyncIOMotorDatabase, campaign_id: str, dm_id: str, entity_data: Dict[str, Any]
    ) -> str:
        """Saves a fully structured homebrew entity to the database."""
        entity_data["campaign_id"] = campaign_id
        entity_data["creator_dm_id"] = dm_id

        # We don't want an _id from the user if it exists
        if "_id" in entity_data:
            del entity_data["_id"]

        result = await db["homebrew_content"].insert_one(entity_data)
        return str(result.inserted_id)

    async def get_campaign_homebrew(
        self, db: AsyncIOMotorDatabase, campaign_id: str, entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves all homebrew items for a specific campaign."""
        query = {"campaign_id": campaign_id}
        if entity_type:
            query["homebrew_type"] = entity_type

        cursor = db["homebrew_content"].find(query)
        items = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            items.append(doc)
        return items

    async def get_homebrew_item(
        self, db: AsyncIOMotorDatabase, item_id: str, campaign_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a single homebrew item by ID."""
        try:
            obj_id = ObjectId(item_id)
        except InvalidId:
            return None

        doc = await db["homebrew_content"].find_one({"_id": obj_id, "campaign_id": campaign_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def update_homebrew(
        self, db: AsyncIOMotorDatabase, item_id: str, campaign_id: str, update_data: Dict[str, Any]
    ) -> bool:
        """Updates an existing homebrew item, ensuring it belongs to the campaign."""
        if "_id" in update_data:
            del update_data["_id"]

        try:
            obj_id = ObjectId(item_id)
        except InvalidId:
            return False

        result = await db["homebrew_content"].update_one(
            {"_id": obj_id, "campaign_id": campaign_id}, {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete_homebrew(
        self, db: AsyncIOMotorDatabase, item_id: str, campaign_id: str
    ) -> bool:
        """Deletes a homebrew item, ensuring it belongs to the campaign."""
        try:
            obj_id = ObjectId(item_id)
        except InvalidId:
            return False

        result = await db["homebrew_content"].delete_one(
            {"_id": obj_id, "campaign_id": campaign_id}
        )
        return result.deleted_count > 0

    async def forge_with_ai(self, prompt: str, entity_type: str) -> Dict[str, Any]:
        """Uses LLM to generate a strictly typed structure for a homebrew item."""

        # Map the requested type to its Pydantic schema class
        schema_map = {
            "weapon": HomebrewWeapon,
            "item": HomebrewItem,
            "spell": HomebrewSpell,
            "feat": HomebrewFeat,
            "feature": HomebrewFeature,
        }

        target_schema = schema_map.get(entity_type)
        if not target_schema:
            raise ValueError(f"Invalid homebrew type: {entity_type}")

        system_instruction = (
            f"You are a D&D 5e mechanics expert. The user wants to homebrew a {entity_type}. "
            f"Parse their intent and output a strict JSON that matches the required schema. "
            f"Fill in appropriate balancing numbers (damage, weight, etc.) if they omitted them."
        )

        # We rely on the LLMProvider to generate JSON conforming to the schema
        response = self.provider.generate_json(
            prompt=prompt,
            schema=target_schema,
            system_instruction=system_instruction,
            temperature=0.4,
        )

        if isinstance(response, BaseModel):
            return response.model_dump()
        return response
