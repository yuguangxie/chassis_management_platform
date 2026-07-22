from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.can_gateway.models import CanFrame
from app.can_gateway.udp_gateway import UdpCanGateway
from app.control.control_121 import Control121Command
from app.control.override_service import (
    OverrideApprovalRequest,
    OverrideConflict,
    OverrideCreateRequest,
    OverrideOperation,
    OverrideRevokeRequest,
    OverrideService,
)
from app.control.safety_interlock import (
    InterlockBlocked,
    SafetyEvaluationContext,
    SafetyInterlockService,
)
from app.core.config import ChannelConfig, RuntimeConfig, load_config
from app.main import app
from app.security.auth import Principal, Role
from app.services.app_state import AppState, state as global_state
from app.storage.database import Database


APPROVED_HASH = "387ae48bd84852c8a6401653f96d1f7fca2a604c90fad018db800bf548ab468c"


class FakeAlarms:
    def __init__(self, items: list[dict] | None = None) -> None:
        self.items = items or []

    def current(self) -> list[dict]:
        return self.items

    def max_level(self) -> int:
        return max((int(item.get("level", 0)) for item in self.items), default=0)


def _channel_status(*, queue_healthy: bool = True) -> list[dict]:
    return [
        {
            "channel": channel,
            "online": True,
            "receive_age_ms": 10,
            "queue_healthy": queue_healthy,
            "queue_depth": 0 if queue_healthy else 16,
            "queue_capacity": 16,
        }
        for channel in ("CAN1", "CAN2")
    ]


def _add_signal(state: AppState, key: str, value, can_id: int, channel: str = "CAN1", quality: str = "good") -> None:
    state.signals.update(
        key,
        value,
        CanFrame(channel=channel, can_id=can_id, data=[0] * 8),
        quality=quality,
    )


def ready_state(*, production: bool = False, database: Database | None = None) -> AppState:
    state = AppState()
    config = load_config(profile="test")
    if production:
        config = RuntimeConfig.model_validate(
            {
                **config.model_dump(),
                "profile": "production",
                "require_dbc_for_control": True,
                "approved_dbc_sha256": APPROVED_HASH,
                "vehicle_series": "JD",
                "config_trust": "signed-package",
                "safe_stop_policy_hardware_validated": True,
            }
        )
    state.config = config
    state.can = SimpleNamespace(status=lambda: _channel_status())
    state.dbc = SimpleNamespace(
        status=lambda: {
            "loaded": True,
            "raw_only": False,
            "hash": APPROVED_HASH,
            "vehicle_series": "JD",
        }
    )
    state.alarms = FakeAlarms()
    state.database = database
    state.db_writable = True
    for key, value, can_id in (
        ("CCU_Vehicle_Speed", 0.0, 0x51),
        ("Heartbeat_0x704", 1, 0x704),
        ("Heartbeat_0x703", 1, 0x703),
        ("CCU_Shift_Level_Status", 0, 0x51),
        ("CCU_Drive_Mode", 2, 0x51),
        ("SAS_Front_Angle", 0.0, 0xE1),
        ("SAS_Rear_Angle", 0.0, 0xE1),
        ("Steering_Disconnect_Warning", 0, 0x77),
        ("Steering_Lock_Warning", 0, 0x77),
        ("Steering_Uncontrollable_Warning", 0, 0x77),
        ("Steering_Error_Warning", 0, 0x77),
        ("Brake_Status", False, 0x51),
        ("Brake_Error_Warning", 0, 0x77),
    ):
        _add_signal(state, key, value, can_id)
    state.safety = SafetyInterlockService(state)
    return state


def _drop_signal(state: AppState, key: str, channel: str = "CAN1") -> None:
    state.signals.current.pop(key, None)
    state.signals.current_by_source.pop((key, channel), None)


def _rule(evaluation: dict, key: str) -> dict:
    return next(item for item in evaluation["rules"] if item["rule"] == key)


def test_nonzero_steering_rejected_when_speed_is_fresh_but_steering_feedback_missing():
    state = ready_state()
    _drop_signal(state, "SAS_Front_Angle")
    result = state.safety.evaluate(Control121Command(front_steering_cmd=10))
    rule = _rule(result, "feedback_steering_front_steering")
    assert result["allowed"] is False
    assert rule["status"] == "FAIL"
    assert rule["current"]["checks"] == {
        "present": False,
        "fresh": False,
        "quality_valid": False,
        "source_valid": False,
        "value_valid": False,
    }
    assert {"rule", "label", "current", "threshold", "blocking"} <= rule.keys()


