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


class TcpCanGateway:
    """USR-CAN115 TCP stream gateway. Stream reassembly is intentionally TCP-only."""

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
        self.allow_non_loopback = allow_non_loopback
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.reader_task: asyncio.Task[None] | None = None
        self.buffer = bytearray()

    async def connect(self) -> None:
        if self.writer:
            return
        if not self.allow_non_loopback and not ipaddress.ip_address(self.config.device_ip).is_loopback:
            raise RuntimeError("non-production TCP destination must use loopback")
        self.reader, self.writer = await asyncio.open_connection(
            self.config.device_ip, self.config.device_port
        )
        self.stats.transport_connected = True
        self.reader_task = asyncio.create_task(
            self._read_loop(), name=f"can-tcp-rx-{self.config.channel}"
        )

    async def disconnect(self) -> None:
        self.stats.transport_connected = False
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        self.reader_task = None
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.reader = None
        self.writer = None
        self.buffer.clear()

    async def _read_loop(self) -> None:
        assert self.reader is not None
        while True:
            chunk = await self.reader.read(4096)
            if not chunk:
                self.stats.transport_connected = False
                return
            self.buffer.extend(chunk)
            frames, self.buffer = self.codec.decode_stream(
                self.buffer,
                self.config.channel,
                "rx",
                f"{self.config.device_ip}:{self.config.device_port}",
            )
            received_monotonic = time.monotonic()
            for frame in frames:
                frame.received_at_monotonic = received_monotonic
                if frame.parse_status != "ok":
                    self.stats.record_protocol_error(frame)
                    continue
                self.stats.record_received(frame, received_monotonic)
                await self.on_frame(frame)

    async def send_frame(self, frame: CanFrame) -> None:
        await self.connect()
        assert self.writer is not None
        packet = self.codec.encode_frame(frame)
        frame.raw_packet = packet
        frame.direction = "tx"
        self.stats.record_tx(frame)
        self.writer.write(packet)
        await self.writer.drain()
        await self.on_frame(frame)
