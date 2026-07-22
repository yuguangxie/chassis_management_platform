from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time

from .models import CanFrame


@dataclass
class MessageStat:
    count: int = 0
    last_received_monotonic: float = 0.0
    period_ms: float = 0.0
    min_period_ms: float = 0.0
    max_period_ms: float = 0.0


@dataclass
class ChannelStats:
    channel: str
    online_timeout_seconds: float = 2.0
    transport_connected: bool = False
    rx_count: int = 0
    tx_count: int = 0
    error_count: int = 0
    fps: float = 0.0
    last_frame_at: float = 0.0
    last_receive_monotonic: float = 0.0
    last_frame_hex: str = ""
    queue_depth: int = 0
    queue_capacity: int = 0
    queue_dropped: int = 0
    stale_dropped: int = 0
    pipeline_queue_depth: int = 0
    pipeline_queue_capacity: int = 0
    pipeline_queue_dropped: int = 0
    malformed_datagrams: int = 0
    unauthorized_datagrams: int = 0
    last_unauthorized_source: str = ""
    processing_errors: int = 0
    last_queue_overflow_monotonic: float = 0.0
    started_monotonic: float = field(default_factory=time.monotonic)
    messages: dict[int, MessageStat] = field(default_factory=dict)
    _recent_rx: deque[float] = field(default_factory=lambda: deque(maxlen=10000), repr=False)

    def record_received(self, frame: CanFrame, received_at_monotonic: float) -> None:
        self.last_receive_monotonic = received_at_monotonic
        self.last_frame_at = frame.timestamp_ns / 1_000_000_000
        self.last_frame_hex = frame.data_hex
        self.rx_count += 1
        if frame.parse_status != "ok":
            self.error_count += 1
        self._recent_rx.append(received_at_monotonic)
        cutoff = received_at_monotonic - 1.0
        while self._recent_rx and self._recent_rx[0] < cutoff:
            self._recent_rx.popleft()
        self.fps = float(len(self._recent_rx))
        message = self.messages.setdefault(frame.can_id, MessageStat())
        if message.last_received_monotonic:
            period = (received_at_monotonic - message.last_received_monotonic) * 1000
            message.period_ms = period
            message.min_period_ms = period if not message.min_period_ms else min(message.min_period_ms, period)
            message.max_period_ms = max(message.max_period_ms, period)
        message.last_received_monotonic = received_at_monotonic
        message.count += 1

    def record_protocol_error(self, frame: CanFrame) -> None:
        self.rx_count += 1
        self.error_count += 1
        self.last_frame_hex = frame.data_hex

    def record_tx(self, frame: CanFrame) -> None:
        self.tx_count += 1
        self.last_frame_hex = frame.data_hex

    def record(self, frame: CanFrame) -> None:
        if frame.direction.lower() == "rx":
            if frame.parse_status == "ok":
                self.record_received(frame, frame.received_at_monotonic)
            else:
                self.record_protocol_error(frame)
        else:
            self.record_tx(frame)

    def set_queue_depth(self, depth: int, capacity: int) -> None:
        self.queue_depth = depth
        self.queue_capacity = capacity

    def record_queue_drop(self) -> None:
        self.queue_dropped += 1
        self.error_count += 1
        self.last_queue_overflow_monotonic = time.monotonic()

    def record_stale_drop(self) -> None:
        self.stale_dropped += 1
        self.error_count += 1

    def set_pipeline_queue(self, depth: int, capacity: int) -> None:
        """Track the shared post-transport pipeline separately from the socket queue."""
        self.pipeline_queue_depth = max(0, depth)
        self.pipeline_queue_capacity = max(0, capacity)

    def record_pipeline_drop(self) -> None:
        self.pipeline_queue_dropped += 1
        self.error_count += 1
        self.last_queue_overflow_monotonic = time.monotonic()

    def record_malformed_datagram(self) -> None:
        self.malformed_datagrams += 1
        self.error_count += 1

    def record_unauthorized_datagram(self, source: str) -> None:
        self.unauthorized_datagrams += 1
        self.last_unauthorized_source = source
        self.error_count += 1

    def snapshot(self) -> dict:
        now = time.monotonic()
        receive_age = now - self.last_receive_monotonic if self.last_receive_monotonic else None
        queue_recovered = (
            not self.last_queue_overflow_monotonic
            or now - self.last_queue_overflow_monotonic > self.online_timeout_seconds
        )
        local_queue_healthy = (
            not self.queue_capacity or self.queue_depth < max(1, int(self.queue_capacity * 0.9))
        )
        pipeline_healthy = (
            not self.pipeline_queue_capacity
            or self.pipeline_queue_depth < max(1, int(self.pipeline_queue_capacity * 0.9))
        )
        queue_healthy = queue_recovered and local_queue_healthy and pipeline_healthy
        online = bool(
            self.transport_connected
            and receive_age is not None
            and receive_age < self.online_timeout_seconds
            and queue_healthy
        )
        return {
            "channel": self.channel,
            "online": online,
            "transport_connected": self.transport_connected,
            "receive_age_ms": round(receive_age * 1000, 1) if receive_age is not None else None,
            "queue_healthy": queue_healthy,
            "queue_depth": self.queue_depth,
            "queue_capacity": self.queue_capacity,
            "queue_dropped": self.queue_dropped,
            "pipeline_queue_depth": self.pipeline_queue_depth,
            "pipeline_queue_capacity": self.pipeline_queue_capacity,
            "pipeline_queue_dropped": self.pipeline_queue_dropped,
            "stale_dropped": self.stale_dropped,
            "malformed_datagrams": self.malformed_datagrams,
            "unauthorized_datagrams": self.unauthorized_datagrams,
            "last_unauthorized_source": self.last_unauthorized_source or None,
            "processing_errors": self.processing_errors,
            "fps": round(self.fps, 1),
            "rx_count": self.rx_count,
            "tx_count": self.tx_count,
            "error_count": self.error_count,
            "last_frame_at": self.last_frame_at,
            "last_frame_hex": self.last_frame_hex,
        }
