from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
from typing import Any

from fastapi import WebSocket


LOGGER = logging.getLogger(__name__)


@dataclass
class _Client:
    websocket: WebSocket
    topics: set[str] = field(default_factory=set)
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=256))
    sender: asyncio.Task[None] | None = None
    dropped: int = 0


class WebSocketManager:
    """Topic-aware fan-out that isolates CAN ingestion from slow renderer clients.

    Messages are put into a bounded queue per client. A client that cannot consume a
    sustained stream is disconnected rather than holding up CAN receive, signal decode,
    persistence, or the remaining clients.
    """

    def __init__(self, *, client_queue_size: int = 256, disconnect_after_drops: int = 32) -> None:
        self.client_queue_size = client_queue_size
        self.disconnect_after_drops = disconnect_after_drops
        self.clients: dict[WebSocket, _Client] = {}

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        client = _Client(websocket=ws, queue=asyncio.Queue(maxsize=self.client_queue_size))
        client.sender = asyncio.create_task(self._sender(client), name="websocket-client-sender")
        self.clients[ws] = client

    def disconnect(self, ws: WebSocket) -> None:
        client = self.clients.pop(ws, None)
        if client and client.sender and not client.sender.done():
            client.sender.cancel()

    async def subscribe(self, ws: WebSocket, topics: list[str]) -> None:
        client = self.clients.get(ws)
        if client:
            client.topics.update(topic for topic in topics if isinstance(topic, str) and topic)

    async def unsubscribe(self, ws: WebSocket, topics: list[str]) -> None:
        client = self.clients.get(ws)
        if client:
            client.topics.difference_update(topics)

    def has_subscribers(self, topic: str) -> bool:
        return any(topic in client.topics or "*" in client.topics for client in self.clients.values())

    async def broadcast(self, topic: str, payload: Any) -> None:
        if not self.clients or not self.has_subscribers(topic):
            return
        message = json.dumps({"topic": topic, "payload": payload}, ensure_ascii=False, default=str)
        overloaded: list[WebSocket] = []
        for ws, client in list(self.clients.items()):
            if topic not in client.topics and "*" not in client.topics:
                continue
            try:
                client.queue.put_nowait(message)
            except asyncio.QueueFull:
                client.dropped += 1
                if client.dropped >= self.disconnect_after_drops:
                    overloaded.append(ws)
        for ws in overloaded:
            await self._close_slow_client(ws)

    async def _sender(self, client: _Client) -> None:
        try:
            while True:
                message = await client.queue.get()
                try:
                    await client.websocket.send_text(message)
                    client.dropped = 0
                finally:
                    client.queue.task_done()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.disconnect(client.websocket)

    async def _close_slow_client(self, ws: WebSocket) -> None:
        client = self.clients.get(ws)
        if not client:
            return
        self.disconnect(ws)
        try:
            await asyncio.wait_for(ws.close(code=1013, reason="slow websocket client"), timeout=0.15)
        except Exception:
            pass
        LOGGER.warning("Disconnected slow WebSocket client after queue overflow")

    def snapshot(self) -> dict[str, int]:
        return {
            "clients": len(self.clients),
            "subscribed_clients": sum(1 for client in self.clients.values() if client.topics),
            "queue_depth": sum(client.queue.qsize() for client in self.clients.values()),
            "queue_capacity": len(self.clients) * self.client_queue_size,
            "dropped_messages": sum(client.dropped for client in self.clients.values()),
        }


manager = WebSocketManager()
