from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.can_gateway.models import CanFrame
from app.can_gateway.usr_can115 import UsrCan115Codec
from app.control.control_121 import Control121Command, encode_control_121, encode_i8_twos
from app.dbc.service import DbcService
from app.services.signal_store import SignalStore


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "audit" / "evidence" / "tests" / "protocol_probe.json"


async def dbc_probe() -> dict:
    store = SignalStore()
    service = DbcService(store)
    database = service.result.database
    messages = list(database.messages) if database else []

    charge_states: dict[str, dict] = {}
    for value in range(4):
        frame = CanFrame(channel="CAN1", can_id=0x101, dlc=8, data=[value, 0, 0, 0, 0, 0, 0, 0])
        decoded = await service.decode(frame)
        charge_states[str(value)] = decoded["signals"]["Charge_or_Discharge_State"]

    protect = CanFrame(channel="CAN1", can_id=0x102, dlc=8, data=[0x01, 0x80, 0, 0, 0, 0, 0, 0])
    protect_decoded = await service.decode(protect)
    return {
        "status": service.status(),
        "message_count": len(messages),
        "signal_count": sum(len(message.signals) for message in messages),
        "charge_states": charge_states,
        "protect_bitmap_0x8001": protect_decoded["signals"].get("BMS_Protect_Bitmap"),
        "note": "Known-message overrides are merged after cantools decode; individual 0x102 protection booleans are not materialized by _decode_known.",
    }


def main() -> None:
    codec = UsrCan115Codec()
    base = CanFrame(
        channel="CAN2",
        can_id=0x121,
        dlc=8,
        data=[0x40, 0xC4, 0x3C, 0x14, 0x02, 0x00, 0x00, 0x00],
    )
    packet = codec.encode_frame(base)
    decoded = codec.decode_packet(packet, "CAN2")

    illegal_dlc_packet = bytes([0x09]) + (0x51).to_bytes(4, "big") + bytes(8)
    illegal_dlc = codec.decode_packet(illegal_dlc_packet, "CAN1")
    reserved_packet = bytes([0x38]) + (0x77).to_bytes(4, "big") + bytes(8)
    reserved = codec.decode_packet(reserved_packet, "CAN1")

    second = codec.encode_frame(CanFrame(channel="CAN1", can_id=0x77, dlc=8, data=[0] * 8))
    sticky_frames, sticky_rest = codec.decode_stream(bytearray(packet + second + packet[:5]), "CAN1")

    # UdpCanGateway retains this buffer between datagrams. A truncated datagram followed
    # by a valid one is therefore decoded as a synthetic 13-byte packet with no resync.
    cross_datagram_buffer = bytearray(packet[:5])
    first_frames, cross_datagram_buffer = codec.decode_stream(cross_datagram_buffer, "CAN2")
    cross_datagram_buffer.extend(second)
    second_frames, cross_datagram_rest = codec.decode_stream(cross_datagram_buffer, "CAN2")

    control_examples = {
        str(value): {
            "encoded_i8": f"0x{encode_i8_twos(value):02X}",
            "payload": " ".join(
                f"{byte:02X}"
                for byte in encode_control_121(
                    Control121Command(front_steering_cmd=value, rear_steering_cmd=value)
                )
            ),
        }
        for value in (-120, -60, 0, 60, 120)
    }

    result = {
        "usr_can115": {
            "frame_length": len(packet),
            "packet_hex": packet.hex(" ").upper(),
            "frame_info": f"0x{packet[0]:02X}",
            "can_id_bytes_big_endian": packet[1:5].hex(" ").upper(),
            "decoded_can_id": decoded.can_id_hex,
            "decoded_data_hex": decoded.data_hex,
            "illegal_dlc_status": illegal_dlc.parse_status,
            "reserved_bits_status": reserved.parse_status,
            "sticky_frame_ids": [frame.can_id_hex for frame in sticky_frames],
            "sticky_remainder_bytes": len(sticky_rest),
            "cross_datagram_first_frame_count": len(first_frames),
            "cross_datagram_second_frame_ids": [frame.can_id_hex for frame in second_frames],
            "cross_datagram_second_parse_status": [frame.parse_status for frame in second_frames],
            "cross_datagram_remainder_bytes": len(cross_datagram_rest),
            "cross_datagram_expected_valid_id": "0x77",
            "cross_datagram_observed_id": second_frames[0].can_id_hex if second_frames else None,
            "codec_stats": vars(codec.stats),
        },
        "control_0x121": control_examples,
        "dbc": asyncio.run(dbc_probe()),
        "implementation_limits": {
            "gateway_recent_frame_capacity": 2000,
            "signal_timeseries_capacity_per_signal": 3000,
            "stream_resynchronization": False,
            "udp_datagram_boundary_preserved": False,
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
