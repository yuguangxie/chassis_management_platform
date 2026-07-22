from __future__ import annotations

from collections.abc import Callable
import hashlib
from pathlib import Path
import sqlite3
from typing import Any

from app.core.time import utc_now


LATEST_SCHEMA_VERSION = 3
Migration = Callable[[sqlite3.Connection], None]


class MigrationError(RuntimeError):
    def __init__(self, version: int, backup_path: Path | None, cause: Exception) -> None:
        super().__init__(f"database migration to version {version} failed: {cause}")
        self.version = version
        self.backup_path = backup_path
        self.cause = cause


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_columns(conn: sqlite3.Connection, table: str, definitions: dict[str, str]) -> None:
    present = _columns(conn, table)
    for name, definition in definitions.items():
        if name not in present:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')


def migration_001(conn: sqlite3.Connection) -> None:
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)


def migration_002(conn: sqlite3.Connection) -> None:
    _add_columns(
        conn,
        "test_sessions",
        {"plan_version": "TEXT", "failure_reason": "TEXT", "safe_stop_json": "TEXT", "report_id": "TEXT"},
    )
    _add_columns(
        conn,
        "test_assertions",
        {"quality": "TEXT", "source_can_id": "TEXT", "source_channel": "TEXT", "source_timestamp": "TEXT"},
    )


def migration_003(conn: sqlite3.Connection) -> None:
    _add_columns(
        conn,
        "reports",
        {"archived_at": "TEXT", "archive_manifest_hash": "TEXT"},
    )
    _add_columns(
        conn,
        "report_print_jobs",
        {
            "printer_name": "TEXT",
            "backend": "TEXT",
            "spooler_job_id": "TEXT",
            "report_hash": "TEXT",
            "attempts": "INTEGER NOT NULL DEFAULT 0",
            "status_detail": "TEXT",
            "completed_at": "TEXT",
            "cancelled_at": "TEXT",
        },
    )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS backup_records (
          id TEXT PRIMARY KEY,
          manifest_path TEXT NOT NULL,
          database_path TEXT NOT NULL,
          database_hash TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          status TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          verified_at TEXT,
          restored_at TEXT
        );
        CREATE TABLE IF NOT EXISTS cleanup_jobs (
          id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          cutoff_utc TEXT NOT NULL,
          requested_by TEXT NOT NULL,
          dry_run INTEGER NOT NULL,
          confirmation TEXT,
          candidate_json TEXT NOT NULL,
          progress_json TEXT NOT NULL,
          cancel_requested INTEGER NOT NULL DEFAULT 0,
          error_message TEXT,
          created_at TEXT NOT NULL,
          started_at TEXT,
          completed_at TEXT,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cleanup_jobs_status ON cleanup_jobs(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_reports_archived ON reports(archived_at, generated_at);
        """
    )


MIGRATIONS: dict[int, tuple[str, Migration]] = {
    1: ("initial_schema", migration_001),
    2: ("persistence_and_safety_metadata", migration_002),
    3: ("data_lifecycle_and_printing", migration_003),
}


class MigrationRunner:
    def __init__(
        self,
        conn: sqlite3.Connection,
        database_path: Path,
        backup_dir: Path,
        *,
        migrations: dict[int, tuple[str, Migration]] | None = None,
    ) -> None:
        self.conn = conn
        self.database_path = database_path
        self.backup_dir = backup_dir
        self.migrations = migrations or MIGRATIONS

    def current_version(self) -> int:
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY,name TEXT NOT NULL,checksum TEXT NOT NULL,applied_at TEXT NOT NULL)"
        )
        row = self.conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()
        return int(row[0] if row else 0)

    def run(self) -> int:
        current = self.current_version()
        latest = max(self.migrations, default=0)
        if current > latest:
            raise RuntimeError(f"database schema version {current} is newer than supported {latest}")
        for version in range(current + 1, latest + 1):
            name, migration = self.migrations[version]
            backup = self._backup_before(version) if self._has_user_schema() else None
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                migration(self.conn)
                checksum = hashlib.sha256(f"{version}:{name}".encode("utf-8")).hexdigest()
                self.conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version,name,checksum,applied_at) VALUES (?,?,?,?)",
                    (version, name, checksum, utc_now()),
                )
                self.conn.execute(f"PRAGMA user_version={version}")
                self.conn.commit()
            except Exception as exc:
                self.conn.rollback()
                raise MigrationError(version, backup, exc) from exc
        return latest

    def _has_user_schema(self) -> bool:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='schema_migrations'"
        ).fetchone()
        return bool(row and int(row[0]) > 0)

    def _backup_before(self, version: int) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = utc_now().replace(":", "").replace("+", "_")
        target = self.backup_dir / f"pre-migration-v{version}-{stamp}.sqlite3"
        destination = sqlite3.connect(target)
        try:
            self.conn.backup(destination)
            result = destination.execute("PRAGMA integrity_check").fetchone()
            if not result or str(result[0]).lower() != "ok":
                raise RuntimeError(f"pre-migration backup integrity failed: {result}")
        finally:
            destination.close()
        return target
