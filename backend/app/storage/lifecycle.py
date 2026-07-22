from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.paths import DataPaths, DataRootError
from app.core.time import utc_now
from app.security.auth import Principal
from app.storage.migrations import LATEST_SCHEMA_VERSION


LOGGER = logging.getLogger(__name__)
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
ACTIVE_SESSION_STATES = ("IDLE", "RUNNING", "PAUSED", "WAITING_OPERATOR")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BackupFileEntry(StrictModel):
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class BackupManifest(StrictModel):
    manifest_version: Literal[1] = 1
    backup_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    created_at: datetime
    created_by: str
    software_version: str
    schema_version: int = Field(ge=1)
    dbc_hash: str | None = None
    config_version: str
    test_plan_version: str
    data_root_layout_version: Literal[1] = 1
    files: list[BackupFileEntry] = Field(min_length=1)

    @field_validator("created_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("created_at must be an aware UTC timestamp")
        return value


class BackupValidation(StrictModel):
    valid: bool
    backup_id: str
    manifest: BackupManifest | None = None
    errors: list[str] = Field(default_factory=list)


class BackupService:
    def __init__(self, state: Any, paths: DataPaths) -> None:
        self.state = state
        self.paths = paths

    def create(self, principal: Principal) -> dict[str, Any]:
        database = self._database()
        backup_id = "BACKUP-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        folder = self.paths.backups / backup_id
        folder.mkdir(parents=False, exist_ok=False)
        db_path = database.online_backup(folder / "database.sqlite3")
        dbc = self.state.dbc.status() if self.state.dbc else {}
        manifest = BackupManifest(
            backup_id=backup_id,
            created_at=datetime.now(timezone.utc),
            created_by=principal.username,
            software_version=self.state.config.software_version,
            schema_version=database.schema_version(),
            dbc_hash=str(dbc.get("hash")) if dbc.get("hash") else None,
            config_version=self.state.config.config_version,
            test_plan_version=self.state.config.test_plan_version,
            files=[
                BackupFileEntry(
                    relative_path="database.sqlite3",
                    sha256=sha256_file(db_path),
                    size_bytes=db_path.stat().st_size,
                )
            ],
        )
        manifest_path = folder / "manifest.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        database.execute(
            "INSERT INTO backup_records(id,manifest_path,database_path,database_hash,schema_version,status,created_by,created_at,verified_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                backup_id, str(manifest_path), str(db_path), manifest.files[0].sha256,
                manifest.schema_version, "VERIFIED", principal.username,
                manifest.created_at.isoformat(), utc_now(),
            ),
        )
        self._audit(principal, "create_backup", backup_id, {"manifest": manifest.model_dump(mode="json")})
        return {
            "backup_id": backup_id,
            "manifest_path": str(manifest_path),
            "database_size_bytes": db_path.stat().st_size,
            "database_sha256": manifest.files[0].sha256,
            "schema_version": manifest.schema_version,
            "created_at": manifest.created_at.isoformat(),
            "status": "VERIFIED",
        }

    def list(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for manifest_path in sorted(self.paths.backups.glob("BACKUP-*/manifest.json"), reverse=True):
            validation = self.validate(manifest_path.parent.name)
            records.append(
                {
                    "backup_id": manifest_path.parent.name,
                    "valid": validation.valid,
                    "created_at": validation.manifest.created_at.isoformat() if validation.manifest else None,
                    "schema_version": validation.manifest.schema_version if validation.manifest else None,
                    "size_bytes": sum(item.size_bytes for item in validation.manifest.files) if validation.manifest else 0,
                    "errors": validation.errors,
                }
            )
        return records

    def validate(self, backup_id: str) -> BackupValidation:
        if not SAFE_ID.fullmatch(backup_id):
            return BackupValidation(valid=False, backup_id=backup_id, errors=["invalid backup id"])
        folder = (self.paths.backups / backup_id).resolve(strict=False)
        if not self.paths.contains(folder) or folder.parent != self.paths.backups:
            return BackupValidation(valid=False, backup_id=backup_id, errors=["backup path escaped data_root"])
        manifest_path = folder / "manifest.json"
        errors: list[str] = []
        manifest: BackupManifest | None = None
        try:
            manifest = BackupManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
            if manifest.backup_id != backup_id:
                errors.append("backup id does not match manifest")
            if manifest.schema_version > LATEST_SCHEMA_VERSION:
                errors.append("backup schema is newer than this software")
            for entry in manifest.files:
                file_path = (folder / entry.relative_path).resolve(strict=False)
                if folder != file_path.parent or not file_path.is_file():
                    errors.append(f"missing or unsafe file: {entry.relative_path}")
                    continue
                if file_path.stat().st_size != entry.size_bytes:
                    errors.append(f"size mismatch: {entry.relative_path}")
                if sha256_file(file_path) != entry.sha256:
                    errors.append(f"hash mismatch: {entry.relative_path}")
        except Exception as exc:
            errors.append(f"invalid manifest: {type(exc).__name__}: {exc}")
        return BackupValidation(valid=not errors, backup_id=backup_id, manifest=manifest, errors=errors)

    def restore(self, backup_id: str, confirmation: str, principal: Principal) -> dict[str, Any]:
        expected = f"RESTORE {backup_id}"
        if confirmation != expected:
            raise ValueError(f"confirmation must exactly equal {expected}")
        validation = self.validate(backup_id)
        if not validation.valid or validation.manifest is None:
            self._audit(principal, "restore_backup_rejected", backup_id, {"errors": validation.errors}, result="REJECTED")
            raise RuntimeError("; ".join(validation.errors))
        active = self._database().query_one(
            "SELECT id,status FROM test_sessions WHERE status IN (?,?,?,?) ORDER BY created_at DESC LIMIT 1",
            ACTIVE_SESSION_STATES,
        )
        if active:
            raise RuntimeError(f"active EOL session {active['id']} must be terminated before restore")
        self._audit(principal, "restore_backup_started", backup_id, {"schema_version": validation.manifest.schema_version})
        self.state.db_writable = False
        rollback = self.paths.backups / "restore-rollbacks" / (
            datetime.now(timezone.utc).strftime("rollback-%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8] + ".sqlite3"
        )
        rollback.parent.mkdir(parents=True, exist_ok=True)
        source = self.paths.backups / backup_id / validation.manifest.files[0].relative_path
        try:
            self._database().restore_from(source, rollback)
            ok, message = self._database().integrity_check()
            if not ok:
                raise RuntimeError(message)
            self._audit(
                principal,
                "restore_backup_completed",
                backup_id,
                {"rollback_path": str(rollback), "schema_version": self._database().schema_version()},
            )
            self.state.db_writable = self._database().writable()
        except Exception as exc:
            self.state.db_writable = False
            self._raise_storage_alarm(f"database restore failed: {exc}")
            raise
        return {
            "backup_id": backup_id,
            "status": "RESTORED",
            "restored_at": utc_now(),
            "schema_version": self._database().schema_version(),
            "rollback_path": str(rollback),
        }

    def _database(self):
        if self.state.database is None:
            raise RuntimeError("database is not initialized")
        return self.state.database

    def _audit(self, principal: Principal, action: str, target: str, payload: dict[str, Any], result: str = "OK") -> None:
        self._database().execute(
            "INSERT INTO operator_actions(timestamp_utc,operator,role,action_type,target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?)",
            (utc_now(), principal.username, principal.role.value, action, target, json.dumps(payload, ensure_ascii=False, default=str), result, ""),
        )

    def _raise_storage_alarm(self, message: str) -> None:
        if self.state.alarms:
            self.state.alarms.raise_system_alarm("storage_unhealthy", 4, "Storage Unhealthy", message)


class RetentionService:
    TABLES = (
        "test_assertions", "test_steps", "raw_can_frames", "decoded_signals",
        "signal_statistics", "alarms", "report_print_jobs", "reports", "test_sessions",
    )

    def __init__(self, state: Any, paths: DataPaths) -> None:
        self.state = state
        self.paths = paths
        self.tasks: dict[str, asyncio.Task[None]] = {}

    def preview(self, cutoff_utc: datetime) -> dict[str, Any]:
        cutoff = self._utc(cutoff_utc)
        database = self.state.database
        rows = database.query(
            "SELECT s.id,COALESCE(s.ended_at,s.created_at) AS timestamp_utc FROM test_sessions s "
            "WHERE s.status NOT IN (?,?,?,?) AND COALESCE(s.ended_at,s.created_at)<? "
            "AND NOT EXISTS (SELECT 1 FROM reports r WHERE r.session_id=s.id AND r.archived_at IS NULL) "
            "ORDER BY COALESCE(s.ended_at,s.created_at)",
            (*ACTIVE_SESSION_STATES, cutoff.isoformat()),
        )
        ids = [str(row["id"]) for row in rows]
        protected_active = database.query_one(
            "SELECT COUNT(*) AS count FROM test_sessions WHERE status IN (?,?,?,?)", ACTIVE_SESSION_STATES
        )
        protected_unarchived = database.query_one(
            "SELECT COUNT(DISTINCT session_id) AS count FROM reports WHERE archived_at IS NULL"
        )
        counts = {table: 0 for table in self.TABLES}
        if ids:
            placeholders = ",".join("?" for _ in ids)
            for table in self.TABLES:
                if table == "report_print_jobs":
                    row = database.query_one(
                        f"SELECT COUNT(*) AS count FROM report_print_jobs WHERE report_id IN (SELECT id FROM reports WHERE session_id IN ({placeholders}))",
                        ids,
                    )
                elif table == "test_sessions":
                    row = database.query_one(f"SELECT COUNT(*) AS count FROM test_sessions WHERE id IN ({placeholders})", ids)
                else:
                    row = database.query_one(f"SELECT COUNT(*) AS count FROM {table} WHERE session_id IN ({placeholders})", ids)
                counts[table] = int(row["count"] if row else 0)
        files = self._candidate_files(ids)
        file_bytes = sum(path.stat().st_size for path in files if path.is_file())
        return {
            "cutoff_utc": cutoff.isoformat(),
            "session_ids": ids,
            "session_count": len(ids),
            "oldest_utc": rows[0]["timestamp_utc"] if rows else None,
            "newest_utc": rows[-1]["timestamp_utc"] if rows else None,
            "row_counts": counts,
            "file_count": len(files),
            "file_bytes": file_bytes,
            "estimated_database_bytes": sum(counts.values()) * 256,
            "total_bytes": file_bytes + sum(counts.values()) * 256,
            "protected": {
                "active_test_sessions": int(protected_active["count"] if protected_active else 0),
                "sessions_with_unarchived_reports": int(protected_unarchived["count"] if protected_unarchived else 0),
                "auth_sessions": "all protected",
                "operator_actions": "all protected",
            },
        }

    def create_job(self, cutoff_utc: datetime, confirmation: str, principal: Principal, *, batch_size: int = 50) -> dict[str, Any]:
        if confirmation != "CLEANUP":
            raise ValueError("confirmation must exactly equal CLEANUP")
        preview = self.preview(cutoff_utc)
        job_id = "CLEANUP-" + uuid.uuid4().hex[:12].upper()
        now = utc_now()
        self.state.database.execute(
            "INSERT INTO cleanup_jobs(id,status,cutoff_utc,requested_by,dry_run,confirmation,candidate_json,progress_json,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (job_id, "QUEUED", preview["cutoff_utc"], principal.username, 0, confirmation, json.dumps(preview), json.dumps({"completed_sessions": 0, "total_sessions": preview["session_count"]}), now, now),
        )
        self._audit(principal, "cleanup_queued", job_id, preview)
        task = asyncio.create_task(asyncio.to_thread(self._run, job_id, preview, principal, batch_size), name=f"retention-{job_id}")
        self.tasks[job_id] = task
        return self.job(job_id)

    def execute_now(
        self,
        cutoff_utc: datetime,
        principal: Principal,
        *,
        batch_size: int = 50,
        should_cancel: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        preview = self.preview(cutoff_utc)
        job_id = "CLEANUP-" + uuid.uuid4().hex[:12].upper()
        now = utc_now()
        self.state.database.execute(
            "INSERT INTO cleanup_jobs(id,status,cutoff_utc,requested_by,dry_run,confirmation,candidate_json,progress_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (job_id, "QUEUED", preview["cutoff_utc"], principal.username, 0, "CLEANUP", json.dumps(preview), json.dumps({"completed_sessions": 0, "total_sessions": preview["session_count"]}), now, now),
        )
        self._run(job_id, preview, principal, batch_size, should_cancel=should_cancel)
        return self.job(job_id)

    def _run(
        self,
        job_id: str,
        preview: dict[str, Any],
        principal: Principal,
        batch_size: int,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        database = self.state.database
        database.execute("UPDATE cleanup_jobs SET status='RUNNING',started_at=?,updated_at=? WHERE id=?", (utc_now(), utc_now(), job_id))
        completed = 0
        deleted_rows = {table: 0 for table in self.TABLES}
        ids = list(preview["session_ids"])
        try:
            for offset in range(0, len(ids), max(1, batch_size)):
                cancelled = bool(should_cancel and should_cancel())
                row = database.query_one("SELECT cancel_requested FROM cleanup_jobs WHERE id=?", (job_id,))
                if cancelled or bool(row and row["cancel_requested"]):
                    database.execute(
                        "UPDATE cleanup_jobs SET status='CANCELLED',completed_at=?,updated_at=?,progress_json=? WHERE id=?",
                        (utc_now(), utc_now(), json.dumps({"completed_sessions": completed, "total_sessions": len(ids), "deleted_rows": deleted_rows}), job_id),
                    )
                    self._audit(principal, "cleanup_cancelled", job_id, {"completed_sessions": completed, "deleted_rows": deleted_rows})
                    return
                batch = ids[offset : offset + max(1, batch_size)]
                quarantined = self._quarantine_files(job_id, batch)
                try:
                    batch_counts = self._delete_batch(batch)
                except Exception:
                    self._restore_quarantine(quarantined)
                    raise
                for _original, quarantine in quarantined:
                    quarantine.unlink(missing_ok=True)
                for table, count in batch_counts.items():
                    deleted_rows[table] += count
                completed += len(batch)
                database.execute(
                    "UPDATE cleanup_jobs SET progress_json=?,updated_at=? WHERE id=?",
                    (json.dumps({"completed_sessions": completed, "total_sessions": len(ids), "deleted_rows": deleted_rows}), utc_now(), job_id),
                )
            database.execute(
                "UPDATE cleanup_jobs SET status='COMPLETED',completed_at=?,updated_at=?,progress_json=? WHERE id=?",
                (utc_now(), utc_now(), json.dumps({"completed_sessions": completed, "total_sessions": len(ids), "deleted_rows": deleted_rows}), job_id),
            )
            self._audit(principal, "cleanup_completed", job_id, {"completed_sessions": completed, "deleted_rows": deleted_rows})
        except Exception as exc:
            database.execute(
                "UPDATE cleanup_jobs SET status='FAILED',error_message=?,completed_at=?,updated_at=? WHERE id=?",
                (str(exc), utc_now(), utc_now(), job_id),
            )
            self._audit(principal, "cleanup_failed", job_id, {"error": str(exc), "completed_sessions": completed}, result="FAILED")
            raise

    def cancel(self, job_id: str, principal: Principal) -> dict[str, Any]:
        if not SAFE_ID.fullmatch(job_id):
            raise ValueError("invalid cleanup job id")
        row = self.job(job_id)
        if row["status"] not in {"QUEUED", "RUNNING"}:
            raise RuntimeError("only queued or running cleanup jobs can be cancelled")
        self.state.database.execute("UPDATE cleanup_jobs SET cancel_requested=1,updated_at=? WHERE id=?", (utc_now(), job_id))
        self._audit(principal, "cleanup_cancel_requested", job_id, {})
        return self.job(job_id)

    async def stop(self) -> None:
        if not self.tasks:
            return
        self.state.database.execute(
            "UPDATE cleanup_jobs SET cancel_requested=1,updated_at=? WHERE status IN ('QUEUED','RUNNING')",
            (utc_now(),),
        )
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.tasks.clear()

    def job(self, job_id: str) -> dict[str, Any]:
        row = self.state.database.query_one("SELECT * FROM cleanup_jobs WHERE id=?", (job_id,))
        if row is None:
            raise KeyError(job_id)
        return {
            **row,
            "dry_run": bool(row["dry_run"]),
            "cancel_requested": bool(row["cancel_requested"]),
            "candidate": json.loads(row["candidate_json"]),
            "progress": json.loads(row["progress_json"]),
        }

    def _delete_batch(self, ids: list[str]) -> dict[str, int]:
        database = self.state.database
        placeholders = ",".join("?" for _ in ids)
        counts = {table: 0 for table in self.TABLES}
        with database.transaction() as conn:
            report_ids = [row[0] for row in conn.execute(f"SELECT id FROM reports WHERE session_id IN ({placeholders})", ids).fetchall()]
            if report_ids:
                report_marks = ",".join("?" for _ in report_ids)
                cursor = conn.execute(f"DELETE FROM report_print_jobs WHERE report_id IN ({report_marks})", report_ids)
                counts["report_print_jobs"] = cursor.rowcount
            for table in ("test_assertions", "test_steps", "raw_can_frames", "decoded_signals", "signal_statistics", "alarms", "reports"):
                cursor = conn.execute(f"DELETE FROM {table} WHERE session_id IN ({placeholders})", ids)
                counts[table] = cursor.rowcount
            cursor = conn.execute(f"DELETE FROM test_sessions WHERE id IN ({placeholders})", ids)
            counts["test_sessions"] = cursor.rowcount
        return counts

    def _candidate_files(self, ids: list[str]) -> list[Path]:
        files: dict[str, Path] = {}
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        for row in self.state.database.query(f"SELECT file_path FROM reports WHERE session_id IN ({placeholders})", ids):
            path = Path(row["file_path"]).resolve(strict=False)
            if self.paths.contains(path) and path.is_file():
                files[str(path)] = path
        for session_id in ids:
            safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in session_id)
            for root, pattern in ((self.paths.raw_can, f"raw_can_{safe}_*"), (self.paths.decoded_signals, f"decoded_signals_{safe}.*")):
                for path in root.glob(pattern):
                    if path.is_file():
                        files[str(path.resolve(strict=False))] = path.resolve(strict=False)
        return list(files.values())

    def _quarantine_files(self, job_id: str, ids: list[str]) -> list[tuple[Path, Path]]:
        target = self.paths.temp / "cleanup" / job_id
        target.mkdir(parents=True, exist_ok=True)
        moved: list[tuple[Path, Path]] = []
        try:
            for index, original in enumerate(self._candidate_files(ids)):
                quarantine = target / f"{index:06d}-{original.name}"
                shutil.move(str(original), str(quarantine))
                moved.append((original, quarantine))
        except Exception:
            self._restore_quarantine(moved)
            raise
        return moved

    @staticmethod
    def _restore_quarantine(items: list[tuple[Path, Path]]) -> None:
        for original, quarantine in reversed(items):
            if quarantine.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(quarantine), str(original))

    def _audit(self, principal: Principal, action: str, target: str, payload: dict[str, Any], result: str = "OK") -> None:
        self.state.database.execute(
            "INSERT INTO operator_actions(timestamp_utc,operator,role,action_type,target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?)",
            (utc_now(), principal.username, principal.role.value, action, target, json.dumps(payload, ensure_ascii=False, default=str), result, ""),
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("cutoff_utc must include a UTC offset")
        utc = value.astimezone(timezone.utc)
        return utc


class StorageHealthMonitor:
    def __init__(self, state: Any, paths: DataPaths, *, minimum_free_bytes: int, interval_seconds: float = 5.0) -> None:
        self.state = state
        self.paths = paths
        self.minimum_free_bytes = minimum_free_bytes
        self.interval_seconds = interval_seconds
        self.task: asyncio.Task[None] | None = None
        self.last: dict[str, Any] = {}

    def check(self) -> dict[str, Any]:
        try:
            readiness = self.paths.ensure_ready(minimum_free_bytes=self.minimum_free_bytes)
            database_ok = bool(self.state.database and self.state.database.writable())
            integrity_ok, integrity_message = self.state.database.integrity_check() if self.state.database else (False, "database unavailable")
            healthy = database_ok and integrity_ok
            if not healthy:
                raise RuntimeError(integrity_message if not integrity_ok else "database is not writable")
            self.state.db_writable = True
            self.last = {**readiness, "healthy": True, "database_integrity": integrity_message, "checked_at": utc_now()}
        except (DataRootError, OSError, RuntimeError) as exc:
            self.state.db_writable = False
            details = exc.details if isinstance(exc, DataRootError) else {}
            self.last = {"healthy": False, "error": str(exc), "details": details, "checked_at": utc_now()}
            if self.state.alarms:
                self.state.alarms.raise_system_alarm("storage_unhealthy", 4, "Storage Unhealthy", str(exc))
        return self.last

    async def start(self) -> None:
        self.check()
        if self.task and not self.task.done():
            return
        self.task = asyncio.create_task(self._run(), name="storage-health-monitor")

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            self.check()

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
