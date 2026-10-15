from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class EventHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, device_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[device_id].add(websocket)

    async def disconnect(self, device_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[device_id].discard(websocket)
            if not self._connections[device_id]:
                self._connections.pop(device_id, None)

    async def emit(self, device_id: str, event: dict[str, Any]) -> int:
        async with self._lock:
            connections = tuple(self._connections.get(device_id, ()))
        delivered = 0
        for connection in connections:
            try:
                await connection.send_json(event)
                delivered += 1
            except Exception:
                await self.disconnect(device_id, connection)
        return delivered

    async def broadcast(self, event: dict[str, Any]) -> None:
        async with self._lock:
            device_ids = tuple(self._connections)
        await asyncio.gather(*(self.emit(device_id, event) for device_id in device_ids), return_exceptions=True)

