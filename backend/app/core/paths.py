from __future__ import annotations
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
CONFIG_DIR = Path(os.getenv("CHASSIS_CONFIG_DIR", PROJECT_ROOT / "configs"))
ASSETS_DIR = Path(os.getenv("CHASSIS_ASSETS_DIR", PROJECT_ROOT / "assets"))
DATA_DIR = Path(os.getenv("CHASSIS_DATA_DIR", PROJECT_ROOT / "data"))
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"
EXPORTS_DIR = DATA_DIR / "exports"
PRINT_JOBS_DIR = DATA_DIR / "print_jobs"
DB_PATH = DATA_DIR / "chassis_eol.db"


class DataRootError(RuntimeError):
    """The configured production data root cannot safely serve persistent data."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class DataPaths:
    """All mutable application paths derived from one canonical data root.

    Callers cannot supply individual child paths.  This is intentional: accepting a
    database or report path independently would re-introduce directory traversal and
    split-brain backup/retention behaviour.
    """

    root: Path
    database_dir: Path
    database: Path
    app_logs: Path
    raw_can: Path
    decoded_signals: Path
    reports: Path
    exports: Path
    temp: Path
    backups: Path
    print_jobs: Path
    auth: Path
    config: Path

    @classmethod
    def from_root(cls, value: str | os.PathLike[str]) -> "DataPaths":
        raw = str(value).strip()
        if not raw or "\x00" in raw:
            raise DataRootError("INVALID_DATA_ROOT", "data_root must be a non-empty filesystem path")
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        root = candidate.resolve(strict=False)
        if root == root.parent:
            raise DataRootError(
                "UNSAFE_DATA_ROOT",
                "data_root must not be a filesystem root",
                details={"data_root": str(root)},
            )

        def child(*parts: str) -> Path:
            path = root.joinpath(*parts).resolve(strict=False)
            if root != path and root not in path.parents:
                raise DataRootError(
                    "PATH_OUTSIDE_DATA_ROOT",
                    "derived storage path escaped data_root",
                    details={"data_root": str(root), "path": str(path)},
                )
            return path

        database_dir = child("database")
        return cls(
            root=root,
            database_dir=database_dir,
            database=child("database", "chassis_eol.sqlite3"),
            app_logs=child("logs", "application"),
            raw_can=child("logs", "raw_can"),
            decoded_signals=child("logs", "decoded_signals"),
            reports=child("reports"),
            exports=child("exports"),
            temp=child("temp"),
            backups=child("backups"),
            print_jobs=child("print_jobs"),
            auth=child("auth"),
            config=child("config"),
        )

    def directories(self) -> tuple[Path, ...]:
        return (
            self.root,
            self.database_dir,
            self.app_logs,
            self.raw_can,
            self.decoded_signals,
            self.reports,
            self.exports,
            self.temp,
            self.backups,
            self.print_jobs,
            self.auth,
            self.config,
        )

    def ensure_ready(self, *, minimum_free_bytes: int = 100 * 1024 * 1024) -> dict[str, Any]:
        try:
            for directory in self.directories():
                directory.mkdir(parents=True, exist_ok=True)
            descriptor, probe_name = tempfile.mkstemp(prefix=".write-probe-", dir=self.temp)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(b"data-root-write-probe")
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                Path(probe_name).unlink(missing_ok=True)
            usage = shutil.disk_usage(self.root)
        except PermissionError as exc:
            raise DataRootError(
                "DATA_ROOT_PERMISSION_DENIED",
                "data_root or one of its managed directories is not writable",
                details={"data_root": str(self.root), "error": str(exc)},
            ) from exc
        except OSError as exc:
            raise DataRootError(
                "DATA_ROOT_NOT_WRITABLE",
                "data_root readiness check failed",
                details={"data_root": str(self.root), "error": str(exc)},
            ) from exc
        if usage.free < minimum_free_bytes:
            raise DataRootError(
                "DATA_ROOT_LOW_SPACE",
                "data_root does not have the configured minimum free space",
                details={
                    "data_root": str(self.root),
                    "free_bytes": usage.free,
                    "minimum_free_bytes": minimum_free_bytes,
                },
            )
        return {
            "data_root": str(self.root),
            "writable": True,
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "minimum_free_bytes": minimum_free_bytes,
            "paths": {key: str(value) for key, value in asdict(self).items()},
        }

    def contains(self, value: str | os.PathLike[str]) -> bool:
        path = Path(value).resolve(strict=False)
        return path == self.root or self.root in path.parents

def ensure_data_dirs() -> None:
    DataPaths.from_root(DATA_DIR).ensure_ready(minimum_free_bytes=0)
