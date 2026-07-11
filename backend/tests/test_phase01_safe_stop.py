import time
from types import SimpleNamespace

import pytest

from app.control.safe_stop import SafeStopService
from app.control.safety_interlock import SafetyInterlockService
from app.security.auth import Principal, Role
from app.services.signal_store import SignalStore


class FakeScheduler:
    def __init__(self, state, feedback: str) -> None:
        self.state = state
        self.feedback = feedback
        self.attempts = 0
        self.stopped = False

    async def stop(self):
        self.stopped = True
        return {"periodic": False}

    async def send_priority(self, command, *, operation):
        self.attempts += 1
        now = time.monotonic()
        if self.feedback == "success":
            speed, brake = 0.0, True
        elif self.feedback == "timeout":
            speed, brake = 1.2, True
        else:
            return {"sent": True}
        self.state.signals.current["CCU_Vehicle_Speed"] = {
            "value": speed,
            "quality": "good",
            "received_at_monotonic": now,
        }
        self.state.signals.current["Brake_Status"] = {
            "value": brake,
            "quality": "good",
            "received_at_monotonic": now,
        }
        return {"sent": True, "operation": operation, "data": command.model_dump()}


def make_state(feedback: str, online: bool = True):
    config = SimpleNamespace(
        control_channel="CAN2",
        channels=[SimpleNamespace(channel="CAN2", control_enabled=True)],
        safe_stop_timeout_ms=100,
        safe_stop_retry_ms=10,
        stopped_speed_threshold_kmh=0.1,
        channel_online_timeout_seconds=2.0,
        require_dbc_for_control=False,
        manual_speed_limit_kmh=3.0,
        steering_limit_absolute=120,
    )
    state = SimpleNamespace(
        config=config,
        can=SimpleNamespace(status=lambda: [{"channel": "CAN2", "online": online, "queue_healthy": True, "queue_depth": 0, "queue_capacity": 16}]),
        signals=SignalStore(),
        alarms=SimpleNamespace(max_level=lambda: 0),
        dbc=SimpleNamespace(status=lambda: {"loaded": True}),
        database=None,
        db_writable=True,
        emergency_stop=False,
        safe_stop_active=False,
        safe_stop_latched=False,
    )
    state.safety = SafetyInterlockService(state)
    state.tx_scheduler = FakeScheduler(state, feedback)
    return state


@pytest.mark.asyncio
async def test_safe_stop_success_confirms_feedback_and_latches():
    state = make_state("success")
    result = await SafeStopService(state).execute(
        emergency=False,
        principal=Principal("operator", Role.OPERATOR),
        reason="test",
        timeout_ms=100,
    )
    assert result["ok"] is True
    assert result["code"] == "STOP_CONFIRMED"
    assert result["feedback"] == {"speed_kmh": 0.0, "brake": True, "stopped": True}
    assert state.safe_stop_latched is True


@pytest.mark.asyncio
async def test_safe_stop_timeout_keeps_latch():
    state = make_state("timeout")
    result = await SafeStopService(state).execute(
        emergency=False,
        principal=Principal("operator", Role.OPERATOR),
        reason="test",
        timeout_ms=60,
    )
    assert result["ok"] is False
    assert result["code"] == "SAFE_STOP_TIMEOUT"
    assert result["alarm"]["level"] == 3
    assert state.safe_stop_latched is True
    assert state.tx_scheduler.attempts >= 2


@pytest.mark.asyncio
async def test_emergency_missing_feedback_stays_emergency_latched():
    state = make_state("missing")
    result = await SafeStopService(state).execute(
        emergency=True,
        principal=Principal("operator", Role.OPERATOR),
        reason="test",
        timeout_ms=50,
    )
    assert result["ok"] is False
    assert result["code"] == "FEEDBACK_MISSING"
    assert result["alarm"]["level"] == 3
    assert state.emergency_stop is True
    assert state.safe_stop_latched is True


@pytest.mark.asyncio
async def test_safe_stop_offline_is_blocked_without_transmission():
    state = make_state("success", online=False)
    result = await SafeStopService(state).execute(
        emergency=True,
        principal=Principal("operator", Role.OPERATOR),
        reason="offline",
    )
    assert result["code"] == "INTERLOCK_BLOCKED"
    assert state.tx_scheduler.attempts == 0
    assert state.emergency_stop is True
