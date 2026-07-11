from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8800/api/v1"
OPERATOR = {"Authorization": "Bearer dev-operator-token"}
VIEWER = {"Authorization": "Bearer dev-viewer-token"}


def wait(callback, timeout: float, label: str):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = callback()
            if value:
                return value
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"timeout waiting for {label}")


def start(command: list[str], log_path: Path, environment: dict[str, str]):
    log = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return process, log


def stop(process, *, kill: bool = False):
    if not process or process.poll() is not None:
        return
    process.kill() if kill else process.terminate()
    process.wait(timeout=8)


def row(session_id: str):
    connection = sqlite3.connect(ROOT / "data" / "chassis_eol.db")
    connection.row_factory = sqlite3.Row
    result = connection.execute(
        "SELECT id,status,overall_result,failure_reason,ended_at FROM test_sessions WHERE id=?",
        (session_id,),
    ).fetchone()
    connection.close()
    return dict(result) if result else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        CHASSIS_RUNTIME_PROFILE="dev", PYTHONUNBUFFERED="1", PYTHONUTF8="1"
    )
    backend = simulator = restarted = None
    logs = []
    client = httpx.Client(timeout=10)
    result = {"real_vehicle_connected": False, "network_boundary": "127.0.0.1 only"}
    try:
        backend, backend_log = start(
            [sys.executable, str(ROOT / "scripts" / "dev_backend.py")],
            output / "recovery_backend_before.log",
            environment,
        )
        logs.append(backend_log)
        wait(lambda: client.get(f"{BASE}/health").status_code == 200, 15, "backend")
        simulator, simulator_log = start(
            [
                sys.executable,
                str(ROOT / "scripts" / "dev_simulator.py"),
                "--profile",
                "normal_pass",
            ],
            output / "recovery_simulator.log",
            environment,
        )
        logs.append(simulator_log)
        wait(
            lambda: all(
                item["online"]
                for item in client.get(
                    f"{BASE}/can/channels/status", headers=VIEWER
                ).json()
            ),
            15,
            "CAN online",
        )
        created = client.post(
            f"{BASE}/eol/sessions",
            headers=OPERATOR,
            json={
                "chassis_no": "PH2-RECOVERY",
                "vin": "PH2RECOVERY000001",
                "station_id": "EOL-STATION-01",
            },
        )
        created.raise_for_status()
        session_id = created.json()["id"]
        client.post(
            f"{BASE}/eol/sessions/{session_id}/start", headers=OPERATOR
        ).raise_for_status()
        wait(
            lambda: len(
                client.get(
                    f"{BASE}/eol/sessions/{session_id}", headers=VIEWER
                ).json().get("steps", [])
            )
            >= 2,
            15,
            "active EOL steps",
        )
        stop(backend, kill=True)
        backend = None
        stop(simulator)
        simulator = None
        before_restart = row(session_id)

        restarted, restart_log = start(
            [sys.executable, str(ROOT / "scripts" / "dev_backend.py")],
            output / "recovery_backend_after.log",
            environment,
        )
        logs.append(restart_log)
        wait(lambda: client.get(f"{BASE}/health").status_code == 200, 15, "restarted backend")
        after_restart = wait(
            lambda: (value if (value := row(session_id)) and value["status"] == "ABORTED" else None),
            10,
            "session recovery",
        )
        result.update(
            session_id=session_id,
            before_restart=before_restart,
            after_restart=after_restart,
            passed=bool(
                before_restart
                and before_restart["status"] in {"RUNNING", "PAUSED", "WAITING_OPERATOR"}
                and after_restart["status"] == "ABORTED"
                and after_restart["overall_result"] == "ABORTED"
                and after_restart["failure_reason"] == "service restart recovery"
            ),
        )
    except Exception as exc:
        result.update(passed=False, error=repr(exc))
    finally:
        stop(simulator)
        stop(backend)
        stop(restarted)
        client.close()
        for log in logs:
            log.close()
    (output / "restart_recovery_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
