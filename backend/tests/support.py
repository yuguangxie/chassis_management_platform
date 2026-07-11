"""Explicit runtime fixtures for tests that exercise dashboard read models.

The application must never depend on a developer's persistent ``data/`` folder.
These helpers seed an isolated database after the FastAPI lifespan has started.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from app.eol.models import AssertionOutcome


def _utc(hour: int, minute: int = 0) -> str:
    return datetime(2026, 4, 1, hour, minute, tzinfo=timezone.utc).isoformat()


def seed_dashboard_session(state: Any, session_id: str = "EOL-QUALITY-DASHBOARD") -> dict[str, Any]:
    """Create one complete persisted PASS session and its real report files."""
    assert state.database and state.repositories and state.eol_uow and state.reports
    existing = state.repositories.session(session_id)
    if existing:
        reports = state.repositories.reports_for_session(session_id)
        return {"session": existing, "database_ids": [item["id"] for item in reports]}

    session = {
        "id": session_id,
        "chassis_no": "YL-QUALITY-001",
        "vin": "LQUALITY000000001",
        "serial_no": "SN-QUALITY-001",
        "operator": "quality-op",
        "station_id": "EOL-STATION-01",
        "test_plan_id": "standard-eol",
        "plan_version": "1.0.2",
        "status": "PASSED",
        "overall_result": "PASS",
        "started_at": _utc(10),
        "ended_at": _utc(10, 2),
        "remarks": "isolated quality fixture",
        "dbc_hash": "quality-dbc-hash",
        "config_hash": "quality-config-hash",
        "software_version": "v1.0.2",
        "failure_reason": "",
    }
    state.database.execute(
        "INSERT INTO test_sessions(id,chassis_no,vin,serial_no,operator,station_id,test_plan_id,plan_version,status,overall_result,started_at,ended_at,remarks,dbc_hash,config_hash,software_version,failure_reason) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        tuple(session[key] for key in (
            "id", "chassis_no", "vin", "serial_no", "operator", "station_id",
            "test_plan_id", "plan_version", "status", "overall_result", "started_at",
            "ended_at", "remarks", "dbc_hash", "config_hash", "software_version",
            "failure_reason",
        )),
    )
    outcome = AssertionOutcome(
        assertion_id="BMS-VOLTAGE",
        description="BMS voltage is in range",
        signal_name="BMS_Voltage",
        operator="between",
        threshold=[280, 360],
        measured_value=329.6,
        unit="V",
        result="PASS",
        severity="failure",
        quality="good",
        source_can_id="0x100",
        source_channel="CAN1",
        source_timestamp=_utc(10, 1),
    )
    state.database.execute(
        "INSERT INTO test_steps(session_id,step_id,step_order,name,status,result,started_at,ended_at,duration_ms,command_summary,measurement_summary) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (session_id, "BMS_CHECK", 1, "BMS Check", "PASSED", "PASS", _utc(10), _utc(10, 1), 1000, "0x7DF 22 01 00", json.dumps({"BMS_Voltage": 329.6})),
    )
    state.database.execute(
        "INSERT INTO test_assertions(session_id,step_id,assertion_id,description,signal_name,operator,threshold_json,measured_value,unit,result,severity,quality,source_can_id,source_channel,source_timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (session_id, "BMS_CHECK", outcome.assertion_id, outcome.description, outcome.signal_name, outcome.operator, json.dumps(outcome.threshold), json.dumps(outcome.measured_value), outcome.unit, outcome.result, outcome.severity, outcome.quality, outcome.source_can_id, outcome.source_channel, outcome.source_timestamp),
    )
    for minute, value in ((0, 329.4), (1, 329.6)):
        state.database.execute(
            "INSERT INTO decoded_signals(session_id,timestamp_utc,channel,can_id_hex,message_name,signal_name,raw_value,physical_value,unit,quality,threshold_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (session_id, _utc(10, minute), "CAN1", "0x100", "BMS_Status", "BMS_Voltage", str(int(value * 10)), str(value), "V", "good", "normal"),
        )
    state.repositories.action("quality_fixture", session_id, {}, operator="quality-op", role="operator", session_id=session_id)
    generated = state.reports.generate(session, [{
        "id": "BMS_CHECK", "order": 1, "name": "BMS Check", "status": "PASSED", "result": "PASS", "duration_ms": 1000,
        "assertions": [outcome.model_dump()],
    }], metadata={"software_version": "v1.0.2", "dbc_hash": session["dbc_hash"], "config_hash": session["config_hash"], "test_plan_version": session["plan_version"]})
    generated["database_ids"] = state.eol_uow.persist_report(session, generated)
    return generated
