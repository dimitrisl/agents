import datetime
import inspect
import logging
import uuid
from typing import Any, List, Optional

from backend.core.schemas import (
    VTTFogSchema,
    VTTGridSchema,
    VTTStateSchema,
    VTTTokenSchema,
)

logger = logging.getLogger("PhyrexianForge.VTTService")


async def _maybe_await(val: Any) -> Any:
    if inspect.isawaitable(val):
        return await val
    return val


class _AsyncMockFacade:
    def __init__(self, coll):
        self._coll = coll

    async def find_one(self, *args, **kwargs):
        return self._coll.find_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._coll.update_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._coll.insert_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._coll.delete_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._coll.count_documents(*args, **kwargs)

    def find(self, *args, **kwargs):
        return self._coll.find(*args, **kwargs)


def _col(db: Any, name: str) -> Any:
    if hasattr(db, "__getitem__"):
        try:
            return db[name]
        except Exception:
            pass
    col = getattr(db, name, None)
    if col is not None:
        return col

    if hasattr(db, "campaigns"):
        camp_col = getattr(db, "campaigns")
        underlying = getattr(camp_col, "_coll", None)
        if underlying is not None and hasattr(underlying, "database"):
            mock_db_inst = underlying.database
            new_coll = mock_db_inst[name]
            facade = _AsyncMockFacade(new_coll)
            try:
                setattr(db, name, facade)
            except Exception:
                pass
            return facade
    return None


