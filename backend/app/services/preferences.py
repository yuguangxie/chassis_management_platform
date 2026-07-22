from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any



DEFAULTS = {
    "watchlist": [
        "BMS_Voltage",
        "BMS_Current",
        "BMS_SOC",
        "CCU_Vehicle_Speed",
        "Wheel_Speed_Front_Left_RPM",
        "SAS_Front_Angle",
        "Torque_feed_left",
        "BMS_Protect_Bitmap",
    ],
    "curve_selection": [],
    "signal_dashboard_layout": {},
}


class PreferenceService:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return json.loads(json.dumps(DEFAULTS))
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return json.loads(json.dumps(DEFAULTS))
        return {**json.loads(json.dumps(DEFAULTS)), **payload}

    def get(self, key: str) -> Any:
        with self._lock:
            return json.loads(json.dumps(self._data.get(key)))

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary.replace(self.path)
