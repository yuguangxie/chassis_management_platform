from __future__ import annotations

"""Collect repeatable runtime evidence for phase 04 queue and WebSocket behaviour."""

import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import httpx
import websockets


BASE = os.getenv("CHASSIS_API_BASE", "http://127.0.0.1:8800/api/v1")
WS = os.getenv("CHASSIS_WS_URL", "ws://127.0.0.1:8800/ws")
TOKEN = os.getenv("CHASSIS_API_TOKEN", "")
if not TOKEN:
    raise RuntimeError("CHASSIS_API_TOKEN is required")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


async def collect_topics(topics: list[str], duration: float) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    samples: dict[str, Any] = {}
    async with websockets.connect(WS, subprotocols=["chassis-session", f"chassis-token.{TOKEN}"], open_timeout=5, close_timeout=2) as socket:
        await socket.send(json.dumps({"action": "subscribe", "topics": topics}))
        deadline = asyncio.get_running_loop().time() + duration
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=remaining)
            except TimeoutError:
                break
            message = json.loads(raw)
            topic = str(message.get("topic") or "unknown")
            counts[topic] += 1
            samples.setdefault(topic, message.get("payload"))
    return {"topics": topics, "duration_seconds": duration, "counts": dict(counts), "samples": samples}


def main() -> int:
    # GitHub's Windows runner can select cp1252 for redirected stdout. Runtime
    # diagnostics include Chinese safety labels, so force UTF-8 rather than
    # allowing successful assertions to be reported as an encoding failure.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=4.0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=10.0)
    result: dict[str, Any] = {"started_at": time.time(), "passed": False}
    try:
        initial = client.get(f"{BASE}/can/runtime-metrics", headers=HEADERS)
        initial.raise_for_status()
        standard = asyncio.run(
            collect_topics(
                [
                    "signals.dashboard",
                    "signals.current",
                    "signals.timeseries.batch",
                    "can.latest_frames.batch",
                    "can.channel_status",
                    "can.statistics",
                ],
                args.duration,
            )
        )
        explicit_raw = asyncio.run(collect_topics(["can.raw_frames.batch"], min(2.0, args.duration)))
        final = client.get(f"{BASE}/can/runtime-metrics", headers=HEADERS)
        final.raise_for_status()
        counts = standard["counts"]
        max_signal_count = int(args.duration * 12) + 2
        max_stats_count = int(args.duration * 2) + 2
        no_implicit_raw = not any("raw_frame" in name for name in counts)
        rates_ok = (
            1 <= counts.get("signals.dashboard", 0) <= max_signal_count
            and 1 <= counts.get("signals.timeseries.batch", 0) <= max_signal_count
            and counts.get("can.statistics", 0) <= max_stats_count
        )
        raw_ok = explicit_raw["counts"].get("can.raw_frames.batch", 0) > 0
        result.update(
            {
                "initial_metrics": initial.json(),
                "standard_subscription": standard,
                "explicit_raw_subscription": explicit_raw,
                "final_metrics": final.json(),
                "assertions": {
                    "signal_topics_at_most_10hz_with_tolerance": rates_ok,
                    "statistics_at_most_1hz_with_tolerance": counts.get("can.statistics", 0) <= max_stats_count,
                    "raw_requires_explicit_subscription": no_implicit_raw and raw_ok,
                },
            }
        )
        result["passed"] = all(result["assertions"].values())
    except Exception as exc:  # keep JSON evidence even on a failed runtime probe
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        client.close()
    result["finished_at"] = time.time()
    (args.output / "runtime_websocket_metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
