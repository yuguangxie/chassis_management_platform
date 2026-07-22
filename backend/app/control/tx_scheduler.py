from __future__ import annotations

import asyncio
import logging

from app.can_gateway.models import CanFrame
from app.control.control_121 import Control121Command, encode_control_121
from app.control.safety_interlock import Operation, SafetyEvaluationContext
from app.core.time import utc_now
from app.services.app_state import AppState

LOGGER = logging.getLogger(__name__)


class TxScheduler:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.task: asyncio.Task[None] | None = None
        self.last_command: Control121Command | None = None
        self.fail_count = 0
        self.period_ms = 20
        self.last_tx_time: str | None = None
        self._send_lock = asyncio.Lock()
        self._periodic_operation: Operation = "manual"
        self._periodic_context: SafetyEvaluationContext | None = None

    async def send_once(
        self,
        command: Control121Command,
        *,
        operation: Operation = "manual",
        context: SafetyEvaluationContext | None = None,
    ) -> dict:
        self.state.safety.require_allowed(command, operation=operation, context=context)
        return await self._transmit(command)

    async def send_priority(
        self,
        command: Control121Command,
        *,
        operation: Operation,
        context: SafetyEvaluationContext | None = None,
    ) -> dict:
        if operation not in {"safe_stop", "emergency"}:
            raise ValueError("priority transmission is reserved for stop operations")
        self.state.safety.require_allowed(command, operation=operation, context=context)
        return await self._transmit(command)

    async def _transmit(self, command: Control121Command) -> dict:
        data = list(encode_control_121(command))
        frame = CanFrame(
            channel=self.state.config.control_channel,
            direction="tx",
            can_id=0x121,
            dlc=8,
            data=data,
            message_name="SCU_Control_Command",
            source="backend",
        )
        async with self._send_lock:
            try:
                await self.state.can.send_frame(self.state.config.control_channel, frame)
            except Exception:
                self.fail_count += 1
                raise
        self.last_command = command
        self.last_tx_time = utc_now()
        return {
            "ok": True,
            "sent": True,
            "frame": frame.ui_dict(),
            "periodic": self.task is not None and not self.task.done(),
        }

    async def start(
        self,
        command: Control121Command,
        period_ms: int = 20,
        *,
        operation: Operation = "manual",
        context: SafetyEvaluationContext | None = None,
    ) -> dict:
        if operation not in {"manual", "eol_motion"}:
            raise ValueError("periodic transmission is only available for manual or EOL motion")
        self.state.safety.require_allowed(command, operation=operation, context=context)
        await self.stop()
        self.period_ms = max(10, min(100, int(period_ms)))
        self.last_command = command
        self._periodic_operation = operation
        self._periodic_context = context
        self.task = asyncio.create_task(self._loop(), name="control-121-periodic")
        return {"ok": True, "periodic": True, "period_ms": self.period_ms}

    async def start_stop_hold(
        self,
        command: Control121Command,
        *,
        operation: Operation,
        period_ms: int,
    ) -> dict:
        if operation not in {"safe_stop", "emergency"}:
            raise ValueError("stop hold is reserved for safe-stop operations")
        self.state.safety.require_allowed(command, operation=operation)
        await self.stop()
        self.period_ms = max(20, min(500, int(period_ms)))
        self.last_command = command
        self._periodic_operation = operation
        self._periodic_context = None
        self.task = asyncio.create_task(self._loop(), name="control-121-stop-hold")
        return {"ok": True, "periodic": True, "period_ms": self.period_ms, "stop_hold": True}

    async def _loop(self) -> None:
        assert self.last_command is not None
        while True:
            try:
                await self.send_once(
                    self.last_command,
                    operation=self._periodic_operation,
                    context=self._periodic_context,
                )
                await asyncio.sleep(self.period_ms / 1000)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.fail_count += 1
                LOGGER.exception("periodic 0x121 stopped after safety/transmit failure")
                return

    async def stop(self) -> dict:
        task = self.task
        self.task = None
        self._periodic_context = None
        if task and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        return {"ok": True, "periodic": False}
