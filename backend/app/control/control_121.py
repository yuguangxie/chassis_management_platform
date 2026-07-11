from __future__ import annotations

from pydantic import BaseModel, Field


class Control121Command(BaseModel):
    shift: str = Field("N", pattern="^(D|N|R)$")
    drive_mode: str = Field("Auto", pattern="^(Manual|Remote|Auto)$")
    target_speed_kmh: float = Field(default=0.0, ge=0.0, le=51.1)
    front_steering_cmd: int = Field(default=0, ge=-120, le=120)
    rear_steering_cmd: int = Field(default=0, ge=-120, le=120)
    brake_enable: bool = False
    left_light: bool = False
    right_light: bool = False
    position_light: bool = False
    low_beam: bool = False
    speed_mode: bool = False


SHIFT_MAP = {"D": 1, "N": 0, "R": 3}
DRIVE_MODE_MAP = {"Manual": 0, "Auto": 1, "Remote": 2}
SHIFT_BY_RAW = {value: key for key, value in SHIFT_MAP.items()}
DRIVE_MODE_BY_RAW = {value: key for key, value in DRIVE_MODE_MAP.items()}


def clamp_i8_angle(value: int) -> int:
    return max(-120, min(120, int(value)))


def encode_i8_twos(value: int) -> int:
    return clamp_i8_angle(value) & 0xFF


def decode_i8_twos(value: int) -> int:
    value &= 0xFF
    return value - 256 if value & 0x80 else value


def set_bits_le(data: bytearray, start: int, length: int, raw: int) -> None:
    for offset in range(length):
        index = start + offset
        byte_index = index // 8
        bit_index = index % 8
        if (raw >> offset) & 1:
            data[byte_index] |= 1 << bit_index
        else:
            data[byte_index] &= ~(1 << bit_index)


def get_bits_le(data: bytes, start: int, length: int) -> int:
    raw = 0
    for offset in range(length):
        index = start + offset
        if data[index // 8] & (1 << (index % 8)):
            raw |= 1 << offset
    return raw


def encode_control_121(command: Control121Command) -> bytes:
    """The sole authoritative 0x121 encoder used by preview and transmission."""
    data = bytearray(8)
    set_bits_le(data, 0, 2, SHIFT_MAP[command.shift])
    set_bits_le(data, 6, 2, DRIVE_MODE_MAP[command.drive_mode])
    data[1] = encode_i8_twos(command.front_steering_cmd)
    data[2] = encode_i8_twos(command.rear_steering_cmd)
    speed_raw = int(round(command.target_speed_kmh / 0.1))
    set_bits_le(data, 24, 9, speed_raw)
    set_bits_le(data, 33, 1, int(command.brake_enable))
    set_bits_le(data, 40, 2, int(command.left_light))
    set_bits_le(data, 42, 2, int(command.right_light))
    set_bits_le(data, 46, 2, int(command.position_light))
    set_bits_le(data, 48, 2, int(command.low_beam))
    set_bits_le(data, 58, 1, int(command.speed_mode))
    return bytes(data)


def decode_control_121(data: bytes) -> dict:
    if len(data) != 8:
        raise ValueError("0x121 data must contain exactly 8 bytes")
    return {
        "shift": SHIFT_BY_RAW.get(get_bits_le(data, 0, 2), "INVALID"),
        "drive_mode": DRIVE_MODE_BY_RAW.get(get_bits_le(data, 6, 2), "INVALID"),
        "front_steering_cmd": decode_i8_twos(data[1]),
        "rear_steering_cmd": decode_i8_twos(data[2]),
        "target_speed_kmh": get_bits_le(data, 24, 9) * 0.1,
        "brake_enable": bool(get_bits_le(data, 33, 1)),
        "left_light": bool(get_bits_le(data, 40, 2)),
        "right_light": bool(get_bits_le(data, 42, 2)),
        "position_light": bool(get_bits_le(data, 46, 2)),
        "low_beam": bool(get_bits_le(data, 48, 2)),
        "speed_mode": bool(get_bits_le(data, 58, 1)),
    }


def preview(command: Control121Command) -> dict:
    data = encode_control_121(command)
    speed_raw = get_bits_le(data, 24, 9)
    return {
        "can_id": "0x121",
        "data": list(data),
        "data_hex": " ".join(f"{value:02X}" for value in data),
        "bytes_dec": list(data),
        "bytes_hex": [f"{value:02X}" for value in data],
        "field_notes": [
            f"Byte0: gear={command.shift}, drive_mode={command.drive_mode}",
            f"Byte1: front steering {command.front_steering_cmd:+d} -> 0x{data[1]:02X} (int8 two's complement)",
            f"Byte2: rear steering {command.rear_steering_cmd:+d} -> 0x{data[2]:02X} (int8 two's complement)",
            f"Byte3~4: target speed raw={speed_raw}, {speed_raw} x 0.1 = {command.target_speed_kmh:.1f} km/h; brake={int(command.brake_enable)}",
            "Byte5~7: lights/control mode/reserved bits; reserved bits remain zero",
        ],
        "encoder": "backend.app.control.control_121.encode_control_121",
    }
