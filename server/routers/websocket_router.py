import json
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import unquote

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from server.dependencies.auth import get_current_user_from_token

logger = logging.getLogger("PhyrexianForge.WebSocket")

router = APIRouter(tags=["WebSockets"])


@dataclass
class CampaignConnection:
    """One live socket plus who is sitting behind it.

    The identity is what makes targeted delivery possible: a whisper meant for a
    single hero must not travel down every other player's socket just to be
    filtered away in their browser.
    """

    websocket: WebSocket
    role: str = "player"
    character: Optional[str] = None

    @property
    def is_dm(self) -> bool:
        return self.role == "dm"

    def is_character(self, names: Set[str]) -> bool:
        if not self.character:
            return False
        return self.character.strip().lower() in names


class ConnectionManager:
    def __init__(self):
        # Maps campaign_id -> List of active connections
        self.active_connections: Dict[str, List[CampaignConnection]] = {}

    async def connect(
        self,
        campaign_id: str,
        websocket: WebSocket,
        role: str = "player",
        character: Optional[str] = None,
    ) -> CampaignConnection:
        await websocket.accept()
        connection = CampaignConnection(websocket=websocket, role=role, character=character)
        self.active_connections.setdefault(campaign_id, []).append(connection)
        logger.info(
            f"WebSocket client connected to campaign channel '{campaign_id}' "
            f"(role={role}, character={character or '-'})"
        )
        return connection

    def disconnect(self, campaign_id: str, websocket: WebSocket):
        connections = self.active_connections.get(campaign_id)
        if connections is not None:
            self.active_connections[campaign_id] = [
                conn for conn in connections if conn.websocket is not websocket
            ]
            if not self.active_connections[campaign_id]:
                del self.active_connections[campaign_id]
        logger.info(f"WebSocket client disconnected from campaign channel '{campaign_id}'")

    async def broadcast(
        self,
        campaign_id: str,
        message: dict,
        characters: Optional[Iterable[str]] = None,
    ):
        """Fan a message out to a campaign room.

        `characters` restricts delivery to the named heroes. DM sockets always
        receive everything — the DM is the one running the table — while a socket
        that never announced a character only sees untargeted traffic.
        """
        campaign_id = unquote(campaign_id)
        connections = self.active_connections.get(campaign_id)
        if not connections:
            return

        targets: Optional[Set[str]] = None
        if characters is not None:
            targets = {name.strip().lower() for name in characters if name}

        dead_connections: List[CampaignConnection] = []
        for connection in list(connections):
            if targets is not None and not (connection.is_dm or connection.is_character(targets)):
                continue
            try:
                await connection.websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Error sending WebSocket message: {e}")
                dead_connections.append(connection)

        for connection in dead_connections:
            self.disconnect(campaign_id, connection.websocket)


manager = ConnectionManager()


@router.websocket("/ws/campaigns/{campaign_id}")
async def campaign_websocket_endpoint(
    websocket: WebSocket,
    campaign_id: str,
    token: str = Query(...),
    role: str = Query("player"),
    character: Optional[str] = Query(None),
):
    try:
        await get_current_user_from_token(token)
    except Exception as e:
        logger.warning(f"Unauthorized WebSocket connection attempt: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # FastAPI does not automatically URL-decode path parameters when they come
    # from a WebSocket URL constructed with encodeURIComponent() on the client.
    # Normalise here so the key always matches the plain campaign_name used
    # everywhere else (DB queries, broadcast calls in campaign_router).
    decoded_id = unquote(campaign_id)
    normalized_role = "dm" if role == "dm" else "player"

    await manager.connect(decoded_id, websocket, role=normalized_role, character=character)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                # Broadcast payload to all subscribers of this campaign room
                await manager.broadcast(decoded_id, payload)
            except Exception as e:
                logger.error(f"Invalid JSON frame received on WebSocket: {e}")
    except WebSocketDisconnect:
        manager.disconnect(decoded_id, websocket)
