from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.core.time import utc_now
from app.eol.models import AssertionOutcome
from app.eol.plan_loader import load_test_plan, load_thresholds, resolve_threshold
from app.storage.database import Database
from app.storage.signal_log_writer import SignalLogWriter
from app.storage.uow import EolUnitOfWork, PersistenceFailure, StationBusyPersistence


def session_payload(session_id: str = "EOL-PHASE02-TEST") -> dict:
    return {
        "id": session_id,
        "chassis_no": "PH2-001",
        "vin": "PHASE02VIN0000001",
        "serial_no": "PH2-SN",
        "operator": "test-operator",
        "station_id": "EOL-STATION-01",
        "operator_role": "operator",
        "auth_session_id": "test-auth-session",
        "vehicle_series": "JD",
        "work_order_id": "PH2-WO",
        "plan_id": "default_chassis_eol_v1",
        "duplicate_policy": "reject",
        "status": "IDLE",
        "overall_result": None,
        "remarks": "",
        "dbc_hash": "dbc-hash",
        "config_hash": "config-hash",
        "software_version": "test",
        "created_at": utc_now(),
    }


def test_production_plan_is_pydantic_validated_and_yaml_driven():
    plan = load_test_plan()
    thresholds = load_thresholds()
    assert plan.plan.id == "default_chassis_eol_v1"
    assert plan.plan.extension_messages_enabled is False
    assert [step.order for step in plan.steps] == list(range(1, 13))
    assert all(step.preconditions is not None for step in plan.steps)
    assert all(step.control_actions is not None for step in plan.steps)
    assert all(step.assertions for step in plan.steps)
    assert all(step.timeout_ms > 0 for step in plan.steps)
    assert all(step.cleanup_actions is not None for step in plan.steps)
    assert resolve_threshold(thresholds, "bms.soc_percent_min") == 30
    assert all(
        action.type == "control_121"
        for step in plan.steps
        for action in step.control_actions
    )


def test_step_and_assertions_rollback_as_one_unit(tmp_path: Path):
    database = Database(tmp_path / "rollback.db")
    uow = EolUnitOfWork(database)
    plan = load_test_plan()
    session = session_payload()
    uow.create_session(session, plan)
    step = {
        "id": "bms_check",
        "order": 3,
        "name": "BMS 检测",
        "status": "DONE",
        "result": "PASS",
        "started_at": utc_now(),
        "ended_at": utc_now(),
        "duration_ms": 10,
        "failure_reason": "",
        "commands": [],
        "measurements": [],
    }
    step["db_id"] = uow.start_step(session["id"], step)
    outcomes = [
        AssertionOutcome(
            assertion_id="a1",
            description="first",
            operator="==",
            result="PASS",
        ),
        AssertionOutcome(
            assertion_id="a2",
            description="second",
            operator="==",
            result="PASS",
        ),
    ]

    def fail_second(outcome: dict) -> None:
        if outcome["assertion_id"] == "a2":
            raise RuntimeError("injected assertion persistence failure")

    uow.before_assertion_insert = fail_second
    with pytest.raises(PersistenceFailure):
        uow.complete_step(session["id"], step, outcomes)
    assert database.query_one(
        "SELECT COUNT(*) AS count FROM test_assertions WHERE session_id=?",
        (session["id"],),
    )["count"] == 0
    persisted_step = database.query_one(
        "SELECT status,result FROM test_steps WHERE session_id=?", (session["id"],)
    )
    assert persisted_step == {"status": "RUNNING", "result": None}
    database.close()


def test_restart_recovery_safely_terminates_incomplete_session(tmp_path: Path):
    database = Database(tmp_path / "recovery.db")
    uow = EolUnitOfWork(database)
    plan = load_test_plan()
    session = session_payload("EOL-RECOVERY")
    uow.create_session(session, plan)
    recovered = uow.recover_incomplete_sessions()
    assert recovered == ["EOL-RECOVERY"]
    row = database.query_one(
        "SELECT status,overall_result,failure_reason FROM test_sessions WHERE id=?",
        (session["id"],),
    )
    assert row == {
        "status": "ABORTED",
        "overall_result": "ABORTED",
        "failure_reason": "service restart recovery",
    }
    database.close()


def test_station_claim_is_transactionally_exclusive(tmp_path: Path):
    database = Database(tmp_path / "station.db")
    uow = EolUnitOfWork(database)
    plan = load_test_plan()
    first = session_payload("EOL-STATION-FIRST")
    second = session_payload("EOL-STATION-SECOND")
    uow.create_session(first, plan)
    uow.create_session(second, plan)
    first["started_at"] = utc_now()
    second["started_at"] = utc_now()
    uow.claim_station_and_start(first)
    with pytest.raises(StationBusyPersistence):
        uow.claim_station_and_start(second)
    assert database.query_one(
        "SELECT status FROM test_sessions WHERE id=?", (second["id"],)
    )["status"] == "IDLE"
    database.close()


def test_signal_log_writer_batches_csv_with_session_id(tmp_path: Path):
    writer = SignalLogWriter(tmp_path, format_name="csv", batch_size=2)
    row = {
        "session_id": "EOL-LOG",
        "timestamp_utc": utc_now(),
        "channel": "CAN2",
        "can_id_hex": "0x100",
        "message_name": "BMS_Status",
        "signal_name": "BMS_SOC",
        "raw_value": 86,
        "physical_value": 86,
        "unit": "%",
        "enum_label": "",
        "quality": "good",
    }
    writer.write_rows("EOL-LOG", [row, row])
    path = tmp_path / "decoded_signals_EOL-LOG.csv"
    assert path.exists()
    with path.open(encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))
    assert len(rows) == 2
    assert {item["session_id"] for item in rows} == {"EOL-LOG"}
    with pytest.raises(ValueError):
        writer.write_rows("", [row])
