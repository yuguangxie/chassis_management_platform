from __future__ import annotations
import struct
from app.can_gateway.models import CanFrame
from app.control.control_121 import decode_control_121, get_bits_le
from app.services.signal_store import SignalStore
from .loader import DbcLoader, DbcLoadResult
from .overrides import WARNING_LEVELS, CHARGE_STATE

class DbcService:
    def __init__(self, signal_store: SignalStore) -> None:
        self.signal_store = signal_store
        self.loader = DbcLoader()
        self.result: DbcLoadResult = self.loader.load()

    def reload(self) -> dict:
        self.result = self.loader.load()
        return self.status()

    def status(self) -> dict:
        return {
            "loaded": self.result.loaded,
            "raw_only": self.result.raw_only,
            "file": self.result.file,
            "hash": self.result.hash,
            "version": self.result.version,
            "vehicle_series": self.result.vehicle_series,
            "error": self.result.error,
        }

    def messages(self) -> list[dict]:
        db = self.result.database
        if not db:
            return []
        return [{"can_id": m.frame_id, "can_id_hex": f"0x{m.frame_id:X}", "name": m.name, "length": m.length, "signals": [s.name for s in m.signals]} for m in db.messages]

    def message(self, can_id: int) -> dict | None:
        for msg in self.messages():
            if msg["can_id"] == can_id:
                return msg
        return None

    async def decode(self, frame: CanFrame) -> dict:
        decoded: dict[str, dict] = {}
        message_name = None
        if self.result.database:
            try:
                msg = self.result.database.get_message_by_frame_id(frame.can_id)
                message_name = msg.name
                values = msg.decode(bytes(frame.data), decode_choices=True, allow_truncated=True)
                for key, value in values.items():
                    # cantools returns NamedSignalValue for enumerations.  Store
                    # only JSON-safe primitives while retaining the human label.
                    enum_value = getattr(value, "value", None)
                    enum_label = getattr(value, "name", None)
                    decoded[key] = {
                        "value": enum_value if enum_label is not None else value,
                        **({"label": str(enum_label)} if enum_label is not None else {}),
                        "unit": "A" if key.startswith(("Torque_req", "Torque_feed")) else "",
                        "quality": "good",
                    }
            except Exception:
                pass
        decoded |= self._decode_known(frame)
        if message_name is None:
            message_name = self._known_name(frame.can_id)
        frame.message_name = message_name
        if frame.direction.lower() == "rx":
            for name, payload in decoded.items():
                self.signal_store.update(
                    name,
                    payload.get("value"),
                    frame,
                    unit=payload.get("unit", ""),
                    label=payload.get("label"),
                    quality=payload.get("quality", "good"),
                )
        return {"message_name": message_name, "signals": decoded, "raw_only": self.result.raw_only}

    def decode_details(self, frame: CanFrame) -> dict:
        """Decode a stored frame without mutating SignalStore."""
        data = bytes((frame.data + [0] * 8)[:8])
        if frame.can_id == 0x121:
            rows = self._control_121_details(data)
            return {
                "message_name": "SCU_Control_Command",
                "signals": rows,
                "raw_only": False,
            }
        if frame.can_id == 0x102:
            return {
                "message_name": "BMS_Protect_Status",
                "signals": self._bms_102_details(data),
                "raw_only": False,
            }

        database = self.result.database
        if database:
            try:
                message = database.get_message_by_frame_id(frame.can_id)
                values = message.decode(data, decode_choices=False, allow_truncated=True)
                rows = []
                for signal in message.signals:
                    physical = values.get(signal.name)
                    raw_value = self._physical_to_raw(signal, physical)
                    choices = getattr(signal, "choices", None) or {}
                    enum_text = " / ".join(
                        f"{key} {getattr(value, 'name', value)}"
                        for key, value in choices.items()
                    ) or "-"
                    rows.append(
                        {
                            "name": signal.name,
                            "start_bit": signal.start,
                            "length": signal.length,
                            "type": f"{'int' if signal.is_signed else 'uint'}{signal.length}",
                            "raw": self._raw_hex(raw_value, signal.length),
                            "raw_value": raw_value,
                            "physical_value": physical,
                            "unit": signal.unit or "-",
                            "enum": enum_text,
                            "remark": self._signal_remark(signal),
                        }
                    )
                return {
                    "message_name": message.name,
                    "signals": rows,
                    "raw_only": False,
                }
            except Exception:
                pass
        return {
            "message_name": self._known_name(frame.can_id),
            "signals": self._raw_byte_details(data),
            "raw_only": True,
        }

    def _known_name(self, can_id: int) -> str:
        return {
            0x51: "VCU_CCU_Status",
            0x77: "VCU_Warning_Level",
            0x100: "BMS_Status",
            0x101: "BMS_Capacity",
            0x102: "BMS_Protect_Status",
            0x103: "BMS_NTC",
            0x104: "BMS_Cell_Part",
            0x105: "BMS_Cell_Part",
            0x121: "SCU_Control_Command",
            0x168: "VCU_Wheel_Speed_Feedback",
            0xE1: "SAS_Angle_Feedback",
            0x7F1: "SCU_Target_Speed_Feedback",
            0x703: "Heartbeat_F",
            0x704: "Heartbeat_R",
        }.get(can_id, "Unknown")

    def _decode_known(self, frame: CanFrame) -> dict[str, dict]:
        d = (frame.data + [0] * 8)[:8]
        out: dict[str, dict] = {}
        if frame.can_id == 0x100:
            voltage = int.from_bytes(bytes(d[0:2]), "big") / 10
            current = int.from_bytes(bytes(d[2:4]), "big", signed=True) / 10
            out |= {"BMS_Voltage": {"value": voltage, "unit": "V"}, "BMS_Current": {"value": current, "unit": "A"}, "BMS_SOC": {"value": d[4], "unit": "%"}}
        elif frame.can_id == 0x101:
            state = d[0] & 0x03
            out["Charge_or_Discharge_State"] = {"value": state, "label": CHARGE_STATE.get(state, "reserved")}
        elif frame.can_id == 0x102:
            protect = int.from_bytes(bytes(d[0:2]), "little", signed=False)
            balance_cell16 = int.from_bytes(bytes(d[2:4]), "little", signed=False)
            balance_cell33 = int.from_bytes(bytes(d[4:6]), "little", signed=False)
            out["BMS_Protect_Bitmap"] = {"value": protect, "unit": "bitmap"}
            protect_names = [
                "single_overvol_protection",
                "single_undervol_protection",
                "total_overvol_protection",
                "total_undervol_protection",
                "charge_overTem",
                "charge_underTem",
                "discharge_overTem",
                "discharge_unnderTem",
                "charge_overCur",
                "discharge_overCur",
                "short_circuit",
                "IC_Error",
                "Lock_MOS",
            ]
            for bit in range(16):
                value = bool((protect >> bit) & 0x01)
                out[f"BMS_Protect_Bit_{bit:02d}"] = {
                    "value": value,
                    "unit": "bool",
                    "label": "triggered" if value else "not_triggered",
                }
                if bit < len(protect_names):
                    out[protect_names[bit]] = {
                        "value": value,
                        "unit": "bool",
                        "label": "triggered" if value else "not_triggered",
                    }
            out["Balance_symbol_cell16"] = {"value": balance_cell16, "unit": "bitmap"}
            out["Balance_symbol_cell33"] = {"value": balance_cell33, "unit": "bitmap"}
            aliases = {
                # Phase-02 override contract exposes the first protection bit as
                # the normalized short-circuit safety alias.
                "BMS_Protect_Short_Circuit": bool(protect & (1 << 0)),
                "BMS_Protect_Over_Current": bool(protect & ((1 << 8) | (1 << 9))),
                "BMS_Protect_Over_Temperature": bool(protect & ((1 << 4) | (1 << 6))),
                "BMS_Protect_Under_Temperature": bool(protect & ((1 << 5) | (1 << 7))),
                "BMS_Protect_Over_Voltage": bool(protect & ((1 << 0) | (1 << 2))),
                "BMS_Protect_Under_Voltage": bool(protect & ((1 << 1) | (1 << 3))),
                "BMS_Protect_MOS_Fault": bool(protect & (1 << 12)),
                "BMS_Protect_Precharge_Fault": bool(protect & (1 << 11)),
            }
            for name, value in aliases.items():
                out[name] = {
                    "value": value,
                    "unit": "bool",
                    "label": "triggered" if value else "not_triggered",
                }
        elif frame.can_id == 0x103:
            out |= {"NTC1": {"value": d[0] - 40, "unit": "degC"}, "NTC2": {"value": d[1] - 40, "unit": "degC"}, "NTC3": {"value": d[2] - 40, "unit": "degC"}}
        elif frame.can_id == 0x51:
            gear = d[0] & 0x03
            out |= {
                "CCU_Shift_Level_Status": {
                    "value": gear,
                    "label": {0: "N", 1: "D", 3: "R"}.get(gear, "Invalid"),
                },
                "CCU_Drive_Mode": {"value": (d[0] >> 6) & 3},
                "CCU_Vehicle_Speed": {"value": d[1] / 10, "unit": "km/h"},
                "Brake_Status": {"value": bool(d[2] & 0x01), "unit": "bool"},
                "Remote_Brake_Request_Status": {"value": bool(d[2] & 0x02), "unit": "bool"},
                "Touch_Brake_Request_Status": {"value": bool(d[2] & 0x04), "unit": "bool"},
                "CCU_Ignition_Status": {"value": d[3] & 0x03},
                "Left_Turn_Light_Status": {"value": bool(d[4] & 0x01), "unit": "bool"},
                "Right_Turn_Light_Status": {"value": bool(d[4] & 0x02), "unit": "bool"},
                "Position_Light_Status": {"value": bool(d[4] & 0x04), "unit": "bool"},
                "Low_Beam_Status": {"value": bool(d[4] & 0x08), "unit": "bool"},
            }
        elif frame.can_id == 0x77:
            level = d[0] & 0x07
            out["VCU_Max_Warning_Level"] = {"value": level, "label": WARNING_LEVELS.get(level, "Reserved")}
        elif frame.can_id == 0xE1:
            front = int.from_bytes(bytes(d[0:2]), "big", signed=True) / 10
            rear = int.from_bytes(bytes(d[2:4]), "big", signed=True) / 10
            out |= {"SAS_Front_Angle": {"value": front, "unit": "cmd"}, "SAS_Rear_Angle": {"value": rear, "unit": "cmd"}}
        elif frame.can_id == 0x168:
            speed = int.from_bytes(bytes(d[0:2]), "big") / 10
            out |= {"Vehicle_Speed": {"value": speed, "unit": "km/h"}, "Wheel_Speed_Front_Left_RPM": {"value": d[2] * 10, "unit": "rpm"}, "Wheel_Speed_Front_Right_RPM": {"value": d[3] * 10, "unit": "rpm"}, "Wheel_Speed_Rear_Left_RPM": {"value": d[4] * 10, "unit": "rpm"}, "Wheel_Speed_Rear_Right_RPM": {"value": d[5] * 10, "unit": "rpm"}}
        elif frame.can_id == 0x7F1:
            out["SCU_Target_Speed_Feedback"] = {"value": int.from_bytes(bytes(d[0:2]), "big") / 10, "unit": "km/h"}
        elif frame.can_id in (0x703, 0x704):
            out[f"Heartbeat_{frame.can_id_hex}"] = {"value": d[0]}
        return out

    @staticmethod
    def _physical_to_raw(signal, physical):
        if physical is None:
            return None
        if isinstance(physical, bool):
            return int(physical)
        try:
            scale = float(signal.scale or 1)
            offset = float(signal.offset or 0)
            raw = (float(physical) - offset) / scale
            return int(round(raw))
        except (TypeError, ValueError, ZeroDivisionError):
            return str(physical)

    @staticmethod
    def _raw_hex(raw_value, length: int) -> str:
        if not isinstance(raw_value, int):
            return "-"
        width = max(1, (length + 3) // 4)
        mask = (1 << length) - 1
        return f"0x{raw_value & mask:0{width}X}"

    @staticmethod
    def _signal_remark(signal) -> str:
        details = []
        if signal.scale not in (None, 1):
            details.append(f"raw × {signal.scale}")
        if signal.offset not in (None, 0):
            details.append(f"offset {signal.offset}")
        details.append("signed" if signal.is_signed else "unsigned")
        return ", ".join(details)

    @staticmethod
    def _raw_byte_details(data: bytes) -> list[dict]:
        return [
            {
                "name": f"Data Byte{index}",
                "start_bit": index * 8,
                "length": 8,
                "type": "uint8",
                "raw": f"0x{value:02X}",
                "raw_value": value,
                "physical_value": value,
                "unit": "-",
                "enum": "-",
                "remark": "raw-only",
            }
            for index, value in enumerate(data)
        ]

    @staticmethod
    def _control_121_details(data: bytes) -> list[dict]:
        decoded = decode_control_121(data)
        fields = [
            ("SCU_Shift_Level_Request", 0, 2, get_bits_le(data, 0, 2), decoded["shift"], "enum", "0 N / 1 D / 3 R", "authoritative 0x121 decoder"),
            ("SCU_Drive_Mode_Request", 6, 2, get_bits_le(data, 6, 2), decoded["drive_mode"], "enum", "0 Manual / 1 Auto / 2 Remote", "authoritative 0x121 decoder"),
            ("SCU_Steering_Angle_Front", 8, 8, data[1], decoded["front_steering_cmd"], "int8", "-", "int8 two's complement"),
            ("SCU_Steering_Angle_Rear", 16, 8, data[2], decoded["rear_steering_cmd"], "int8", "-", "int8 two's complement"),
            ("SCU_Target_Speed", 24, 9, get_bits_le(data, 24, 9), decoded["target_speed_kmh"], "uint9", "-", "raw × 0.1 km/h"),
            ("SCU_Brake_Enable", 33, 1, get_bits_le(data, 33, 1), decoded["brake_enable"], "unsigned bool", "0 False / 1 True", "authoritative 0x121 decoder"),
            ("GW_Left_Turn_Light_Request", 40, 2, get_bits_le(data, 40, 2), decoded["left_light"], "uint2", "0 OFF / 1 ON", "authoritative 0x121 decoder"),
            ("GW_Right_Turn_Light_Request", 42, 2, get_bits_le(data, 42, 2), decoded["right_light"], "uint2", "0 OFF / 1 ON", "authoritative 0x121 decoder"),
            ("GW_Position_Light_Request", 46, 2, get_bits_le(data, 46, 2), decoded["position_light"], "uint2", "0 OFF / 1 ON", "authoritative 0x121 decoder"),
            ("GW_Low_Beam_Request", 48, 2, get_bits_le(data, 48, 2), decoded["low_beam"], "uint2", "0 OFF / 1 ON", "authoritative 0x121 decoder"),
            ("SCU_Torque_Or_Speed_Mode", 58, 1, get_bits_le(data, 58, 1), decoded["speed_mode"], "unsigned bool", "0 current / 1 speed", "current mode uses A, never Nm"),
        ]
        rows = []
        for name, start, length, raw, physical, type_name, enum, remark in fields:
            rows.append(
                {
                    "name": name,
                    "start_bit": start,
                    "length": length,
                    "type": type_name,
                    "raw": DbcService._raw_hex(raw, length),
                    "raw_value": raw,
                    "physical_value": physical,
                    "unit": "km/h" if name == "SCU_Target_Speed" else "deg" if "Angle" in name else "-",
                    "enum": enum,
                    "remark": remark,
                }
            )
        return rows

    @staticmethod
    def _bms_102_details(data: bytes) -> list[dict]:
        protect = int.from_bytes(data[0:2], "little", signed=False)
        balance16 = int.from_bytes(data[2:4], "little", signed=False)
        balance33 = int.from_bytes(data[4:6], "little", signed=False)
        rows = [
            {
                "name": "BMS_Protect_Bitmap",
                "start_bit": 0,
                "length": 16,
                "type": "unsigned bitmap",
                "raw": f"0x{protect:04X}",
                "raw_value": protect,
                "physical_value": protect,
                "unit": "bitmap",
                "enum": "0 inactive / 1 active",
                "remark": "override: unsigned protection bitmap",
            },
            {
                "name": "Balance_symbol_cell16",
                "start_bit": 16,
                "length": 16,
                "type": "unsigned bitmap",
                "raw": f"0x{balance16:04X}",
                "raw_value": balance16,
                "physical_value": balance16,
                "unit": "bitmap",
                "enum": "0 inactive / 1 active",
                "remark": "override: unsigned bitmap",
            },
            {
                "name": "Balance_symbol_cell33",
                "start_bit": 32,
                "length": 16,
                "type": "unsigned bitmap",
                "raw": f"0x{balance33:04X}",
                "raw_value": balance33,
                "physical_value": balance33,
                "unit": "bitmap",
                "enum": "0 inactive / 1 active",
                "remark": "override: unsigned bitmap",
            },
        ]
        names = [
            "single_overvol_protection",
            "single_undervol_protection",
            "total_overvol_protection",
            "total_undervol_protection",
            "charge_overTem",
            "charge_underTem",
            "discharge_overTem",
            "discharge_unnderTem",
            "charge_overCur",
            "discharge_overCur",
            "short_circuit",
            "IC_Error",
            "Lock_MOS",
        ]
        for bit in range(16):
            value = (protect >> bit) & 1
            rows.append(
                {
                    "name": f"BMS_Protect_Bit_{bit:02d}",
                    "start_bit": bit,
                    "length": 1,
                    "type": "unsigned bool",
                    "raw": f"0x{value:X}",
                    "raw_value": value,
                    "physical_value": "触发" if value else "未触发",
                    "unit": "-",
                    "enum": "0 未触发 / 1 触发",
                    "remark": "override: unsigned bool",
                }
            )
            if bit < len(names):
                rows.append(
                    {
                        "name": names[bit],
                        "start_bit": bit,
                        "length": 1,
                        "type": "unsigned bool",
                        "raw": f"0x{value:X}",
                        "raw_value": value,
                        "physical_value": "triggered" if value else "not_triggered",
                        "unit": "-",
                        "enum": "0 not_triggered / 1 triggered",
                        "remark": "override: unsigned bool",
                    }
                )
        alias_bits = {
            "BMS_Protect_Short_Circuit": (0,),
            "BMS_Protect_Over_Current": (8, 9),
            "BMS_Protect_Over_Temperature": (4, 6),
            "BMS_Protect_Under_Temperature": (5, 7),
            "BMS_Protect_Over_Voltage": (0, 2),
            "BMS_Protect_Under_Voltage": (1, 3),
            "BMS_Protect_MOS_Fault": (12,),
            "BMS_Protect_Precharge_Fault": (11,),
        }
        for name, bits in alias_bits.items():
            value = int(any(protect & (1 << bit) for bit in bits))
            rows.append(
                {
                    "name": name,
                    "start_bit": min(bits),
                    "length": len(bits),
                    "type": "unsigned bool",
                    "raw": f"0x{value:X}",
                    "raw_value": value,
                    "physical_value": "triggered" if value else "not_triggered",
                    "unit": "-",
                    "enum": "0 not_triggered / 1 triggered",
                    "remark": "semantic alias over unsigned protection bits",
                }
            )
        crc = int.from_bytes(data[6:8], "little", signed=False)
        rows.append(
            {
                "name": "CRC_16",
                "start_bit": 48,
                "length": 16,
                "type": "uint16",
                "raw": f"0x{crc:04X}",
                "raw_value": crc,
                "physical_value": crc,
                "unit": "-",
                "enum": "-",
                "remark": "unsigned CRC",
            }
        )
        return rows
