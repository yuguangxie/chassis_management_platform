from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def call(base: str, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    raw = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        f"{base}/api/v1{path}",
        data=raw,
        method=method,
        headers={"Content-Type": "application/json", "X-Trace-Id": "audit-eol"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--expected", choices=["PASS", "FAIL"], required=True)
    parser.add_argument("--base", default="http://127.0.0.1:8800")
    parser.add_argument("--output-dir", default="docs/audit/evidence/simulation")
    args = parser.parse_args()
    reports_dir = Path("data/reports")
    before = {path.name for path in reports_dir.glob("*")}
    _, channels = call(args.base, "GET", "/can/channels/status")
    _, signals = call(args.base, "GET", "/signals/current")
    _, alarms = call(args.base, "GET", "/alarms/current")
    create_status, session = call(
        args.base,
        "POST",
        "/eol/sessions",
        {
            "chassis_no": f"AUDIT-{args.profile}",
            "vin": "LAUDIT00000000001",
            "serial_no": f"AUDIT-{args.profile}",
            "operator": "audit",
            "station_id": "EOL-STATION-01",
            "plan_id": "default_chassis_eol_v1",
            "remarks": f"audit profile {args.profile}",
        },
    )
    sid = session.get("id") or session.get("session_id")
    start_status, start_body = call(args.base, "POST", f"/eol/sessions/{sid}/start", {})
    final_status = None
    final_body: Any = None
    started = time.monotonic()
    while time.monotonic() - started < 8:
        final_status, final_body = call(args.base, "GET", f"/eol/sessions/{sid}")
        if isinstance(final_body, dict) and final_body.get("status") not in {"IDLE", "RUNNING", "PAUSED"}:
            break
        time.sleep(0.1)
    after = {path.name for path in reports_dir.glob("*")}
    new_files = sorted(after - before)
    actual = final_body.get("overall_result") if isinstance(final_body, dict) else None
    result = {
        "audit_time": datetime.now().astimezone().isoformat(),
        "profile": args.profile,
        "expected_result": args.expected,
        "actual_result": actual,
        "matches_expected": actual == args.expected,
        "create_http_status": create_status,
        "start_http_status": start_status,
        "final_http_status": final_status,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "session_id": sid,
        "session_status": final_body.get("status") if isinstance(final_body, dict) else None,
        "step_count": len(final_body.get("steps", [])) if isinstance(final_body, dict) else 0,
        "failed_steps": [step for step in final_body.get("steps", []) if step.get("result") == "FAIL"] if isinstance(final_body, dict) else [],
        "channels": channels,
        "signal_snapshot": signals,
        "alarms": alarms,
        "start_response": start_body,
        "final_session": final_body,
        "new_report_files": new_files,
        "report_files_exist": all((reports_dir / name).is_file() and (reports_dir / name).stat().st_size > 0 for name in new_files),
    }
    output = Path(args.output_dir) / f"{args.profile}_eol_result.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {key: result[key] for key in ("profile", "expected_result", "actual_result", "matches_expected", "session_status", "step_count", "elapsed_seconds", "new_report_files")},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
