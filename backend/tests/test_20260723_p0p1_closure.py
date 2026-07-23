from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.configuration.diagnostics import adapter_identity_check
from app.configuration.models import ProductionConfiguration, configuration_hash
from app.configuration.service import runtime_configuration
from app.control.hardware_acceptance import (
    EvidenceFile,
    HardwareAcceptanceArtifact,
    HardwareAcceptanceService,
    PhysicalChecklist,
    sign_acceptance_artifact,
)
from app.control.intent_service import ControlIntentPersistenceError, ControlIntentService
from app.core.config import ChannelConfig, RuntimeConfig
from app.core.paths import CONFIG_DIR, DataPaths
from app.core.release_metadata import ReleaseMetadata
from app.main import app
from app.security.auth import Principal, Role
from app.services.app_state import state as global_state
from app.storage.database import Database


def _production_config(tmp_path: Path) -> RuntimeConfig:
    return RuntimeConfig.model_validate(
        {
            **RuntimeConfig().model_dump(),
            "profile": "production",
            "channels": [
                ChannelConfig(channel="CAN1", local_receive_port=18234, device_port=19234),
                ChannelConfig(channel="CAN2", local_receive_port=18235, device_port=19235, control_enabled=True),
            ],
            "require_dbc_for_control": True,
            "approved_dbc_sha256": "a" * 64,
            "vehicle_series": "JD",
            "network_interface_name": "Approved Adapter",
            "network_interface_index": 7,
            "network_interface_mac": "00:11:22:33:44:55",
            "data_root": str(tmp_path / "production-data"),
            "config_trust": "signed-package",
            "config_version": "prod-test-v1",
        }
    )


def test_production_unsigned_configuration_paths_are_rejected_and_audited(auth_headers):
    with TestClient(app) as client:
        original_profile = global_state.config.profile
        try:
            global_state.config.profile = "production"
            body = {
                "local_network": {},
                "channels": [
                    {
                        "name": item.channel,
                        "protocol": item.protocol.upper(),
                        "local_ip": item.local_ip,
                        "local_port": item.local_receive_port,
                        "device_ip": item.device_ip,
                        "device_port": item.simulated_device_port or item.device_port,
                        "enabled": item.enabled,
                        "control_enabled": item.control_enabled,
                    }
                    for item in global_state.config.channels
                ],
            }
            responses = [
                client.put("/api/v1/config/channels", json=body, headers=auth_headers("admin")),
                client.post("/api/v1/config/channels/restore-defaults", headers=auth_headers("admin")),
                client.put("/api/v1/config", json={"reason": "unsigned production mutation"}, headers=auth_headers("engineer")),
                client.post(
                    "/api/v1/config/restore-safe-defaults",
                    json={"confirmation": "RESTORE", "reason": "unsigned production restore"},
                    headers=auth_headers("admin"),
                ),
            ]
            assert all(item.status_code == 409 for item in responses)
            assert all(item.json()["code"] == "SIGNED_CONFIG_REQUIRED" for item in responses)
            actions = {
                row["action_type"]
                for row in global_state.database.query(
                    "SELECT action_type FROM operator_actions WHERE action_type LIKE '%rejected'"
                )
            }
            assert {
                "update_channels_rejected",
                "restore_channels_defaults_rejected",
                "save_system_config_rejected",
                "restore_safe_defaults_rejected",
            } <= actions
        finally:
            global_state.config.profile = original_profile


class _IntentScheduler:
    def __init__(self) -> None:
        self.sent = 0
        self.stopped = 0

    async def stop(self):
        self.stopped += 1

    async def send_priority(self, *_args, **_kwargs):
        self.sent += 1