def test_brake_command_rejected_when_steering_is_fresh_but_brake_feedback_missing():
    state = ready_state()
    _drop_signal(state, "Brake_Status")
    result = state.safety.evaluate(
        Control121Command(front_steering_cmd=5, brake_enable=True)
    )
    assert result["allowed"] is False
    assert _rule(result, "feedback_brake_brake_status")["status"] == "FAIL"


@pytest.mark.parametrize("heartbeat", ["Heartbeat_0x703", "Heartbeat_0x704"])
def test_each_stale_heartbeat_blocks_motion(heartbeat: str):
    state = ready_state()
    item = state.signals.current_by_source[(heartbeat, "CAN1")]
    item["received_at_monotonic"] -= 2
    result = state.safety.evaluate(Control121Command(shift="D", target_speed_kmh=1.0))
    matching = [reason for reason in result["reasons"] if heartbeat.lower().replace("_", "") in str(reason).lower().replace("_", "")]
    assert result["allowed"] is False
    assert matching or any("heartbeat" in reason["rule"] for reason in result["reasons"])


def test_invalid_quality_wrong_channel_and_out_of_range_each_block():
    invalid = ready_state()
    invalid.signals.current_by_source[("CCU_Vehicle_Speed", "CAN1")]["quality"] = "invalid"
    assert _rule(invalid.safety.evaluate(Control121Command()), "feedback_base_vehicle_speed")["current"]["checks"]["quality_valid"] is False

    wrong_source = ready_state()
    _drop_signal(wrong_source, "CCU_Vehicle_Speed")
    _add_signal(wrong_source, "CCU_Vehicle_Speed", 0.0, 0x51, channel="CAN2")
    source_rule = _rule(wrong_source.safety.evaluate(Control121Command()), "feedback_base_vehicle_speed")
    assert source_rule["current"]["checks"]["source_valid"] is False

    out_of_range = ready_state()
    out_of_range.signals.current_by_source[("CCU_Vehicle_Speed", "CAN1")]["value"] = 99.0
    range_rule = _rule(out_of_range.safety.evaluate(Control121Command()), "feedback_base_vehicle_speed")
    assert range_rule["current"]["checks"]["value_valid"] is False


@pytest.mark.parametrize(
    ("dbc_status", "expected_check"),
    [
        ({"loaded": False, "hash": APPROVED_HASH, "vehicle_series": "JD"}, "loaded"),
        ({"loaded": True, "hash": "0" * 64, "vehicle_series": "JD"}, "hash_match"),
        ({"loaded": True, "hash": APPROVED_HASH, "vehicle_series": "TD"}, "vehicle_match"),
    ],
)
def test_production_dbc_missing_hash_or_vehicle_mismatch_is_fail_closed(dbc_status: dict, expected_check: str):
    state = ready_state(production=True)
    state.dbc = SimpleNamespace(status=lambda: dbc_status)
    result = state.safety.evaluate(Control121Command())
    dbc_rule = _rule(result, "dbc_ready")
    assert result["allowed"] is False
    assert dbc_rule["status"] == "FAIL"
    if expected_check != "loaded":
        assert dbc_rule["current"][expected_check] is False


def test_nonproduction_raw_only_is_explicitly_degraded_not_disguised_as_hardware():
    state = ready_state()
    state.dbc = SimpleNamespace(status=lambda: {"loaded": False, "raw_only": True, "hash": None, "vehicle_series": None})
    result = state.safety.evaluate(Control121Command())
    assert result["degraded_mode"] is True
    assert result["profile"] == "test"
    assert _rule(result, "dbc_ready")["status"] == "PASS"


def test_legal_mock_0x121_with_required_feedback_is_allowed():
    state = ready_state()
    result = state.safety.evaluate(
        Control121Command(shift="D", target_speed_kmh=1.0, drive_mode="Remote")
    )
    assert result["allowed"] is True
    assert result["feedback_groups"] == ["base", "drive"]


def test_database_emergency_and_queue_failures_remain_blocking():
    state = ready_state()
    state.db_writable = False
    assert _rule(state.safety.evaluate(Control121Command()), "database_writable")["status"] == "FAIL"
    state.db_writable = True
    state.emergency_stop = True
    assert _rule(state.safety.evaluate(Control121Command()), "emergency_released")["status"] == "FAIL"
    state.emergency_stop = False
    state.can = SimpleNamespace(status=lambda: _channel_status(queue_healthy=False))
    assert _rule(state.safety.evaluate(Control121Command()), "can2_queue_healthy")["status"] == "FAIL"
    state.can = SimpleNamespace(status=lambda: _channel_status())
    state.alarms = FakeAlarms([{"id": "critical-unapproved", "level": 3}])
    assert _rule(state.safety.evaluate(Control121Command()), "no_severe_alarm")["status"] == "FAIL"
    assert state.safety.evaluate(Control121Command(), operation="eol")["allowed"] is False


