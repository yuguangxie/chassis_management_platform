import asyncio
from types import SimpleNamespace

import pytest

from app.control.safety_interlock import InterlockBlocked, SafetyInterlockService
from app.eol.engine import EolEngine
from app.eol.models import AssertionOutcome, CreateSessionRequest
from app.services.app_state import AppState


class AllowSafety:
    def require_allowed(self, *args, **kwargs):
        return {"allowed": True, "reasons": []}

    def evaluate(self, *args, **kwargs):
        return {"allowed": True, "reasons": []}


class NullWs:
    async def broadcast(self, *_args, **_kwargs):
        return None


class NullTxScheduler:
    async def start(self, *_args, **_kwargs):
        return {"ok": True}

    async def stop(self):
        return {"ok": True}


class NullControlIntents:
    def create_authorized(self, *_args, **_kwargs):
        return "INT-TEST"

    def mark(self, *_args, **_kwargs):
        return None

    async def compensate_after_send_failure(self, *_args, **_kwargs):
        return None


class PassEvaluator:
    async def evaluate(self, spec, _context):
        return AssertionOutcome(
            assertion_id=spec.id,
            description=spec.description or spec.id,
            signal_name=spec.signal or ",".join(spec.signals),
            operator=spec.operator,
            result="PASS",
            quality="good",
        )


class TestSignals:
    current = {"BMS_SOC": {"value": 86}}

    def require_sample(self, key, **_kwargs):
        return {
            "key": key,
            "value": 0,
            "quality": "good",
            "unit": "",
            "can_id": "0x51",
            "channel": "CAN1",
            "updated_at": "test",
        }

    def window(self, key, **_kwargs):
        return [self.require_sample(key)]


class NullReports:
    def generate(self, session, _steps, **_kwargs):
        return {"id": "test-report", "result": session.get("overall_result"), "files": {}}


def make_engine(step_delay: float = 0.05) -> EolEngine:
    state = SimpleNamespace(
        safety=AllowSafety(),
        ws=NullWs(),
        alarms=SimpleNamespace(current=lambda: [], max_level=lambda: 0),
        signals=TestSignals(),
        reports=NullReports(),
        tx_scheduler=NullTxScheduler(),
        control_intents=NullControlIntents(),
        safe_stop=None,
        telemetry=None,
        database=None,
        db_writable=True,
        dbc=None,
        can=None,
        config=SimpleNamespace(
            profile="test",
            software_version="test",
            vehicle_series="JD",
            channel_online_timeout_seconds=2.0,
        ),
    )
    return EolEngine(state, step_delay_seconds=step_delay, evaluator=PassEvaluator())


def create_session(engine: EolEngine, suffix: str = "01") -> dict:
    request = CreateSessionRequest(
        chassis_no=f"TEST-{suffix}",
        vin=f"L{int(suffix):016d}",
        serial_no=f"TEST-SN-{suffix}",
        vehicle_series="JD",
        work_order_id=f"TEST-WO-{suffix}",
        plan_id="default_chassis_eol_v1",
        mock_session=True,
    )
    return engine.create_session(
        request,
        operator="test-operator",
        operator_role="operator",
        auth_session_id="test-auth-session",
        station_id="TEST-STATION",
    )


async def wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("condition was not reached")
        await asyncio.sleep(0.005)


@pytest.mark.asyncio
async def test_pause_does_not_advance_and_resume_continues():
    engine = make_engine()
    session = create_session(engine)
    await engine.start(session["id"])
    await wait_for(lambda: len(session["steps"]) == 1)
    await engine.pause(session["id"])
    snapshot = (len(session["steps"]), session["steps"][0]["result"])
    await asyncio.sleep(0.12)
    assert session["status"] == "PAUSED"
    assert (len(session["steps"]), session["steps"][0]["result"]) == snapshot
    await engine.resume(session["id"])
    await wait_for(lambda: session["status"] == "PASSED")
    assert len(session["steps"]) == 12


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "terminal"),
    [("abort", "ABORTED"), ("emergency_stop", "EMERGENCY_STOPPED")],
)
async def test_terminal_request_stops_next_step_and_cannot_be_overwritten(method: str, terminal: str):
    engine = make_engine(step_delay=0.08)
    session = create_session(engine)
    await engine.start(session["id"])
    await wait_for(lambda: len(session["steps"]) == 1)
    before = len(session["steps"])
    await getattr(engine, method)(session["id"], "phase-01 test")
    await asyncio.sleep(0.2)
    assert session["status"] == terminal
    assert session["overall_result"] == "ABORTED"
    assert len(session["steps"]) == before


@pytest.mark.asyncio
async def test_eol_is_rejected_when_can_channels_are_offline():
    state = AppState()
    state.can = SimpleNamespace(
        status=lambda: [
            {"channel": "CAN1", "online": False, "queue_healthy": True},
            {"channel": "CAN2", "online": False, "queue_healthy": True},
        ]
    )
    state.dbc = SimpleNamespace(status=lambda: {"loaded": True})
    state.alarms = SimpleNamespace(max_level=lambda: 0, current=lambda: [])
    state.database = SimpleNamespace(
        execute=lambda *_args, **_kwargs: None,
        query_one=lambda *_args, **_kwargs: None,
    )
    state.safety = SafetyInterlockService(state)
    state.ws = NullWs()
    engine = EolEngine(state)
    session = create_session(engine)
    with pytest.raises(InterlockBlocked):
        await engine.start(session["id"])
    assert session["status"] == "IDLE"
