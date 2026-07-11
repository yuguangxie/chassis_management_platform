from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = "http://127.0.0.1:8800/api/v1"


def call(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(BASE + path, data=raw, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            return {"status": response.status, "body": json.loads(response.read().decode("utf-8"))}
    except HTTPError as exc:
        return {"status": exc.code, "body": json.loads(exc.read().decode("utf-8"))}


def create(label: str) -> str:
    response = call(
        "POST",
        "/eol/sessions",
        {
            "chassis_no": f"AUDIT-{label}",
            "vin": "LAUDIT00000000002",
            "serial_no": label,
            "operator": "audit",
            "station_id": "EOL-STATION-01",
            "plan_id": "default_chassis_eol_v1",
            "remarks": label,
        },
    )
    return str(response["body"]["id"])


def session(sid: str) -> dict[str, Any]:
    return call("GET", f"/eol/sessions/{sid}")["body"]


def db_count() -> int:
    connection = sqlite3.connect("data/chassis_eol.db")
    try:
        return int(connection.execute("SELECT COUNT(*) FROM test_sessions").fetchone()[0])
    finally:
        connection.close()


def main() -> int:
    result: dict[str, Any] = {"audit_time": datetime.now().astimezone().isoformat(), "db_sessions_before": db_count()}

    pause_sid = create("pause")
    call("POST", f"/eol/sessions/{pause_sid}/start", {})
    time.sleep(0.2)
    pause_response = call("POST", f"/eol/sessions/{pause_sid}/pause", {})
    pause_steps = len(session(pause_sid).get("steps", []))
    time.sleep(0.45)
    pause_later = session(pause_sid)
    result["pause"] = {
        "response": pause_response,
        "steps_at_pause": pause_steps,
        "steps_after_450ms": len(pause_later.get("steps", [])),
        "status_after_450ms": pause_later.get("status"),
        "execution_continued": len(pause_later.get("steps", [])) > pause_steps,
    }
    call("POST", f"/eol/sessions/{pause_sid}/resume", {})
    time.sleep(0.8)
    result["pause"]["final"] = session(pause_sid)

    abort_sid = create("abort")
    call("POST", f"/eol/sessions/{abort_sid}/start", {})
    time.sleep(0.2)
    abort_response = call("POST", f"/eol/sessions/{abort_sid}/abort", {})
    time.sleep(1.2)
    abort_final = session(abort_sid)
    result["abort"] = {
        "response": abort_response,
        "final_status": abort_final.get("status"),
        "final_result": abort_final.get("overall_result"),
        "step_count": len(abort_final.get("steps", [])),
        "abort_was_respected": abort_final.get("status") == "ABORTED",
    }

    emergency_sid = create("emergency")
    call("POST", f"/eol/sessions/{emergency_sid}/start", {})
    time.sleep(0.2)
    emergency_response = call("POST", f"/eol/sessions/{emergency_sid}/emergency-stop", {})
    time.sleep(1.2)
    emergency_final = session(emergency_sid)
    result["emergency"] = {
        "response": emergency_response,
        "final_status": emergency_final.get("status"),
        "final_result": emergency_final.get("overall_result"),
        "step_count": len(emergency_final.get("steps", [])),
        "emergency_stopped_test": emergency_final.get("overall_result") != "PASS",
    }
    call("POST", "/control/emergency-stop/release", {})

    first = create("concurrent-a")
    second = create("concurrent-b")
    call("POST", f"/eol/sessions/{first}/start", {})
    call("POST", f"/eol/sessions/{second}/start", {})
    time.sleep(1.4)
    first_final, second_final = session(first), session(second)
    result["concurrent"] = {
        "first_result": first_final.get("overall_result"),
        "second_result": second_final.get("overall_result"),
        "both_executed": bool(first_final.get("steps")) and bool(second_final.get("steps")),
    }

    stop_channels = call("POST", "/can/channels/stop-all", {})
    offline_status = call("GET", "/can/channels/status")
    disconnected_sid = create("can-disconnected")
    call("POST", f"/eol/sessions/{disconnected_sid}/start", {})
    time.sleep(1.4)
    disconnected_final = session(disconnected_sid)
    result["can_disconnected"] = {
        "stop_response": stop_channels,
        "channel_status": offline_status,
        "final_status": disconnected_final.get("status"),
        "final_result": disconnected_final.get("overall_result"),
        "incorrectly_passed": disconnected_final.get("overall_result") == "PASS",
    }
    call("POST", "/can/channels/CAN1/connect", {})
    call("POST", "/can/channels/CAN2/connect", {})

    result["db_sessions_after"] = db_count()
    result["sessions_persisted"] = result["db_sessions_after"] > result["db_sessions_before"]
    Path("docs/audit/evidence/tests/eol_state_machine.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        "pause_execution_continued": result["pause"]["execution_continued"],
        "abort_was_respected": result["abort"]["abort_was_respected"],
        "emergency_stopped_test": result["emergency"]["emergency_stopped_test"],
        "concurrent_both_executed": result["concurrent"]["both_executed"],
        "can_disconnected_incorrectly_passed": result["can_disconnected"]["incorrectly_passed"],
        "sessions_persisted": result["sessions_persisted"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
