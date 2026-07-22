from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from typing import Any, Callable

import httpx


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8800/api/v1"
OPERATOR = {"Authorization": f"Bearer {os.getenv('CHASSIS_OPERATOR_TOKEN', '')}"}
VIEWER = {"Authorization": f"Bearer {os.getenv('CHASSIS_VIEWER_TOKEN', '')}"}
TERMINAL = {"PASSED", "FAILED", "ABORTED", "EMERGENCY_STOPPED"}
PROFILE_EXPECTATIONS = {
    "normal_pass": ("PASSED", None, 12),
    "bms_low_soc": ("FAILED", "bms_check", 3),
    "warning_fault": ("FAILED", "alarm_recheck", 11),
    "steering_no_response": ("FAILED", "steering_check", 8),
    "brake_fail": ("FAILED", "brake_stop_check", 10),
}


class VerificationError(RuntimeError):
    pass


def wait_until(
    callback: Callable[[], Any], timeout: float, message: str, interval: float = 0.1
) -> Any:
    deadline = time.monotonic() + timeout
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = callback()
            if last:
                return last
        except (OSError, httpx.HTTPError, KeyError, ValueError):
            pass
        time.sleep(interval)
    raise VerificationError(f"{message}; last={last!r}")


def stop_process(process: subprocess.Popen[Any] | None, *, kill: bool = False) -> None:
    if process is None or process.poll() is not None:
        return
    if kill:
        process.kill()
    else:
        process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def start_backend(output: Path, name: str, fault: str = ""):
    environment = os.environ.copy()
    environment.update(
        CHASSIS_RUNTIME_PROFILE="dev",
        PYTHONUNBUFFERED="1",
        PYTHONUTF8="1",
    )
    if fault:
        environment["CHASSIS_TEST_FAULT"] = fault
    log = (output / f"{name}_backend.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "dev_backend.py")],
        cwd=ROOT,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    client = httpx.Client(timeout=10.0)
    wait_until(
        lambda: client.get(f"{BASE}/health").status_code == 200,
        15,
        f"backend did not start for {name}",
    )
    return process, log, client, environment


def start_simulator(output: Path, name: str, profile: str, environment: dict[str, str]):
    log = (output / f"{name}_simulator.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "dev_simulator.py"),
            "--profile",
            profile,
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
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return process, log


def wait_channels(client: httpx.Client) -> list[dict[str, Any]]:
    return wait_until(
        lambda: (
            rows
            if len(rows := client.get(f"{BASE}/can/channels/status", headers=VIEWER).json()) == 2
            and all(row.get("online") for row in rows)
            else None
        ),
        15,
        "CAN channels did not become online",
    )


def create_and_start(client: httpx.Client, name: str) -> tuple[str, httpx.Response]:
    payload = {
        "chassis_no": f"PH2-{name.upper()[:20]}",
        "vin": f"PH2{name.upper().replace('_', '')[:13]:0<13}",
        "serial_no": f"PH2-{int(time.time() * 1000)}",
        "station_id": "EOL-STATION-01",
        "plan_id": "default_chassis_eol_v1",
    }
    created = client.post(f"{BASE}/eol/sessions", headers=OPERATOR, json=payload)
    created.raise_for_status()
    session_id = created.json()["id"]
    response = client.post(f"{BASE}/eol/sessions/{session_id}/start", headers=OPERATOR)
    return session_id, response


def wait_session(client: httpx.Client, session_id: str, timeout: float = 70) -> dict[str, Any]:
    return wait_until(
        lambda: (
            payload
            if (payload := client.get(f"{BASE}/eol/sessions/{session_id}", headers=VIEWER).json()).get("status")
            in TERMINAL
            else None
        ),
        timeout,
        f"EOL session {session_id} did not reach terminal state",
        interval=0.2,
    )


def database_counts(session_id: str) -> dict[str, int]:
    connection = sqlite3.connect(ROOT / "data" / "chassis_eol.db")
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
    for table in tables:
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        if table == "test_sessions":
            row = connection.execute(
                "SELECT COUNT(*) FROM test_sessions WHERE id=?", (session_id,)
            ).fetchone()
        elif "session_id" in columns:
            row = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE session_id=?", (session_id,)
            ).fetchone()
        else:
            row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        counts[table] = int(row[0])
    counts["software_versions"] = int(
        connection.execute("SELECT COUNT(*) FROM software_versions").fetchone()[0]
    )
    connection.close()
    return counts


def failed_step(session: dict[str, Any]) -> str | None:
    return next(
        (step.get("id") for step in session.get("steps", []) if step.get("result") == "FAIL"),
        None,
    )


def run_profile(output: Path, profile: str) -> dict[str, Any]:
    backend = simulator = None
    backend_log = simulator_log = None
    client = None
    try:
        backend, backend_log, client, environment = start_backend(output, profile)
        simulator, simulator_log = start_simulator(output, profile, profile, environment)
        channels = wait_channels(client)
        session_id, start_response = create_and_start(client, profile)
        start_response.raise_for_status()

        pause_check: dict[str, Any] | None = None
        concurrency_check: dict[str, Any] | None = None
        if profile == "normal_pass":
            wait_until(
                lambda: (
                    payload
                    if len(
                        (payload := client.get(
                            f"{BASE}/eol/sessions/{session_id}", headers=VIEWER
                        ).json()).get("steps", [])
                    )
                    >= 2
                    else None
                ),
                10,
                "normal profile did not start steps",
            )
            paused = client.post(
                f"{BASE}/eol/sessions/{session_id}/pause", headers=OPERATOR
            )
            paused.raise_for_status()
            before = client.get(
                f"{BASE}/eol/sessions/{session_id}", headers=VIEWER
            ).json()
            time.sleep(0.8)
            after = client.get(
                f"{BASE}/eol/sessions/{session_id}", headers=VIEWER
            ).json()
            pause_check = {
                "status": after.get("status"),
                "steps_before": len(before.get("steps", [])),
                "steps_after": len(after.get("steps", [])),
                "stable": len(before.get("steps", [])) == len(after.get("steps", [])),
            }
            client.post(
                f"{BASE}/eol/sessions/{session_id}/resume", headers=OPERATOR
            ).raise_for_status()

            second_id, second_start = create_and_start(client, "concurrent")
            concurrency_check = {
                "session_id": second_id,
                "status_code": second_start.status_code,
                "body": second_start.json(),
                "rejected": second_start.status_code == 409,
            }

        session = wait_session(client, session_id)
        time.sleep(0.8)
        counts = database_counts(session_id)
        expected_status, expected_failure, expected_steps = PROFILE_EXPECTATIONS[profile]
        actual_failure = failed_step(session)
        reports_ok = counts["reports"] >= 4 and bool((session.get("report") or {}).get("id"))
        persistence_ok = all(
            [
                counts["test_sessions"] == 1,
                counts["test_steps"] == len(session.get("steps", [])),
                counts["test_assertions"] > 0,
                counts["raw_can_frames"] > 0,
                counts["decoded_signals"] > 0,
                counts["signal_statistics"] > 0,
                counts["operator_actions"] >= 2,
                counts["software_versions"] > 0,
                reports_ok,
            ]
        )
        result = {
            "profile": profile,
            "session_id": session_id,
            "expected": {
                "status": expected_status,
                "failure_step": expected_failure,
                "step_count": expected_steps,
            },
            "actual": {
                "status": session.get("status"),
                "result": session.get("overall_result"),
                "failure_step": actual_failure,
                "step_count": len(session.get("steps", [])),
                "step_results": [
                    {"id": step.get("id"), "result": step.get("result")}
                    for step in session.get("steps", [])
                ],
                "failure_reason": session.get("failure_reason", ""),
                "safe_stop": session.get("safe_stop_result"),
                "report_id": (session.get("report") or {}).get("id"),
            },
            "channels_at_start": channels,
            "database_counts": counts,
            "persistence_ok": persistence_ok,
            "pause_resume": pause_check,
            "concurrency": concurrency_check,
        }
        result["passed"] = all(
            [
                session.get("status") == expected_status,
                actual_failure == expected_failure,
                len(session.get("steps", [])) == expected_steps,
                persistence_ok,
                pause_check is None or pause_check["stable"],
                concurrency_check is None or concurrency_check["rejected"],
            ]
        )
        (output / f"{profile}_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result
    finally:
        stop_process(simulator)
        stop_process(backend)
        if client:
            client.close()
        if simulator_log:
            simulator_log.close()
        if backend_log:
            backend_log.close()


def run_start_guard(
    output: Path,
    name: str,
    *,
    fault: str = "",
    simulator_enabled: bool,
    expected_start_code: int | None,
) -> dict[str, Any]:
    backend = simulator = None
    backend_log = simulator_log = None
    client = None
    try:
        backend, backend_log, client, environment = start_backend(output, name, fault)
        if simulator_enabled:
            simulator, simulator_log = start_simulator(
                output, name, "normal_pass", environment
            )
            wait_channels(client)
        else:
            time.sleep(2.3)
        session_id, response = create_and_start(client, name)
        result: dict[str, Any] = {
            "name": name,
            "session_id": session_id,
            "start_status_code": response.status_code,
            "start_body": response.json(),
        }
        if expected_start_code is not None:
            result["passed"] = response.status_code == expected_start_code
        else:
            response.raise_for_status()
            session = wait_session(client, session_id, timeout=20)
            result["terminal"] = session
            result["passed"] = session.get("status") == "FAILED"
        (output / f"{name}_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result
    finally:
        stop_process(simulator)
        stop_process(backend)
        if client:
            client.close()
        if simulator_log:
            simulator_log.close()
        if backend_log:
            backend_log.close()


def run_terminal_guard(output: Path, action: str) -> dict[str, Any]:
    name = f"lifecycle_{action.replace('-', '_')}"
    backend = simulator = None
    backend_log = simulator_log = None
    client = None
    try:
        backend, backend_log, client, environment = start_backend(output, name)
        simulator, simulator_log = start_simulator(
            output, name, "normal_pass", environment
        )
        wait_channels(client)
        session_id, response = create_and_start(client, name)
        response.raise_for_status()
        wait_until(
            lambda: (
                payload
                if len(
                    (payload := client.get(
                        f"{BASE}/eol/sessions/{session_id}", headers=VIEWER
                    ).json()).get("steps", [])
                )
                >= 2
                else None
            ),
            10,
            f"{action} session did not start",
        )
        response = client.post(
            f"{BASE}/eol/sessions/{session_id}/{action}", headers=OPERATOR
        )
        body = response.json()
        session = client.get(
            f"{BASE}/eol/sessions/{session_id}", headers=VIEWER
        ).json()
        expected = "ABORTED" if action == "abort" else "EMERGENCY_STOPPED"
        result = {
            "name": name,
            "session_id": session_id,
            "action_status_code": response.status_code,
            "action_body": body,
            "terminal_status": session.get("status"),
            "step_count": len(session.get("steps", [])),
            "safe_stop": session.get("safe_stop_result"),
            "passed": response.status_code == 200 and session.get("status") == expected,
        }
        (output / f"{name}_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result
    finally:
        stop_process(simulator)
        stop_process(backend)
        if client:
            client.close()
        if simulator_log:
            simulator_log.close()
        if backend_log:
            backend_log.close()


def run_mid_session_disconnect(output: Path) -> dict[str, Any]:
    name = "can_disconnect_mid_session"
    backend = simulator = None
    backend_log = simulator_log = None
    client = None
    try:
        backend, backend_log, client, environment = start_backend(output, name)
        simulator, simulator_log = start_simulator(
            output, name, "normal_pass", environment
        )
        wait_channels(client)
        session_id, response = create_and_start(client, name)
        response.raise_for_status()
        wait_until(
            lambda: (
                payload
                if (payload := client.get(
                    f"{BASE}/eol/sessions/{session_id}", headers=VIEWER
                ).json()).get("current_step_id")
                in {"low_speed_drive_check", "steering_check"}
                else None
            ),
            20,
            "session did not reach a motion step",
        )
        stop_process(simulator)
        simulator = None
        session = wait_session(client, session_id, timeout=25)
        result = {
            "name": name,
            "session_id": session_id,
            "terminal_status": session.get("status"),
            "failure_step": failed_step(session),
            "failure_reason": session.get("failure_reason"),
            "safe_stop": session.get("safe_stop_result"),
            "passed": session.get("status") == "FAILED",
        }
        (output / f"{name}_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result
    finally:
        stop_process(simulator)
        stop_process(backend)
        if client:
            client.close()
        if simulator_log:
            simulator_log.close()
        if backend_log:
            backend_log.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "real_vehicle_connected": False,
        "network_boundary": "127.0.0.1 only",
        "profiles": {},
        "guards": {},
    }
    try:
        for profile in PROFILE_EXPECTATIONS:
            results["profiles"][profile] = run_profile(output, profile)
        results["guards"]["can_disconnected_start"] = run_start_guard(
            output,
            "can_disconnected_start",
            simulator_enabled=False,
            expected_start_code=409,
        )
        results["guards"]["dbc_unloaded"] = run_start_guard(
            output,
            "dbc_unloaded",
            fault="dbc_unloaded",
            simulator_enabled=True,
            expected_start_code=None,
        )
        results["guards"]["database_unwritable"] = run_start_guard(
            output,
            "database_unwritable",
            fault="database_unwritable",
            simulator_enabled=True,
            expected_start_code=409,
        )
        results["guards"]["abort"] = run_terminal_guard(output, "abort")
        results["guards"]["emergency_stop"] = run_terminal_guard(
            output, "emergency-stop"
        )
        results["guards"]["mid_session_disconnect"] = run_mid_session_disconnect(
            output
        )
    except Exception as exc:
        results["fatal_error"] = repr(exc)
    all_checks = [
        item.get("passed", False) for item in results["profiles"].values()
    ] + [item.get("passed", False) for item in results["guards"].values()]
    results["gate_passed"] = bool(all_checks) and all(all_checks) and not results.get(
        "fatal_error"
    )
    results["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (output / "phase02_eol_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if results["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
