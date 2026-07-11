from types import SimpleNamespace

import pytest

from app.can_gateway.manager import CanGatewayManager
from app.can_gateway.models import CanFrame
from app.core.config import ChannelConfig, RuntimeConfig, load_config


def test_default_dev_profile_is_loopback_only():
    config = load_config(profile="dev")
    assert config.profile == "dev"
    assert config.channels
    assert all(channel.local_ip == "127.0.0.1" for channel in config.channels)
    assert all(channel.device_ip == "127.0.0.1" for channel in config.channels)


def test_public_production_template_is_loopback_only():
    config = load_config(profile="production")
    assert all(channel.local_ip == "127.0.0.1" for channel in config.channels)
    assert all(channel.device_ip == "127.0.0.1" for channel in config.channels)


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