@pytest.mark.asyncio
async def test_control_intent_prewrite_and_postsend_failures_are_fail_closed(tmp_path: Path):
    database = Database(tmp_path / "intent.sqlite3")
    scheduler = _IntentScheduler()
    state = SimpleNamespace(
        database=database,
        db_writable=True,
        alarms=None,
        tx_scheduler=scheduler,
        safe_stop_latched=False,
    )
    service = ControlIntentService(state)
    principal = Principal("engineer", Role.ENGINEER, "session-1")
    intent = service.create_authorized(
        principal,
        operation="control_manual",
        target="CAN2:0x121",
        command={"target_speed_kmh": 1.0},
        safety_evaluation={"allowed": True, "rules": []},
        trace_id="trace-intent",
        vehicle_id="L0000000000000001",
    )
    row = database.query_one("SELECT status,command_hash,safety_evaluation_hash FROM control_intents WHERE id=?", (intent,))
    assert row["status"] == "AUTHORIZED"
    assert len(row["command_hash"]) == len(row["safety_evaluation_hash"]) == 64

    database.close()
    with pytest.raises(ControlIntentPersistenceError):
        service.mark(intent, "SENT")
    await service.compensate_after_send_failure(intent, RuntimeError("post-send persistence failure"))
    assert state.db_writable is False
    assert state.safe_stop_latched is True
    assert scheduler.stopped == 1
    assert scheduler.sent == 1

    unavailable = SimpleNamespace(database=None, db_writable=True, alarms=None, tx_scheduler=scheduler)
    with pytest.raises(ControlIntentPersistenceError):
        ControlIntentService(unavailable).create_authorized(
            principal,
            operation="control_manual",
            target="CAN2:0x121",
            command={},
            safety_evaluation={"allowed": True},
            trace_id="trace-no-db",
        )
    assert scheduler.sent == 1


def test_restart_recovers_unfinished_control_intents(tmp_path: Path):
    database = Database(tmp_path / "recovery.sqlite3")
    state = SimpleNamespace(database=database, db_writable=True, alarms=None)
    service = ControlIntentService(state)
    intent = service.create_authorized(
        Principal("engineer", Role.ENGINEER, "session-2"),
        operation="control_manual",
        target="CAN2:0x121",
        command={"target_speed_kmh": 0},
        safety_evaluation={"allowed": True},
        trace_id="trace-recover",
    )
    assert service.recover_unfinished() == [intent]
    assert database.query_one("SELECT status FROM control_intents WHERE id=?", (intent,))["status"] == "CANCELLED"
    database.close()


def _acceptance_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config = _production_config(tmp_path)
    paths = DataPaths.from_root(tmp_path / "production-data")
    paths.ensure_ready(minimum_free_bytes=0)
    state = SimpleNamespace(
        config=config,
        data_paths=paths,
        dbc=SimpleNamespace(status=lambda: {"loaded": True, "hash": "a" * 64, "vehicle_series": "JD"}),
    )
    release = ReleaseMetadata(
        available=True,
        software_version="1.0.2",
        commit="b" * 40,
        built_at_utc="2026-07-23T00:00:00+00:00",
        release_label="signed-production-candidate",
        signed=True,
        formal_release=True,
        dirty=False,
        manifest_sha256="c" * 64,
    )
    monkeypatch.setattr("app.control.hardware_acceptance.load_release_metadata", lambda: release)
    key = "hardware-acceptance-independent-key-32-bytes-minimum"
    path = paths.config / "hardware-acceptance.json"
    monkeypatch.setenv("CHASSIS_HARDWARE_ACCEPTANCE_KEY", key)
    monkeypatch.setenv("CHASSIS_HARDWARE_ACCEPTANCE_PATH", str(path))
    plan_hash = hashlib.sha256((CONFIG_DIR / "test_plan.yaml").read_bytes()).hexdigest()
    unsigned = HardwareAcceptanceArtifact(
        station_id=config.station_id,
        vehicle_series=config.vehicle_series,
        controller="controller-test",
        firmware="firmware-test",
        release_hash=release.manifest_sha256,
        config_hash=configuration_hash(runtime_configuration(config)),
        dbc_hash="a" * 64,
        test_plan_hash=plan_hash,
        physical_checklist=PhysicalChecklist(
            emergency_stop_verified=True,
            plc_interlock_verified=True,
            propulsion_relay_verified=True,
            steering_relay_verified=True,
            brake_relay_verified=True,
        ),
        watchdog_policy="watchdog verified by signed evidence",
        safe_stop_policy="safe stop verified by signed evidence",
        evidence_files=[EvidenceFile(name="evidence.json", sha256="d" * 64)],
        requester="requester-a",
        approvers=["approver-b", "approver-c"],
        valid_from=datetime.now(timezone.utc) - timedelta(minutes=1),
        valid_to=datetime.now(timezone.utc) + timedelta(minutes=10),
        signature="0" * 64,
    )
    artifact = unsigned.model_copy(update={"signature": sign_acceptance_artifact(unsigned, key)})
    return state, path, key, artifact


