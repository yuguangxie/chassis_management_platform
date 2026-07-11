from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import websockets


async def probe(url: str, duration: float) -> dict:
    counts: Counter[str] = Counter()
    samples: dict[str, object] = {}
    started = datetime.now().astimezone()
    async with websockets.connect(url, open_timeout=5, close_timeout=2) as socket:
        await socket.send(json.dumps({"action": "subscribe", "topics": ["*"]}))
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
            topic = str(message.get("topic", "unknown"))
            counts[topic] += 1
            samples.setdefault(topic, message.get("payload"))
    return {
        "url": url,
        "duration_seconds": duration,
        "started_at": started.isoformat(),
        "finished_at": datetime.now().astimezone().isoformat(),
        "total_messages": sum(counts.values()),
        "topic_counts": dict(sorted(counts.items())),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8800/ws")
    parser.add_argument("--duration", type=float, default=3.0)
    parser.add_argument("--output", default="docs/audit/evidence/api/websocket_probe.json")
    args = parser.parse_args()
    result = asyncio.run(probe(args.url, args.duration))
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}, ensure_ascii=False, indent=2))
    return 0 if result["total_messages"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
