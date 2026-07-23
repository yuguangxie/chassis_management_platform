from __future__ import annotations

from datetime import datetime, timezone
import gzip
import logging
from pathlib import Path
import shutil
import sqlite3
from types import SimpleNamespace

import pytest

from app.core.paths import DataPaths, DataRootError
from app.core.logging import HybridRotatingFileHandler
from app.reports.printing import PrintService, VirtualPrintBackend
from app.reports.dependencies import report_dependency_status
from app.reports.service import ReportService
from app.security.auth import Principal, Role
from app.storage.database import Database
from app.storage.config import StorageConfig, load_storage_config
from app.storage.lifecycle import BackupService, RetentionService
from app.storage.migrations import MIGRATIONS, MigrationError
from app.storage.repositories import Repositories


ADMIN = Principal("lifecycle-admin", Role.ADMIN)
OPERATOR = Principal("line-operator", Role.OPERATOR)


def _state(paths: DataPaths, database: Database) -> SimpleNamespace:
    state = SimpleNamespace(
        data_paths=paths,
        database=database,
        db_writable=True,
        alarms=None,
        dbc=None,
        config=SimpleNamespace(
            software_version="v-test",
            config_version="cfg-test",
            test_plan_version="plan-test",
            printer_name=None,
            profile="test",
        ),
        reports=SimpleNamespace(output_dir=paths.reports),
        repositories=Repositories(database),
        preferences=None,
    )
    state.report_service = ReportService(state)
    return state


def _session(database: Database, session_id: str, status: str, timestamp: str) -> None:
    database.execute(
        "INSERT INTO test_sessions(id,chassis_no,vin,operator,station_id,test_plan_id,status,ended_at) VALUES (?,?,?,?,?,?,?,?)",
        (session_id, "CHASSIS", "L0000000000000001", "op", "station", "plan", status, timestamp),
    )


def test_data_root_handles_spaces_chinese_and_rejects_low_space(tmp_path: Path, monkeypatch):
    paths = DataPaths.from_root(tmp_path / "生产 数据 root")
    result = paths.ensure_ready(minimum_free_bytes=0)
    assert result["writable"] is True
    assert all(paths.contains(path) for path in paths.directories())
    assert paths.database == paths.root / "database" / "chassis_eol.sqlite3"

    usage = shutil.disk_usage(paths.root)
    monkeypatch.setattr("app.core.paths.shutil.disk_usage", lambda _path: usage._replace(free=1))
    with pytest.raises(DataRootError) as raised:
        paths.ensure_ready(minimum_free_bytes=2)
    assert raised.value.code == "DATA_ROOT_LOW_SPACE"


def test_data_root_permission_failure_is_actionable(tmp_path: Path, monkeypatch):
    paths = DataPaths.from_root(tmp_path / "readonly")
    paths.ensure_ready(minimum_free_bytes=0)

    def denied(*_args, **_kwargs):
        raise PermissionError("denied by test ACL")

    monkeypatch.setattr("app.core.paths.tempfile.mkstemp", denied)
    with pytest.raises(DataRootError) as raised:
        paths.ensure_ready(minimum_free_bytes=0)
    assert raised.value.code == "DATA_ROOT_PERMISSION_DENIED"


@pytest.mark.parametrize("old_version", [1, 2, 3])
def test_every_old_schema_version_upgrades_idempotently(tmp_path: Path, old_version: int):
    path = tmp_path / f"old-v{old_version}.sqlite3"
    database = Database(path)
    database.execute("DELETE FROM schema_migrations WHERE version>?", (old_version,))
    database.execute(f"PRAGMA user_version={old_version}")
    database.close()

    upgraded = Database(path)
    assert upgraded.schema_version() == 4
    assert upgraded.integrity_check() == (True, "ok")
    upgraded.close()
    repeated = Database(path)
    assert repeated.schema_version() == 4
    repeated.close()


def test_failed_migration_restores_pre_migration_backup(tmp_path: Path):
    path = tmp_path / "migration failure.sqlite3"
    database = Database(path)
    database.execute("CREATE TABLE marker(value TEXT)")
    database.execute("INSERT INTO marker(value) VALUES ('preserved')")
    database.close()

    def fail(_conn: sqlite3.Connection) -> None:
        raise RuntimeError("injected migration failure")

    with pytest.raises(MigrationError) as raised:
        Database(path, backup_dir=tmp_path / "backups", migrations={**MIGRATIONS, 5: ("injected_failure", fail)})
    assert raised.value.backup_path and raised.value.backup_path.is_file()
    restored = Database(path)
    assert restored.query_one("SELECT value FROM marker")["value"] == "preserved"
    restored.close()


