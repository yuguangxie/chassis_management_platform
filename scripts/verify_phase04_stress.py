from __future__ import annotations

"""Loopback-only 1000 fps CAN soak test with queue, log, and process metrics."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from typing import Any

import httpx


BASE = os.getenv("CHASSIS_API_BASE", "http://127.0.0.1:8800/api/v1")
HEADERS = {"Authorization": "Bearer dev-viewer-token"}
FRAME_COUNT_PER_CHANNEL = 25
TICKS_PER_SECOND = 20


def frame(can_id: int, data: list[int]) -> bytes:
    return bytes([8]) + can_id.to_bytes(4, "big") + bytes((data + [0] * 8)[:8])


def packet(channel: str, sequence: int) -> bytes:
    frames: list[bytes] = []
    for index in range(FRAME_COUNT_PER_CHANNEL):
        if channel == "CAN1":
            can_id = (0x51, 0x77, 0x168, 0xE1, 0x703, 0x704)[index % 6]
            data = [128 if can_id == 0x51 else 0, sequence & 0xFF, 0, 1, 0, 0, 0, 0]
        else:
            can_id = (0x100, 0x101, 0x102, 0x103, 0x104, 0x105, 0x7F1)[index % 7]
            data = [2, 8, 0, 12, 86, 0, sequence & 0xFF, 0]
        frames.append(frame(can_id, data))
    return b"".join(frames)


def process_metrics(pid: int | None) -> dict[str, Any]:
    if not pid:
        return {}
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        f"Get-Process -Id {pid} | Select-Object Id,Handles,WorkingSet64,CPU | ConvertTo-Json -Compress",
    ]
    try:
        output = subprocess.check_output(command, text=True, timeout=3).strip()
        return json.loads(output) if output else {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def compact_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    can = payload.get("can") or {}
    telemetry = payload.get("telemetry") or {}
    websocket = payload.get("websocket") or {}
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "channels": [
            {
                key: row.get(key)
                for key in (
                    "channel", "online", "fps", "receive_age_ms", "queue_depth",
                    "queue_capacity", "queue_dropped", "pipeline_queue_depth",
                    "pipeline_queue_capacity", "pipeline_queue_dropped", "stale_dropped",
                    "processing_errors",
                )
            }
            for row in can.get("channels", [])
        ],
        "pipeline": can.get("pipeline"),
        "telemetry": {
            key: telemetry.get(key)
            for key in ("queue_depth", "queue_capacity", "dropped", "healthy", "last_error", "raw_log", "signal_log")
        },
        "websocket": websocket,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=600.0)
    parser.add_argument("--backend-pid", type=int)
    parser.add_argument("--sample-interval", type=float, default=10.0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "network_boundary": "127.0.0.1 only",
        "target_fps": FRAME_COUNT_PER_CHANNEL * 2 * TICKS_PER_SECOND,
        "duration_seconds": args.duration,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "samples": [],
        "passed": False,
    }
    client = httpx.Client(timeout=10.0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        initial = compact_metrics(client.get(f"{BASE}/can/runtime-metrics", headers=HEADERS).json())
        result["initial"] = initial
        can1 = packet("CAN1", 0)
        can2 = packet("CAN2", 0)
        deadline = time.monotonic() + args.duration
        next_tick = time.monotonic()
        next_sample = next_tick
        sent = 0
        sequence = 0
        while time.monotonic() < deadline:
            sock.sendto(can1, ("127.0.0.1", int(os.getenv("CHASSIS_CAN1_PORT", "8234"))))
            sock.sendto(can2, ("127.0.0.1", int(os.getenv("CHASSIS_CAN2_PORT", "8235"))))
            sent += FRAME_COUNT_PER_CHANNEL * 2
            sequence += 1
            if sequence % 256 == 0:
                can1 = packet("CAN1", sequence)
                can2 = packet("CAN2", sequence)
            now = time.monotonic()
            if now >= next_sample:
                sampled = compact_metrics(client.get(f"{BASE}/can/runtime-metrics", headers=HEADERS).json())
                sampled["process"] = process_metrics(args.backend_pid)
                result["samples"].append(sampled)
                next_sample = now + args.sample_interval
            next_tick += 1 / TICKS_PER_SECOND
            time.sleep(max(0.0, next_tick - time.monotonic()))
        final = compact_metrics(client.get(f"{BASE}/can/runtime-metrics", headers=HEADERS).json())
        final["process"] = process_metrics(args.backend_pid)
        result.update({"sent_frames": sent, "achieved_send_fps": round(sent / args.duration, 2), "final": final})
        channels = final.get("channels", [])
        all_online = len(channels) == 2 and all(row.get("online") for row in channels)
        no_backlog = all((row.get("queue_depth") or 0) == 0 and (row.get("pipeline_queue_depth") or 0) == 0 for row in channels)
        no_drops = all((row.get("queue_dropped") or 0) == 0 and (row.get("pipeline_queue_dropped") or 0) == 0 for row in channels)
        healthy_logs = bool(final.get("telemetry", {}).get("healthy")) and not final.get("telemetry", {}).get("dropped")
        result["assertions"] = {
            "target_send_rate": result["achieved_send_fps"] >= 990,
            "channels_online": all_online,
            "no_sustained_backlog": no_backlog,
            "no_pipeline_drops": no_drops,
            "telemetry_healthy": healthy_logs,
        }
        result["passed"] = all(result["assertions"].values())
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        sock.close()
        client.close()
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    (args.output / "stress_1000fps.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {"samples"}}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
