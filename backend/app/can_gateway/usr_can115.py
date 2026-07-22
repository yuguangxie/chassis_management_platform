from __future__ import annotations
from dataclasses import dataclass
from .models import CanFrame

FRAME_LEN = 13

@dataclass
class DecodeStats:
    total_packets: int = 0
    decoded_frames: int = 0
    dlc_errors: int = 0
    reserved_bit_errors: int = 0
    short_packets: int = 0
    invalid_length_errors: int = 0
    can_id_range_errors: int = 0

class UsrCan115Codec:
    def __init__(self) -> None:
        self.stats = DecodeStats()

    def encode_frame(self, frame: CanFrame) -> bytes:
        if not 0 <= frame.dlc <= 8:
            raise ValueError("DLC must be 0..8")
        self._validate_can_id(frame.can_id, frame.is_extended)
        if len(frame.data) > 8:
            raise ValueError("USR-CAN115 data area may not exceed 8 bytes")
        if any(not 0 <= int(value) <= 0xFF for value in frame.data):
            raise ValueError("CAN data bytes must be 0..255")
        frame_info = (0x80 if frame.is_extended else 0) | (0x40 if frame.is_remote else 0) | frame.dlc
        data = bytes((frame.data + [0] * 8)[:8])
        return bytes([frame_info]) + int(frame.can_id).to_bytes(4, "big") + data

    def decode_packet(self, packet: bytes, channel: str, direction: str = "rx", source: str = "unknown") -> CanFrame:
        self.stats.total_packets += 1
        if len(packet) != FRAME_LEN:
            self.stats.invalid_length_errors += 1
            raise ValueError("USR-CAN115 packet must be exactly 13 bytes")
        frame_info = packet[0]
        dlc = frame_info & 0x0F
        reserved = frame_info & 0x30
        parse_status = "ok"
        if dlc > 8:
            self.stats.dlc_errors += 1
            parse_status = "dlc_error"
        if reserved:
            self.stats.reserved_bit_errors += 1
            parse_status = "reserved_bits_error"
        can_id = int.from_bytes(packet[1:5], "big")
        try:
            self._validate_can_id(can_id, bool(frame_info & 0x80))
        except ValueError:
            self.stats.can_id_range_errors += 1
            parse_status = "can_id_range_error"
        frame = CanFrame(
            channel=channel,
            direction=direction,
            can_id=can_id,
            is_extended=bool(frame_info & 0x80),
            is_remote=bool(frame_info & 0x40),
            dlc=min(dlc, 8),
            data=list(packet[5:13]),
            raw_packet=bytes(packet),
            parse_status=parse_status,
            source=source,
        )
        self.stats.decoded_frames += 1
        return frame

    def decode_stream(self, buffer: bytearray, channel: str, direction: str = "rx", source: str = "unknown") -> tuple[list[CanFrame], bytearray]:
        frames: list[CanFrame] = []
        while len(buffer) >= FRAME_LEN:
            packet = bytes(buffer[:FRAME_LEN])
            del buffer[:FRAME_LEN]
            frames.append(self.decode_packet(packet, channel, direction, source))
        if buffer:
            self.stats.short_packets += 1
        return frames, buffer

    def decode_datagram(self, datagram: bytes, channel: str, source: str = "unknown") -> list[CanFrame]:
        """Decode one UDP datagram without carrying bytes into another datagram."""
        if not datagram or len(datagram) % FRAME_LEN:
            self.stats.invalid_length_errors += 1
            self.stats.short_packets += 1
            raise ValueError("USR-CAN115 UDP datagram length must be a non-zero multiple of 13")
        return [
            self.decode_packet(datagram[offset : offset + FRAME_LEN], channel, "rx", source)
            for offset in range(0, len(datagram), FRAME_LEN)
        ]

    @staticmethod
    def _validate_can_id(can_id: int, is_extended: bool) -> None:
        upper = 0x1FFFFFFF if is_extended else 0x7FF
        frame_type = "extended" if is_extended else "standard"
        if not 0 <= int(can_id) <= upper:
            raise ValueError(f"{frame_type} CAN ID must be 0..0x{upper:X}")