def test_locked_and_corrupt_database_fail_closed(tmp_path: Path):
    messages: list[str] = []
    path = tmp_path / "locked.sqlite3"
    database = Database(path, failure_callback=messages.append)
    database.conn.execute("PRAGMA busy_timeout=1")
    locker = sqlite3.connect(path, isolation_level=None)
    locker.execute("PRAGMA journal_mode=WAL")
    locker.execute("BEGIN EXCLUSIVE")
    try:
        assert database.writable() is False
        assert messages and "writable" in messages[-1]
    finally:
        locker.rollback()
        locker.close()
        database.close()

    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"this is not sqlite")
    with pytest.raises(sqlite3.DatabaseError):
        Database(corrupt)


def test_backup_tamper_validation_and_successful_restore(tmp_path: Path):
    paths = DataPaths.from_root(tmp_path / "data root")
    paths.ensure_ready(minimum_free_bytes=0)
    database = Database(paths.database, backup_dir=paths.backups / "migration")
    state = _state(paths, database)
    backups = BackupService(state, paths)
    _session(database, "TERMINAL-1", "PASSED", "2026-01-01T00:00:00+00:00")

    created = backups.create(ADMIN)
    database.execute("UPDATE test_sessions SET chassis_no='CHANGED' WHERE id='TERMINAL-1'")
    restored = backups.restore(created["backup_id"], f"RESTORE {created['backup_id']}", ADMIN)
    assert restored["status"] == "RESTORED"
    assert database.query_one("SELECT chassis_no FROM test_sessions WHERE id='TERMINAL-1'")["chassis_no"] == "CHASSIS"
    assert Path(restored["rollback_path"]).is_file()

    second = backups.create(ADMIN)
    backup_db = paths.backups / second["backup_id"] / "database.sqlite3"
    backup_db.write_bytes(backup_db.read_bytes() + b"tampered")
    validation = backups.validate(second["backup_id"])
    assert validation.valid is False
    assert any("mismatch" in item for item in validation.errors)
    with pytest.raises(RuntimeError):
        backups.restore(second["backup_id"], f"RESTORE {second['backup_id']}", ADMIN)
    database.close()


def test_online_backup_uses_short_internal_name_for_long_windows_path(tmp_path: Path):
    database = Database(tmp_path / "source.sqlite3")
    database.execute("CREATE TABLE long_path_probe(value TEXT)")
    database.execute("INSERT INTO long_path_probe(value) VALUES ('preserved')")

    destination_parent = tmp_path
    while len(str(destination_parent.resolve(strict=False))) < 215:
        remaining = 215 - len(str(destination_parent.resolve(strict=False)))
        destination_parent /= "长" + ("x" * min(48, max(1, remaining - 2)))
    destination = destination_parent / "database.sqlite3"
    assert len(str(destination.resolve(strict=False))) < 260

    created = database.online_backup(destination)
    restored = sqlite3.connect(created)
    try:
        assert restored.execute("SELECT value FROM long_path_probe").fetchone()[0] == "preserved"
    finally:
        restored.close()
        database.close()
    assert not list(destination_parent.glob(".backup-*.tmp"))


