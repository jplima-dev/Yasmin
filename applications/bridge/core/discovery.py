from __future__ import annotations

import asyncio
import json
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable


MAGIC = "BRIDGE_DISCOVERY_V1"
BROADCAST_INTERVAL = 4.0


class DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self, payload: Callable[[], dict[str, Any]]):
        self.payload = payload
        self.transport: asyncio.DatagramTransport | None = None
        self.peers: dict[str, dict[str, Any]] = {}

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            message = json.loads(data.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if message.get("magic") != MAGIC:
            return
        fingerprint = message.get("fingerprint")
        if fingerprint:
            self.peers[fingerprint] = {**message, "address": addr[0], "seen_at": time.time()}

    def broadcast(self, port: int) -> None:
        if not self.transport:
            return
        body = json.dumps({"magic": MAGIC, **self.payload()}).encode()
        self.transport.sendto(body, ("255.255.255.255", port))

    def current_peers(self) -> list[dict[str, Any]]:
        threshold = time.time() - BROADCAST_INTERVAL * 3
        return [peer for peer in self.peers.values() if peer["seen_at"] >= threshold]


@dataclass
class DiscoveryService:
    port: int
    payload: Callable[[], dict[str, Any]]
    protocol: DiscoveryProtocol | None = None
    task: asyncio.Task | None = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)
        sock.bind(("0.0.0.0", self.port))
        _, protocol = await loop.create_datagram_endpoint(
            lambda: DiscoveryProtocol(self.payload), sock=sock
        )
        self.protocol = protocol  # type: ignore[assignment]
        self.task = asyncio.create_task(self._broadcast_loop())

    async def _broadcast_loop(self) -> None:
        while True:
            assert self.protocol
            self.protocol.broadcast(self.port)
            await asyncio.sleep(BROADCAST_INTERVAL)

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.protocol and self.protocol.transport:
            self.protocol.transport.close()

    def peers(self) -> list[dict[str, Any]]:
        return self.protocol.current_peers() if self.protocol else []

