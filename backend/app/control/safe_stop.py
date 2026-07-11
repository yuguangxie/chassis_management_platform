from __future__ import annotations

import asyncio
import time
from typing import Literal

from app.control.control_121 import Control121Command
from app.control.safety_interlock import InterlockBlocked
from app.security.auth import Principal
from app.services.audit import record_operator_action
from app.core.time import utc_now


def safe_stop_command() -> Control121Command:
    return Control121Command(
        shift="N",
        drive_mode="Remote",
        target_speed_kmh=0,
        front_steering_cmd=0,
        rear_steering_cmd=0,
        brake_enable=True,
        speed_mode=True,
    )


class SafeStopService:
    def __init__(self, state) -> None:
        self.state = state
        self._lock = asyncio.Lock()

    async def execute(
        self,
        *,
        emergency: bool,
        principal: Principal | None,
        reason: str,
        timeout_ms: int | None = None,
    ) -> dict:
        operation: Literal["safe_stop", "emergency"] = "emergency" if emergency else "safe_stop"
        timeout = (timeout_ms or self.state.config.safe_stop_timeout_ms) / 1000
        command = safe_stop_command()
        async with self._lock:
            self.state.safe_stop_active = True
            self.state.safe_stop_latched = True
            if emergency:
                self.state.emergency_stop = True
            await self.state.tx_scheduler.stop()
            started = time.monotonic()
            attempts = 0
            feedback_seen = False
            try:
                self.state.safety.require_allowed(command, operation=operation)
            except InterlockBlocked as exc:
                result = {
                    "ok": False,
                    "code": "INTERLOCK_BLOCKED",
                    "message": "停车通道不可用，停车锁存保持",
                    "details": exc.evaluation,
                    "attempts": 0,
                    "latched": True,
                }
                result["alarm"] = await self._raise_failure_alarm(result["code"], result["message"])
                record_operator_action(self.state, principal, operation, "control.0x121", {"reason": reason}, "BLOCKED")
                self.state.safe_stop_active = False
                return result

            while time.monotonic() - started < timeout:
                try:
                    await self.state.tx_scheduler.send_priority(command, operation=operation)
                    attempts += 1
                except InterlockBlocked as exc:
                    result = {
                        "ok": False,
                        "code": "INTERLOCK_BLOCKED",
                        "message": "停车过程中通道失效，停车锁存保持",
                        "details": exc.evaluation,
                        "attempts": attempts,
                        "latched": True,
                    }
                    result["alarm"] = await self._raise_failure_alarm(result["code"], result["message"])
                    record_operator_action(self.state, principal, operation, "control.0x121", {"reason": reason, "attempts": attempts}, "BLOCKED")
                    self.state.safe_stop_active = False
                    return result

                feedback = self._feedback_after(started)
                if feedback is not None:
                    feedback_seen = True
                    if feedback["stopped"]:
                        self.state.safe_stop_active = False
                        result = {
                            "ok": True,
                            "code": "STOP_CONFIRMED",
                            "message": "已通过零速与制动反馈确认停车",
                            "attempts": attempts,
                            "feedback": feedback,
                            "latched": True,
                            "emergency_stop": self.state.emergency_stop,
                        }
                        record_operator_action(self.state, principal, operation, "control.0x121", {"reason": reason, "attempts": attempts, "feedback": feedback}, "CONFIRMED")
                        return result
                await asyncio.sleep(self.state.config.safe_stop_retry_ms / 1000)

            self.state.safe_stop_active = False
            code = "SAFE_STOP_TIMEOUT" if feedback_seen else "FEEDBACK_MISSING"
            result = {
                "ok": False,
                "code": code,
                "message": "停车反馈超时，停车锁存保持" if feedback_seen else "未收到可信停车反馈，停车锁存保持",
                "attempts": attempts,
                "latched": True,
                "emergency_stop": self.state.emergency_stop,
            }
            result["alarm"] = await self._raise_failure_alarm(code, result["message"])
            record_operator_action(self.state, principal, operation, "control.0x121", {"reason": reason, "attempts": attempts}, code)
            return result

    async def release_emergency(
        self,
        principal: Principal,
        *,
        confirmation: str,
        reason: str,
    ) -> dict:
        if confirmation != "RELEASE":
            return {"ok": False, "code": "CONFIRMATION_REQUIRED", "message": "解除急停必须输入 RELEASE"}
        evaluation = self.state.safety.evaluate(operation="release_emergency")
        if not evaluation["allowed"]:
            record_operator_action(self.state, principal, "release_emergency", "control.estop", {"reason": reason}, "BLOCKED")
            return {"ok": False, "code": "INTERLOCK_BLOCKED", "message": "解除急停条件不满足", "details": evaluation}
        self.state.emergency_stop = False
        self.state.safe_stop_latched = False
        record_operator_action(self.state, principal, "release_emergency", "control.estop", {"reason": reason}, "OK")
        return {"ok": True, "emergency_stop": False, "message": "急停锁存已解除"}

    def _feedback_after(self, started_monotonic: float) -> dict | None:
        speed_item = self.state.signals.freshest(
            "CCU_Vehicle_Speed",
            "Vehicle_Speed",
            max_age_seconds=self.state.config.channel_online_timeout_seconds,
        )
        brake_item = self.state.signals.freshest(
            "Brake_Status", max_age_seconds=self.state.config.channel_online_timeout_seconds
        )
        if not speed_item or not brake_item:
            return None
        if min(
            float(speed_item.get("received_at_monotonic", 0)),
            float(brake_item.get("received_at_monotonic", 0)),
        ) < started_monotonic:
            return None
        speed = float(speed_item.get("value", 999))
        brake = bool(brake_item.get("value"))
        return {
            "speed_kmh": speed,
            "brake": brake,
            "stopped": abs(speed) <= self.state.config.stopped_speed_threshold_kmh and brake,
        }

    async def _raise_failure_alarm(self, code: str, message: str) -> dict:
        alarm_id = f"control_{code.lower()}"
        alarm = {
            "id": alarm_id,
            "level": 3,
            "label": code,
            "description": message,
            "status": "active",
        }
        if self.state.alarms and hasattr(self.state.alarms, "raise_system_alarm"):
            alarm = self.state.alarms.raise_system_alarm(alarm_id, 3, code, message)
        if self.state.database is not None:
            try:
                self.state.database.execute(
                    "INSERT INTO alarms(timestamp_utc, channel, can_id_hex, signal_name, level, level_label, status, description) VALUES (?,?,?,?,?,?,?,?)",
                    (utc_now(), self.state.config.control_channel, "0x121", code, 3, "Critical", "active", message),
                )
            except Exception:
                pass
        if getattr(self.state, "ws", None):
            await self.state.ws.broadcast("alarms.current", self.state.alarms.current() if self.state.alarms else [alarm])
        return alarm
