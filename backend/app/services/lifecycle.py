from __future__ import annotations
import asyncio
from collections import deque
import logging
import os
from app.alarms.service import AlarmService
from app.can_gateway.manager import CanGatewayManager
from app.control.safety_interlock import SafetyInterlockService
from app.control.safe_stop import SafeStopService
from app.control.tx_scheduler import TxScheduler
from app.control.override_service import OverrideService
from app.control.intent_service import ControlIntentService
from app.control.hardware_acceptance import HardwareAcceptanceService
from app.dbc.service import DbcService
from app.eol.engine import EolEngine
from app.reports.generator import ReportGenerator
from app.reports.printing import PrintService, build_print_backend
from app.reports.dependencies import report_dependency_status
from app.reports.service import ReportService
from app.services.app_state import state
from app.services.preferences import PreferenceService
from app.services.history_service import HistoryService
from app.storage.database import Database
from app.storage.raw_log_writer import RawLogWriter
from app.storage.signal_log_writer import SignalLogWriter
from app.storage.telemetry import TelemetryRecorder
from app.storage.uow import EolUnitOfWork
from app.storage.repositories import Repositories
from app.storage.lifecycle import BackupService, RetentionService, StorageHealthMonitor
from app.storage.config import load_storage_config
from app.core.logging import configure_logging
from app.core.paths import CONFIG_DIR, DataPaths
from app.core.time import utc_now
from app.websocket.manager import manager as ws_manager

LOGGER = logging.getLogger(__name__)


class RealtimePublisher:
    """Publish bounded snapshots on a fixed cadence instead of per incoming CAN frame."""

    def __init__(self) -> None:
        self.latest_updates: dict[str, dict] = {}
        self.raw_frames: deque[dict] = deque(maxlen=512)
        self.task: asyncio.Task[None] | None = None
        self._running = False
        self._last_statistics = 0.0

    async def start(self) -> None:
        if self.task and not self.task.done():
            return
        self._running = True
        self.task = asyncio.create_task(self._run(), name="realtime-publisher")

    async def stop(self) -> None:
        self._running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        self.latest_updates.clear()
        self.raw_frames.clear()

    def record(self, frame) -> None:
        if state.can:
            self.latest_updates[f"{frame.channel}:{frame.can_id:X}"] = state.can.latest_frame_update(frame)
        # Raw data is intentionally only retained for clients that explicitly subscribe.
        if state.ws and (
            state.ws.has_subscribers("can.raw_frames.batch")
            or state.ws.has_subscribers("can.raw_frame")
        ):
            self.raw_frames.append(frame.ui_dict())

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while self._running:
            await asyncio.sleep(0.1)  # signal snapshots: at most 10 Hz
            ws = state.ws
            if not ws:
                continue
            if self.latest_updates and (
                ws.has_subscribers("can.latest_frames.batch")
                or ws.has_subscribers("can.latest_frame_update")
            ):
                items = list(self.latest_updates.values())
                self.latest_updates.clear()
                if ws.has_subscribers("can.latest_frames.batch"):
                    await ws.broadcast("can.latest_frames.batch", {"items": items})
                # Preserve the phase-03 topic for explicit legacy subscribers, still at
                # the publisher cadence rather than once per transport callback.
                if ws.has_subscribers("can.latest_frame_update"):
                    for item in items:
                        await ws.broadcast("can.latest_frame_update", item)
            elif not (
                ws.has_subscribers("can.latest_frames.batch")
                or ws.has_subscribers("can.latest_frame_update")
            ):
                self.latest_updates.clear()
            if self.raw_frames and (
                ws.has_subscribers("can.raw_frames.batch") or ws.has_subscribers("can.raw_frame")
            ):
                items = list(self.raw_frames)
                self.raw_frames.clear()
                if ws.has_subscribers("can.raw_frames.batch"):
                    await ws.broadcast("can.raw_frames.batch", {"items": items})
                if ws.has_subscribers("can.raw_frame"):
                    for item in items:
                        await ws.broadcast("can.raw_frame", item)
            if ws.has_subscribers("signals.current"):
                await ws.broadcast("signals.current", state.signals.snapshot())
            if ws.has_subscribers("signals.dashboard"):
                # REST and WebSocket deliberately share one envelope so a missing
                # top-level quality field can never downgrade a healthy UI snapshot.
                from app.api.signals import live_dashboard_payload
                await ws.broadcast("signals.dashboard", live_dashboard_payload())
            if ws.has_subscribers("signals.timeseries.batch"):
                # The renderer consumes the same chart-shaped payload as REST, avoiding a
                # follow-up GET for every WebSocket message.
                from app.api.signals import live_timeseries_batch
                await ws.broadcast("signals.timeseries.batch", live_timeseries_batch())
            now = loop.time()
            if now - self._last_statistics >= 1.0:  # status/statistics: at most 1 Hz
                self._last_statistics = now
                if state.can and ws.has_subscribers("can.statistics"):
                    await ws.broadcast("can.statistics", state.can.statistics())
                if state.can and ws.has_subscribers("can.channel_status"):
                    await ws.broadcast("can.channel_status", state.can.status())
                if state.alarms and ws.has_subscribers("alarms.current"):
                    await ws.broadcast("alarms.current", state.alarms.current())
                if ws.has_subscribers("system.runtime_metrics"):
                    await ws.broadcast(
                        "system.runtime_metrics",
                        {
                            "can": state.can.statistics() if state.can else {},
                            "telemetry": state.telemetry.metrics() if state.telemetry else {},
                            "websocket": ws.snapshot(),
                        },
                    )


