import json
import logging
from datetime import date, datetime

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class _SafeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime, bytes, and other non-serializable types."""

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        if isinstance(o, bytes):
            return o.decode("utf-8", errors="replace")
        try:
            return super().default(o)
        except TypeError:
            return str(o)


class ConnectionManager:
    """Manages WebSocket connections to Tauri frontend clients."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send a JSON message to all connected clients."""
        data = json.dumps(message, cls=_SafeEncoder)
        disconnected = []
        for conn in self.active_connections:
            try:
                await conn.send_text(data)
            except Exception:
                disconnected.append(conn)
        for conn in disconnected:
            self.disconnect(conn)

    async def send_to(self, websocket: WebSocket, message: dict):
        """Send a JSON message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send to client: {e}")
            self.disconnect(websocket)

    async def handle_command(self, data: dict, websocket: WebSocket):
        """Handle a command received from the Tauri frontend."""
        cmd = data.get("command")
        logger.info(f"Received command: {cmd}")

        match cmd:
            case "ping":
                await self.send_to(websocket, {"type": "pong"})
            case "subscribe":
                # Client wants to receive pipeline events
                await self.send_to(websocket, {"type": "subscribed", "ok": True})
            case _:
                logger.warning(f"Unknown command: {cmd}")

    async def shutdown(self):
        """Close all connections on shutdown."""
        for conn in self.active_connections:
            try:
                await conn.close()
            except Exception:
                pass
        self.active_connections.clear()
