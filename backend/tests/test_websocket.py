import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.websocket.manager import ConnectionManager

@pytest.fixture
def manager():
    return ConnectionManager()

@pytest.fixture
def mock_websocket():
    ws = AsyncMock()
    # Mock the send_text method to complete immediately
    ws.send_text = AsyncMock()
    ws.accept = AsyncMock()
    return ws

@pytest.mark.asyncio
async def test_websocket_connect(manager, mock_websocket):
    await manager.connect(mock_websocket)
    mock_websocket.accept.assert_called_once()
    assert manager.connection_count == 1
    assert mock_websocket in manager._connections

@pytest.mark.asyncio
async def test_websocket_disconnect(manager, mock_websocket):
    await manager.connect(mock_websocket)
    assert manager.connection_count == 1
    await manager.disconnect(mock_websocket)
    assert manager.connection_count == 0

@pytest.mark.asyncio
async def test_websocket_broadcast(manager, mock_websocket):
    ws2 = AsyncMock()
    await manager.connect(mock_websocket)
    await manager.connect(ws2)
    
    await manager.broadcast("test_event", {"foo": "bar"})
    
    # Verify both received the exact same serialized payload
    import json
    expected_payload = json.dumps({"event": "test_event", "data": {"foo": "bar"}})
    mock_websocket.send_text.assert_called_once_with(expected_payload)
    ws2.send_text.assert_called_once_with(expected_payload)

@pytest.mark.asyncio
async def test_websocket_broadcast_removes_dead_connections(manager, mock_websocket):
    ws_dead = AsyncMock()
    ws_dead.send_text.side_effect = Exception("Connection closed")
    
    await manager.connect(mock_websocket)
    await manager.connect(ws_dead)
    assert manager.connection_count == 2
    
    await manager.broadcast("ping")
    
    # The dead connection should be pruned
    assert manager.connection_count == 1
    assert mock_websocket in manager._connections
    assert ws_dead not in manager._connections

@pytest.mark.asyncio
async def test_websocket_send_to(manager, mock_websocket):
    await manager.send_to(mock_websocket, "direct", "message")
    import json
    expected = json.dumps({"event": "direct", "data": "message"})
    mock_websocket.send_text.assert_called_once_with(expected)
