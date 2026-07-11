from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
import time
from typing import Any

from app.can_gateway.models import CanFrame
from app.core.time import utc_now


WATCHLIST_CATALOG = {
    "BMS_Voltage": ("BMS_总压", "[60.0 ~ 840.0]"),
    "BMS_Current": ("BMS_电流", "[-500.0 ~ 500.0]"),
    "BMS_SOC": ("BMS_SOC", "[10 ~ 100]"),
    "CCU_Vehicle_Speed": ("VCU_车速", "[0 ~ 40]"),
    "Vehicle_Speed": ("车辆速度", "[0 ~ 40]"),
    "Wheel_Speed_Front_Left_RPM": ("WHL_FL_轮速", "[0 ~ 80]"),
    "SAS_Front_Angle": ("STEER_前转角反馈", "[-120 ~ 120]"),
    "SAS_Rear_Angle": ("STEER_后转角反馈", "[-120 ~ 120]"),
    "Torque_feed_left": ("MCU_相电流", "[-200 ~ 200]"),
    "BMS_Protect_Bitmap": ("BMS_保护位", "[0]"),
}


class SignalStore:
    def __init__(self) -> None:
        self.current: dict[str, dict] = {}
        self.current_by_source: dict[tuple[str, str], dict] = {}
        self.timeseries: dict[str, deque[dict]] = defaultdict(lambda: deque(maxlen=3000))
        self.watchlist = list(WATCHLIST_CATALOG)[:8]

    def update(
        self,
        key: str,
        value,
        frame: CanFrame,
        unit: str = "",
        label: str | None = None,
        quality: str = "good",
    ) -> None:
        item = {
            "key": key,
            "value": value,
            "unit": unit,
            "label": label,
            "quality": quality,
            "updated_at": utc_now(),
            "timestamp_ns": frame.timestamp_ns,
            "received_at_monotonic": frame.received_at_monotonic,
            "can_id": frame.can_id_hex,
            "message_name": frame.message_name or "",
            "channel": frame.channel,
        }
        self.current_by_source[(key, frame.channel)] = item
        existing = self.current.get(key)
        if not existing or float(existing.get("received_at_monotonic", 0)) <= float(
            frame.received_at_monotonic
        ):
            self.current[key] = item
        if isinstance(value, (int, float, bool)):
            self.timeseries[key].append(
                {
                    "t": item["updated_at"],
                    "value": float(value),
                    "unit": unit,
                    "quality": quality,
                    "timestamp_ns": frame.timestamp_ns,
                    "received_at_monotonic": frame.received_at_monotonic,
                    "can_id": frame.can_id_hex,
                    "message_name": frame.message_name or "",
                    "channel": frame.channel,
                }
            )

    def snapshot(self) -> dict:
        return {
            "signals": deepcopy(self.current),
            "watchlist": list(self.watchlist),
            "updated_at": self._latest_update() or utc_now(),
            "quality": self.overall_quality(),
        }

    def timeseries_batch(self, keys: list[str] | None = None) -> dict:
        selected = keys or self.watchlist
        return {key: list(self.timeseries.get(key, []))[-300:] for key in selected}

    def threshold_status(self) -> dict:
        soc = self._number("BMS_SOC")
        warning = self._number("VCU_Max_Warning_Level")
        return {
            "BMS_SOC": "UNAVAILABLE" if soc is None else "PASS" if soc >= 30 else "FAIL",
            "VCU_Max_Warning_Level": "UNAVAILABLE" if warning is None else "PASS" if warning == 0 else "FAIL",
        }

    def freshest(self, *keys: str, max_age_seconds: float = 1.0) -> dict | None:
        now = time.monotonic()
        candidates = [self.current.get(key) for key in keys]
        fresh = [
            item
            for item in candidates
            if item
            and item.get("quality", "good") == "good"
            and now - float(item.get("received_at_monotonic", 0)) <= max_age_seconds
        ]
        return max(fresh, key=lambda item: float(item.get("received_at_monotonic", 0))) if fresh else None

    def fresh_value(self, *keys: str, max_age_seconds: float = 1.0):
        item = self.freshest(*keys, max_age_seconds=max_age_seconds)
        return item.get("value") if item else None

    def require_sample(
        self,
        key: str,
        *,
        max_age_seconds: float = 1.0,
        allowed_qualities: set[str] | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        item = self.current_by_source.get((key, channel)) if channel else self.current.get(key)
        if not item:
            raise KeyError("signal is missing")
        qualities = allowed_qualities or {"good"}
        quality = str(item.get("quality", "invalid"))
        if quality not in qualities:
            raise ValueError(f"signal quality is {quality!r}, expected one of {sorted(qualities)}")
        received = float(item.get("received_at_monotonic", 0) or 0)
        if received <= 0:
            raise ValueError("signal has no trusted receive timestamp")
        age = time.monotonic() - received
        if age > max_age_seconds:
            raise ValueError(f"signal is stale: age={age:.3f}s > {max_age_seconds:.3f}s")
        if not item.get("can_id") or not item.get("channel"):
            raise ValueError("signal has no source CAN ID/channel")
        return deepcopy(item) | {"age_ms": round(age * 1000, 3)}

    def window(
        self,
        key: str,
        *,
        since_monotonic: float,
        allowed_qualities: set[str] | None = None,
        channel: str | None = None,
    ) -> list[dict[str, Any]]:
        qualities = allowed_qualities or {"good"}
        return [
            deepcopy(item)
            for item in self.timeseries.get(key, [])
            if float(item.get("received_at_monotonic", 0)) >= since_monotonic
            and str(item.get("quality", "invalid")) in qualities
            and item.get("can_id")
            and item.get("channel")
            and (channel is None or item.get("channel") == channel)
        ]

    def overall_quality(self, max_age_seconds: float = 2.0) -> str:
        if not self.current:
            return "unavailable"
        now = time.monotonic()
        fresh = [
            item
            for item in self.current.values()
            if item.get("quality") == "good"
            and now - float(item.get("received_at_monotonic", 0)) <= max_age_seconds
        ]
        if not fresh:
            return "unavailable"
        return "good" if len(fresh) == len(self.current) else "degraded"

    def dashboard_summary(self, watchlist: list[str] | None = None) -> dict:
        quality = self.overall_quality()
        updated_at = self._latest_update() or utc_now()
        cell_values = [
            float(item["value"])
            for key, item in self.current.items()
            if "cell" in key.lower()
            and "voltage" in key.lower()
            and isinstance(item.get("value"), (int, float))
        ]
        temperatures = [
            value
            for key in ("NTC1", "NTC2", "NTC3")
            if (value := self._number(key)) is not None
        ]
        wheel_values = {
            key: self._rpm_to_kmh(key)
            for key in (
                "Wheel_Speed_Front_Left_RPM",
                "Wheel_Speed_Front_Right_RPM",
                "Wheel_Speed_Rear_Left_RPM",
                "Wheel_Speed_Rear_Right_RPM",
            )
        }
        warning = int(self._number("VCU_Max_Warning_Level") or 0)
        current_values = [
            value
            for key in ("Torque_feed_left", "Torque_feed_right")
            if (value := self._number(key)) is not None
        ]
        speed_values = [
            value
            for key in ("Speed_feed_left", "Speed_feed_right")
            if (value := self._number(key)) is not None
        ]
        thresholds = self.threshold_status()
        return {
            "status": {
                "overall": "normal" if warning == 0 and quality == "good" else "degraded" if quality != "unavailable" else "unavailable",
                "updated_at": updated_at,
                "mock": False,
                "quality": quality,
            },
            "bms": {
                "status": self._status_label(["BMS_Voltage", "BMS_Current", "BMS_SOC"]),
                "total_voltage": self._number("BMS_Voltage") or 0.0,
                "current": self._number("BMS_Current") or 0.0,
                "soc": self._number("BMS_SOC") or 0.0,
                "ntc_temperature": round(sum(temperatures) / len(temperatures), 1) if temperatures else 0.0,
                "cell_max_voltage": max(cell_values, default=0.0),
                "cell_min_voltage": min(cell_values, default=0.0),
                "cell_delta_mv": round((max(cell_values) - min(cell_values)) * 1000, 1) if cell_values else 0.0,
                "charge_discharge_state": self._charge_label(),
                "trend": {
                    "voltage": self._trend("BMS_Voltage"),
                    "current": self._trend("BMS_Current"),
                    "soc": self._trend("BMS_SOC"),
                    "ntc": self._trend("NTC1"),
                },
            },
            "vehicle": {
                "status": self._status_label(["CCU_Shift_Level_Status", "CCU_Vehicle_Speed"]),
                "gear": str(self.current.get("CCU_Shift_Level_Status", {}).get("label") or "-"),
                "drive_mode": self._drive_mode_label(),
                "ignition": "ON" if (self._number("CCU_Ignition_Status") or 0) > 0 else "OFF",
                "parking": "ENGAGED" if bool(self.current.get("Brake_Status", {}).get("value")) else "RELEASED",
                "speed": self._number("CCU_Vehicle_Speed", "Vehicle_Speed") or 0.0,
            },
            "wheel_speed": {
                "status": self._status_label(list(wheel_values)),
                "unit": "km/h",
                "front_left": wheel_values["Wheel_Speed_Front_Left_RPM"],
                "front_right": wheel_values["Wheel_Speed_Front_Right_RPM"],
                "rear_left": wheel_values["Wheel_Speed_Rear_Left_RPM"],
                "rear_right": wheel_values["Wheel_Speed_Rear_Right_RPM"],
            },
            "steering": {
                "status": self._status_label(["SAS_Front_Angle", "SAS_Rear_Angle"]),
                "front_cmd": self._number("SCU_Steering_Angle_Front") or 0.0,
                "front_feedback": self._number("SAS_Front_Angle") or 0.0,
                "rear_cmd": self._number("SCU_Steering_Angle_Rear") or 0.0,
                "rear_feedback": self._number("SAS_Rear_Angle") or 0.0,
                "front_trend": self._trend("SAS_Front_Angle"),
                "rear_trend": self._trend("SAS_Rear_Angle"),
            },
            "motor": {
                "status": self._status_label(["Heartbeat_0x703", "Heartbeat_0x704"]),
                "speed_rpm": round(sum(speed_values) / len(speed_values), 1) if speed_values else 0.0,
                "phase_current_a": round(sum(current_values) / len(current_values), 1) if current_values else 0.0,
                "heartbeat": "0x703 / 0x704",
                "heartbeat_status": self._status_label(["Heartbeat_0x703", "Heartbeat_0x704"]),
                "speed_trend": self._combined_trend(["Speed_feed_left", "Speed_feed_right"]),
                "current_trend": self._combined_trend(["Torque_feed_left", "Torque_feed_right"]),
            },
            "lights_brake": {
                "left_turn": self._on_off("Left_Turn_Light_Status"),
                "right_turn": self._on_off("Right_Turn_Light_Status"),
                "position_light": self._on_off("Position_Light_Status"),
                "low_beam": self._on_off("Low_Beam_Status"),
                "brake_request": self._on_off("Brake_Status"),
            },
            "alarm": {
                "status": "正常" if warning == 0 else "告警",
                "level": warning,
                "label": {0: "Normal", 1: "Warning", 2: "Fault", 3: "Critical"}.get(min(3, warning), "Critical"),
                "thresholds": [
                    {"name": "SOC阈值", "status": self._threshold_label(thresholds["BMS_SOC"])},
                    {"name": "告警等级", "status": self._threshold_label(thresholds["VCU_Max_Warning_Level"])},
                    {"name": "保护位", "status": "正常" if not (self._number("BMS_Protect_Bitmap") or 0) else "触发"},
                ],
            },
            "watchlist": self.watchlist_rows(watchlist),
        }

    def watchlist_rows(self, keys: list[str] | None = None) -> list[dict[str, Any]]:
        rows = []
        for key in keys or self.watchlist:
            item = self.current.get(key)
            label, threshold = WATCHLIST_CATALOG.get(key, (key, "-"))
            rows.append(
                {
                    "signal_name": label,
                    "signal_key": key,
                    "can_id": item.get("can_id", "-") if item else "-",
                    "channel": item.get("channel", "-") if item else "-",
                    "value": item.get("value", 0) if item else 0,
                    "unit": item.get("unit", "") if item else "",
                    "threshold": threshold,
                    "quality": "100%" if item and item.get("quality") == "good" else "0%",
                    "updated_at": item.get("updated_at", "-") if item else "-",
                    "trend": self._trend(key),
                }
            )
        return rows

    def _number(self, *keys: str) -> float | None:
        for key in keys:
            value = self.current.get(key, {}).get("value")
            if isinstance(value, bool):
                return float(value)
            try:
                if value is not None:
                    return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def _trend(self, key: str, count: int = 24) -> list[float]:
        return [float(item["value"]) for item in list(self.timeseries.get(key, []))[-count:] if item.get("quality") == "good"]

    def _combined_trend(self, keys: list[str], count: int = 24) -> list[float]:
        series = [self._trend(key, count) for key in keys]
        series = [values for values in series if values]
        if not series:
            return []
        length = min(len(values) for values in series)
        return [round(sum(values[-length + index] for values in series) / len(series), 3) for index in range(length)]

    def _rpm_to_kmh(self, key: str) -> float:
        value = self._number(key)
        return round(value / 50.0, 2) if value is not None else 0.0

    def _status_label(self, keys: list[str]) -> str:
        return "正常" if any(key in self.current for key in keys) else "无数据"

    def _charge_label(self) -> str:
        label = str(self.current.get("Charge_or_Discharge_State", {}).get("label") or "")
        return {"idle": "空闲", "charging": "充电", "discharging": "放电", "reserved": "保留"}.get(label, "无数据")

    def _drive_mode_label(self) -> str:
        value = self._number("CCU_Drive_Mode")
        return {0: "Manual", 1: "Remote", 2: "Auto"}.get(int(value), "-") if value is not None else "-"

    def _on_off(self, key: str) -> str:
        item = self.current.get(key)
        return "ON" if item and bool(item.get("value")) else "OFF"

    @staticmethod
    def _threshold_label(value: str) -> str:
        return {"PASS": "正常", "FAIL": "异常", "UNAVAILABLE": "无数据"}.get(value, value)

    def _latest_update(self) -> str | None:
        timestamps = [item.get("updated_at") for item in self.current.values() if item.get("updated_at")]
        return str(max(timestamps)) if timestamps else None
