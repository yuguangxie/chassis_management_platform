from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import logging
from typing import Any, Callable

from app.can_gateway.models import CanFrame
from app.core.time import utc_now
from app.storage.database import Database
from app.storage.raw_log_writer import RawLogWriter
from app.storage.signal_log_writer import SignalLogWriter


LOGGER = logging.getLogger(__name__)


@dataclass
class TelemetryItem:
    session_id: str | None
    frame: CanFrame
    decoded: dict[str, Any]


class TelemetryRecorder:
    def __init__(
        self,
        database: Database,
        raw_writer: RawLogWriter,
        signal_writer: SignalLogWriter,
        session_id_provider: Callable[[], str | None],
        *,
        queue_size: int = 20_000,
        batch_size: int = 200,
    ) -> None:
        self.database = database
        self.raw_writer = raw_writer
        self.signal_writer = signal_writer
        self.session_id_provider = session_id_provider
        self.queue: asyncio.Queue[TelemetryItem] = asyncio.Queue(maxsize=queue_size)
        self.batch_size = batch_size
        self.task: asyncio.Task[None] | None = None
        self.healthy = True
        self.dropped = 0
        self.last_error = ""
        self._alarm_levels: dict[tuple[str, str], int] = {}

    async def start(self) -> None:
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self._worker(), name="telemetry-persistence")

    def enqueue(self, frame: CanFrame, decoded: dict[str, Any]) -> None:
        session_id = self.session_id_provider()
        try:
            # All disk access happens in the single persistence worker.  This keeps the
            # CAN ingress path bounded even while logs rotate or the filesystem is slow.
            self.queue.put_nowait(TelemetryItem(session_id, frame.model_copy(deep=True), decoded))
        except asyncio.QueueFull:
            self.dropped += 1
            self.healthy = False
            self.last_error = "telemetry persistence queue overflow"

    async def drain(self, session_id: str | None = None) -> None:
        await self.queue.join()
        self.raw_writer.flush(session_id)
        self.signal_writer.flush(session_id)

    async def stop(self) -> None:
        await self.drain()
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        self.raw_writer.close()
        self.signal_writer.close()

    async def _worker(self) -> None:
        while True:
            first = await self.queue.get()
            batch = [first]
            try:
                while len(batch) < self.batch_size:
                    try:
                        batch.append(self.queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                self._persist_batch(batch)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.healthy = False
                self.last_error = str(exc)
                LOGGER.exception("telemetry persistence batch failed")
            finally:
                for _ in batch:
                    self.queue.task_done()

    def _persist_batch(self, batch: list[TelemetryItem]) -> None:
        raw_rows: list[tuple[Any, ...]] = []
        signal_rows: list[tuple[Any, ...]] = []
        file_rows: dict[str, list[dict[str, Any]]] = {}
        alarm_rows: list[tuple[Any, ...]] = []
        for item in batch:
            frame = item.frame
            self.raw_writer.write(frame, item.session_id)
            if not item.session_id:
                continue
            timestamp = utc_now()
            raw_rows.append(
                (
                    item.session_id,
                    timestamp,
                    frame.channel,
                    frame.direction,
                    frame.can_id_hex,
                    int(frame.is_extended),
                    int(frame.is_remote),
                    frame.dlc,
                    frame.data_hex,
                    frame.raw_packet_hex,
                    frame.source,
                    None,
                    frame.parse_status,
                    None,
                    frame.message_name or "",
                    None,
                )
            )
            for name, payload in item.decoded.get("signals", {}).items():
                value = payload.get("value")
                signal_rows.append(
                    (
                        item.session_id,
                        timestamp,
                        frame.channel,
                        frame.can_id_hex,
                        item.decoded.get("message_name") or frame.message_name or "",
                        name,
                        json.dumps(value, ensure_ascii=False, default=str),
                        json.dumps(value, ensure_ascii=False, default=str),
                        payload.get("unit", ""),
                        payload.get("label", ""),
                        payload.get("quality", "good"),
                        "",
                    )
                )
                file_rows.setdefault(item.session_id, []).append(
                    {
                        "session_id": item.session_id,
                        "timestamp_utc": timestamp,
                        "channel": frame.channel,
                        "can_id_hex": frame.can_id_hex,
                        "message_name": item.decoded.get("message_name") or frame.message_name or "",
                        "signal_name": name,
                        "raw_value": value,
                        "physical_value": value,
                        "unit": payload.get("unit", ""),
                        "enum_label": payload.get("label", ""),
                        "quality": payload.get("quality", "good"),
                    }
                )
            if frame.can_id == 0x77:
                level = int(item.decoded.get("signals", {}).get("VCU_Max_Warning_Level", {}).get("value", 0))
                alarm_key = (item.session_id, "VCU_Max_Warning_Level")
                if level > 0 and self._alarm_levels.get(alarm_key) != level:
                    alarm_rows.append(
                        (
                            item.session_id,
                            timestamp,
                            frame.channel,
                            frame.can_id_hex,
                            "VCU_Max_Warning_Level",
                            level,
                            {1: "Warning", 2: "Derating", 3: "Fault", 4: "Severe"}.get(level, "Reserved"),
                            "active",
                            f"0x77 warning level {level}",
                        )
                    )
                self._alarm_levels[alarm_key] = level
        with self.database.transaction() as conn:
            conn.executemany(
                "INSERT INTO raw_can_frames(session_id,timestamp_utc,channel,direction,can_id_hex,"
                "is_extended,is_remote,dlc,data_hex,packet_hex,source_ip,source_port,parse_status,"
                "error_code,message_name,period_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                raw_rows,
            )
            if signal_rows:
                conn.executemany(
                    "INSERT INTO decoded_signals(session_id,timestamp_utc,channel,can_id_hex,"
                    "message_name,signal_name,raw_value,physical_value,unit,enum_label,quality,"
                    "threshold_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    signal_rows,
                )
            if alarm_rows:
                conn.executemany(
                    "INSERT INTO alarms(session_id,timestamp_utc,channel,can_id_hex,signal_name,"
                    "level,level_label,status,description) VALUES (?,?,?,?,?,?,?,?,?)",
                    alarm_rows,
                )
        for session_id, rows in file_rows.items():
            self.signal_writer.write_rows(session_id, rows)

    def metrics(self) -> dict[str, Any]:
        return {
            "queue_depth": self.queue.qsize(),
            "queue_capacity": self.queue.maxsize,
            "dropped": self.dropped,
            "healthy": self.healthy,
            "last_error": self.last_error,
            "raw_log": self.raw_writer.metrics(),
            "signal_log": self.signal_writer.metrics(),
        }
