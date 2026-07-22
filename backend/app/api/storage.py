from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, HTTPException

from app.api.models import (
    BackupCreateResponse,
    BackupListResponse,
    BackupRestoreRequest,
    BackupRestoreResponse,
    BackupValidationResponse,
    CleanupExecuteRequest,
    CleanupJobResponse,
    CleanupPreviewRequest,
    CleanupPreviewResponse,
    ObjectResponse,
    SchemaVersionResponse,
    StorageStatsResponse,
    StorageTrendPoint,
)
from app.security.auth import Principal, Role, require_role
from app.services.app_state import state
from app.storage.migrations import LATEST_SCHEMA_VERSION


router = APIRouter()


def _require_services() -> None:
    if not state.data_paths or not state.database or not state.backups or not state.retention:
        raise HTTPException(503, {"code": "STORAGE_SERVICE_UNAVAILABLE", "message": "storage lifecycle service is not initialized", "details": {}})


def _raise(exc: Exception, *, operation: str, status: int = 409) -> None:
    raise HTTPException(status, {"code": f"{operation.upper()}_FAILED", "message": str(exc), "details": {"operation": operation}}) from exc


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
    except OSError:
        return -1
    return total


@router.get("/storage/stats", response_model=StorageStatsResponse)
async def storage_stats(_principal: Principal = Depends(require_role(Role.VIEWER))):
    _require_services()
    paths = state.data_paths
    usage = shutil.disk_usage(paths.root)
    sizes = {
        "database": paths.database.stat().st_size if paths.database.exists() else 0,
        "application_logs": _dir_size(paths.app_logs),
        "raw_can": _dir_size(paths.raw_can),
        "decoded_signals": _dir_size(paths.decoded_signals),
        "reports": _dir_size(paths.reports),
        "exports": _dir_size(paths.exports),
        "backups": _dir_size(paths.backups),
        "temp": _dir_size(paths.temp),
    }
    return {
        "data_root": str(paths.root),
        "paths": {name: str(getattr(paths, name)) for name in ("database", "app_logs", "raw_can", "decoded_signals", "reports", "exports", "temp", "backups", "print_jobs")},
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": round(usage.used * 100 / usage.total, 2) if usage.total else 0.0,
        "category_bytes": sizes,
        "schema_version": state.database.schema_version(),
        "latest_schema_version": LATEST_SCHEMA_VERSION,
        "database_writable": state.db_writable,
        "health": state.storage_health.last if state.storage_health else {},
        "measured_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/storage/trend", response_model=list[StorageTrendPoint])
async def storage_trend(_principal: Principal = Depends(require_role(Role.VIEWER))):
    stats = await storage_stats(_principal)
    return [{
        "timestamp_utc": stats["measured_at"],
        "date": stats["measured_at"][:10],
        "used_bytes": stats["used_bytes"],
        "free_bytes": stats["free_bytes"],
        "used_gb": round(stats["used_bytes"] / 1024 ** 3, 3),
        "source": "current-measurement",
    }]


@router.get("/storage/schema-version", response_model=SchemaVersionResponse)
async def schema_version(_principal: Principal = Depends(require_role(Role.VIEWER))):
    _require_services()
    return {"schema_version": state.database.schema_version()}


@router.post("/storage/health/recheck", response_model=ObjectResponse)
async def health_recheck(_principal: Principal = Depends(require_role(Role.ADMIN))):
    _require_services()
    result = state.storage_health.check()
    if not result.get("healthy"):
        raise HTTPException(409, {"code": "STORAGE_UNHEALTHY", "message": result.get("error", "storage check failed"), "details": result})
    if state.alarms:
        state.alarms.clear_system_alarm("storage_unhealthy")
    return result


@router.get("/storage/backups", response_model=BackupListResponse)
async def backups(_principal: Principal = Depends(require_role(Role.ADMIN))):
    _require_services()
    return {"items": state.backups.list()}


@router.post("/storage/backups", response_model=BackupCreateResponse)
async def create_backup(principal: Principal = Depends(require_role(Role.ADMIN))):
    _require_services()
    try:
        return state.backups.create(principal)
    except Exception as exc:
        _raise(exc, operation="backup", status=500)


@router.get("/storage/backups/{backup_id}/validate", response_model=BackupValidationResponse)
async def validate_backup(backup_id: str, _principal: Principal = Depends(require_role(Role.ADMIN))):
    _require_services()
    return state.backups.validate(backup_id).model_dump(mode="json")


@router.post("/storage/backups/{backup_id}/restore", response_model=BackupRestoreResponse)
async def restore_backup(backup_id: str, payload: BackupRestoreRequest, principal: Principal = Depends(require_role(Role.ADMIN))):
    _require_services()
    try:
        return state.backups.restore(backup_id, payload.confirmation, principal)
    except ValueError as exc:
        _raise(exc, operation="restore_confirmation", status=422)
    except Exception as exc:
        _raise(exc, operation="restore", status=409)


@router.post("/storage/cleanup/preview", response_model=CleanupPreviewResponse)
async def cleanup_preview(payload: CleanupPreviewRequest, _principal: Principal = Depends(require_role(Role.ADMIN))):
    _require_services()
    try:
        return {"dry_run": True, **state.retention.preview(payload.cutoff_utc)}
    except Exception as exc:
        _raise(exc, operation="cleanup_preview", status=422)


@router.post("/storage/cleanup", response_model=CleanupJobResponse)
async def cleanup_start(payload: CleanupExecuteRequest, principal: Principal = Depends(require_role(Role.ADMIN))):
    _require_services()
    try:
        return state.retention.create_job(payload.cutoff_utc, payload.confirmation, principal, batch_size=payload.batch_size)
    except ValueError as exc:
        _raise(exc, operation="cleanup_confirmation", status=422)
    except Exception as exc:
        _raise(exc, operation="cleanup", status=409)


@router.get("/storage/cleanup/{job_id}", response_model=CleanupJobResponse)
async def cleanup_job(job_id: str, _principal: Principal = Depends(require_role(Role.ADMIN))):
    _require_services()
    try:
        return state.retention.job(job_id)
    except KeyError as exc:
        _raise(exc, operation="cleanup_job", status=404)


@router.post("/storage/cleanup/{job_id}/cancel", response_model=CleanupJobResponse)
async def cleanup_cancel(job_id: str, principal: Principal = Depends(require_role(Role.ADMIN))):
    _require_services()
    try:
        return state.retention.cancel(job_id, principal)
    except KeyError as exc:
        _raise(exc, operation="cleanup_job", status=404)
    except Exception as exc:
        _raise(exc, operation="cleanup_cancel", status=409)
