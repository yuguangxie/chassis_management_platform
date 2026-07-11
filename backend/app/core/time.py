from __future__ import annotations
from datetime import datetime, timezone
import time

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def now_ns() -> int:
    return time.time_ns()