class VTTService:
    @staticmethod
    def remap_fog_indices(
        revealed: List[int],
        old_width: int,
        old_height: int,
        new_width: int,
        new_height: int,
    ) -> List[int]:
        """Remap revealed cell indices when grid width or height changes."""
        if old_width <= 0 or new_width <= 0 or new_height <= 0:
            return []
        if old_width == new_width and old_height == new_height:
            return [idx for idx in revealed if 0 <= idx < new_width * new_height]

        remapped = []
        seen = set()
        for idx in revealed:
            if idx < 0:
                continue
            x = idx % old_width
            y = idx // old_width
            if 0 <= x < new_width and 0 <= y < new_height:
                new_idx = y * new_width + x
                if new_idx not in seen:
                    seen.add(new_idx)
                    remapped.append(new_idx)
        return remapped

    @staticmethod
    def redact_for_player(
        state: VTTStateSchema, player_character_name: Optional[str] = None
    ) -> VTTStateSchema:
        """Return a copy of the state without DM-only (hidden) tokens and with unrevealed fog filtered."""
        redacted = state.model_copy(deep=True)
        visible_tokens = [t for t in redacted.tokens if not t.is_hidden]

        if redacted.fog and redacted.fog.enabled:
            revealed_set = set(redacted.fog.revealed or [])
            width = max(1, redacted.grid.width or 30)
            height = max(1, redacted.grid.height or 30)
            cell_size = max(1, redacted.grid.cell_size or 50)
            player_norm = (player_character_name or "").strip().lower()

            fog_filtered = []
            for token in visible_tokens:
                # Player's own token is always visible to them
                if player_norm and token.name.strip().lower() == player_norm:
                    fog_filtered.append(token)
                    continue

                start_col = int(token.x) // cell_size
                start_row = int(token.y) // cell_size
                scale = max(1, int(token.size or 1))

                is_revealed = False
                for dy in range(scale):
                    for dx in range(scale):
                        cx = start_col + dx
                        cy = start_row + dy
                        if 0 <= cx < width and 0 <= cy < height:
                            cell_idx = cy * width + cx
                            if cell_idx in revealed_set:
                                is_revealed = True
                                break
                    if is_revealed:
                        break

                if is_revealed:
                    fog_filtered.append(token)

            visible_tokens = fog_filtered

        redacted.tokens = visible_tokens
        return redacted

    async def _ensure_state(self, db: Any, campaign_name: str) -> Optional[str]:
        """Ensure campaign has active_scene_id and a valid scene in campaign_scenes.
        Performs lazy migration of legacy inline grid/tokens into a Default scene."""
        camp = await _maybe_await(_col(db, "campaigns").find_one({"campaign_name": campaign_name}))
        if not camp or not isinstance(camp, dict):
            # Campaign doesn't exist yet or is a bare mock
            return None

        vtt_st = camp.get("vtt_state") or {}
        active_scene_id = vtt_st.get("active_scene_id")

        if active_scene_id:
            scene = await _maybe_await(
                _col(db, "campaign_scenes").find_one({"scene_id": active_scene_id})
            )
            if isinstance(scene, dict):
                return active_scene_id

        # Check if any scene already exists for this campaign
        first_scene = await _maybe_await(
            _col(db, "campaign_scenes").find_one({"campaign_name": campaign_name})
        )
        if isinstance(first_scene, dict):
            scene_id = first_scene["scene_id"]
            has_dict = isinstance(camp.get("vtt_state"), dict)
            update_body = (
                {
                    "$set": {
                        "vtt_state.active_scene_id": scene_id,
                        "vtt_state.is_active": vtt_st.get("is_active", False),
                    }
                }
                if has_dict
                else {
                    "$set": {
                        "vtt_state": {
                            "active_scene_id": scene_id,
                            "is_active": vtt_st.get("is_active", False),
                        }
                    }
                }
            )
            await _maybe_await(
                _col(db, "campaigns").update_one(
                    {"campaign_name": campaign_name},
                    update_body,
                )
            )
            return scene_id

        # Migrate legacy vtt_state to "Default" scene
        scene_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)
        grid_dict = vtt_st.get("grid") or VTTGridSchema().model_dump()
        tokens_list = vtt_st.get("tokens") or []
        default_scene = {
            "scene_id": scene_id,
            "campaign_name": campaign_name,
            "name": "Default",
            "dm_notes": "",
            "grid": grid_dict,
            "tokens": tokens_list,
            "fog": VTTFogSchema().model_dump(),
            "order": 0,
            "created_at": now,
            "updated_at": now,
            "last_activated_at": now,
        }
        await _maybe_await(_col(db, "campaign_scenes").insert_one(default_scene))
        has_dict = isinstance(camp.get("vtt_state"), dict)
        update_body = (
            {
                "$set": {
                    "vtt_state.active_scene_id": scene_id,
                    "vtt_state.is_active": vtt_st.get("is_active", False),
                }
            }
            if has_dict
            else {
                "$set": {
                    "vtt_state": {
                        "active_scene_id": scene_id,
                        "is_active": vtt_st.get("is_active", False),
                    }
                }
            }
        )
        await _maybe_await(
            _col(db, "campaigns").update_one(
                {"campaign_name": campaign_name},
                update_body,
            )
        )
        return scene_id

    async def get_vtt_state(self, db: Any, campaign_name: str) -> VTTStateSchema:
        """Returns the hydrated VTTStateSchema for the active scene."""
        active_scene_id = await self._ensure_state(db, campaign_name)
        camp = await _maybe_await(_col(db, "campaigns").find_one({"campaign_name": campaign_name}))
        is_active = False
        if isinstance(camp, dict) and camp.get("vtt_state"):
            is_active = bool(camp["vtt_state"].get("is_active", False))

        if active_scene_id:
            scene = await _maybe_await(
                _col(db, "campaign_scenes").find_one({"scene_id": active_scene_id})
            )
            if isinstance(scene, dict):
                return VTTStateSchema(
                    is_active=is_active,
                    active_scene_id=active_scene_id,
                    scene_name=scene.get("name", "Default"),
                    grid=VTTGridSchema(**(scene.get("grid") or {})),
                    tokens=[VTTTokenSchema(**t) for t in (scene.get("tokens") or [])],
                    fog=VTTFogSchema(**(scene.get("fog") or {})),
                )

        # Fallback for mock environments without scenes
        if isinstance(camp, dict) and camp.get("vtt_state"):
            try:
                st = VTTStateSchema(**camp["vtt_state"])
                st.is_active = is_active
                return st
            except Exception:
                pass
        return VTTStateSchema(is_active=is_active)

    async def toggle_vtt(self, db: Any, campaign_name: str, is_active: bool) -> VTTStateSchema:
        active_scene_id = await self._ensure_state(db, campaign_name)
        camp = await _maybe_await(_col(db, "campaigns").find_one({"campaign_name": campaign_name}))
        has_dict = isinstance(camp.get("vtt_state") if isinstance(camp, dict) else None, dict)
        update_body = (
            {"$set": {"vtt_state.is_active": is_active}}
            if has_dict
            else {
                "$set": {"vtt_state": {"is_active": is_active, "active_scene_id": active_scene_id}}
            }
        )
        await _maybe_await(
            _col(db, "campaigns").update_one(
                {"campaign_name": campaign_name},
                update_body,
            )
        )
        return await self.get_vtt_state(db, campaign_name)

    async def move_token(
        self,
        db: Any,
        campaign_name: str,
        token_id: str,
        x: int,
        y: int,
        role: str,
        character_name: Optional[str],
    ) -> VTTStateSchema:
        state = await self.get_vtt_state(db, campaign_name)
        can_move = False
        for token in state.tokens:
            if token.id == token_id:
                can_move = role == "dm" or bool(
                    character_name and token.name.lower() == character_name.lower()
                )
                break

        if can_move:
            active_scene_id = state.active_scene_id
            if active_scene_id:
                await _maybe_await(
                    _col(db, "campaign_scenes").update_one(
                        {"scene_id": active_scene_id, "tokens.id": token_id},
                        {"$set": {"tokens.$.x": x, "tokens.$.y": y}},
                    )
                )
            else:
                await _maybe_await(
                    _col(db, "campaigns").update_one(
                        {"campaign_name": campaign_name, "vtt_state.tokens.id": token_id},
                        {"$set": {"vtt_state.tokens.$.x": x, "vtt_state.tokens.$.y": y}},
                    )
                )

        return await self.get_vtt_state(db, campaign_name)

    async def update_grid(self, db: Any, campaign_name: str, grid_data: dict) -> VTTStateSchema:
        allowed = VTTGridSchema.model_fields.keys()
        provided = {k: v for k, v in grid_data.items() if k in allowed}
        validated = VTTGridSchema(**provided).model_dump(include=set(provided))

        if validated:
            active_scene_id = await self._ensure_state(db, campaign_name)
            if active_scene_id:
                scene = await _maybe_await(
                    _col(db, "campaign_scenes").find_one({"scene_id": active_scene_id})
                )
                if isinstance(scene, dict):
                    old_grid = scene.get("grid") or {}
                    old_w = old_grid.get("width", 30)
                    old_h = old_grid.get("height", 30)
                    new_w = validated.get("width", old_w)
                    new_h = validated.get("height", old_h)

                    update_dict = {f"grid.{k}": v for k, v in validated.items()}
                    if old_w != new_w or old_h != new_h:
                        cur_fog = (scene.get("fog") or {}).get("revealed", [])
                        remapped = self.remap_fog_indices(cur_fog, old_w, old_h, new_w, new_h)
                        update_dict["fog.revealed"] = remapped

                    await _maybe_await(
                        _col(db, "campaign_scenes").update_one(
                            {"scene_id": active_scene_id},
                            {"$set": update_dict},
                        )
                    )
            else:
                await _maybe_await(
                    _col(db, "campaigns").update_one(
                        {"campaign_name": campaign_name},
                        {"$set": {f"vtt_state.grid.{k}": v for k, v in validated.items()}},
                    )
                )

        return await self.get_vtt_state(db, campaign_name)

    async def add_token(self, db: Any, campaign_name: str, token_data: dict) -> VTTStateSchema:
        token = VTTTokenSchema(**token_data)
        active_scene_id = await self._ensure_state(db, campaign_name)

        if active_scene_id:
            replaced = await _maybe_await(
                _col(db, "campaign_scenes").update_one(
                    {"scene_id": active_scene_id, "tokens.id": token.id},
                    {"$set": {"tokens.$": token.model_dump()}},
                )
            )
            matched = getattr(replaced, "matched_count", 0) if replaced else 0
            if matched == 0:
                await _maybe_await(
                    _col(db, "campaign_scenes").update_one(
                        {"scene_id": active_scene_id, "tokens.id": {"$ne": token.id}},
                        {"$push": {"tokens": token.model_dump()}},
                    )
                )
        else:
            replaced = await _maybe_await(
                _col(db, "campaigns").update_one(
                    {"campaign_name": campaign_name, "vtt_state.tokens.id": token.id},
                    {"$set": {"vtt_state.tokens.$": token.model_dump()}},
                )
            )
            matched = getattr(replaced, "matched_count", 0) if replaced else 0
            if matched == 0:
                await _maybe_await(
                    _col(db, "campaigns").update_one(
                        {"campaign_name": campaign_name, "vtt_state.tokens.id": {"$ne": token.id}},
                        {"$push": {"vtt_state.tokens": token.model_dump()}},
                    )
                )

        return await self.get_vtt_state(db, campaign_name)

    async def remove_token(self, db: Any, campaign_name: str, token_id: str) -> VTTStateSchema:
        active_scene_id = await self._ensure_state(db, campaign_name)
        if active_scene_id:
            await _maybe_await(
                _col(db, "campaign_scenes").update_one(
                    {"scene_id": active_scene_id},
                    {"$pull": {"tokens": {"id": token_id}}},
                )
            )
        else:
            await _maybe_await(
                _col(db, "campaigns").update_one(
                    {"campaign_name": campaign_name},
                    {"$pull": {"vtt_state.tokens": {"id": token_id}}},
                )
            )
        return await self.get_vtt_state(db, campaign_name)

    # -------------------------------------------------------------
    # Fog of War Operations (#157)
    # -------------------------------------------------------------
    def _extract_valid_cell_indices(self, payload: dict, width: int, height: int) -> List[int]:
        """Extract and validate cell indices from cells [[x,y], ...] or rect {x,y,w,h}."""
        cells = payload.get("cells")
        rect = payload.get("rect")
        extracted_coords = []

        if cells and isinstance(cells, list):
            for c in cells:
                if isinstance(c, (list, tuple)) and len(c) >= 2:
                    extracted_coords.append((int(c[0]), int(c[1])))

        if rect and isinstance(rect, dict):
            rx = int(rect.get("x", 0))
            ry = int(rect.get("y", 0))
            rw = int(rect.get("w", 0))
            rh = int(rect.get("h", 0))
            for dy in range(rh):
                for dx in range(rw):
                    extracted_coords.append((rx + dx, ry + dy))

        if len(extracted_coords) > 2500:
            raise ValueError("Fog update exceeds maximum limit of 2500 cells per event")

        indices = []
        seen = set()
        for x, y in extracted_coords:
            if x < 0 or x >= width or y < 0 or y >= height:
                raise ValueError(
                    f"Cell coordinates ({x}, {y}) out of grid bounds ({width}x{height})"
                )
            idx = y * width + x
            if idx not in seen:
                seen.add(idx)
                indices.append(idx)

        return indices

    async def toggle_fog(self, db: Any, campaign_name: str, enabled: bool) -> VTTStateSchema:
        active_scene_id = await self._ensure_state(db, campaign_name)
        if active_scene_id:
            await _maybe_await(
                _col(db, "campaign_scenes").update_one(
                    {"scene_id": active_scene_id},
                    {"$set": {"fog.enabled": bool(enabled)}},
                )
            )
        return await self.get_vtt_state(db, campaign_name)

    async def reveal_fog(self, db: Any, campaign_name: str, payload: dict) -> VTTStateSchema:
        state = await self.get_vtt_state(db, campaign_name)
        indices = self._extract_valid_cell_indices(payload, state.grid.width, state.grid.height)
        if indices and state.active_scene_id:
            await _maybe_await(
                _col(db, "campaign_scenes").update_one(
                    {"scene_id": state.active_scene_id},
                    {"$addToSet": {"fog.revealed": {"$each": indices}}},
                )
            )
        return await self.get_vtt_state(db, campaign_name)

    async def hide_fog(self, db: Any, campaign_name: str, payload: dict) -> VTTStateSchema:
        state = await self.get_vtt_state(db, campaign_name)
        indices = self._extract_valid_cell_indices(payload, state.grid.width, state.grid.height)
        if indices and state.active_scene_id:
            await _maybe_await(
                _col(db, "campaign_scenes").update_one(
                    {"scene_id": state.active_scene_id},
                    {"$pull": {"fog.revealed": {"$in": indices}}},
                )
            )
        return await self.get_vtt_state(db, campaign_name)

    async def reveal_all_fog(self, db: Any, campaign_name: str) -> VTTStateSchema:
        state = await self.get_vtt_state(db, campaign_name)
        if state.active_scene_id:
            all_indices = list(range(state.grid.width * state.grid.height))
            await _maybe_await(
                _col(db, "campaign_scenes").update_one(
                    {"scene_id": state.active_scene_id},
                    {"$set": {"fog.revealed": all_indices}},
                )
            )
        return await self.get_vtt_state(db, campaign_name)

    async def hide_all_fog(self, db: Any, campaign_name: str) -> VTTStateSchema:
        state = await self.get_vtt_state(db, campaign_name)
        if state.active_scene_id:
            await _maybe_await(
                _col(db, "campaign_scenes").update_one(
                    {"scene_id": state.active_scene_id},
                    {"$set": {"fog.revealed": []}},
                )
            )
        return await self.get_vtt_state(db, campaign_name)
