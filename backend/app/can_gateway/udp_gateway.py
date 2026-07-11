from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
from collections.abc import Awaitable, Callable

from app.core.config import ChannelConfig

from .models import CanFrame
from .statistics import ChannelStats
from .usr_can115 import UsrCan115Codec

LOGGER = logging.getLogger(__name__)


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, gateway: "UdpCanGateway") -> None:
        self.gateway = gateway

    def datagram_received(self, data: bytes, addr) -> None:
        self.gateway.on_datagram(data, f"{addr[0]}:{addr[1]}")

    def error_received(self, exc: Exception) -> None:
        LOGGER.warning("UDP error on %s: %s", self.gateway.config.channel, exc)


class UdpCanGateway:
    def __init__(
        self,
        config: ChannelConfig,
        on_frame: Callable[[CanFrame], Awaitable[None]],
        *,
        online_timeout_seconds: float = 2.0,
        allow_non_loopback: bool = False,
    ) -> None:
        self.config = config
        self.on_frame = on_frame
        self.codec = UsrCan115Codec()
        self.stats = ChannelStats(config.channel, online_timeout_seconds=online_timeout_seconds)
        self.transport: asyncio.DatagramTransport | None = None
        self.queue: asyncio.Queue[CanFrame] = asyncio.Queue(maxsize=config.receive_queue_size)
        self.worker_task: asyncio.Task[None] | None = None
        self.allow_non_loopback = allow_non_loopback
        self.stats.set_queue_depth(0, self.queue.maxsize)

    async def connect(self) -> None:
        if self.transport:
            return
        self._validate_network_boundary()
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _Protocol(self),
            local_addr=(self.config.local_ip, self.config.local_receive_port),
        )
        self.transport = transport
        self.stats.transport_connected = True
        self.worker_task = asyncio.create_task(
            self._process_queue(), name=f"can-rx-{self.config.channel}"
        )

    async def disconnect(self) -> None:
        self.stats.transport_connected = False
        if self.transport:
            self.transport.close()
        self.transport = None
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        self.worker_task = None
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break
        self.stats.set_queue_depth(0, self.queue.maxsize)

    def on_datagram(self, data: bytes, source: str) -> None:
        received_monotonic = time.monotonic()
        try:
            frames = self.codec.decode_datagram(data, self.config.channel, source)
        except ValueError:
            self.stats.record_malformed_datagram()
            LOGGER.warning(
                "discard malformed UDP datagram channel=%s bytes=%s source=%s",
                self.config.channel,
                len(data),
                source,
            )
            return
        for frame in frames:
            frame.received_at_monotonic = received_monotonic
            if frame.parse_status != "ok":
                self.stats.record_protocol_error(frame)
                continue
            self.stats.record_received(frame, received_monotonic)
            try:
                self.queue.put_nowait(frame)
            except asyncio.QueueFull:
                self.stats.record_queue_drop()
        self.stats.set_queue_depth(self.queue.qsize(), self.queue.maxsize)

    async def _process_queue(self) -> None:
        max_age_seconds = self.config.max_frame_age_ms / 1000
        while True:
            frame = await self.queue.get()
            self.stats.set_queue_depth(self.queue.qsize(), self.queue.maxsize)
            try:
                if time.monotonic() - frame.received_at_monotonic > max_age_seconds:
                    self.stats.record_stale_drop()
                    continue
                await self.on_frame(frame)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.stats.processing_errors += 1
                self.stats.error_count += 1
                LOGGER.exception("CAN frame processing failed on %s", self.config.channel)
            finally:
                self.queue.task_done()
                self.stats.set_queue_depth(self.queue.qsize(), self.queue.maxsize)

    async def send_frame(self, frame: CanFrame) -> None:
        await self.connect()
        self._validate_network_boundary()
        packet = self.codec.encode_frame(frame)
        frame.raw_packet = packet
        frame.direction = "tx"
        self.stats.record_tx(frame)
        port = self.config.simulated_device_port or self.config.device_port
        assert self.transport is not None
        self.transport.sendto(packet, (self.config.device_ip, port))
        await self.on_frame(frame)

    def _validate_network_boundary(self) -> None:
        if self.allow_non_loopback:
            return
        if not ipaddress.ip_address(self.config.local_ip).is_loopback:
            raise RuntimeError("non-production UDP bind must use loopback")
        if not ipaddress.ip_address(self.config.device_ip).is_loopback:
            raise RuntimeError("non-production UDP destination must use loopback")
