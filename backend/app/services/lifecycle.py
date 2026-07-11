from __future__ import annotations
import asyncio
from collections import deque
import logging
import os
from pathlib import Path
import yaml
from app.alarms.service import AlarmService
from app.can_gateway.manager import CanGatewayManager
from app.control.safety_interlock import SafetyInterlockService
from app.control.safe_stop import SafeStopService
from app.control.tx_scheduler import TxScheduler
from app.dbc.service import DbcService
from app.eol.engine import EolEngine
from app.reports.generator import ReportGenerator
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
from app.core.paths import CONFIG_DIR, DATA_DIR, REPORTS_DIR
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
                await ws.broadcast("signals.dashboard", state.signals.dashboard_summary())
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
    state.can.record_recent(frame)
    if state.telemetry:
        state.telemetry.enqueue(frame, decoded)
        if not state.telemetry.healthy:
            state.db_writable = False
    if state.realtime_publisher:
        state.realtime_publisher.record(frame)

async def startup() -> None:
    state.ws = ws_manager
    state.database = Database()
    state.db_writable = state.database.writable()
    state.dbc = DbcService(state.signals)
    test_fault = os.getenv("CHASSIS_TEST_FAULT", "").strip().lower()
    if state.config.profile != "production" and test_fault == "dbc_unloaded":
        state.dbc.result.loaded = False
        state.dbc.result.raw_only = True
        state.dbc.result.error = "phase-02 injected DBC unavailable fault"
    state.alarms = AlarmService(state.signals)
    state.can = CanGatewayManager(state.config, on_frame)
    state.safety = SafetyInterlockService(state)
    state.tx_scheduler = TxScheduler(state)
    state.safe_stop = SafeStopService(state)
    state.preferences = PreferenceService()
    preferred_report_dir = state.preferences.get("report_directory")
    report_dir = REPORTS_DIR
    if preferred_report_dir:
        candidate = Path(str(preferred_report_dir)).resolve(strict=False)
        if candidate.is_dir() and (DATA_DIR.resolve() == candidate or DATA_DIR.resolve() in candidate.parents):
            report_dir = candidate
    state.reports = ReportGenerator(report_dir)
    state.report_service = ReportService(state)
    state.history_service = HistoryService(state)
    state.repositories = Repositories(state.database)
    state.eol_uow = EolUnitOfWork(state.database)
    state.eol_uow.ensure_software_version(state)
    state.eol = EolEngine(state, uow=state.eol_uow)
    if state.config.profile != "production" and test_fault == "database_unwritable":
        state.db_writable = False
    storage_path = CONFIG_DIR / "storage_config.yaml"
    storage_config = (
        yaml.safe_load(storage_path.read_text(encoding="utf-8")) or {}
        if storage_path.exists()
        else {}
    )
    signal_format = (
        storage_config.get("decoded_signal_logging", {}).get("format", "csv")
    )
    raw_logging = storage_config.get("raw_can_logging", {})
    retention = storage_config.get("retention", {})
    state.raw_writer = RawLogWriter(
        batch_size=200,
        retention_days=int(retention.get("raw_can_days", 180)),
        compress_rotated=bool(raw_logging.get("compress_after_days", 0)),
    )
    state.signal_writer = SignalLogWriter(format_name=signal_format)
    state.telemetry = TelemetryRecorder(
        state.database,
        state.raw_writer,
        state.signal_writer,
        lambda: state.eol.active_session_id if state.eol else None,
    )
    await state.telemetry.start()
    state.realtime_publisher = RealtimePublisher()
    await state.realtime_publisher.start()
    await state.can.start_all()
    await state.ws.broadcast("system.version", state.snapshot())

async def shutdown() -> None:
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
