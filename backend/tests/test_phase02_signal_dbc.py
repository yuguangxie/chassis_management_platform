from __future__ import annotations

import time

import pytest

from app.can_gateway.models import CanFrame
from app.api.can import decoded_signals_for
from app.dbc.service import DbcService
from app.services.signal_store import SignalStore


def frame(channel: str, can_id: int, data: list[int], *, age: float = 0) -> CanFrame:
    return CanFrame(
        channel=channel,
        direction="rx",
        can_id=can_id,
        dlc=8,
        data=data,
        received_at_monotonic=time.monotonic() - age,
    )


@pytest.mark.asyncio
async def test_0x102_is_expanded_as_unsigned_bool_and_bitmap():
    store = SignalStore()
    dbc = DbcService(store)
    decoded = await dbc.decode(frame("CAN2", 0x102, [0x01, 0x80, 0x34, 0x12, 0x78, 0x56, 0, 0]))
    signals = decoded["signals"]
    assert signals["BMS_Protect_Bitmap"]["value"] == 0x8001
    assert signals["BMS_Protect_Bit_00"]["value"] is True
    assert signals["BMS_Protect_Bit_15"]["value"] is True
    assert signals["BMS_Protect_Bit_01"]["value"] is False
    assert signals["BMS_Protect_Short_Circuit"]["label"] == "triggered"
    assert signals["Balance_symbol_cell16"]["value"] == 0x1234
    assert signals["Balance_symbol_cell33"]["value"] == 0x5678
    assert all(
        int(payload["value"]) >= 0
        for name, payload in signals.items()
        if name.startswith("BMS_Protect_")
    )


def test_signal_store_requires_quality_freshness_source_and_channel():
    store = SignalStore()
    can1 = frame("CAN1", 0xE1, [0] * 8)
    can2 = frame("CAN2", 0xE1, [0] * 8)
    store.update("SAS_Front_Angle", 29.5, can1, unit="cmd")
    store.update("SAS_Front_Angle", 0.0, can2, unit="cmd")
    assert store.require_sample("SAS_Front_Angle", channel="CAN1")["value"] == 29.5
    assert store.require_sample("SAS_Front_Angle", channel="CAN2")["value"] == 0.0

    stale = frame("CAN1", 0x100, [0] * 8, age=3)
    store.update("STALE", 1, stale)
    with pytest.raises(ValueError, match="stale"):
        store.require_sample("STALE", max_age_seconds=1)

    invalid = frame("CAN1", 0x100, [0] * 8)
    store.update("INVALID", 1, invalid, quality="invalid")
    with pytest.raises(ValueError, match="quality"):
        store.require_sample("INVALID")


@pytest.mark.asyncio
async def test_tx_decoding_never_overwrites_trusted_rx_feedback():
    store = SignalStore()
    dbc = DbcService(store)
    await dbc.decode(frame("CAN1", 0x51, [1, 15, 0, 1, 0, 0, 0, 0]))
    before = store.require_sample("CCU_Vehicle_Speed", channel="CAN1")
    tx = CanFrame(
        channel="CAN2",
        direction="tx",
        can_id=0x121,
        dlc=8,
        data=[0] * 8,
    )
    await dbc.decode(tx)
    after = store.require_sample("CCU_Vehicle_Speed", channel="CAN1")
    assert before["value"] == after["value"] == 1.5
    assert after["can_id"] == "0x51"


def test_can_monitor_0x102_detail_uses_actual_frame_bits():
    rows = decoded_signals_for(0x102, "01 80 34 12 78 56 00 00")
    by_name = {row["name"]: row for row in rows}
    assert by_name["BMS_Protect_Short_Circuit"]["raw_value"] == 1
    assert by_name["BMS_Protect_Bit_15"]["raw_value"] == 1
    assert by_name["BMS_Protect_Over_Current"]["raw_value"] == 0
    assert by_name["Balance_symbol_cell16"]["raw_value"] == 0x1234
    assert by_name["Balance_symbol_cell33"]["raw_value"] == 0x5678
