from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from app.core.paths import CONFIG_DIR


class StorageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StorageLayout(StorageModel):
    layout_version: Literal[1] = 1
    database: Literal["database/chassis_eol.sqlite3"]
    application_logs: Literal["logs/application"]
    raw_can: Literal["logs/raw_can"]
    decoded_signals: Literal["logs/decoded_signals"]
    reports: Literal["reports"]
    exports: Literal["exports"]
    temporary: Literal["temp"]
    backups: Literal["backups"]
    print_jobs: Literal["print_jobs"]


class ApplicationLogging(StorageModel):
    max_bytes: int = Field(default=16 * 1024 * 1024, ge=1024 * 1024, le=1024 * 1024 * 1024)
    interval_hours: int = Field(default=24, ge=1, le=168)
    backup_count: int = Field(default=30, ge=1, le=365)
    compress_rotated: bool = True


class RawCanLogging(StorageModel):
    enabled: bool = True
    format: Literal["csv"] = "csv"
    rotate_by: Literal["session_and_date"] = "session_and_date"
    flush_interval_ms: int = Field(default=1000, ge=50, le=60_000)
    rotate_bytes: int = Field(default=32 * 1024 * 1024, ge=1024 * 1024, le=4 * 1024 * 1024 * 1024)
    compress_rotated: bool = True


class DecodedSignalLogging(StorageModel):
    enabled: bool = True
    format: Literal["csv", "parquet"] = "csv"
    sample_mode: Literal["change_or_periodic"] = "change_or_periodic"
    periodic_sample_ms: int = Field(default=100, ge=10, le=60_000)


class RetentionPolicy(StorageModel):
    raw_can_days: int = Field(default=180, ge=1, le=3650)
    decoded_signal_days: int = Field(default=180, ge=1, le=3650)
    reports_days: int = Field(default=3650, ge=1, le=36500)
    app_logs_days: int = Field(default=90, ge=1, le=3650)
    exports_days: int = Field(default=30, ge=1, le=3650)
    temp_days: int = Field(default=7, ge=1, le=365)
    backup_days: int = Field(default=365, ge=1, le=36500)
    unattended_cleanup: bool = False
    require_admin_confirmation: Literal[True] = True


class IntegrityPolicy(StorageModel):
    write_file_hash: bool = True
    report_records_log_hash: bool = True
    backup_manifest_hash: Literal["sha256"] = "sha256"


class StorageConfig(StorageModel):
    storage: StorageLayout
    application_logging: ApplicationLogging = Field(default_factory=ApplicationLogging)
    raw_can_logging: RawCanLogging = Field(default_factory=RawCanLogging)
    decoded_signal_logging: DecodedSignalLogging = Field(default_factory=DecodedSignalLogging)
    retention: RetentionPolicy = Field(default_factory=RetentionPolicy)
    integrity: IntegrityPolicy = Field(default_factory=IntegrityPolicy)

    @model_validator(mode="after")
    def unattended_delete_remains_disabled(self) -> "StorageConfig":
        if self.retention.unattended_cleanup:
            raise ValueError("unattended cleanup is not approved; use admin preview and confirmation")
        return self


def load_storage_config(
    profile: str,
    path: Path | None = None,
) -> StorageConfig:
    config_path = path or CONFIG_DIR / "storage_config.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config = StorageConfig.model_validate(payload)
    if profile == "production" and config.decoded_signal_logging.format == "parquet":
        raise ValueError(
            "production Parquet logging is disabled until an append-friendly partition writer is qualified"
        )
    return config
