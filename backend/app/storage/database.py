from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading
from typing import Any

from app.core.paths import DB_PATH, ensure_data_dirs
from app.core.time import utc_now


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        ensure_data_dirs()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._closed = False
        self.conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            isolation_level=None,
            timeout=5.0,
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        with self._lock:
            self.conn.executescript(schema)
            self._migrate_existing_schema()

    def _migrate_existing_schema(self) -> None:
        required = {
            "test_sessions": {
                "plan_version": "TEXT",
                "failure_reason": "TEXT",
                "safe_stop_json": "TEXT",
                "report_id": "TEXT",
            },
            "test_assertions": {
                "quality": "TEXT",
                "source_can_id": "TEXT",
                "source_channel": "TEXT",
                "source_timestamp": "TEXT",
            },
        }
        for table, additions in required.items():
            columns = {
                str(row["name"])
                for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for name, column_type in additions.items():
                if name not in columns:
                    self.conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"
                    )

    def writable(self) -> bool:
        try:
            with self.transaction() as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS write_probe(ts TEXT)")
                conn.execute("INSERT INTO write_probe(ts) VALUES (?)", (utc_now(),))
            return True
        except sqlite3.Error:
            return False

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self._assert_open()
        with self._lock:
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                yield self.conn
            except Exception:
                self.conn.rollback()
                raise
            else:
                self.conn.commit()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        self._assert_open()
        with self._lock:
            return self.conn.execute(sql, tuple(params))

    def executemany(
        self,
        sql: str,
        rows: Sequence[Sequence[Any]],
        *,
        connection: sqlite3.Connection | None = None,
    ) -> sqlite3.Cursor:
        self._assert_open()
        if connection is not None:
            return connection.executemany(sql, rows)
        with self.transaction() as conn:
            return conn.executemany(sql, rows)

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        self._assert_open()
        with self._lock:
            return [dict(row) for row in self.conn.execute(sql, tuple(params)).fetchall()]

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def table_counts(self, session_id: str | None = None) -> dict[str, int]:
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
            "software_versions",
        ]
        result: dict[str, int] = {}
        for table in tables:
            columns = {
                row["name"] for row in self.query(f"PRAGMA table_info({table})")
            }
            if session_id and "session_id" in columns:
                row = self.query_one(
                    f"SELECT COUNT(*) AS count FROM {table} WHERE session_id=?",
                    (session_id,),
                )
            elif session_id and table == "test_sessions":
                row = self.query_one(
                    "SELECT COUNT(*) AS count FROM test_sessions WHERE id=?", (session_id,)
                )
            else:
                row = self.query_one(f"SELECT COUNT(*) AS count FROM {table}")
            result[table] = int(row["count"] if row else 0)
        return result

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self.conn.close()
            self._closed = True

    def _assert_open(self) -> None:
        if self._closed:
            raise sqlite3.ProgrammingError("database connection is closed")
