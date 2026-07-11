from __future__ import annotations

"""Loopback verification for phase 03 business data, reports, and history."""

import argparse
import base64
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8800/api/v1"
VIEWER = {"Authorization": "Bearer dev-viewer-token"}
OPERATOR = {"Authorization": "Bearer dev-operator-token"}


class VerificationError(RuntimeError):
    pass


def wait_until(check, message: str, timeout: float = 30.0, interval: float = 0.15):
    deadline = time.monotonic() + timeout
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = check()
            if last:
                return last
        except (OSError, httpx.HTTPError, KeyError, ValueError):
            pass
        time.sleep(interval)
    raise VerificationError(f"{message}; last={last!r}")


def stop_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def json_file(output: Path, name: str, payload: Any) -> None:
    (output / "api").mkdir(parents=True, exist_ok=True)
    (output / "api" / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def api_record(
    client: httpx.Client,
    output: Path,
    name: str,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    expected: int = 200,
) -> dict[str, Any]:
    response = client.request(method, f"{BASE}{path}", headers=headers, json=body)
    try:
        payload: Any = response.json()
    except ValueError:
        payload = {"content_type": response.headers.get("content-type"), "size": len(response.content)}
    record = {
        "request": {"method": method, "path": path, "body": body},
        "status_code": response.status_code,
        "trace_id": response.headers.get("x-trace-id"),
        "body": payload,
    }
    json_file(output, name, record)
    if response.status_code != expected:
        raise VerificationError(f"{method} {path}: expected {expected}, got {response.status_code}: {payload}")
    return record


def download(
    client: httpx.Client,
    output: Path,
    url: str,
    suggested_name: str,
) -> dict[str, Any]:
    response = client.get(f"{BASE}{url}", headers=VIEWER)
    if response.status_code != 200:
        raise VerificationError(f"download {url}: {response.status_code} {response.text}")
    target = output / "downloads" / suggested_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return {
        "path": str(target.relative_to(output)),
        "bytes": len(response.content),
        "content_type": response.headers.get("content-type"),
        "trace_id": response.headers.get("x-trace-id"),
    }


def session_counts(session_id: str) -> dict[str, int]:
    database = sqlite3.connect(ROOT / "data" / "chassis_eol.db")
    tables = [
        "test_sessions",
        "test_steps",
        "test_assertions",
        "raw_can_frames",
        "decoded_signals",
        "signal_statistics",
        "alarms",
        "reports",
        "operator_actions",
    ]
    counts: dict[str, int] = {}
    try:
        for table in tables:
            columns = {row[1] for row in database.execute(f"PRAGMA table_info({table})")}
            query = f"SELECT COUNT(*) FROM {table} WHERE id=?" if table == "test_sessions" else f"SELECT COUNT(*) FROM {table} WHERE session_id=?"
            if table != "test_sessions" and "session_id" not in columns:
                continue
            counts[table] = int(database.execute(query, (session_id,)).fetchone()[0])
    finally:
        database.close()
    return counts


def wait_terminal(client: httpx.Client, session_id: str) -> dict[str, Any]:
    def terminal() -> dict[str, Any] | None:
        payload = client.get(f"{BASE}/eol/sessions/{session_id}", headers=VIEWER).json()
        return payload if payload.get("status") in {"PASSED", "FAILED", "ABORTED", "EMERGENCY_STOPPED"} else None

    return wait_until(terminal, f"session {session_id} did not finish", timeout=70.0, interval=0.2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    backend = simulator = None
    backend_log = simulator_log = None
    result: dict[str, Any] = {
        "verification": "phase-03-business-data-api-reports",
        "network_boundary": "127.0.0.1 only",
        "real_vehicle_connected": False,
        "passed": False,
    }
    try:
        environment = {
            **__import__("os").environ,
            "CHASSIS_RUNTIME_PROFILE": "dev",
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
        }
        backend_log = (output / "backend.log").open("w", encoding="utf-8")
        backend = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "dev_backend.py")],
            cwd=ROOT,
            env=environment,
            stdout=backend_log,
            stderr=subprocess.STDOUT,
        )
        client = httpx.Client(timeout=15.0)
        wait_until(lambda: client.get(f"{BASE}/health").status_code == 200, "backend did not start", timeout=20)

        simulator_log = (output / "simulator.log").open("w", encoding="utf-8")
        simulator = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "scripts" / "dev_simulator.py"),
                "--profile",
                "normal_pass",
                "--can1-target",
                "127.0.0.1:8234",
                "--can2-target",
                "127.0.0.1:8235",
                "--can1-listen",
                "127.0.0.1:12341",
                "--can2-listen",
                "127.0.0.1:12342",
            ],
            cwd=ROOT,
            env=environment,
            stdout=simulator_log,
            stderr=subprocess.STDOUT,
        )

        def live_channels():
            response = client.get(f"{BASE}/can/channels/status", headers=VIEWER)
            payload = response.json() if response.status_code == 200 else []
            return payload if len(payload) == 2 and all(row.get("online") for row in payload) else None

        result["channels"] = wait_until(live_channels, "CAN channels did not become online", timeout=20)
        wait_until(
            lambda: client.get(f"{BASE}/can/frames/latest", headers=VIEWER).json().get("total", 0) >= 8,
            "simulator frames did not reach the backend",
            timeout=20,
        )

        dashboard_paths = {
            "overview.json": "/overview/summary",
            "can_latest.json": "/can/frames/latest",
            "can_statistics.json": "/can/statistics/monitor",
            "signal_dashboard.json": "/signals/dashboard",
            "curve_config.json": "/signals/curve-config",
            "curve_timeseries.json": "/signals/timeseries?mode=live",
            "alarm_dashboard.json": "/alarms/dashboard",
        }
        provenance: dict[str, Any] = {}
        for name, path in dashboard_paths.items():
            record = api_record(client, output, name, "GET", path, headers=VIEWER)
            body = record["body"]
            provenance[path] = {
                key: body.get(key) for key in ("data_source", "mock", "quality", "updated_at", "trace_id")
            }
            if body.get("mock") is not False or not body.get("data_source") or not body.get("updated_at"):
                raise VerificationError(f"dashboard provenance invalid: {path}: {body}")

        api_record(client, output, "decoded_0x77.json", "GET", "/can/frames/latest/0x77/decoded", headers=VIEWER)
        api_record(client, output, "decoded_0x102.json", "GET", "/can/frames/latest/0x102/decoded", headers=VIEWER)

        created = api_record(
            client,
            output,
            "create_session.json",
            "POST",
            "/eol/sessions",
            headers=OPERATOR,
            body={
                "chassis_no": "PH3-NORMAL-001",
                "vin": "PH3NORMAL0000001",
                "serial_no": f"PH3-{int(time.time() * 1000)}",
                "station_id": "EOL-STATION-01",
                "plan_id": "default_chassis_eol_v1",
            },
        )
        session_id = created["body"]["id"]
        api_record(client, output, "start_session.json", "POST", f"/eol/sessions/{session_id}/start", headers=OPERATOR)
        terminal = wait_terminal(client, session_id)
        json_file(output, "terminal_session.json", terminal)
        if terminal.get("status") != "PASSED" or len(terminal.get("steps", [])) != 12:
            raise VerificationError(f"normal_pass EOL result invalid: {terminal}")
        api_record(client, output, "decoded_0x121.json", "GET", "/can/frames/latest/0x121/decoded", headers=VIEWER)

        reports = api_record(client, output, "reports_dashboard.json", "GET", "/reports/dashboard", headers=VIEWER)["body"]
        matching_reports = [item for item in reports["reports"] if item["session_id"] == session_id]
        pdf = next(item for item in matching_reports if item["type"] == ".pdf")
        json_report = next(item for item in matching_reports if item["type"] == ".json")
        preview = api_record(client, output, "report_preview.json", "GET", f"/reports/{pdf['report_id']}/preview", headers=VIEWER)["body"]
        image = preview.get("preview_image_data_url") or ""
        if not image.startswith("data:image/png;base64,"):
            raise VerificationError("PDF preview did not return a rendered image")
        image_path = output / "screenshots" / "report_preview_page_1.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(base64.b64decode(image.split(",", 1)[1]))

        report_actions = {
            "report_scan.json": ("POST", "/reports/scan", {}),
            "report_open_directory.json": ("POST", "/reports/open-directory", {}),
            "report_export_word.json": ("POST", f"/reports/{pdf['report_id']}/export-word", {}),
            "report_export_pdf.json": ("POST", f"/reports/{pdf['report_id']}/export-pdf", {}),
            "report_print.json": ("POST", f"/reports/{pdf['report_id']}/print", {}),
            "report_regenerate.json": ("POST", f"/reports/{pdf['report_id']}/regenerate", {}),
        }
        action_results = {}
        for name, (method, path, body) in report_actions.items():
            action_results[name] = api_record(client, output, name, method, path, headers=OPERATOR, body=body)["body"]
        for name in ("report_export_word.json", "report_export_pdf.json"):
            details = action_results[name].get("details", {})
            action_results[name]["download"] = download(
                client,
                output,
                str(details["download_url"]),
                str(details["file_name"]),
            )
        report_file = download(client, output, f"/reports/{pdf['report_id']}/file", pdf["path"].split("\\")[-1])

        history = api_record(
            client,
            output,
            "history_dashboard.json",
            "GET",
            f"/history/dashboard?chassis_no=PH3-NORMAL-001&page=1&page_size=20",
            headers=VIEWER,
        )["body"]
        if history["pagination"]["total"] < 1 or history["sessions"][0]["session_id"] != session_id:
            raise VerificationError(f"history did not return the EOL session: {history}")
        api_record(client, output, "history_timeline.json", "GET", f"/test-sessions/{session_id}/timeline", headers=VIEWER)
        api_record(client, output, "history_operator_actions.json", "GET", f"/test-sessions/{session_id}/operator-actions", headers=VIEWER)
        downloads = api_record(client, output, "history_downloads.json", "GET", f"/test-sessions/{session_id}/downloads", headers=VIEWER)["body"]
        api_record(client, output, "history_replay.json", "GET", f"/test-sessions/{session_id}/replay", headers=VIEWER)
        file_results = {}
        type_map = {
            "raw_can": "raw-can",
            "decoded_signals": "decoded-signals",
            "report_bundle": "report-bundle",
            "audit_log": "audit-log",
            "curve_replay": "curve-replay",
        }
        for item in downloads:
            key = item["key"]
            file_results[key] = download(client, output, f"/test-sessions/{session_id}/download/{type_map[key]}", f"{session_id}-{key}{item['extension'].split(' ')[0]}")
        exported_history = api_record(
            client,
            output,
            "history_export.json",
            "POST",
            "/history/export",
            headers=OPERATOR,
            body={"chassis_no": "PH3-NORMAL-001"},
        )["body"]
        history_export = download(
            client,
            output,
            str(exported_history["details"]["download_url"]),
            str(exported_history["details"]["file_name"]),
        )

        signal_actions = {
            "signal_watchlist.json": ("PUT", "/signals/watchlist", {"signals": ["Vehicle_Speed", "BMS_Voltage"]}),
            "signal_curve_selection.json": ("PUT", "/signals/curve-selection", {"signals": ["Vehicle_Speed", "BMS_Total_Voltage"]}),
            "signal_snapshot.json": ("POST", "/signals/snapshot", {}),
            "signal_export.json": ("POST", "/signals/export-csv", {"signals": ["Vehicle_Speed", "BMS_Total_Voltage"]}),
        }
        for name, (method, path, body) in signal_actions.items():
            action_results[name] = api_record(client, output, name, method, path, headers=OPERATOR, body=body)["body"]
        for name in ("signal_snapshot.json", "signal_export.json"):
            details = action_results[name]["details"]
            action_results[name]["download"] = download(client, output, str(details["download_url"]), str(details["file_name"]))

        database_counts = session_counts(session_id)
        json_preview = api_record(client, output, "json_report_preview.json", "GET", f"/reports/{json_report['report_id']}/preview", headers=VIEWER)["body"]
        traceability = (json_preview.get("json_summary") or {}).get("traceability") or {}
        required_traceability = ["software_version", "dbc_hash", "config_hash", "test_plan_id", "test_plan_version", "operator"]
        if not all(traceability.get(key) for key in required_traceability):
            raise VerificationError(f"report traceability incomplete: {traceability}")
        if not all(database_counts.get(key, 0) > 0 for key in ("test_sessions", "test_steps", "test_assertions", "raw_can_frames", "decoded_signals", "signal_statistics", "reports", "operator_actions")):
            raise VerificationError(f"database linkage incomplete: {database_counts}")

        result.update(
            {
                "session_id": session_id,
                "terminal_status": terminal.get("status"),
                "step_count": len(terminal.get("steps", [])),
                "dashboard_provenance": provenance,
                "database_counts": database_counts,
                "report": {
                    "pdf_report_id": pdf["report_id"],
                    "json_report_id": json_report["report_id"],
                    "preview_screenshot": str(image_path.relative_to(output)),
                    "direct_download": report_file,
                    "traceability": traceability,
                },
                "history_downloads": file_results,
                "history_export": history_export,
                "button_actions": {
                    name: {"ok": body.get("ok"), "message": body.get("message"), "trace_id": body.get("trace_id")}
                    for name, body in action_results.items()
                },
                "passed": True,
            }
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        stop_process(simulator)
        stop_process(backend)
        if simulator_log:
            simulator_log.close()
        if backend_log:
            backend_log.close()
        if "client" in locals():
            client.close()
    (output / "phase03_business_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
