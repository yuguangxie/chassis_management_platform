import asyncio
import time

import pytest

from app.can_gateway.models import CanFrame
from app.can_gateway.statistics import ChannelStats
from app.can_gateway.udp_gateway import UdpCanGateway
from app.can_gateway.usr_can115 import UsrCan115Codec
from app.core.config import ChannelConfig


def channel_config(**overrides) -> ChannelConfig:
    data = {
        "channel": "CAN1",
        "local_ip": "127.0.0.1",
        "local_receive_port": 18234,
        "device_ip": "127.0.0.1",
        "device_port": 12341,
        "receive_queue_size": 16,
        "max_frame_age_ms": 50,
    }
    data.update(overrides)
    return ChannelConfig(**data)


def test_udp_truncated_datagram_is_not_joined_with_next_datagram():
    codec = UsrCan115Codec()
    packet = codec.encode_frame(CanFrame(channel="CAN1", can_id=0x51, data=[1] * 8))
    with pytest.raises(ValueError):
        codec.decode_datagram(packet[:5], "CAN1")
    frames = codec.decode_datagram(packet, "CAN1")
    assert [frame.can_id for frame in frames] == [0x51]
    assert codec.stats.decoded_frames == 1


def test_udp_gateway_discards_partial_and_bounds_queue():
    async def consume(_frame):
        return None

    gateway = UdpCanGateway(channel_config(), consume)
    packet = gateway.codec.encode_frame(CanFrame(channel="CAN1", can_id=0x51, data=[1] * 8))
    gateway.on_datagram(packet[:7], "127.0.0.1:1")
    assert gateway.queue.qsize() == 0
    gateway.on_datagram(packet, "127.0.0.1:1")
    assert gateway.queue.qsize() == 1
    for _ in range(20):
        gateway.on_datagram(packet, "127.0.0.1:1")
    snapshot = gateway.stats.snapshot()
    assert gateway.queue.qsize() == gateway.queue.maxsize
    assert snapshot["queue_dropped"] > 0
    assert snapshot["queue_healthy"] is False


@pytest.mark.asyncio
async def test_expired_queued_frame_does_not_reach_application():
    processed = []

    async def consume(frame):
        processed.append(frame)

    gateway = UdpCanGateway(channel_config(), consume)
    frame = CanFrame(channel="CAN1", can_id=0x51, data=[1] * 8)
    frame.received_at_monotonic = time.monotonic() - 1
    await gateway.queue.put(frame)
    gateway.worker_task = asyncio.create_task(gateway._process_queue())
    await asyncio.sleep(0.03)
    await gateway.disconnect()
    assert processed == []
    assert gateway.stats.stale_dropped == 1


def test_tx_and_stale_processing_cannot_keep_channel_online():
    stats = ChannelStats("CAN2", online_timeout_seconds=2.0)
    stats.transport_connected = True
    received = CanFrame(channel="CAN2", direction="rx", can_id=0x51, data=[0] * 8)
    stats.record_received(received, time.monotonic() - 2.1)
    stats.record_tx(CanFrame(channel="CAN2", direction="tx", can_id=0x121, data=[0] * 8))
    assert stats.snapshot()["online"] is False


def test_reserved_or_invalid_dlc_frame_cannot_mark_channel_online():
    async def consume(_frame):
        raise AssertionError("invalid protocol frame reached application")

    gateway = UdpCanGateway(channel_config(), consume)
    invalid = bytes([0x39]) + (0x51).to_bytes(4, "big") + bytes(8)
    gateway.stats.transport_connected = True
    gateway.on_datagram(invalid, "127.0.0.1:1")
    snapshot = gateway.stats.snapshot()
    assert snapshot["online"] is False
    assert snapshot["error_count"] == 1
    assert gateway.queue.qsize() == 0
