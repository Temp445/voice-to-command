"""
ACE Voice Controller — WebSocket Connection Manager
Manages real-time event broadcasting to all connected Tauri frontends.
"""

import asyncio
from typing import Any
from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info(f"WS client connected. Total: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections = [c for c in self._connections if c != websocket]
        logger.info(f"WS client disconnected. Total: {len(self._connections)}")

    async def broadcast(self, event: str, data: Any = None) -> None:
        """Broadcast a typed event to all connected clients."""
        payload = {"event": event, "data": data}
        dead: list[WebSocket] = []

        async with self._lock:
            connections = list(self._connections)

        for ws in connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        # Prune dead connections
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)

    async def send_to(self, websocket: WebSocket, event: str, data: Any = None) -> None:
        """Send a targeted event to one client."""
        try:
            await websocket.send_json({"event": event, "data": data})
        except Exception as e:
            logger.warning(f"Failed to send to WS client: {e}")

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton instance shared across all routers
ws_manager = ConnectionManager()
