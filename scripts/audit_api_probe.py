from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GET_ENDPOINTS = [
    "/health",
    "/overview/summary",
    "/config/system-dashboard",
    "/config",
    "/config/history",
    "/config/export",
    "/storage/stats",
    "/storage/trend",
    "/system/version",
    "/auth/roles",
    "/dbc/status",
    "/dbc/messages",
    "/can/channels/status",
    "/can/frames/latest",
    "/can/statistics",
    "/can/statistics/monitor",
    "/logs/raw-can-files",
    "/signals/current",
    "/signals/dashboard",
    "/signals/watchlist",
    "/signals/curve-config",
    "/signals/timeseries",
    "/signals/threshold-status",
    "/control/status",
    "/control/interlock-status",
    "/control/manual-feedback",
    "/control/manual-curves",
    "/eol/dashboard",
    "/alarms/dashboard",
    "/alarms/current",
    "/alarms/history",
    "/reports/dashboard",
    "/reports",
    "/reports/storage-stats",
    "/history/dashboard",
    "/history/statistics",
    "/test-sessions",
    "/audit/operator-actions",
]


ACTION_ENDPOINTS: list[tuple[str, str, dict[str, Any]]] = [
    ("POST", "/config/import", {}),
    ("POST", "/storage/cleanup", {}),
    ("POST", "/dbc/reload", {}),
    ("POST", "/can/channels/self-test", {}),
    ("POST", "/can/frames/clear-display", {}),
    ("POST", "/logs/export/raw-can", {}),
    ("POST", "/logs/export/csv", {}),
    ("POST", "/logs/load-history", {}),
    ("POST", "/signals/snapshot", {}),
    ("POST", "/signals/export-csv", {}),
    ("PUT", "/signals/curve-selection", {"signals": ["Vehicle_Speed"]}),
    (
        "POST",
        "/control/121/preview",
        {
            "shift": "D",
            "drive_mode": "Remote",
            "target_speed_kmh": 2.0,
            "front_steering": -60,
            "rear_steering": 60,
            "brake_enabled": False,
            "left_turn": False,
            "right_turn": False,
            "position_light": True,
            "low_beam": False,
        },
    ),
    ("POST", "/alarms/export-diagnosis", {}),
    ("POST", "/alarms/jump-can-frame", {}),
    ("POST", "/alarms/audit-sample/ack", {}),
    ("POST", "/alarms/audit-sample/override-request", {"reason": "audit"}),
    ("POST", "/reports/scan", {}),
    ("POST", "/history/export", {}),
]


def request_json(url: str, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json", "X-Trace-Id": "audit-probe"},
    )
    started = datetime.now().astimezone()
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
            headers = dict(response.headers.items())
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
        headers = dict(exc.headers.items())
    except URLError as exc:
        return {
            "url": url,
            "method": method,
            "status": None,
            "error": repr(exc),
            "started_at": started.isoformat(),
        }
    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError:
        parsed = raw
    return {
        "url": url,
        "method": method,
        "status": status,
        "headers": headers,
        "body": parsed,
        "started_at": started.isoformat(),
        "finished_at": datetime.now().astimezone().isoformat(),
    }


def slug(path: str) -> str:
    value = path.strip("/").replace("/", "__").replace("?", "_").replace("=", "-")
    return value or "root"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8800")
    parser.add_argument("--output", default="docs/audit/evidence/api")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    openapi_result = request_json(f"{args.base}/openapi.json")
    (output / "openapi_response.json").write_text(
        json.dumps(openapi_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    spec = openapi_result.get("body") if isinstance(openapi_result.get("body"), dict) else {}
    routes: list[dict[str, Any]] = []
    for path, operations in sorted(spec.get("paths", {}).items()):
        for method, operation in sorted(operations.items()):
            if method.lower() not in {"get", "post", "put", "delete", "patch", "options", "head"}:
                continue
            routes.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId", ""),
                    "has_request_body": bool(operation.get("requestBody")),
                    "response_codes": ",".join(sorted(operation.get("responses", {}).keys())),
                }
            )
    with (output / "openapi_routes.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(routes[0].keys()) if routes else ["method", "path"])
        writer.writeheader()
        writer.writerows(routes)

    results: list[dict[str, Any]] = []
    for path in GET_ENDPOINTS:
        result = request_json(f"{args.base}/api/v1{path}")
        results.append(result)
        (output / f"get__{slug(path)}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    for method, path, body in ACTION_ENDPOINTS:
        result = request_json(f"{args.base}/api/v1{path}", method, body)
        results.append(result)
        (output / f"{method.lower()}__{slug(path)}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    summary = {
        "audit_time": datetime.now().astimezone().isoformat(),
        "openapi_status": openapi_result.get("status"),
        "openapi_route_count": len(routes),
        "probe_count": len(results),
        "status_counts": {
            str(status): sum(1 for item in results if item.get("status") == status)
            for status in sorted({item.get("status") for item in results}, key=lambda value: str(value))
        },
        "results": [
            {
                "method": item.get("method"),
                "url": item.get("url"),
                "status": item.get("status"),
                "error": item.get("error"),
                "stub": item.get("body", {}).get("stub") if isinstance(item.get("body"), dict) else None,
                "message": item.get("body", {}).get("message") if isinstance(item.get("body"), dict) else None,
            }
            for item in results
        ],
    }
    (output / "api_probe_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0 if openapi_result.get("status") == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
