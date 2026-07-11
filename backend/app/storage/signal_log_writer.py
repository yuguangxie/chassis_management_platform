from __future__ import annotations

import csv
from collections import defaultdict
import logging
from pathlib import Path
from typing import Any

from app.core.paths import LOGS_DIR


LOGGER = logging.getLogger(__name__)
SIGNAL_HEADERS = [
    "session_id",
    "timestamp_utc",
    "channel",
    "can_id_hex",
    "message_name",
    "signal_name",
    "raw_value",
    "physical_value",
    "unit",
    "enum_label",
    "quality",
]


class SignalLogWriter:
    def __init__(
        self,
        root: Path = LOGS_DIR,
        *,
        format_name: str = "csv",
        batch_size: int = 200,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.format_name = format_name.lower()
        self.batch_size = batch_size
        self.buffers: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.paths: dict[str, Path] = {}
        if self.format_name not in {"csv", "parquet"}:
            raise ValueError("decoded signal format must be csv or parquet")

    def write_rows(self, session_id: str, rows: list[dict[str, Any]]) -> None:
        if not session_id:
            raise ValueError("decoded signal rows require session_id")
        for row in rows:
            self.buffers[session_id].append({key: row.get(key, "") for key in SIGNAL_HEADERS})
        if len(self.buffers[session_id]) >= self.batch_size:
            self.flush(session_id)

    def flush(self, session_id: str | None = None) -> None:
        keys = [session_id] if session_id else list(self.buffers)
        for key in keys:
            rows = self.buffers.get(key, [])
            if not rows:
                continue
            if self.format_name == "parquet":
                self._flush_parquet(key, rows)
            else:
                self._flush_csv(key, rows)
            rows.clear()

    def _flush_csv(self, session_id: str, rows: list[dict[str, Any]]) -> None:
        path = self.paths.setdefault(
            session_id, self.root / f"decoded_signals_{session_id}.csv"
        )
        exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=SIGNAL_HEADERS)
            if not exists:
                writer.writeheader()
            writer.writerows(rows)

    def _flush_parquet(self, session_id: str, rows: list[dict[str, Any]]) -> None:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError(
                "Parquet logging was selected but pyarrow is not installed; use CSV or install pyarrow"
            ) from exc
        path = self.paths.setdefault(
            session_id, self.root / f"decoded_signals_{session_id}.parquet"
        )
        table = pa.Table.from_pylist(rows)
        if path.exists():
            previous = pq.read_table(path)
            table = pa.concat_tables([previous, table])
        pq.write_table(table, path)

    def close(self) -> None:
        self.flush()

    def metrics(self) -> dict[str, Any]:
        total_bytes = sum(path.stat().st_size for path in self.root.glob("decoded_signals_*") if path.is_file())
        return {
            "buffers": sum(len(rows) for rows in self.buffers.values()),
            "active_files": len(self.paths),
            "bytes": total_bytes,
            "format": self.format_name,
        }
