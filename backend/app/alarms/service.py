from __future__ import annotations
from app.services.signal_store import SignalStore
from .models import Alarm

class AlarmService:
    def __init__(self, signals: SignalStore) -> None:
        self.signals = signals
        self.acked: set[str] = set()
        self.system_alarms: dict[str, Alarm] = {}

    def current(self) -> list[dict]:
        level = int(self.signals.current.get("VCU_Max_Warning_Level", {}).get("value", 0) or 0)
        alarms: list[Alarm] = []
        alarms.extend(self.system_alarms.values())
        if level >= 1:
            alarms.append(Alarm(id="vcu_warning", level=level, label="VCU Warning", description=f"最高告警等级 {level}"))
        soc = float(self.signals.current.get("BMS_SOC", {}).get("value", 100) or 0)
        if soc < 30:
            alarms.append(Alarm(id="bms_low_soc", level=3, label="BMS Low SOC", description=f"SOC {soc}% 低于阈值"))
        return [a.model_dump() | {"acked": a.id in self.acked} for a in alarms]

    def raise_system_alarm(self, alarm_id: str, level: int, label: str, description: str) -> dict:
        alarm = Alarm(id=alarm_id, level=level, label=label, description=description)
        self.system_alarms[alarm_id] = alarm
        return alarm.model_dump() | {"acked": alarm_id in self.acked}

    def clear_system_alarm(self, alarm_id: str) -> None:
        self.system_alarms.pop(alarm_id, None)

    def max_level(self) -> int:
        alarms = self.current()
        return max([a["level"] for a in alarms], default=0)