def test_cleanup_dry_run_protection_execution_and_cancel(tmp_path: Path):
    paths = DataPaths.from_root(tmp_path / "cleanup-data")
    paths.ensure_ready(minimum_free_bytes=0)
    database = Database(paths.database, backup_dir=paths.backups / "migration")
    state = _state(paths, database)
    retention = RetentionService(state, paths)
    old = "2025-01-01T00:00:00+00:00"
    _session(database, "ARCHIVED", "PASSED", old)
    _session(database, "UNARCHIVED", "FAILED", old)
    _session(database, "ACTIVE", "RUNNING", old)
    archived_file = paths.reports / "archived.pdf"
    unarchived_file = paths.reports / "unarchived.pdf"
    archived_file.write_bytes(b"%PDF archived")
    unarchived_file.write_bytes(b"%PDF unarchived")
    database.execute(
        "INSERT INTO reports(id,session_id,chassis_no,vin,result,report_type,file_path,generation_status,generated_at,archived_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("R-ARCHIVED", "ARCHIVED", "C", "V", "PASS", "pdf", str(archived_file), "COMPLETED", old, old),
    )
    database.execute(
        "INSERT INTO reports(id,session_id,chassis_no,vin,result,report_type,file_path,generation_status,generated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("R-UNARCHIVED", "UNARCHIVED", "C", "V", "FAIL", "pdf", str(unarchived_file), "COMPLETED", old),
    )
    database.execute(
        "INSERT INTO operator_actions(session_id,timestamp_utc,operator,action_type,result) VALUES (?,?,?,?,?)",
        ("ARCHIVED", old, "op", "important_audit", "OK"),
    )

    cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
    preview = retention.preview(cutoff)
    assert preview["session_ids"] == ["ARCHIVED"]
    assert preview["protected"]["active_test_sessions"] == 1
    assert preview["protected"]["sessions_with_unarchived_reports"] == 1
    assert preview["file_bytes"] == archived_file.stat().st_size

    cancelled = retention.execute_now(cutoff, ADMIN, should_cancel=lambda: True)
    assert cancelled["status"] == "CANCELLED"
    assert database.query_one("SELECT id FROM test_sessions WHERE id='ARCHIVED'")

    completed = retention.execute_now(cutoff, ADMIN)
    assert completed["status"] == "COMPLETED"
    assert database.query_one("SELECT id FROM test_sessions WHERE id='ARCHIVED'") is None
    assert database.query_one("SELECT id FROM test_sessions WHERE id='UNARCHIVED'") is not None
    assert database.query_one("SELECT id FROM test_sessions WHERE id='ACTIVE'") is not None
    assert database.query_one("SELECT id FROM operator_actions WHERE action_type='important_audit'") is not None
    assert not archived_file.exists() and unarchived_file.exists()
    database.close()


def test_cleanup_database_failure_restores_quarantined_files(tmp_path: Path, monkeypatch):
    paths = DataPaths.from_root(tmp_path / "cleanup-failure")
    paths.ensure_ready(minimum_free_bytes=0)
    database = Database(paths.database, backup_dir=paths.backups / "migration")
    state = _state(paths, database)
    retention = RetentionService(state, paths)
    old = "2025-01-01T00:00:00+00:00"
    _session(database, "FAIL-RESTORE", "FAILED", old)
    report = paths.reports / "must-return.pdf"
    report.write_bytes(b"%PDF must survive")
    database.execute(
        "INSERT INTO reports(id,session_id,chassis_no,vin,result,report_type,file_path,generation_status,generated_at,archived_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("R-FAIL", "FAIL-RESTORE", "C", "V", "FAIL", "pdf", str(report), "COMPLETED", old, old),
    )

    monkeypatch.setattr(
        retention,
        "_delete_batch",
        lambda _ids, **_kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("disk full")),
    )
    with pytest.raises(sqlite3.OperationalError):
        retention.execute_now(datetime(2026, 1, 1, tzinfo=timezone.utc), ADMIN)
    assert report.is_file()
    assert database.query_one("SELECT id FROM test_sessions WHERE id='FAIL-RESTORE'")
    failed = database.query_one("SELECT status,error_message FROM cleanup_jobs ORDER BY created_at DESC LIMIT 1")
    assert failed["status"] == "FAILED" and "disk full" in failed["error_message"]
    database.close()


def test_cleanup_batch_audit_failure_rolls_back_rows_and_restores_files(tmp_path: Path, monkeypatch):
    paths = DataPaths.from_root(tmp_path / "cleanup-audit-failure")
    paths.ensure_ready(minimum_free_bytes=0)
    database = Database(paths.database, backup_dir=paths.backups / "migration")
    state = _state(paths, database)
    retention = RetentionService(state, paths)
    old = "2025-01-01T00:00:00+00:00"
    _session(database, "AUDIT-RESTORE", "FAILED", old)
    report = paths.reports / "audit-must-return.pdf"
    report.write_bytes(b"%PDF audit must survive")
    database.execute(
        "INSERT INTO reports(id,session_id,chassis_no,vin,result,report_type,file_path,generation_status,generated_at,archived_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("R-AUDIT", "AUDIT-RESTORE", "C", "V", "FAIL", "pdf", str(report), "COMPLETED", old, old),
    )
    original_audit = retention._audit

    def fail_batch_audit(principal, action, target, payload, result="OK", **kwargs):
        if action == "cleanup_batch_deleted":
            raise sqlite3.OperationalError("audit disk full")
        return original_audit(principal, action, target, payload, result, **kwargs)

    monkeypatch.setattr(retention, "_audit", fail_batch_audit)
    with pytest.raises(sqlite3.OperationalError, match="audit disk full"):
        retention.execute_now(datetime(2026, 1, 1, tzinfo=timezone.utc), ADMIN)
    assert report.is_file()
    assert database.query_one("SELECT id FROM test_sessions WHERE id='AUDIT-RESTORE'")
    assert database.query_one("SELECT status FROM cleanup_jobs ORDER BY created_at DESC LIMIT 1")["status"] == "FAILED"
    database.close()


