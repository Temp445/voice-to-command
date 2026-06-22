"""
ACE Voice Controller — WebSocket Connection Manager
Manages real-time event broadcasting to all connected Tauri frontends.

Optimizations:
- Parallel broadcast: all clients receive events simultaneously via asyncio.gather
- Non-blocking: lock only used for list mutation, never during send
- Per-client timeout: a stalled client never blocks other clients
"""

import asyncio
import json
from typing import Any
from fastapi import WebSocket
from loguru import logger

# Max time (seconds) to wait for a single client send before treating it as dead
_SEND_TIMEOUT = 2.0


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
        """
        Broadcast a typed event to ALL connected clients SIMULTANEOUSLY.
        Uses asyncio.gather so all clients get the event at the same time
        instead of one by one. Dead connections are pruned automatically.
        """
        if not self._connections:
            return

        # Pre-serialize once — avoids re-encoding the same JSON N times
        payload_str = json.dumps({"event": event, "data": data})

        # Snapshot the connections list without holding the lock during sends
        async with self._lock:
            connections = list(self._connections)

        async def _send_one(ws: WebSocket):
            try:
                await asyncio.wait_for(ws.send_text(payload_str), timeout=_SEND_TIMEOUT)
            except Exception as e:
                logger.error(f"Error: {e}")
                return ws  # Mark as dead
            return None

        # Fire all sends in parallel — all clients receive simultaneously
        results = await asyncio.gather(*(_send_one(ws) for ws in connections))

        # Prune any dead connections
        dead = [ws for ws in results if ws is not None]
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)

    async def send_to(self, websocket: WebSocket, event: str, data: Any = None) -> None:
        """Send a targeted event to one specific client."""
        try:
            payload_str = json.dumps({"event": event, "data": data})
            await asyncio.wait_for(
                websocket.send_text(payload_str), timeout=_SEND_TIMEOUT
            )
        except Exception as e:
            logger.warning(f"Failed to send to WS client: {e}")

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton instance shared across all routers
ws_manager = ConnectionManager()