@pytest.mark.parametrize(
    ("mutation", "expected_rule"),
    [
        ("bad_signature", "artifact_signature"),
        ("expired", "artifact_validity"),
        ("revoked", "artifact_revocation"),
        ("same_person", "artifact_separation_of_duties"),
        ("scope", "artifact_scope_station_id"),
        ("release_hash", "artifact_scope_release_hash"),
        ("config_hash", "artifact_scope_config_hash"),
        ("dbc_hash", "artifact_scope_dbc_hash"),
        ("plan_hash", "artifact_scope_test_plan_hash"),
    ],
)
def test_hardware_acceptance_rejects_invalid_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str, expected_rule: str):
    state, path, key, artifact = _acceptance_fixture(tmp_path, monkeypatch)
    if mutation == "bad_signature":
        artifact = artifact.model_copy(update={"signature": "e" * 64})
    elif mutation == "expired":
        artifact = artifact.model_copy(update={"valid_from": datetime.now(timezone.utc) - timedelta(minutes=20), "valid_to": datetime.now(timezone.utc) - timedelta(minutes=10), "signature": "0" * 64})
        artifact = artifact.model_copy(update={"signature": sign_acceptance_artifact(artifact, key)})
    elif mutation == "revoked":
        artifact = artifact.model_copy(update={"revoked_at": datetime.now(timezone.utc), "revoke_reason": "test revocation", "signature": "0" * 64})
        artifact = artifact.model_copy(update={"signature": sign_acceptance_artifact(artifact, key)})
    elif mutation == "same_person":
        artifact = artifact.model_copy(update={"approvers": [artifact.requester, "approver-c"], "signature": "0" * 64})
        artifact = artifact.model_copy(update={"signature": sign_acceptance_artifact(artifact, key)})
    elif mutation == "scope":
        artifact = artifact.model_copy(update={"station_id": "OTHER-STATION", "signature": "0" * 64})
        artifact = artifact.model_copy(update={"signature": sign_acceptance_artifact(artifact, key)})
    elif mutation == "release_hash":
        artifact = artifact.model_copy(update={"release_hash": "1" * 64, "signature": "0" * 64})
        artifact = artifact.model_copy(update={"signature": sign_acceptance_artifact(artifact, key)})
    elif mutation == "config_hash":
        artifact = artifact.model_copy(update={"config_hash": "2" * 64, "signature": "0" * 64})
        artifact = artifact.model_copy(update={"signature": sign_acceptance_artifact(artifact, key)})
    elif mutation == "dbc_hash":
        artifact = artifact.model_copy(update={"dbc_hash": "3" * 64, "signature": "0" * 64})
        artifact = artifact.model_copy(update={"signature": sign_acceptance_artifact(artifact, key)})
    elif mutation == "plan_hash":
        artifact = artifact.model_copy(update={"test_plan_hash": "4" * 64, "signature": "0" * 64})
        artifact = artifact.model_copy(update={"signature": sign_acceptance_artifact(artifact, key)})
    path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    result = HardwareAcceptanceService(state).evaluate()
    assert result["allowed"] is False
    reason = next(item for item in result["reasons"] if item["rule"] == expected_rule)
    assert {"rule", "label", "current", "threshold", "blocking"} <= reason.keys()


def test_hardware_acceptance_missing_and_valid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    state, path, _key, artifact = _acceptance_fixture(tmp_path, monkeypatch)
    missing = HardwareAcceptanceService(state).evaluate()
    assert missing["allowed"] is False
    assert missing["reasons"][0]["rule"] == "artifact_present"
    path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    approved = HardwareAcceptanceService(state).evaluate()
    assert approved["allowed"] is True
    assert approved["artifact"]["station_id"] == state.config.station_id
    assert "signature" not in approved["artifact"]


def test_production_schema_rejects_tcp_and_adapter_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    configuration = runtime_configuration(_production_config(tmp_path))
    payload = configuration.model_dump(mode="json")
    payload["can_endpoints"][1]["protocol"] = "tcp"
    with pytest.raises(ValueError, match="UDP only"):
        ProductionConfiguration.model_validate(payload)

    monkeypatch.setattr(
        "app.configuration.diagnostics._adapter_identities",
        lambda: [
            {
                "name": configuration.network_interface.adapter_name,
                "index": configuration.network_interface.adapter_index,
                "mac": "00:11:22:33:44:66",
                "ip": configuration.network_interface.bind_address,
            }
        ],
    )
    check = adapter_identity_check(configuration)
    assert check["passed"] is False
    assert check["blocking"] is True
    assert {"rule", "label", "current", "threshold", "blocking"} <= check.keys()