def test_application_log_rotation_compresses_and_reports_write_failures(tmp_path: Path, monkeypatch):
    failures: list[str] = []
    (tmp_path / "logs").mkdir()
    handler = HybridRotatingFileHandler(
        tmp_path / "logs" / "app.log",
        max_bytes=32,
        interval_hours=24,
        backup_count=2,
        compress=True,
        failure_callback=failures.append,
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.emit(logging.LogRecord("test", logging.INFO, __file__, 1, "first-message-that-rotates", (), None))
    handler.emit(logging.LogRecord("test", logging.INFO, __file__, 2, "second-message-that-rotates", (), None))
    handler.flush()
    archives = list((tmp_path / "logs").glob("app.log.*.gz"))
    assert archives
    with gzip.open(archives[0], "rt", encoding="utf-8") as stream:
        assert "first-message" in stream.read()

    monkeypatch.setattr(handler, "shouldRollover", lambda _record: (_ for _ in ()).throw(OSError("read only")))
    handler.emit(logging.LogRecord("test", logging.ERROR, __file__, 3, "write-failure", (), None))
    assert failures and "read only" in failures[-1]
    handler.close()


def test_storage_schema_rejects_unknown_fields_and_production_parquet(tmp_path: Path):
    payload = load_storage_config("test").model_dump()
    payload["unknown_storage_key"] = True
    with pytest.raises(ValueError):
        StorageConfig.model_validate(payload)

    config = tmp_path / "storage.yaml"
    payload.pop("unknown_storage_key")
    payload["decoded_signal_logging"]["format"] = "parquet"
    import yaml

    config.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Parquet"):
        load_storage_config("production", config)


def test_virtual_print_backend_completed_failed_cancelled_and_retry(tmp_path: Path):
    paths = DataPaths.from_root(tmp_path / "print-data")
    paths.ensure_ready(minimum_free_bytes=0)
    database = Database(paths.database, backup_dir=paths.backups / "migration")
    state = _state(paths, database)
    _session(database, "PRINT-SESSION", "PASSED", "2026-01-01T00:00:00+00:00")
    pdf = paths.reports / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4\nvirtual\n%%EOF")
    database.execute(
        "INSERT INTO reports(id,session_id,chassis_no,vin,result,report_type,file_path,generation_status,generated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("REPORT-PDF", "PRINT-SESSION", "C", "V", "PASS", "pdf", str(pdf), "COMPLETED", "2026-01-01T00:00:00+00:00"),
    )
    backend = VirtualPrintBackend()
    printing = PrintService(state, backend)
    state.printing = printing

    with pytest.raises(ValueError):
        printing.create("REPORT-PDF", OPERATOR, preview_confirmed=False, printer_name=None)
    completed = printing.create("REPORT-PDF", OPERATOR, preview_confirmed=True, printer_name=None)
    assert completed["status"] == "QUEUED" and completed["spooler_job_id"]
    backend.set_status(completed["spooler_job_id"], "COMPLETED")
    assert printing.job(completed["id"])["status"] == "COMPLETED"

    cancelled = printing.create("REPORT-PDF", OPERATOR, preview_confirmed=True, printer_name=None)
    assert printing.cancel(cancelled["id"], OPERATOR)["status"] == "CANCELLED"
    retried = printing.retry(cancelled["id"], OPERATOR)
    assert retried["status"] == "QUEUED" and retried["attempts"] == 2
    backend.set_status(retried["spooler_job_id"], "FAILED", "paper jam")
    assert printing.job(retried["id"])["status"] == "FAILED"
    assert printing.retry(retried["id"], OPERATOR)["attempts"] == 3
    database.close()


def test_missing_docx_to_pdf_converter_is_actionable_and_not_faked(tmp_path: Path, monkeypatch):
    config = tmp_path / "report.yaml"
    config.write_text(
        "report:\n  pdf_renderer: reportlab-native\n  docx_to_pdf_converter: libreoffice\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("app.reports.dependencies.shutil.which", lambda _name: None)
    status = report_dependency_status(config)
    assert status["ready"] is False
    assert status["docx_to_pdf_available"] is False
    assert "Install LibreOffice" in status["action"]
