from __future__ import annotations
import ipaddress
import os
from pathlib import Path
from typing import Any, Literal
import yaml
from pydantic import AliasChoices, BaseModel, Field, model_validator
from .paths import CONFIG_DIR

class ChannelConfig(BaseModel):
    channel: str
    protocol: str = "udp"
    local_ip: str = "127.0.0.1"
    local_receive_port: int
    device_ip: str = "127.0.0.1"
    device_port: int = 1234
    simulated_device_port: int | None = None
    enabled: bool = True
    control_enabled: bool = Field(default=False, validation_alias=AliasChoices("control_enabled", "control_allowed"))
    receive_queue_size: int = Field(default=512, ge=16, le=8192)
    recent_buffer_size: int = Field(default=10_000, ge=100, le=100_000)
    max_frame_age_ms: int = Field(default=500, ge=50, le=5000)

class RuntimeConfig(BaseModel):
    profile: Literal["dev", "mock", "test", "production"] = "dev"
    host: str = "127.0.0.1"
    port: int = 8800
    station_id: str = "EOL-STATION-01"
    operator: str = "op01"
    software_version: str = "v1.0.2"
    control_channel: str = "CAN2"
    channels: list[ChannelConfig] = Field(default_factory=list)
    manual_speed_limit_kmh: float = 3.0
    steering_limit_default: int = 60
    steering_limit_absolute: int = 120
    require_dbc_for_control: bool = False
    channel_online_timeout_seconds: float = Field(default=2.0, gt=0.1, le=10.0)
    safe_stop_timeout_ms: int = Field(default=1500, ge=500, le=5000)
    safe_stop_retry_ms: int = Field(default=50, ge=10, le=500)
    stopped_speed_threshold_kmh: float = Field(default=0.1, ge=0, le=1.0)
    allowed_tx_can_ids: set[int] = Field(default_factory=lambda: {0x121})

    @model_validator(mode="after")
    def validate_runtime_boundary(self) -> "RuntimeConfig":
        control_channels = [item.channel for item in self.channels if item.control_enabled]
        if len(control_channels) > 1:
            raise ValueError("multiple control channels are forbidden")
        if self.profile != "production":
            for channel in self.channels:
                if not ipaddress.ip_address(channel.local_ip).is_loopback:
                    raise ValueError(f"{self.profile} profile requires loopback local_ip: {channel.channel}")
                if not ipaddress.ip_address(channel.device_ip).is_loopback:
                    raise ValueError(f"{self.profile} profile forbids non-loopback device_ip: {channel.channel}")
        return self

def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}

def load_config(dev: bool | None = None, profile: str | None = None) -> RuntimeConfig:
    selected_profile = (profile or os.getenv("CHASSIS_RUNTIME_PROFILE") or ("dev" if dev is not False else "production")).lower()
    if selected_profile not in {"dev", "mock", "test", "production"}:
        raise ValueError("CHASSIS_RUNTIME_PROFILE must be dev, mock, test, or production")
    station = _read_yaml(CONFIG_DIR / "station.yaml")
    thresholds = _read_yaml(CONFIG_DIR / "thresholds.yaml")
    profile_file = CONFIG_DIR / f"channels.{selected_profile}.yaml"
    if selected_profile == "production":
        channels_path = CONFIG_DIR / "channels.yaml"
    elif profile_file.exists():
        channels_path = profile_file
    else:
        channels_path = CONFIG_DIR / "channels.dev.yaml"
    channels_doc = _read_yaml(channels_path)
    channel_items = channels_doc.get("channels", [])
    channels: list[ChannelConfig] = []
    if isinstance(channel_items, dict):
        for name, raw in channel_items.items():
            raw = raw or {}
            channels.append(ChannelConfig(channel=name, **raw))
    elif isinstance(channel_items, list):
        for raw in channel_items:
            raw = raw or {}
            channels.append(ChannelConfig(**raw))
    if not channels:
        channels = [
            ChannelConfig(channel="CAN1", local_receive_port=8234, simulated_device_port=12341, device_port=12341),
            ChannelConfig(channel="CAN2", local_receive_port=8235, simulated_device_port=12342, device_port=12342, control_enabled=True),
        ]
    test_port_base = os.getenv("CHASSIS_TEST_PORT_BASE")
    if selected_profile == "test" and test_port_base:
        base = int(test_port_base)
        channels = [
            channel.model_copy(
                update={
                    "local_ip": "127.0.0.1",
                    "device_ip": "127.0.0.1",
                    "local_receive_port": base + index,
                    "device_port": base + 100 + index,
                    "simulated_device_port": base + 100 + index,
                }
            )
            for index, channel in enumerate(channels)
        ]
    vehicle = thresholds.get("vehicle", {}) if isinstance(thresholds.get("vehicle"), dict) else {}
    steering = thresholds.get("steering", {}) if isinstance(thresholds.get("steering"), dict) else {}
    software = station.get("software", {}) if isinstance(station.get("software"), dict) else {}
    station_info = station.get("station", {}) if isinstance(station.get("station"), dict) else {}
    return RuntimeConfig(
        profile=selected_profile,
        host=software.get("backend_host", "127.0.0.1"),
        port=int(software.get("backend_port", 8800)),
        station_id=station_info.get("id", "EOL-STATION-01"),
        channels=channels,
        manual_speed_limit_kmh=float(vehicle.get("manual_speed_limit_kmh", 3.0)),
        steering_limit_default=int(steering.get("command_limit_default", 60)),
        steering_limit_absolute=int(steering.get("command_limit_absolute", 120)),
        safe_stop_timeout_ms=int(thresholds.get("control", {}).get("safe_stop_timeout_ms", 1500)),
    )
