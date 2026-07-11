from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import gzip
from pathlib import Path
from typing import Any

from app.can_gateway.models import CanFrame
from app.core.paths import LOGS_DIR
from app.core.time import utc_now


RAW_HEADERS = [
    "timestamp_utc", "session_id", "channel", "direction", "can_id_hex",
    "is_extended", "is_remote", "dlc", "data_hex", "packet_hex", "source",
    "parse_status", "message_name",
]


class RawLogWriter:
    """Batch CSV writer with session/date/size rotation and optional gzip archival."""

    def __init__(
        self,
        root: Path = LOGS_DIR,
        *,
        batch_size: int = 200,
        rotate_bytes: int = 32 * 1024 * 1024,
        retention_days: int = 180,
        compress_rotated: bool = True,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size
        self.rotate_bytes = rotate_bytes
        self.retention_days = retention_days
        self.compress_rotated = compress_rotated
        self.buffers: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self.paths: dict[tuple[str, str], Path] = {}
        self.rotations = 0
        self.compressed = 0
        self._cleanup_done_for: str | None = None

    def write(self, frame: CanFrame, session_id: str | None = None) -> None:
        timestamp = utc_now()
        session = session_id or "unassigned"
        date = timestamp[:10].replace("-", "")
        key = (self._safe_component(session), date)
        self.buffers[key].append(
            {
                "timestamp_utc": timestamp,
                "session_id": session_id or "",
                "channel": frame.channel,
                "direction": frame.direction,
                "can_id_hex": frame.can_id_hex,
                "is_extended": int(frame.is_extended),
                "is_remote": int(frame.is_remote),
                "dlc": frame.dlc,
                "data_hex": frame.data_hex,
                "packet_hex": frame.raw_packet_hex,
                "source": frame.source,
                "parse_status": frame.parse_status,
                "message_name": frame.message_name or "",
            }
        )
        if len(self.buffers[key]) >= self.batch_size:
            self.flush_key(key)

    def flush(self, session_id: str | None = None) -> None:
        keys = list(self.buffers)
        if session_id is not None:
            wanted = self._safe_component(session_id or "unassigned")
            keys = [key for key in keys if key[0] == wanted]
        for key in keys:
            self.flush_key(key)

    def flush_key(self, key: tuple[str, str]) -> None:
        rows = self.buffers.get(key, [])
        if not rows:
            return
        self._cleanup_old_files(key[1])
        path = self._active_path(key, rows)
        exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=RAW_HEADERS)
            if not exists:
                writer.writeheader()
            writer.writerows(rows)
        rows.clear()

    def _active_path(self, key: tuple[str, str], rows: list[dict[str, Any]]) -> Path:
        path = self.paths.get(key)
        estimate = max(256, sum(len(str(row)) for row in rows) + len(rows) * 2)
        if path is None:
            path = self._new_path(key)
        elif path.exists() and path.stat().st_size + estimate > self.rotate_bytes:
            self._archive(path)
            path = self._new_path(key)
            self.rotations += 1
        self.paths[key] = path
        return path

    def _new_path(self, key: tuple[str, str]) -> Path:
        session, date = key
        # Keep files directly below the approved log root so existing audited download
        # endpoints can continue to validate a file id without accepting path segments.
        folder = self.root
        existing = sorted(folder.glob(f"raw_can_{session}_{date}_*.csv*"))
        index = len(existing) + 1
        return folder / f"raw_can_{session}_{date}_{index:03d}.csv"

    def _archive(self, path: Path) -> None:
        if not self.compress_rotated or not path.exists() or path.stat().st_size == 0:
            return
        target = path.with_suffix(path.suffix + ".gz")
        with path.open("rb") as source, gzip.open(target, "wb") as destination:
            destination.writelines(source)
        path.unlink(missing_ok=True)
        self.compressed += 1

    def _cleanup_old_files(self, date: str) -> None:
        if self._cleanup_done_for == date:
            return
        self._cleanup_done_for = date
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
            for path in self.root.rglob("raw_can_*.csv*"):
                if datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) < cutoff:
                    path.unlink(missing_ok=True)
        except OSError:
            # A retention failure must not break audit logging of the active session.
            return

    @staticmethod
    def _safe_component(value: str) -> str:
        return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value) or "unassigned"

    def metrics(self) -> dict[str, Any]:
        total_bytes = sum(path.stat().st_size for path in self.root.rglob("raw_can_*.csv*") if path.is_file())
        return {
            "buffers": sum(len(rows) for rows in self.buffers.values()),
            "active_files": len(self.paths),
            "rotations": self.rotations,
            "compressed": self.compressed,
            "bytes": total_bytes,
            "retention_days": self.retention_days,
        }

    def close(self) -> None:
        self.flush()
