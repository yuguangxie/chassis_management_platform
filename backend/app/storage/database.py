from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
import os
import shutil
import sqlite3
import threading
from typing import Any
import uuid

from app.storage.migrations import LATEST_SCHEMA_VERSION, MigrationError, MigrationRunner


class Database:
    """Thread-safe SQLite authority with migrations, integrity and online backup."""

    def __init__(
        self,
        path: Path,
        *,
        backup_dir: Path | None = None,
        failure_callback: Callable[[str], None] | None = None,
        migrations: dict | None = None,
    ) -> None:
        self.path = Path(path).resolve(strict=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir = Path(backup_dir or self.path.parent / "migration-backups").resolve(strict=False)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.failure_callback = failure_callback
        self._lock = threading.RLock()
        self._closed = False
        self.last_error: str | None = None
        self.conn = self._connect()
        try:
            self.schema = MigrationRunner(
                self.conn,
                self.path,
                self.backup_dir,
                migrations=migrations,
            ).run()
        except MigrationError as exc:
            self.conn.close()
            self._closed = True
            if exc.backup_path:
                self._restore_failed_migration(exc.backup_path)
            self._notify_failure(str(exc))
            raise

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _restore_failed_migration(self, backup_path: Path) -> None:
        for suffix in ("-wal", "-shm"):
            Path(f"{self.path}{suffix}").unlink(missing_ok=True)
        # Keep internal names short.  Repeating the database name plus a full UUID
        # can push otherwise valid Windows data roots beyond MAX_PATH.
        temporary = self.path.with_name(f".restore-{uuid.uuid4().hex[:12]}.tmp")
        shutil.copy2(backup_path, temporary)
        os.replace(temporary, self.path)

    def schema_version(self) -> int:
        row = self.query_one("SELECT COALESCE(MAX(version),0) AS version FROM schema_migrations")
        return int(row["version"] if row else 0)

    def integrity_check(self) -> tuple[bool, str]:
        try:
            with self._lock:
                row = self.conn.execute("PRAGMA integrity_check").fetchone()
            message = str(row[0]) if row else "no integrity result"
            return message.lower() == "ok", message
        except sqlite3.Error as exc:
            self._notify_failure(f"database integrity check failed: {exc}")
            return False, str(exc)

    def online_backup(self, destination: Path) -> Path:
        self._assert_open()
        target = Path(destination).resolve(strict=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".backup-{uuid.uuid4().hex[:12]}.tmp")
        backup = sqlite3.connect(temporary)
        try:
            with self._lock:
                self.conn.backup(backup)
            row = backup.execute("PRAGMA integrity_check").fetchone()
            if not row or str(row[0]).lower() != "ok":
                raise sqlite3.DatabaseError(f"backup integrity check failed: {row}")
            backup.close()
            os.replace(temporary, target)
            return target
        except Exception as exc:
            try:
                backup.close()
            finally:
                temporary.unlink(missing_ok=True)
            self._notify_failure(f"database backup failed: {exc}")
            raise

    def restore_from(self, source: Path, rollback_path: Path) -> Path:
        """Atomically replace the live database after an offline integrity check.

        The caller must enforce authorization and confirmation. A consistent rollback
        copy is always created before the live path is replaced.
        """
        self._assert_open()
        source_path = Path(source).resolve(strict=True)
        source_conn = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
        try:
            row = source_conn.execute("PRAGMA integrity_check").fetchone()
            if not row or str(row[0]).lower() != "ok":
                raise sqlite3.DatabaseError(f"restore source integrity failed: {row}")
        finally:
            source_conn.close()
        self.online_backup(rollback_path)
        replacement = self.path.with_name(f".replace-{uuid.uuid4().hex[:12]}.tmp")
        shutil.copy2(source_path, replacement)
        with self._lock:
            self.conn.close()
            self._closed = True
            try:
                for suffix in ("-wal", "-shm"):
                    Path(f"{self.path}{suffix}").unlink(missing_ok=True)
                os.replace(replacement, self.path)
                self.conn = self._connect()
                self._closed = False
                ok, message = self.integrity_check()
                if not ok:
                    raise sqlite3.DatabaseError(message)
                version = self.schema_version()
                if version > LATEST_SCHEMA_VERSION:
                    raise sqlite3.DatabaseError(
                        f"restore schema version {version} is newer than supported {LATEST_SCHEMA_VERSION}"
                    )
                MigrationRunner(self.conn, self.path, self.backup_dir).run()
            except Exception:
                if not self._closed:
                    self.conn.close()
                shutil.copy2(rollback_path, self.path)
                self.conn = self._connect()
                self._closed = False
                replacement.unlink(missing_ok=True)
                raise
        return rollback_path

    def writable(self) -> bool:
        try:
            with self.transaction() as conn:
                conn.execute("CREATE TEMP TABLE IF NOT EXISTS write_probe(ts TEXT)")
                conn.execute("DELETE FROM write_probe")
                conn.execute("INSERT INTO write_probe(ts) VALUES (strftime('%Y-%m-%dT%H:%M:%fZ','now'))")
            self.last_error = None
            return True
        except (sqlite3.Error, OSError) as exc:
            self._notify_failure(f"database is not writable: {exc}")
            return False

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self._assert_open()
        with self._lock:
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                yield self.conn
            except Exception as exc:
                self.conn.rollback()
                if isinstance(exc, (sqlite3.Error, OSError)):
                    self._notify_failure(str(exc))
                raise
            else:
                try:
                    self.conn.commit()
                except Exception as exc:
                    self.conn.rollback()
                    self._notify_failure(f"database commit failed: {exc}")
                    raise

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        self._assert_open()
        with self._lock:
            try:
                return self.conn.execute(sql, tuple(params))
            except (sqlite3.Error, OSError) as exc:
                self._notify_failure(str(exc))
                raise

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
            try:
                return [dict(row) for row in self.conn.execute(sql, tuple(params)).fetchall()]
            except sqlite3.Error as exc:
                self._notify_failure(str(exc))
                raise

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def table_counts(self, session_id: str | None = None) -> dict[str, int]:
        tables = [
            "test_sessions", "test_steps", "test_assertions", "raw_can_frames",
            "decoded_signals", "signal_statistics", "alarms", "reports",
            "operator_actions", "software_versions",
        ]
        result: dict[str, int] = {}
        for table in tables:
            columns = {row["name"] for row in self.query(f"PRAGMA table_info({table})")}
            if session_id and "session_id" in columns:
                row = self.query_one(f"SELECT COUNT(*) AS count FROM {table} WHERE session_id=?", (session_id,))
            elif session_id and table == "test_sessions":
                row = self.query_one("SELECT COUNT(*) AS count FROM test_sessions WHERE id=?", (session_id,))
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

    def _notify_failure(self, message: str) -> None:
        self.last_error = message
        if self.failure_callback:
            try:
                self.failure_callback(message)
            except Exception:
                pass

    def _assert_open(self) -> None:
        if self._closed:
            raise sqlite3.ProgrammingError("database connection is closed")