def test_interlock_rejection_is_persisted_to_operator_audit(tmp_path):
    database = Database(tmp_path / "audit.sqlite3")
    state = ready_state(database=database)
    state.db_writable = False
    with pytest.raises(InterlockBlocked):
        state.safety.require_allowed(Control121Command())
    row = database.query_one(
        "SELECT action_type,result,request_json FROM operator_actions ORDER BY id DESC LIMIT 1"
    )
    assert row and row["action_type"] == "safety_interlock_reject"
    assert row["result"] == "BLOCKED"
    assert "database_writable" in row["request_json"]
    database.close()


def test_udp_rejects_unapproved_source_before_online_or_signal_queue_update():
    events: list[dict] = []

    async def consume(_frame):
        raise AssertionError("unauthorized frame reached application")

    config = ChannelConfig(
        channel="CAN1",
        local_ip="127.0.0.1",
        local_receive_port=18234,
        device_ip="127.0.0.1",
        device_port=12341,
        receive_queue_size=16,
    )
    gateway = UdpCanGateway(config, consume, on_security_event=events.append)
    packet = gateway.codec.encode_frame(CanFrame(channel="CAN1", can_id=0x51, data=[0] * 8))
    gateway.stats.transport_connected = True
    gateway.on_datagram(packet, ("127.0.0.1", 54321))
    snapshot = gateway.stats.snapshot()
    assert gateway.queue.qsize() == 0
    assert snapshot["online"] is False
    assert snapshot["rx_count"] == 0
    assert snapshot["last_frame_at"] == 0
    assert snapshot["last_frame_hex"] == ""
    assert gateway.stats.last_receive_monotonic == 0
    assert snapshot["unauthorized_datagrams"] == 1
    assert events and events[0]["source"] == "127.0.0.1:54321"
    gateway.on_datagram(packet, ("127.0.0.1", 12341))
    assert gateway.queue.qsize() == 1
    assert gateway.stats.rx_count == 1


def _create_approved_override(database: Database) -> tuple[OverrideService, str]:
    service = OverrideService(database)
    request = OverrideCreateRequest(
        reason="controlled diagnosis request",
        session_id="EOL-OVERRIDE-1",
        operation=OverrideOperation.MANUAL,
        vehicle_id="YL-JD-001",
        authorized_user="operator-a",
        duration_seconds=60,
    )
    record = service.create("alarm-critical", request, Principal("engineer-a", Role.ENGINEER))
    approved = service.approve(
        record.id,
        OverrideApprovalRequest(confirmation="APPROVE", reason="independent review approved"),
        Principal("admin-b", Role.ADMIN),
    )
    return service, approved.id


def test_override_requires_separation_exact_scope_and_cannot_bypass_core_rules(tmp_path):
    database = Database(tmp_path / "override.sqlite3")
    service = OverrideService(database)
    request = OverrideCreateRequest(
        reason="controlled diagnosis request",
        session_id="EOL-OVERRIDE-1",
        operation=OverrideOperation.MANUAL,
        vehicle_id="YL-JD-001",
        authorized_user="operator-a",
        duration_seconds=60,
    )
    pending = service.create("alarm-critical", request, Principal("same-user", Role.ENGINEER))
    with pytest.raises(OverrideConflict) as same_user:
        service.approve(
            pending.id,
            OverrideApprovalRequest(confirmation="APPROVE", reason="same user cannot approve"),
            Principal("same-user", Role.ADMIN),
        )
    assert same_user.value.code == "SEPARATION_OF_DUTIES"

    service, override_id = _create_approved_override(database)
    state = ready_state(database=database)
    state.overrides = service
    state.alarms = FakeAlarms([{"id": "alarm-critical", "level": 3}])
    context = SafetyEvaluationContext(
        actor="operator-a",
        session_id="EOL-OVERRIDE-1",
        vehicle_id="YL-JD-001",
        override_id=override_id,
    )
    result = state.safety.evaluate(Control121Command(), context=context)
    assert result["allowed"] is True
    assert _rule(result, "no_severe_alarm")["current"]["override"]["allowed"] is True

    wrong_actor = context.model_copy(update={"actor": "operator-b"})
    assert state.safety.evaluate(Control121Command(), context=wrong_actor)["allowed"] is False

    state.db_writable = False
    assert state.safety.evaluate(Control121Command(), context=context)["allowed"] is False
    state.db_writable = True
    state.emergency_stop = True
    assert state.safety.evaluate(Control121Command(), context=context)["allowed"] is False
    state.emergency_stop = False
    _drop_signal(state, "CCU_Vehicle_Speed")
    assert state.safety.evaluate(Control121Command(), context=context)["allowed"] is False

    # An approved alarm override is deliberately powerless against DBC identity.
    state = ready_state(production=True, database=database)
    state.overrides = service
    state.alarms = FakeAlarms([{"id": "alarm-critical", "level": 3}])
    state.dbc = SimpleNamespace(
        status=lambda: {
            "loaded": True,
            "raw_only": False,
            "hash": "0" * 64,
            "vehicle_series": "JD",
        }
    )
    assert state.safety.evaluate(Control121Command(), context=context)["allowed"] is False
    assert _rule(
        state.safety.evaluate(Control121Command(), context=context), "dbc_ready"
    )["status"] == "FAIL"
    database.close()


