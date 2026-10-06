from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.schemas import VTTGridSchema, VTTStateSchema, VTTTokenSchema


class VTTService:
    @staticmethod
    def redact_for_player(state: VTTStateSchema) -> VTTStateSchema:
        """Return a copy of the state without DM-only (hidden) tokens."""
        redacted = state.model_copy(deep=True)
        redacted.tokens = [t for t in redacted.tokens if not t.is_hidden]
        return redacted

    async def _ensure_state(self, db: AsyncIOMotorDatabase, campaign_name: str) -> None:
        """Campaigns are stored with `vtt_state: null` until first use; Mongo refuses
        dotted writes into a null field, so materialise the default state first."""
        await db.campaigns.update_one(
            {"campaign_name": campaign_name, "vtt_state": None},
            {"$set": {"vtt_state": VTTStateSchema().model_dump()}},
        )

    async def get_vtt_state(self, db: AsyncIOMotorDatabase, campaign_name: str) -> VTTStateSchema:
        campaign = await db.campaigns.find_one({"campaign_name": campaign_name})
        if campaign and "vtt_state" in campaign and campaign["vtt_state"]:
            return VTTStateSchema(**campaign["vtt_state"])
        return VTTStateSchema()

    async def toggle_vtt(
        self, db: AsyncIOMotorDatabase, campaign_name: str, is_active: bool
    ) -> VTTStateSchema:
        await self._ensure_state(db, campaign_name)
        await db.campaigns.update_one(
            {"campaign_name": campaign_name}, {"$set": {"vtt_state.is_active": is_active}}
        )
        return await self.get_vtt_state(db, campaign_name)

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

        # Validation: Only DM or the owning character can move the token
        can_move = False
        for token in state.tokens:
            if token.id == token_id:
                can_move = role == "dm" or bool(
                    character_name and token.name.lower() == character_name.lower()
                )
                break

        if can_move:
            await db.campaigns.update_one(
                {"campaign_name": campaign_name, "vtt_state.tokens.id": token_id},
                {"$set": {"vtt_state.tokens.$.x": x, "vtt_state.tokens.$.y": y}},
            )

        return await self.get_vtt_state(db, campaign_name)

    async def update_grid(
        self, db: AsyncIOMotorDatabase, campaign_name: str, grid_data: dict
    ) -> VTTStateSchema:
        # Validate through the schema so types are coerced/rejected, and only
        # touch the fields the client actually sent.
        allowed = VTTGridSchema.model_fields.keys()
        provided = {k: v for k, v in grid_data.items() if k in allowed}
        validated = VTTGridSchema(**provided).model_dump(include=set(provided))

        if validated:
            await self._ensure_state(db, campaign_name)
            await db.campaigns.update_one(
                {"campaign_name": campaign_name},
                {"$set": {f"vtt_state.grid.{k}": v for k, v in validated.items()}},
            )
        return await self.get_vtt_state(db, campaign_name)

    async def add_token(
        self, db: AsyncIOMotorDatabase, campaign_name: str, token_data: dict
    ) -> VTTStateSchema:
        token = VTTTokenSchema(**token_data)
        await self._ensure_state(db, campaign_name)

        # Replace in place if a token with this id already exists...
        replaced = await db.campaigns.update_one(
            {"campaign_name": campaign_name, "vtt_state.tokens.id": token.id},
            {"$set": {"vtt_state.tokens.$": token.model_dump()}},
        )
        # ...otherwise append, guarded so concurrent adds cannot create duplicates.
        if replaced.matched_count == 0:
            await db.campaigns.update_one(
                {"campaign_name": campaign_name, "vtt_state.tokens.id": {"$ne": token.id}},
                {"$push": {"vtt_state.tokens": token.model_dump()}},
            )
        return await self.get_vtt_state(db, campaign_name)

    async def remove_token(
        self, db: AsyncIOMotorDatabase, campaign_name: str, token_id: str
    ) -> VTTStateSchema:
        await self._ensure_state(db, campaign_name)
        await db.campaigns.update_one(
            {"campaign_name": campaign_name}, {"$pull": {"vtt_state.tokens": {"id": token_id}}}
        )
        return await self.get_vtt_state(db, campaign_name)
