import json
import logging
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("PhyrexianForge.WebSocket")

router = APIRouter(tags=["WebSockets"])


class ConnectionManager:
    def __init__(self):
        # Maps campaign_id -> List of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, campaign_id: str, websocket: WebSocket):
        await websocket.accept()
        if campaign_id not in self.active_connections:
            self.active_connections[campaign_id] = []
        self.active_connections[campaign_id].append(websocket)
        logger.info(f"WebSocket client connected to campaign channel '{campaign_id}'")

    def disconnect(self, campaign_id: str, websocket: WebSocket):
        if campaign_id in self.active_connections:
            if websocket in self.active_connections[campaign_id]:
                self.active_connections[campaign_id].remove(websocket)
            if not self.active_connections[campaign_id]:
                del self.active_connections[campaign_id]
        logger.info(f"WebSocket client disconnected from campaign channel '{campaign_id}'")

    async def broadcast(self, campaign_id: str, message: dict):
        if campaign_id in self.active_connections:
            for connection in self.active_connections[campaign_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Error sending WebSocket message: {e}")


manager = ConnectionManager()


@router.websocket("/ws/campaigns/{campaign_id}")
async def campaign_websocket_endpoint(websocket: WebSocket, campaign_id: str):
    await manager.connect(campaign_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                # Broadcast payload to all subscribers of this campaign room
                await manager.broadcast(campaign_id, payload)
            except Exception as e:
                logger.error(f"Invalid JSON frame received on WebSocket: {e}")
    except WebSocketDisconnect:
        manager.disconnect(campaign_id, websocket)
