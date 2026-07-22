from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


DataQuality = Literal["good", "degraded", "unavailable", "mock"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObjectResponse(RootModel[dict[str, Any]]):
    pass


class ObjectListResponse(RootModel[list[dict[str, Any]]]):
    pass


class ErrorResponse(ApiModel):
    code: str
    message: str
    details: Any = Field(default_factory=dict)
    trace_id: str


class DashboardMetadata(ApiModel):
    data_source: str
    mock: bool
    quality: DataQuality
    updated_at: str
    trace_id: str = ""


class ActionResponse(ApiModel):
    ok: bool = True
    message: str
    trace_id: str = ""
    data_source: str = "service"
    mock: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class OverviewDashboardResponse(DashboardMetadata):
    station: dict[str, Any]
    kpi: dict[str, Any]
    channels: dict[str, Any]
    current_vehicle: dict[str, Any]
    alarm_summary: dict[str, Any]
    charts: dict[str, Any]
    recent_sessions: list[dict[str, Any]]
    status: dict[str, Any]
    signals: dict[str, Any]


class CanLatestFramesResponse(DashboardMetadata):
    items: list[dict[str, Any]]
    total: int


class CanDecodedResponse(DashboardMetadata):
    frame: dict[str, Any]
    signals: list[dict[str, Any]]
    dbc_status: str


class CanMonitorStatisticsResponse(DashboardMetadata):
    can_id_distribution: list[dict[str, Any]]
    fps_trend: list[dict[str, Any]]
    period_jitter: list[dict[str, Any]]
    error_summary: dict[str, Any]
    history_files: list[dict[str, Any]]
    footer_status: dict[str, Any]


class SignalDashboardResponse(DashboardMetadata):
    status: dict[str, Any]
    bms: dict[str, Any]
    vehicle: dict[str, Any]
    wheel_speed: dict[str, Any]
    steering: dict[str, Any]
    motor: dict[str, Any]
    lights_brake: dict[str, Any]
    alarm: dict[str, Any]
    watchlist: list[dict[str, Any]]


class CurveConfigResponse(DashboardMetadata):
    groups: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    default_window: str
    default_sample_rate: str
    default_downsample: str
    default_playback_speed: str


class CurveTimeseriesResponse(DashboardMetadata):
    mode: Literal["live", "history"]
    charts: dict[str, Any]


class AlarmDashboardResponse(DashboardMetadata):
    summary: dict[str, Any]
    warning_matrix_0x77: list[dict[str, Any]]
    bms_protect_0x102: dict[str, Any]
    diagnosis_suggestions: list[dict[str, Any]]
    history: list[dict[str, Any]]
    charts: dict[str, Any]


class ReportItem(ApiModel):
    report_id: str
    session_id: str
    chassis_no: str
    vin: str
    test_time: str
    result: str
    operator: str
    type: str
    size: str
    size_bytes: int
    path: str
    generation_status: str
    file_hash: str | None = None


class ReportPreviewResponse(DashboardMetadata):
    report_id: str
    filename: str
    file_type: str
    file_sha256: str
    file_size_bytes: int
    preview: dict[str, Any]
    json_summary: dict[str, Any] | None = None
    csv_rows: list[dict[str, Any]] | None = None
    document_text: list[str] | None = None
    preview_image_data_url: str | None = None


class ReportDashboardResponse(DashboardMetadata):
    directory: dict[str, Any]
    reports: list[ReportItem]
    selected_report: ReportPreviewResponse | None
    related_data: dict[str, Any]
    charts: dict[str, Any]


class ReportListResponse(DashboardMetadata):
    items: list[ReportItem]
    total: int


class HistoryDashboardResponse(DashboardMetadata):
    filters: dict[str, Any]
    summary: dict[str, Any]
    sessions: list[dict[str, Any]]
    selected_session: dict[str, Any] | None
    charts: dict[str, Any]
    pagination: dict[str, Any]


class EolDashboardResponse(DashboardMetadata):
    session: dict[str, Any]
    steps: list[dict[str, Any]]
    current_step: dict[str, Any]
    measurements: list[dict[str, Any]]
    assertions: list[dict[str, Any]]
    step_logs: list[dict[str, Any]]
    charts: dict[str, Any]
    stats: dict[str, Any]
    source: str
    report: dict[str, Any] | None = None
    safe_stop: dict[str, Any] | None = None


class SystemDashboardResponse(DashboardMetadata):
    save_state: dict[str, Any]
    auth: dict[str, Any]
    basic: dict[str, Any]
    dbc: dict[str, Any]
    storage: dict[str, Any]
    thresholds: list[dict[str, Any]]
    roles: list[dict[str, Any]]
    maintenance: dict[str, Any]
    safe_defaults: list[dict[str, Any]]
    version: dict[str, Any]
    storage_trend: list[dict[str, Any]]
    storage_summary: dict[str, Any]
    config_history: list[dict[str, Any]]


class ReportChangeDirectoryRequest(ApiModel):
    path: str


class ReportPrintRequest(ApiModel):
    preview_confirmed: bool
    printer_name: str | None = Field(default=None, min_length=1, max_length=256)


class BackupRestoreRequest(ApiModel):
    confirmation: str = Field(min_length=1, max_length=256)


class CleanupPreviewRequest(ApiModel):
    cutoff_utc: datetime


class CleanupExecuteRequest(CleanupPreviewRequest):
    confirmation: Literal["CLEANUP"]
    batch_size: int = Field(default=50, ge=1, le=500)


class RawLogDeleteRequest(ApiModel):
    confirmation: Literal["DELETE"]
    reason: str = Field(min_length=2, max_length=500)


class StorageStatsResponse(ApiModel):
    data_root: str
    paths: dict[str, str]
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float
    category_bytes: dict[str, int]
    schema_version: int
    latest_schema_version: int
    database_writable: bool
    health: dict[str, Any]
    measured_at: str


class StorageTrendPoint(ApiModel):
    timestamp_utc: str
    date: str
    used_bytes: int
    free_bytes: int
    used_gb: float
    source: Literal["current-measurement"]


class SchemaVersionResponse(ApiModel):
    schema_version: int


class BackupCreateResponse(ApiModel):
    backup_id: str
    manifest_path: str
    database_size_bytes: int
    database_sha256: str
    schema_version: int
    created_at: str
    status: Literal["VERIFIED"]


class BackupListItem(ApiModel):
    backup_id: str
    valid: bool
    created_at: str | None
    schema_version: int | None
    size_bytes: int
    errors: list[str]


class BackupListResponse(ApiModel):
    items: list[BackupListItem]


class BackupValidationResponse(ApiModel):
    valid: bool
    backup_id: str
    manifest: dict[str, Any] | None
    errors: list[str]


class BackupRestoreResponse(ApiModel):
    backup_id: str
    status: Literal["RESTORED"]
    restored_at: str
    schema_version: int
    rollback_path: str


class CleanupPreviewResponse(ApiModel):
    dry_run: bool = True
    cutoff_utc: str
    session_ids: list[str]
    session_count: int
    oldest_utc: str | None
    newest_utc: str | None
    row_counts: dict[str, int]
    file_count: int
    file_bytes: int
    estimated_database_bytes: int
    total_bytes: int
    protected: dict[str, int | str]


class CleanupJobResponse(ApiModel):
    id: str
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
    cutoff_utc: str
    requested_by: str
    dry_run: bool
    confirmation: str | None
    candidate_json: str
    progress_json: str
    cancel_requested: bool
    error_message: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    updated_at: str
    candidate: dict[str, Any]
    progress: dict[str, Any]


class PrinterInfoResponse(ApiModel):
    name: str
    is_default: bool
    status: str


class PrinterStatusResponse(ApiModel):
    backend: str
    available: bool
    default_printer: str | None
    printers: list[PrinterInfoResponse]
    error: str | None


class PrintJobResponse(ApiModel):
    id: str
    job_id: str
    report_id: str
    file_path: str
    requested_by: str
    status: Literal["QUEUED", "PRINTING", "COMPLETED", "FAILED", "CANCELLED"]
    printer_name: str | None
    backend: str | None
    spooler_job_id: str | None
    report_hash: str | None
    attempts: int
    status_detail: str | None
    error_message: str | None
    completed_at: str | None
    cancelled_at: str | None
    created_at: str
    updated_at: str


class PrintJobEnvelope(ApiModel):
    job: PrintJobResponse


class HistoryExportRequest(ApiModel):
    chassis_no: str | None = None
    vin: str | None = None
    serial_no: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    result: str | None = None
    operator: str | None = None
    station: str | None = None


class ReplaySeekRequest(ApiModel):
    progress_percent: float = Field(ge=0, le=100)


class AlarmActionRequest(ApiModel):
    alarm_id: str | None = None
    can_id: str | None = None
    reason: str | None = None


class SafetyOverrideUseRequest(ApiModel):
    override_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    vehicle_id: str = Field(min_length=1, max_length=128)


class WatchlistUpdateRequest(ApiModel):
    signals: list[str] = Field(min_length=1, max_length=256)


class CurveSelectionRequest(ApiModel):
    signals: list[str] = Field(min_length=1, max_length=256)


class DashboardLayoutRequest(ApiModel):
    layout: dict[str, Any]


class ChannelSettingsItem(ApiModel):
    name: Literal["CAN1", "CAN2"]
    protocol: Literal["UDP", "TCP"]
    local_ip: str
    local_port: int = Field(ge=1, le=65535)
    device_ip: str
    device_port: int = Field(ge=1, le=65535)
    tx_enabled: bool = True
    rx_status: str = "offline"
    period_ms: int = Field(default=20, ge=10, le=100)
    control_enabled: bool = False
    status: str = "active"


class ChannelSettingsUpdateRequest(ApiModel):
    local_network: dict[str, Any] = Field(default_factory=dict)
    channels: list[ChannelSettingsItem] = Field(min_length=1, max_length=2)


class ChannelSettingsResponse(ApiModel):
    local_network: dict[str, Any]
    channels: list[dict[str, Any]]
    runtime_profile: str | None = None
    saved: bool | None = None
    restored: bool | None = None
    reconnected: bool | None = None
    message: str | None = None
    trace_id: str = ""
