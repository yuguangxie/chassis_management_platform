from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.can_gateway.manager import CanGatewayManager
from app.can_gateway.models import CanFrame
from app.core.config import ChannelConfig, RuntimeConfig
from app.storage.raw_log_writer import RawLogWriter
from app.storage.telemetry import TelemetryRecorder
from app.websocket.manager import WebSocketManager


def test_raw_writer_rotates_and_archives_by_session_date_and_size(tmp_path: Path):
    writer = RawLogWriter(tmp_path, batch_size=1, rotate_bytes=1, compress_rotated=True)
    frame = CanFrame(channel="CAN1", can_id=0x51, data=[1] * 8)
    writer.write(frame, "EOL-ROTATE")
    writer.write(frame, "EOL-ROTATE")
    writer.close()

    assert list(tmp_path.glob("raw_can_EOL-ROTATE_*.csv"))
    assert list(tmp_path.glob("raw_can_EOL-ROTATE_*.csv.gz"))
    metrics = writer.metrics()
    assert metrics["rotations"] >= 1
    assert metrics["compressed"] >= 1


@pytest.mark.asyncio
async def test_telemetry_log_write_is_deferred_to_persistence_worker():
    class Writer:
        def __init__(self):
            self.writes: list[CanFrame] = []

        def write(self, frame, _session):
            self.writes.append(frame)

        def flush(self, *_args):
            return None

        def close(self):
            return None

        def metrics(self):
            return {}

    raw = Writer()
    signals = Writer()
    recorder = TelemetryRecorder(object(), raw, signals, lambda: None, batch_size=1)
    recorder.enqueue(CanFrame(channel="CAN1", can_id=0x51, data=[0] * 8), {})
    assert raw.writes == []
    await recorder.start()
    await recorder.drain()
    assert len(raw.writes) == 1
    await recorder.stop()


@pytest.mark.asyncio
async def test_can_manager_pipeline_is_bounded_and_preserves_critical_feedback():
    processed: list[int] = []

    async def consume(frame: CanFrame):
        processed.append(frame.can_id)

    config = RuntimeConfig(
        profile="test",
        control_channel="CAN1",
        channels=[
            ChannelConfig(
                channel="CAN1",
                local_ip="127.0.0.1",
                local_receive_port=19334,
                device_ip="127.0.0.1",
                device_port=19335,
                control_enabled=True,
                receive_queue_size=16,
            )
        ],
    )
    manager = CanGatewayManager(config, consume)
    try:
        for _ in range(manager._pipeline_capacity):
            await manager._enqueue_frame(CanFrame(channel="CAN1", can_id=0x555, data=[0] * 8))
        await manager._enqueue_frame(CanFrame(channel="CAN1", can_id=0x556, data=[0] * 8))
        assert manager.gateways["CAN1"].stats.pipeline_queue_dropped == 1

        manager._pipeline_task = asyncio.create_task(manager._process_pipeline())
        await manager._enqueue_frame(CanFrame(channel="CAN1", can_id=0x77, data=[0] * 8))
        await asyncio.wait_for(manager._pipeline.join(), timeout=2)
        assert 0x77 in processed
        assert manager.statistics()["pipeline"]["depth"] == 0
    finally:
        await manager.stop_all()


@pytest.mark.asyncio
async def test_slow_websocket_client_is_disconnected_without_blocking_broadcast():
    class SlowSocket:
        def __init__(self):
            self.send_started = asyncio.Event()
            self.release = asyncio.Event()
            self.closed = False

        async def accept(self):
            return None

        async def send_text(self, _message: str):
            self.send_started.set()
            await self.release.wait()

        async def close(self, *_args, **_kwargs):
            self.closed = True

    ws = SlowSocket()
    manager = WebSocketManager(client_queue_size=1, disconnect_after_drops=2)
    await manager.connect(ws)  # type: ignore[arg-type]
    await manager.subscribe(ws, ["signals.current"])  # type: ignore[arg-type]
    await manager.broadcast("signals.current", {"index": 0})
    await asyncio.wait_for(ws.send_started.wait(), timeout=1)
    await manager.broadcast("signals.current", {"index": 1})
    await manager.broadcast("signals.current", {"index": 2})
    await manager.broadcast("signals.current", {"index": 3})
    assert not manager.clients
    assert ws.closed