def test_override_expiry_and_revoke_default_to_deny(tmp_path):
    database = Database(tmp_path / "override-expire.sqlite3")
    service, override_id = _create_approved_override(database)
    database.execute(
        "UPDATE safety_overrides SET expires_at=? WHERE id=?",
        ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), override_id),
    )
    expired = service.validate_for_interlock(
        override_id,
        actor="operator-a",
        session_id="EOL-OVERRIDE-1",
        operation="manual",
        vehicle_id="YL-JD-001",
        critical_alarm_ids=["alarm-critical"],
    )
    assert expired["allowed"] is False
    assert service.get(override_id).status.value == "EXPIRED"

    service, active_id = _create_approved_override(database)
    service.revoke(
        active_id,
        OverrideRevokeRequest(reason="diagnostic authorization withdrawn"),
        Principal("admin-b", Role.ADMIN),
    )
    revoked = service.validate_for_interlock(
        active_id,
        actor="operator-a",
        session_id="EOL-OVERRIDE-1",
        operation="manual",
        vehicle_id="YL-JD-001",
        critical_alarm_ids=["alarm-critical"],
    )
    assert revoked["allowed"] is False
    database.close()


def test_override_api_uses_typed_scope_admin_approval_and_revoke(auth_headers):
    with TestClient(app) as client:
        alarm = global_state.alarms.raise_system_alarm(
            "override-api-alarm", 3, "test", "typed override API test"
        )
        payload = {
            "reason": "controlled API diagnosis request",
            "session_id": "EOL-API-OVERRIDE",
            "operation": "manual",
            "vehicle_id": "YL-JD-API",
            "authorized_user": "test-operator",
            "duration_seconds": 60,
        }
        created = client.post(
            f"/api/v1/alarms/{alarm['id']}/override-request",
            json=payload,
            headers=auth_headers("engineer"),
        )
        assert created.status_code == 200, created.text
        override_id = created.json()["override"]["id"]
        approved = client.post(
            f"/api/v1/alarms/overrides/{override_id}/approve",
            json={"confirmation": "APPROVE", "reason": "independent admin approval"},
            headers=auth_headers("admin"),
        )
        assert approved.status_code == 200
        assert approved.json()["override"]["status"] == "APPROVED"
        listed = client.get("/api/v1/alarms/overrides", headers=auth_headers("viewer"))
        assert listed.status_code == 200
        assert any(item["id"] == override_id for item in listed.json()["items"])
        revoked = client.post(
            f"/api/v1/alarms/overrides/{override_id}/revoke",
            json={"reason": "test cleanup revocation"},
            headers=auth_headers("admin"),
        )
        assert revoked.status_code == 200
        assert revoked.json()["override"]["status"] == "REVOKED"
        global_state.alarms.clear_system_alarm("override-api-alarm")


def test_control_api_returns_409_with_structured_blocking_rule(auth_headers):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/121/send-once",
            json={
                "gear": "N",
                "target_speed": 0,
                "front_steer": 10,
                "rear_steer": 0,
                "brake_enable": False,
            },
            headers=auth_headers("engineer"),
        )
        assert response.status_code == 409
        payload = response.json()
        assert payload["code"] == "INTERLOCK_BLOCKED"
        reasons = payload["details"]["reasons"]
        assert reasons
        assert all(
            {"rule", "label", "current", "threshold", "blocking"} <= item.keys()
            for item in reasons
        )