async def on_frame(frame):
    decoded = await state.dbc.decode(frame)
    state.can.record_recent(
        frame, state.eol.active_session_id if state.eol else None
    )
    if state.telemetry:
        state.telemetry.enqueue(frame, decoded)
        if not state.telemetry.healthy:
            state.db_writable = False
    if state.realtime_publisher:
        state.realtime_publisher.record(frame)


def on_can_security_event(event: dict) -> None:
    channel = str(event.get("channel") or "UNKNOWN")
    source = str(event.get("source") or "unknown")
    description = (
        f"拒绝未授权 UDP 来源 {source}; expected="
        f"{event.get('expected_ip')}:{event.get('expected_port')}"
    )
    if state.alarms:
        state.alarms.raise_system_alarm(
            f"can_source_rejected_{channel.lower()}",
            3,
            "Unauthorized CAN UDP Source",
            description,
        )
    if state.database:
        try:
            state.database.execute(
                "INSERT INTO alarms(timestamp_utc, channel, can_id_hex, signal_name, level, level_label, status, description) VALUES (?,?,?,?,?,?,?,?)",
                (utc_now(), channel, "UDP", "UnauthorizedSource", 3, "Critical", "active", description),
            )
        except Exception:
            LOGGER.exception("failed to persist CAN source security alarm")


def on_storage_failure(message: str) -> None:
    state.db_writable = False
    if state.alarms:
        state.alarms.raise_system_alarm(
            "storage_unhealthy",
            4,
            "Storage Unhealthy",
            message,
        )

