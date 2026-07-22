from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.can_gateway.manager import CanGatewayManager
from app.can_gateway.models import CanFrame
from app.core.config import ChannelConfig, RuntimeConfig, load_config
from app.configuration.models import ProductionConfiguration, SignedConfigurationPackage, sign_package


def test_default_dev_profile_is_loopback_only():
    config = load_config(profile="dev")
    assert config.profile == "dev"
    assert config.channels
    assert all(channel.local_ip == "127.0.0.1" for channel in config.channels)
    assert all(channel.device_ip == "127.0.0.1" for channel in config.channels)


def test_backend_host_port_environment_names_are_consumed(monkeypatch):
    monkeypatch.setenv("CHASSIS_BACKEND_HOST", "127.0.0.1")
    monkeypatch.setenv("CHASSIS_BACKEND_PORT", "18880")
    config = load_config(profile="dev")
    assert config.host == "127.0.0.1"
    assert config.port == 18880


def test_nonproduction_backend_host_fails_closed_off_loopback(monkeypatch):
    monkeypatch.setenv("CHASSIS_BACKEND_HOST", "0.0.0.0")
    with pytest.raises(ValueError, match="loopback backend host"):
        load_config(profile="dev")


def test_production_refuses_repository_template_without_signed_active_package(monkeypatch, tmp_path):
    monkeypatch.setenv("CHASSIS_ACTIVE_CONFIG_PATH", str(tmp_path / "missing.json"))
    with pytest.raises(ValueError, match="signed active configuration package"):
        load_config(profile="production")


def test_signed_production_package_loads_with_approved_identity(monkeypatch, tmp_path):
    key = "test-signing-key-which-is-longer-than-thirty-two-characters"
    path = tmp_path / "active-package.json"
    configuration = ProductionConfiguration.model_validate(
        {
            "config_version": "production-test-v1",
            "runtime_profile": "production",
            "network_interface": {"adapter_name": "approved-test-adapter", "bind_address": "127.0.0.1"},
            "can_endpoints": [
                {"channel": "CAN1", "protocol": "udp", "local_ip": "127.0.0.1", "local_port": 8234, "device_ip": "127.0.0.1", "device_port": 12341, "source_allowlist": [{"ip": "127.0.0.1", "port": 12341}], "enabled": True, "control_enabled": False},
                {"channel": "CAN2", "protocol": "udp", "local_ip": "127.0.0.1", "local_port": 8235, "device_ip": "127.0.0.1", "device_port": 12342, "source_allowlist": [{"ip": "127.0.0.1", "port": 12342}], "enabled": True, "control_enabled": True},
            ],
            "vehicle_series": "JD",
            "approved_dbc_sha256": "a" * 64,
            "test_plan_version": "approved-plan-v1",
            "data_root": str(tmp_path / "data"),
            "station_id": "APPROVED-STATION",
            "printer": {"name": None, "required": False},
        }
    )
    unsigned = SignedConfigurationPackage(
        package_id=uuid4(), issued_at=datetime.now(timezone.utc), issuer="test-admin",
        configuration=configuration, signature="0" * 64,
    )
    package = unsigned.model_copy(update={"signature": sign_package(unsigned, key)})
    path.write_text(package.model_dump_json(indent=2), encoding="utf-8")
    monkeypatch.setenv("CHASSIS_ACTIVE_CONFIG_PATH", str(path))
    monkeypatch.setenv("CHASSIS_CONFIG_SIGNING_KEY", key)
    config = load_config(profile="production")
    assert all(channel.local_ip == "127.0.0.1" for channel in config.channels)
    assert all(channel.device_ip == "127.0.0.1" for channel in config.channels)
    assert config.require_dbc_for_control is True
    assert config.approved_dbc_sha256 == "a" * 64
    assert config.vehicle_series == "JD"
    assert all(channel.validate_source_endpoint for channel in config.channels)
    assert config.config_trust == "signed-package"


def test_production_profile_requires_approved_dbc_identity_fields():
    with pytest.raises(ValueError, match="requires DBC"):
        RuntimeConfig(profile="production")
    with pytest.raises(ValueError, match="full approved DBC SHA-256"):
        RuntimeConfig(profile="production", require_dbc_for_control=True)


def test_non_production_profile_rejects_production_destination():
    with pytest.raises(ValueError, match="forbids non-loopback"):
        RuntimeConfig(
            profile="dev",
            channels=[
                ChannelConfig(
                    channel="CAN2",
                    local_ip="127.0.0.1",
                    local_receive_port=8235,
                    device_ip="203.0.113.99",
                    device_port=1234,
                    control_enabled=True,
                )
            ],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("can_id", [0x000, 0x123, 0x126, 0x710, 0x715])
async def test_gateway_rejects_disabled_dangerous_ids(can_id: int):
    async def on_frame(_frame):
        return None

    config = load_config(profile="dev")
    manager = CanGatewayManager(config, on_frame)
    manager.gateways["CAN2"] = SimpleNamespace(send_frame=lambda _frame: None)
    with pytest.raises(PermissionError):
        await manager.send_frame(
            "CAN2", CanFrame(channel="CAN2", direction="tx", can_id=can_id, data=[0] * 8)
        )
