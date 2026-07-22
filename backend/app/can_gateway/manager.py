from __future__ import annotations
import asyncio
from collections import Counter, deque
from collections.abc import Awaitable, Callable
import time
from app.core.config import RuntimeConfig
from .models import CanFrame
from .udp_gateway import UdpCanGateway
from .tcp_gateway import TcpCanGateway

class CanGatewayManager:
    def __init__(
        self,
        config: RuntimeConfig,
        on_frame: Callable[[CanFrame], Awaitable[None]],
        on_security_event: Callable[[dict], None] | None = None,
    ) -> None:
        self.config = config
        self.on_frame = on_frame
        # Keep a bounded diagnostic window per channel. One noisy channel must not evict
        # the other channel's recent evidence or inflate renderer memory without limit.
        self.recent_by_channel: dict[str, deque[CanFrame]] = {
            channel.channel: deque(maxlen=channel.recent_buffer_size) for channel in config.channels
        }
        self.recent_frames: deque[CanFrame] = deque(maxlen=min(20_000, sum(channel.recent_buffer_size for channel in config.channels)))
        self._pipeline_capacity = max(
            1024, min(16_384, sum(channel.receive_queue_size for channel in config.channels) * 4)
        )
        self._pipeline: asyncio.Queue[CanFrame] = asyncio.Queue(maxsize=self._pipeline_capacity)
        self._pipeline_depths: Counter[str] = Counter()
        self._pipeline_task: asyncio.Task[None] | None = None
        self._stopping = False
        self._batch_size = 256
        self._critical_ids = {0x51, 0x77, 0x100, 0x102, 0x121, 0x168, 0xE1, 0x703, 0x704}
        self.gateways = {}
        for channel in config.channels:
            common = {
                "online_timeout_seconds": config.channel_online_timeout_seconds,
                "allow_non_loopback": config.profile == "production",
            }
            if channel.protocol.lower() == "udp":
                gateway = UdpCanGateway(
                    channel,
                    self._enqueue_frame,
                    on_security_event=on_security_event,
                    **common,
                )
            elif channel.protocol.lower() == "tcp":
                gateway = TcpCanGateway(channel, self._enqueue_frame, **common)
            else:
                raise ValueError(f"unsupported CAN transport: {channel.protocol}")
            self.gateways[channel.channel] = gateway
        self.latest_frames: dict[str, dict] = {}

    async def start_all(self) -> None:
        self._stopping = False
        if not self._pipeline_task or self._pipeline_task.done():
            self._pipeline_task = asyncio.create_task(
                self._process_pipeline(), name="can-frame-pipeline"
            )
        for channel in self.gateways:
            await self.start_channel(channel)

    async def stop_all(self) -> None:
        for gateway in self.gateways.values():
            await gateway.disconnect()
        self._stopping = True
        if self._pipeline_task:
            self._pipeline_task.cancel()
            try:
                await self._pipeline_task
            except asyncio.CancelledError:
                pass
        self._pipeline_task = None
        self._pipeline_depths.clear()
        while not self._pipeline.empty():
            try:
                self._pipeline.get_nowait()
                self._pipeline.task_done()
            except asyncio.QueueEmpty:
                break
        self._refresh_pipeline_stats()

    async def start_channel(self, channel: str) -> dict:
        if not self._pipeline_task or self._pipeline_task.done():
            self._stopping = False
            self._pipeline_task = asyncio.create_task(
                self._process_pipeline(), name="can-frame-pipeline"
            )
        await self.gateways[channel].connect()
        return self.gateways[channel].stats.snapshot()

    async def stop_channel(self, channel: str) -> dict:
        await self.gateways[channel].disconnect()
        return self.gateways[channel].stats.snapshot()

    async def send_frame(self, channel: str, frame: CanFrame) -> None:
        if frame.can_id not in self.config.allowed_tx_can_ids:
            raise PermissionError(f"CAN ID {frame.can_id_hex} is disabled by the runtime safety profile")
        if channel != self.config.control_channel:
            raise PermissionError(f"control transmission is restricted to {self.config.control_channel}")
        await self.gateways[channel].send_frame(frame)

    async def _enqueue_frame(self, frame: CanFrame) -> None:
        """Bound the work after transport receipt without losing safety-critical frames first.

        Gateways update their receive timestamps before this method is called.  Therefore a
        stalled application pipeline cannot make a stale source look fresh to an interlock.
        Non-critical telemetry is shed under sustained pressure; critical feedback waits for
        capacity and is still subject to the per-channel max-frame-age check in the worker.
        """
        gateway = self.gateways.get(frame.channel)
        if self._pipeline.full():
            if frame.can_id not in self._critical_ids:
                if gateway:
                    gateway.stats.record_pipeline_drop()
                self._refresh_pipeline_stats()
                return
            # Preserve feedback used by the safety interlock. This waits for one bounded
            # queue slot rather than spawning unbounded work.
            await self._pipeline.put(frame)
        else:
            self._pipeline.put_nowait(frame)
        self._pipeline_depths[frame.channel] += 1
        self._refresh_pipeline_stats()

    async def _process_pipeline(self) -> None:
        while True:
            first = await self._pipeline.get()
            batch = [first]
            try:
                while len(batch) < self._batch_size:
                    try:
                        batch.append(self._pipeline.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                for frame in batch:
                    self._pipeline_depths[frame.channel] = max(0, self._pipeline_depths[frame.channel] - 1)
                    gateway = self.gateways.get(frame.channel)
                    max_age = (gateway.config.max_frame_age_ms / 1000) if gateway else 0.5
                    if frame.received_at_monotonic and asyncio.get_running_loop().time() - frame.received_at_monotonic > max_age:
                        if gateway:
                            gateway.stats.record_stale_drop()
                        continue
                    try:
                        await self.on_frame(frame)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        if gateway:
                            gateway.stats.processing_errors += 1
                            gateway.stats.error_count += 1
            finally:
                for _ in batch:
                    self._pipeline.task_done()
                self._refresh_pipeline_stats()

    def _refresh_pipeline_stats(self) -> None:
        for channel, gateway in self.gateways.items():
            gateway.stats.set_pipeline_queue(
                self._pipeline_depths.get(channel, 0), self._pipeline_capacity
            )

    def record_recent(self, frame: CanFrame) -> None:
        self.recent_frames.appendleft(frame)
        self.recent_by_channel.setdefault(frame.channel, deque(maxlen=10_000)).appendleft(frame)
        key = f"{frame.channel}:{frame.can_id:X}"
        now = frame.timestamp_ns / 1_000_000_000
        previous = self.latest_frames.get(key)
        first_seen = previous["first_seen"] if previous else now
        frame_count = int(previous["frame_count"]) + 1 if previous else 1
        period_ms = round((now - float(previous["last_seen"])) * 1000, 1) if previous else 0
        self.latest_frames[key] = {
            "key": key,
            "timestamp_ns": frame.timestamp_ns,
            "timestamp": self._format_timestamp(frame.timestamp_ns),
            "channel": frame.channel,
            "direction": frame.direction.upper(),
            "can_id": frame.can_id,
            "can_id_hex": frame.can_id_hex,
            "frame_type": "扩展帧" if frame.is_extended else "标准帧",
            "dlc": frame.dlc,
            "data_hex": frame.data_hex,
            "message_name": frame.message_name or "Unknown",
            "period_ms": period_ms,
            "status": "正常" if frame.parse_status == "ok" else "错误",
            "source_session": "S20260401-001",
            "frame_count": frame_count,
            "first_seen": first_seen,
            "last_seen": now,
            "last_seen_ms": 0,
        }

    def latest_frame_update(self, frame: CanFrame) -> dict:
        return self.latest_frames.get(f"{frame.channel}:{frame.can_id:X}", {})

    def latest_items(self, split_by_channel: bool = False) -> list[dict]:
        now = time.time()
        items = [{**item, "last_seen_ms": max(0, int((now - float(item["last_seen"])) * 1000))} for item in self.latest_frames.values()]
        if split_by_channel:
            return items
        by_id: dict[int, dict] = {}
        for item in items:
            existing = by_id.get(item["can_id"])
            if not existing:
                by_id[item["can_id"]] = item
                continue
            newer = item if item["last_seen"] >= existing["last_seen"] else existing
            by_id[item["can_id"]] = {**newer, "frame_count": int(existing["frame_count"]) + int(item["frame_count"])}
        return list(by_id.values())

    @staticmethod
    def _format_timestamp(timestamp_ns: int) -> str:
        seconds = timestamp_ns / 1_000_000_000
        local = time.localtime(seconds)
        millis = int((timestamp_ns % 1_000_000_000) / 1_000_000)
        micros = int((timestamp_ns % 1_000_000) / 1000)
        return f"{local.tm_hour:02d}:{local.tm_min:02d}:{local.tm_sec:02d}.{millis:03d}.{micros:03d}"

    def status(self) -> list[dict]:
        rows: list[dict] = []
        for channel, gateway in self.gateways.items():
            recent = self.recent_by_channel.get(channel)
            rows.append(
                gateway.stats.snapshot()
                | {
                    "protocol": gateway.config.protocol,
                    "local_ip": gateway.config.local_ip,
                    "local_port": gateway.config.local_receive_port,
                    "device_ip": gateway.config.device_ip,
                    "device_port": gateway.config.device_port,
                    "recent_buffer_depth": len(recent or ()),
                    "recent_buffer_capacity": (recent.maxlen if recent else gateway.config.recent_buffer_size),
                }
            )
        return rows

    def statistics(self) -> dict:
        return {
            "channels": self.status(),
            "frames": [f.ui_dict() for f in list(self.recent_frames)[:200]],
            "pipeline": {
                "depth": self._pipeline.qsize(),
                "capacity": self._pipeline_capacity,
                "per_channel": dict(self._pipeline_depths),
            },
        }