async def startup() -> None:
    state.ws = ws_manager
    # The isolated test profile uses loopback transports but must not relabel real
    # repository/database payloads as UI mock data. Only the explicit mock profile
    # advertises mock provenance to operators.
    state.mock_enabled = state.config.profile == "mock"
    state.data_paths = DataPaths.from_root(state.config.data_root)
    minimum_free_bytes = int(os.getenv("CHASSIS_MIN_FREE_BYTES", str(100 * 1024 * 1024)))
    state.data_paths.ensure_ready(minimum_free_bytes=minimum_free_bytes)
    state.storage_config = load_storage_config(state.config.profile)
    configure_logging(
        state.data_paths.app_logs,
        settings=state.storage_config.application_logging,
        failure_callback=on_storage_failure,
    )
    state.alarms = AlarmService(state.signals)
    state.database = Database(
        state.data_paths.database,
        backup_dir=state.data_paths.backups / "migration",
        failure_callback=on_storage_failure,
    )
    state.db_writable = state.database.writable()
    state.auth.bootstrap_path = state.data_paths.auth / "bootstrap-admin.secret"
    state.auth.bind_database(state.database)
    state.overrides = OverrideService(state.database, state)
    state.control_intents = ControlIntentService(state)
    recovered_intents = state.control_intents.recover_unfinished()
    if recovered_intents:
        LOGGER.warning("recovered %s unfinished control intents", len(recovered_intents))
    state.dbc = DbcService(state.signals)
    state.hardware_acceptance = HardwareAcceptanceService(state)
    test_fault = os.getenv("CHASSIS_TEST_FAULT", "").strip().lower()
    if state.config.profile != "production" and test_fault == "dbc_unloaded":
        state.dbc.result.loaded = False
        state.dbc.result.raw_only = True
        state.dbc.result.error = "phase-02 injected DBC unavailable fault"
    state.can = CanGatewayManager(state.config, on_frame, on_can_security_event)
    state.safety = SafetyInterlockService(state)
    state.tx_scheduler = TxScheduler(state)
    state.safe_stop = SafeStopService(state)
    state.preferences = PreferenceService(state.data_paths.config / "ui_preferences.json")
    state.reports = ReportGenerator(state.data_paths.reports)
    state.report_service = ReportService(state)
    state.printing = PrintService(state, build_print_backend(state.config.profile))
    report_dependencies = report_dependency_status(CONFIG_DIR / "report_config.yaml")
    if state.config.profile == "production" and not report_dependencies["ready"]:
        raise RuntimeError(
            "production report dependencies are incomplete: "
            + str(report_dependencies.get("action") or report_dependencies)
        )
    printer_status = state.printing.printer_status()
    if state.config.profile == "production" and state.config.printer_required and not printer_status["available"]:
        raise RuntimeError(
            "production printer is required but unavailable: " + str(printer_status.get("error"))
        )
    await state.printing.start()
    state.history_service = HistoryService(state)
    state.repositories = Repositories(state.database)
    state.eol_uow = EolUnitOfWork(state.database)
    state.eol_uow.ensure_software_version(state)
    state.eol = EolEngine(state, uow=state.eol_uow)
    if state.config.profile != "production" and test_fault == "database_unwritable":
        state.db_writable = False
    signal_format = state.storage_config.decoded_signal_logging.format
    raw_logging = state.storage_config.raw_can_logging
    retention = state.storage_config.retention
    state.raw_writer = RawLogWriter(
        root=state.data_paths.raw_can,
        batch_size=200,
        rotate_bytes=raw_logging.rotate_bytes,
        retention_days=retention.raw_can_days,
        compress_rotated=raw_logging.compress_rotated,
    )
    state.signal_writer = SignalLogWriter(root=state.data_paths.decoded_signals, format_name=signal_format)
    state.telemetry = TelemetryRecorder(
        state.database,
        state.raw_writer,
        state.signal_writer,
        lambda: state.eol.active_session_id if state.eol else None,
        failure_callback=on_storage_failure,
    )
    state.backups = BackupService(state, state.data_paths)
    state.retention = RetentionService(state, state.data_paths)
    state.storage_health = StorageHealthMonitor(
        state,
        state.data_paths,
        minimum_free_bytes=minimum_free_bytes,
    )
    await state.storage_health.start()
    await state.telemetry.start()
    state.realtime_publisher = RealtimePublisher()
    await state.realtime_publisher.start()
    await state.can.start_all()
    await state.ws.broadcast("system.version", state.snapshot())

async def shutdown() -> None:
    if state.printing:
        await state.printing.stop()
    if state.storage_health:
        await state.storage_health.stop()
    state.storage_health = None
    if state.retention:
        await state.retention.stop()
    if state.eol:
        await state.eol.shutdown()
    if state.tx_scheduler:
        await state.tx_scheduler.stop()
    if state.can:
        await state.can.stop_all()
    if state.realtime_publisher:
        await state.realtime_publisher.stop()
    state.realtime_publisher = None
    if state.telemetry:
        await state.telemetry.stop()
    if state.database:
        state.database.close()
    state.auth.database = None
