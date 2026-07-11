from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8800/api/v1"


class VerificationFailure(RuntimeError):
    pass


def wait_until(predicate, timeout: float, message: str, interval: float = 0.05):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except (httpx.HTTPError, OSError):
            pass
        time.sleep(interval)
    raise VerificationFailure(f"{message}; last={last!r}")


def stop_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def response_summary(response: httpx.Response) -> dict[str, Any]:
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text
    return {"status_code": response.status_code, "body": body}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    backend_log_path = output / "backend_loopback.log"
    normal_log_path = output / "simulator_normal_pass.log"
    brake_log_path = output / "simulator_brake_fail.log"
    result_path = output / "loopback_results.json"
    backend_log = backend_log_path.open("w", encoding="utf-8")
    normal_log = normal_log_path.open("w", encoding="utf-8")
    brake_log = brake_log_path.open("w", encoding="utf-8")
    backend: subprocess.Popen[Any] | None = None
    simulator: subprocess.Popen[Any] | None = None
    results: dict[str, Any] = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S%z"), "checks": {}}

    viewer = {"Authorization": "Bearer dev-viewer-token"}
    operator = {"Authorization": "Bearer dev-operator-token"}
    engineer = {"Authorization": "Bearer dev-engineer-token"}

    try:
        environment = os.environ.copy()
        environment["CHASSIS_RUNTIME_PROFILE"] = "dev"
        environment["PYTHONUNBUFFERED"] = "1"
        backend = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "dev_backend.py")],
            cwd=ROOT,
            env=environment,
            stdout=backend_log,
            stderr=subprocess.STDOUT,
        )
        client = httpx.Client(timeout=5.0)
        wait_until(lambda: client.get(f"{BASE_URL}/health").status_code == 200, 10, "backend did not start")

        simulator = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "dev_simulator.py"), "--profile", "normal_pass"],
            cwd=ROOT,
            env=environment,
            stdout=normal_log,
            stderr=subprocess.STDOUT,
        )

        def channels_online():
            rows = client.get(f"{BASE_URL}/can/channels/status").json()
            return rows if len(rows) == 2 and all(row["online"] for row in rows) else None

        online_rows = wait_until(channels_online, 8, "CAN1/CAN2 did not become online")
        results["checks"]["loopback_online"] = online_rows

        channel_config = client.get(f"{BASE_URL}/config/channels", headers=viewer).json()
        if channel_config["runtime_profile"] != "dev" or any(
            row["device_ip"] != "127.0.0.1" for row in channel_config["channels"]
        ):
            raise VerificationFailure("dev profile exposed a non-loopback destination")
        results["checks"]["profile_isolation"] = channel_config

        control_payload = {
            "gear": "D",
            "drive_mode": "Remote",
            "target_speed": 2.0,
            "front_steer": -60,
            "rear_steer": 60,
            "brake_enable": False,
            "position_light": True,
            "low_beam": True,
            "control_mode": "speed",
        }
        preview = client.post(f"{BASE_URL}/control/121/preview", headers=engineer, json=control_payload)
        sent = client.post(f"{BASE_URL}/control/121/send-once", headers=engineer, json=control_payload)
        preview.raise_for_status()
        sent.raise_for_status()
        preview_body = preview.json()
        sent_body = sent.json()
        if preview_body["data"] != sent_body["frame"]["data"]:
            raise VerificationFailure("preview bytes differ from transmitted bytes")
        wait_until(
            lambda: "'front': -60" in normal_log_path.read_text(encoding="utf-8", errors="replace")
            and "'rear': 60" in normal_log_path.read_text(encoding="utf-8", errors="replace"),
            3,
            "simulator did not log the transmitted 0x121",
        )
        results["checks"]["control_121_loopback"] = {
            "preview_bytes": preview_body["data"],
            "transmitted_bytes": sent_body["frame"]["data"],
            "simulator_rx_observed": True,
        }

        safe_stop = client.post(
            f"{BASE_URL}/control/safe-stop",
            headers=operator,
            json={"reason": "phase-01 loopback safe stop"},
        )
        safe_stop.raise_for_status()
        if safe_stop.json()["code"] != "STOP_CONFIRMED":
            raise VerificationFailure("safe stop was not feedback-confirmed")
        emergency = client.post(
            f"{BASE_URL}/control/emergency-stop",
            headers=operator,
            json={"reason": "phase-01 loopback emergency"},
        )
        emergency.raise_for_status()
        release = client.post(
            f"{BASE_URL}/control/emergency-stop/release",
            headers=engineer,
            json={"confirmation": "RELEASE", "reason": "phase-01 verification"},
        )
        release.raise_for_status()
        results["checks"]["stop_success"] = {
            "safe_stop": safe_stop.json(),
            "emergency_stop": emergency.json(),
            "release": release.json(),
        }

        create_payload = {
            "chassis_no": "PHASE01",
            "vin": "LOOPBACK000000001",
            "serial_no": "P01",
            "operator": "forged-admin",
        }
        created = client.post(f"{BASE_URL}/eol/sessions", headers=operator, json=create_payload).json()
        session_id = created["id"]
        if created["operator"] != "dev-operator":
            raise VerificationFailure("EOL trusted operator was taken from request body")
        client.post(f"{BASE_URL}/eol/sessions/{session_id}/start", headers=operator, json={}).raise_for_status()
        client.post(f"{BASE_URL}/eol/sessions/{session_id}/pause", headers=operator, json={}).raise_for_status()
        time.sleep(0.25)
        paused = client.get(f"{BASE_URL}/eol/sessions/{session_id}", headers=viewer).json()
        if paused["status"] != "PAUSED" or len(paused["steps"]) > 1:
            raise VerificationFailure("paused EOL session advanced")
        client.post(f"{BASE_URL}/eol/sessions/{session_id}/resume", headers=operator, json={}).raise_for_status()
        final = wait_until(
            lambda: (
                payload
                if (payload := client.get(f"{BASE_URL}/eol/sessions/{session_id}", headers=viewer).json())["status"] in {"PASSED", "FAILED"}
                else None
            ),
            5,
            "resumed EOL session did not finish",
        )
        if final["status"] != "PASSED" or len(final["steps"]) != 12:
            raise VerificationFailure("normal loopback EOL did not PASS all 12 steps")
        results["checks"]["eol_pause_resume"] = {
            "paused_steps": len(paused["steps"]),
            "final_status": final["status"],
            "final_steps": len(final["steps"]),
            "report_files": final.get("report", {}).get("files", {}),
        }

        def terminal_scenario(action: str, expected: str) -> dict[str, Any]:
            session = client.post(f"{BASE_URL}/eol/sessions", headers=operator, json=create_payload).json()
            sid = session["id"]
            client.post(f"{BASE_URL}/eol/sessions/{sid}/start", headers=operator, json={}).raise_for_status()
            time.sleep(0.06)
            action_response = client.post(f"{BASE_URL}/eol/sessions/{sid}/{action}", headers=operator, json={})
            action_response.raise_for_status()
            time.sleep(0.2)
            terminal = client.get(f"{BASE_URL}/eol/sessions/{sid}", headers=viewer).json()
            if terminal["status"] != expected or terminal["overall_result"] != "ABORTED":
                raise VerificationFailure(f"{action} terminal state was overwritten")
            if action == "emergency-stop":
                client.post(
                    f"{BASE_URL}/control/emergency-stop/release",
                    headers=engineer,
                    json={"confirmation": "RELEASE", "reason": "phase-01 terminal scenario"},
                ).raise_for_status()
            else:
                client.post(f"{BASE_URL}/control/reset-defaults", headers=engineer, json={}).raise_for_status()
            return {"session_id": sid, "status": terminal["status"], "steps": len(terminal["steps"])}

        results["checks"]["eol_abort"] = terminal_scenario("abort", "ABORTED")
        results["checks"]["eol_emergency"] = terminal_scenario("emergency-stop", "EMERGENCY_STOPPED")

        unauth = client.post(f"{BASE_URL}/control/121/preview", json=control_payload)
        viewer_denied = client.post(f"{BASE_URL}/control/121/preview", headers=viewer, json=control_payload)
        role_forgery = client.post(
            f"{BASE_URL}/maintenance/enter",
            headers=engineer,
            json={"confirmation": "MAINTENANCE", "reason": "forged", "role": "admin"},
        )
        report_id = client.get(f"{BASE_URL}/reports/dashboard").json()["selected_report"]["report_id"]
        header_forgery = client.delete(
            f"{BASE_URL}/reports/{report_id}",
            headers={**operator, "x-role": "admin"},
        )
        auth_codes = [unauth.status_code, viewer_denied.status_code, role_forgery.status_code, header_forgery.status_code]
        if auth_codes != [401, 403, 403, 403]:
            raise VerificationFailure(f"RBAC boundary responses unexpected: {auth_codes}")
        results["checks"]["rbac"] = {
            "unauthenticated_control": response_summary(unauth),
            "viewer_control": response_summary(viewer_denied),
            "body_role_forgery": response_summary(role_forgery),
            "header_role_forgery": response_summary(header_forgery),
        }

        stop_process(simulator)
        simulator = None
        stopped_at = time.monotonic()

        def channels_offline():
            rows = client.get(f"{BASE_URL}/can/channels/status").json()
            return rows if rows and all(not row["online"] for row in rows) else None

        offline_rows = wait_until(channels_offline, 2.4, "channels did not become offline within two-second boundary")
        offline_elapsed = time.monotonic() - stopped_at
        if offline_elapsed > 2.25:
            raise VerificationFailure(f"offline detection was too slow: {offline_elapsed:.3f}s")
        remaining = 5.0 - (time.monotonic() - stopped_at)
        if remaining > 0:
            time.sleep(remaining)
        stale_control = client.post(f"{BASE_URL}/control/121/send-once", headers=engineer, json=control_payload)
        stale_body = stale_control.json()
        reasons = stale_body.get("detail", {}).get("details", {}).get("reasons", [])
        if stale_control.status_code != 409 or not any(item.get("rule") == "can2_online" for item in reasons):
            raise VerificationFailure("stale CAN state still allowed control")
        offline_session = client.post(f"{BASE_URL}/eol/sessions", headers=operator, json=create_payload).json()
        stale_eol = client.post(
            f"{BASE_URL}/eol/sessions/{offline_session['id']}/start", headers=operator, json={}
        )
        eol_reasons = stale_eol.json().get("detail", {}).get("details", {}).get("reasons", [])
        if stale_eol.status_code != 409 or not any(
            item.get("rule") in {"can1_online", "can2_online"} for item in eol_reasons
        ):
            raise VerificationFailure("offline CAN state still allowed EOL start")
        results["checks"]["stale_online"] = {
            "offline_elapsed_seconds": round(offline_elapsed, 3),
            "channel_status": offline_rows,
            "control_after_5s": response_summary(stale_control),
            "eol_start_after_5s": response_summary(stale_eol),
        }

        simulator = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "dev_simulator.py"), "--profile", "brake_fail"],
            cwd=ROOT,
            env=environment,
            stdout=brake_log,
            stderr=subprocess.STDOUT,
        )
        wait_until(channels_online, 8, "brake_fail simulator did not become online")
        brake_timeout = client.post(
            f"{BASE_URL}/control/safe-stop",
            headers=operator,
            json={"reason": "phase-01 brake_fail", "timeout_ms": 500},
        )
        brake_body = brake_timeout.json()
        if brake_timeout.status_code != 504 or brake_body.get("detail", {}).get("code") != "SAFE_STOP_TIMEOUT":
            raise VerificationFailure("brake_fail did not produce a locked safe-stop timeout")
        if brake_body["detail"].get("latched") is not True:
            raise VerificationFailure("safe-stop timeout did not remain latched")
        results["checks"]["stop_timeout"] = response_summary(brake_timeout)

        stop_process(simulator)
        simulator = None
        time.sleep(2.1)
        before = {row["channel"]: row for row in client.get(f"{BASE_URL}/can/channels/status").json()}
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        valid = bytes([8]) + (0x555).to_bytes(4, "big") + bytes(range(8))
        udp.sendto(valid[:7], ("127.0.0.1", 8234))
        udp.sendto(valid, ("127.0.0.1", 8234))
        udp.close()
        time.sleep(0.2)
        after = {row["channel"]: row for row in client.get(f"{BASE_URL}/can/channels/status").json()}
        if after["CAN1"]["malformed_datagrams"] != before["CAN1"]["malformed_datagrams"] + 1:
            raise VerificationFailure("truncated UDP datagram was not counted as malformed")
        if after["CAN1"]["rx_count"] != before["CAN1"]["rx_count"] + 1:
            raise VerificationFailure("truncated UDP bytes were combined with the next datagram")
        results["checks"]["udp_datagram_boundary"] = {
            "before": before["CAN1"],
            "after": after["CAN1"],
        }

        results["all_passed"] = True
        return_code = 0
    except Exception as exc:
        results["all_passed"] = False
        results["failure"] = f"{type(exc).__name__}: {exc}"
        return_code = 1
    finally:
        stop_process(simulator)
        stop_process(backend)
        results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S%z")
        result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        backend_log.close()
        normal_log.close()
        brake_log.close()

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
