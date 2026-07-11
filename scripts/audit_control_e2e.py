from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = "http://127.0.0.1:8800/api/v1"


def call(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        BASE + path,
        data=raw,
        method=method,
        headers={"Content-Type": "application/json", "X-Trace-Id": "audit-control"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            content = json.loads(response.read().decode("utf-8"))
            return {"status": response.status, "body": content}
    except HTTPError as exc:
        return {"status": exc.code, "body": json.loads(exc.read().decode("utf-8"))}


def signal_values() -> dict[str, Any]:
    snapshot = call("GET", "/signals/current")["body"].get("signals", {})
    keys = ["CCU_Vehicle_Speed", "SAS_Front_Angle", "SAS_Rear_Angle", "Brake_Status"]
    return {key: snapshot.get(key) for key in keys}


def main() -> int:
    command = {
        "gear": "D",
        "drive_mode": "Remote",
        "target_speed": 2.0,
        "front_steer": -60,
        "rear_steer": 60,
        "brake_enable": False,
        "left_turn": False,
        "right_turn": False,
        "position_light": True,
        "low_beam": False,
        "control_mode": "speed",
    }
    result: dict[str, Any] = {
        "audit_time": datetime.now().astimezone().isoformat(),
        "scope": "loopback-only temporary channels.dev.yaml",
        "initial_interlock": call("GET", "/control/interlock-status"),
        "initial_signals": signal_values(),
    }
    result["preview"] = call("POST", "/control/121/preview", command)
    result["send_once"] = call("POST", "/control/121/send-once", command)
    time.sleep(1.2)
    result["after_send_once_signals"] = signal_values()

    result["start_periodic"] = call("POST", "/control/121/start-periodic?period_ms=50", command)
    time.sleep(0.45)
    result["stop_periodic"] = call("POST", "/control/121/stop", {})
    result["safe_stop"] = call("POST", "/control/safe-stop", {})
    time.sleep(1.2)
    result["after_safe_stop_signals"] = signal_values()

    overspeed = dict(command)
    overspeed["target_speed"] = 9.0
    result["overspeed_attempt"] = call("POST", "/control/121/send-once", overspeed)
    result["emergency_stop"] = call("POST", "/control/emergency-stop", {})
    result["send_during_emergency"] = call("POST", "/control/121/send-once", command)
    result["emergency_release"] = call("POST", "/control/emergency-stop/release", {})
    result["final_status"] = call("GET", "/control/status")

    preview = result["preview"]["body"]
    result["checks"] = {
        "actual_front_minus_60_is_c4": preview.get("data", [None, None])[1] == 0xC4,
        "actual_rear_plus_60_is_3c": preview.get("data", [None, None, None])[2] == 0x3C,
        "ui_preview_matches_transmitted_payload": preview.get("bytes_hex") == [f"{item:02X}" for item in preview.get("data", [])],
        "overspeed_blocked": result["overspeed_attempt"]["status"] == 409,
        "emergency_blocks_send": result["send_during_emergency"]["status"] == 409,
        "send_once_reached_simulator": float((result["after_send_once_signals"].get("CCU_Vehicle_Speed") or {}).get("value") or 0) > 0,
        "safe_stop_reduced_speed": float((result["after_safe_stop_signals"].get("CCU_Vehicle_Speed") or {}).get("value") or 0) < float((result["after_send_once_signals"].get("CCU_Vehicle_Speed") or {}).get("value") or 0),
    }
    output = Path("docs/audit/evidence/simulation/control_loopback_e2e.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["checks"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
