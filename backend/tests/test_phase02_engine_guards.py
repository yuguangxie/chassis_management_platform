from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.eol.engine import EolEngine, SessionConflict
from app.eol.models import (
    AssertionOutcome,
    CreateSessionRequest,
    ManualAction,
    TestPlanDocument as PlanDocument,
)
from app.eol.plan_loader import load_test_plan


class AllowSafety:
    def require_allowed(self, *_args, **_kwargs):
        return {"allowed": True, "reasons": []}


class NullWs:
    async def broadcast(self, *_args, **_kwargs):
        return None


class RecordingWs:
    def __init__(self):
        self.events = []

    async def broadcast(self, topic, payload):
        self.events.append((topic, payload))


class NullTx:
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


class GoodSignals:
    current = {}

    def require_sample(self, key, **_kwargs):
        return {
            "key": key,
            "value": 0,
            "unit": "",
            "quality": "good",
            "can_id": "0x51",
            "channel": "CAN1",
            "updated_at": "test",
        }

    def window(self, key, **_kwargs):
        return [self.require_sample(key)]


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


class NullReports:
    def generate(self, session, _steps, **_kwargs):
        return {"id": "report", "result": session.get("overall_result"), "files": {}}


def state_fixture():
    return SimpleNamespace(
        safety=AllowSafety(),
        ws=NullWs(),
        alarms=SimpleNamespace(current=lambda: [], max_level=lambda: 0),
        signals=GoodSignals(),
        reports=NullReports(),
        tx_scheduler=NullTx(),
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


def create_session(engine: EolEngine, suffix: int = 1) -> dict:
    request = CreateSessionRequest(
        chassis_no=f"GUARD-{suffix:03d}",
        vin=f"L{suffix:016d}",
        serial_no=f"GUARD-SN-{suffix:03d}",
        vehicle_series="JD",
        work_order_id=f"GUARD-WO-{suffix:03d}",
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


async def wait_for(predicate, timeout: float = 3) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("condition was not reached")
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_same_station_rejects_second_active_session():
    engine = EolEngine(
        state_fixture(), evaluator=PassEvaluator(), step_delay_seconds=0.05
    )
    first = create_session(engine, 1)
    second = create_session(engine, 2)
    await engine.start(first["id"])
    with pytest.raises(SessionConflict):
        await engine.start(second["id"])
    await engine.abort(first["id"], "test cleanup")


def manual_plan(timeout_ms: int = 1000) -> PlanDocument:
    payload = load_test_plan().model_dump(mode="json")
    payload["steps"][0]["manual_action"] = ManualAction(
        prompt="踩下制动踏板", timeout_ms=timeout_ms, require_note=True
    ).model_dump(mode="json")
    payload["steps"][0]["timeout_ms"] = timeout_ms + 1000
    return PlanDocument.model_validate(payload)


@pytest.mark.asyncio
async def test_manual_step_waits_for_operator_confirmation_and_records_log():
    engine = EolEngine(
        state_fixture(),
        plan=manual_plan(),
        evaluator=PassEvaluator(),
        step_delay_seconds=0.01,
    )
    session = create_session(engine)
    await engine.start(session["id"])
    await wait_for(lambda: session["status"] == "WAITING_OPERATOR")
    step_count = len(session["steps"])
    await asyncio.sleep(0.1)
    assert len(session["steps"]) == step_count
    await engine.confirm_manual(
        session["id"], approved=True, note="台架动作已确认", operator="operator01"
    )
    await wait_for(lambda: any(log["action"] == "人工步骤确认" for log in session["logs"]))
    await engine.abort(session["id"], "test cleanup")


@pytest.mark.asyncio
async def test_manual_step_timeout_fails_instead_of_passing():
    engine = EolEngine(
        state_fixture(),
        plan=manual_plan(timeout_ms=1000),
        evaluator=PassEvaluator(),
        step_delay_seconds=0.01,
    )
    session = create_session(engine)
    await engine.start(session["id"])
    await wait_for(lambda: session["status"] == "FAILED", timeout=3)
    assert session["overall_result"] == "FAIL"
    assert session["steps"][0]["result"] == "FAIL"
    assert "timed out" in session["failure_reason"]


@pytest.mark.asyncio
async def test_websocket_progress_uses_actual_session_snapshot():
    state = state_fixture()
    state.ws = RecordingWs()
    engine = EolEngine(
        state,
        evaluator=PassEvaluator(),
        step_delay_seconds=0.001,
    )
    session = create_session(engine)

    await engine.start(session["id"])
    await wait_for(lambda: session["status"] == "PASSED")

    progress = [
        payload
        for topic, payload in state.ws.events
        if topic == "test.session_progress"
    ]
    assert progress
    assert all(payload["id"] == session["id"] for payload in progress)
    assert progress[-1]["status"] == "PASSED"
    assert len(progress[-1]["steps"]) == 12