def test_eol_identity_cannot_spoof_principal_or_signed_station(auth_headers):
    with TestClient(app) as client:
        spoofed = client.post(
            "/api/v1/eol/sessions",
            headers=auth_headers("operator"),
            json={
                "chassis_no": "TRACE-001",
                "vin": "L0000000000000011",
                "serial_no": "TRACE-SN-001",
                "vehicle_series": "JD",
                "work_order_id": "TRACE-WO-001",
                "plan_id": "default_chassis_eol_v1",
                "operator": "admin",
                "station_id": "SPOOFED-STATION",
            },
        )
        assert spoofed.status_code == 422
        created = client.post(
            "/api/v1/eol/sessions",
            headers=auth_headers("operator"),
            json={
                "chassis_no": "TRACE-002",
                "vin": "L0000000000000012",
                "serial_no": "TRACE-SN-002",
                "vehicle_series": "JD",
                "work_order_id": "TRACE-WO-002",
                "plan_id": "default_chassis_eol_v1",
                "mock_session": True,
            },
        )
        assert created.status_code == 200
        body = created.json()
        assert body["operator"] == "test-operator"
        assert body["station_id"] == global_state.config.station_id
        duplicate = client.post(
            "/api/v1/eol/sessions",
            headers=auth_headers("operator"),
            json={
                "chassis_no": "TRACE-003",
                "vin": "L0000000000000012",
                "serial_no": "TRACE-SN-003",
                "vehicle_series": "JD",
                "work_order_id": "TRACE-WO-003",
                "plan_id": "default_chassis_eol_v1",
                "mock_session": True,
            },
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "DUPLICATE_VEHICLE_IDENTITY"


def test_can_source_session_is_never_a_fixed_demo_value():
    config = RuntimeConfig(
        profile="test",
        channels=[ChannelConfig(channel="CAN2", local_receive_port=18235, control_enabled=True)],
    )
    from app.can_gateway.manager import CanGatewayManager
    from app.can_gateway.models import CanFrame

    async def consume(_frame):
        return None

    manager = CanGatewayManager(config, consume)
    frame = CanFrame(channel="CAN2", can_id=0x51, data=[0] * 8)
    manager.record_recent(frame)
    assert manager.latest_items()[0]["source_session"] == "-"
    manager.record_recent(frame, "EOL-TRACE")
    assert manager.latest_items()[0]["source_session"] == "EOL-TRACE"


def test_unloaded_dbc_and_release_metadata_do_not_use_fixed_fallbacks(auth_headers):
    with TestClient(app) as client:
        original = global_state.dbc
        try:
            global_state.dbc = SimpleNamespace(
                status=lambda: {"loaded": False, "raw_only": True, "file": "", "hash": "", "version": "raw-only", "error": "test unavailable"},
                messages=lambda: [],
            )
            response = client.get("/api/v1/config/system-dashboard", headers=auth_headers("viewer"))
            assert response.status_code == 200
            payload = response.json()
            assert payload["dbc"]["filename"] is None
            assert payload["dbc"]["hash"] is None
            assert payload["dbc"]["message_count"] == payload["dbc"]["signal_count"] == 0
            assert payload["version"]["config"] == global_state.config.config_version
            assert payload["version"]["test_plan"] == global_state.config.test_plan_version
            assert payload["version"]["build_time"] != datetime.now(timezone.utc).isoformat()
        finally:
            global_state.dbc = original


def test_windows_release_manifest_freezes_clean_source_state_before_build():
    repository_root = Path(__file__).resolve().parents[2]
    generator = (repository_root / "scripts" / "generate_release_metadata.mjs").read_text(encoding="utf-8")
    build_script = (repository_root / "scripts" / "build_windows_release.ps1").read_text(encoding="utf-8")

    assert "source_dirty_file_count: currentSourceStatus" in generator
    assert "const prepared = JSON.parse(readFileSync(buildStatePath" in generator
    assert "if (prepared.commit !== commit)" in generator
    assert "dirty: sourceDirty, dirty_file_count: sourceDirtyFileCount" in generator
    assert "Windows release candidates must be built from a clean source tree" in build_script
