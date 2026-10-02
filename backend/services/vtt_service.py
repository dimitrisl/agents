from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.schemas import VTTStateSchema, VTTTokenSchema


class VTTService:
    async def get_vtt_state(self, db: AsyncIOMotorDatabase, campaign_name: str) -> VTTStateSchema:
        campaign = await db.campaigns.find_one({"campaign_name": campaign_name})
        if campaign and "vtt_state" in campaign and campaign["vtt_state"]:
            return VTTStateSchema(**campaign["vtt_state"])
        return VTTStateSchema()

    async def save_vtt_state(
        self, db: AsyncIOMotorDatabase, campaign_name: str, state: VTTStateSchema
    ):
        await db.campaigns.update_one(
            {"campaign_name": campaign_name}, {"$set": {"vtt_state": state.model_dump()}}
        )

    async def toggle_vtt(
        self, db: AsyncIOMotorDatabase, campaign_name: str, is_active: bool
    ) -> VTTStateSchema:
        state = await self.get_vtt_state(db, campaign_name)
        state.is_active = is_active
        await self.save_vtt_state(db, campaign_name, state)
        return state

    async def move_token(
        self,
        db: AsyncIOMotorDatabase,
        campaign_name: str,
        token_id: str,
        x: int,
        y: int,
        role: str,
        character_name: Optional[str],
    ) -> VTTStateSchema:
        state = await self.get_vtt_state(db, campaign_name)

        for token in state.tokens:
            if token.id == token_id:
                # Validation: Only DM or the owning character can move the token
                if role == "dm" or (
                    character_name and token.name.lower() == character_name.lower()
                ):
                    token.x = x
                    token.y = y
                break

        await self.save_vtt_state(db, campaign_name, state)
        return state

    async def update_grid(
        self, db: AsyncIOMotorDatabase, campaign_name: str, grid_data: dict
    ) -> VTTStateSchema:
        state = await self.get_vtt_state(db, campaign_name)
        for k, v in grid_data.items():
            if hasattr(state.grid, k):
                setattr(state.grid, k, v)
        await self.save_vtt_state(db, campaign_name, state)
        return state

    async def add_token(
        self, db: AsyncIOMotorDatabase, campaign_name: str, token_data: dict
    ) -> VTTStateSchema:
        state = await self.get_vtt_state(db, campaign_name)
        token = VTTTokenSchema(**token_data)
        # Avoid duplicates
        state.tokens = [t for t in state.tokens if t.id != token.id]
        state.tokens.append(token)
        await self.save_vtt_state(db, campaign_name, state)
        return state

    async def remove_token(
        self, db: AsyncIOMotorDatabase, campaign_name: str, token_id: str
    ) -> VTTStateSchema:
        state = await self.get_vtt_state(db, campaign_name)
        state.tokens = [t for t in state.tokens if t.id != token_id]
        await self.save_vtt_state(db, campaign_name, state)
        return state
