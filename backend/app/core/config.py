from __future__ import annotations
import ipaddress
import os
from pathlib import Path
from typing import Any, Literal
import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from .paths import CONFIG_DIR, DATA_DIR


class SourceEndpointConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ip: str
    port: int = Field(ge=1, le=65535)

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        return str(ipaddress.ip_address(value))

class ChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
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
    validate_source_endpoint: bool = True
    source_allowlist: list[SourceEndpointConfig] = Field(default_factory=list, max_length=16)

    def approved_source_endpoints(self) -> set[tuple[str, int]]:
        if self.source_allowlist:
            return {(item.ip, item.port) for item in self.source_allowlist}
        return {(self.device_ip, self.simulated_device_port or self.device_port)}


class FeedbackRequirement(BaseModel):
    id: str
    label: str
    signals: list[str] = Field(min_length=1)
    channel: Literal["CAN1", "CAN2"]
    max_age_ms: int = Field(default=500, ge=50, le=10_000)
    expected_can_ids: set[str] = Field(default_factory=set)
    allowed_values: list[bool | int | float | str] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def validate_requirement(self) -> "FeedbackRequirement":
        normalized: set[str] = set()
        for raw in self.expected_can_ids:
            parsed = int(str(raw), 0)
            if not 0 <= parsed <= 0x1FFFFFFF:
                raise ValueError(f"feedback requirement {self.id} has invalid CAN ID {raw}")
            normalized.add(f"0x{parsed:X}")
        self.expected_can_ids = normalized
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(f"feedback requirement {self.id} minimum exceeds maximum")
        return self


class FeedbackDependencyMatrix(BaseModel):
    base: list[FeedbackRequirement]
    drive: list[FeedbackRequirement]
    steering: list[FeedbackRequirement]
    brake: list[FeedbackRequirement]


def _default_feedback_dependencies() -> FeedbackDependencyMatrix:
    return FeedbackDependencyMatrix.model_validate(
        {
            "base": [
                {"id": "vehicle_speed", "label": "车辆速度反馈", "signals": ["CCU_Vehicle_Speed", "Vehicle_Speed"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x51", "0x168"], "minimum": 0, "maximum": 51.1},
                {"id": "controller_heartbeat_front", "label": "前控制器心跳", "signals": ["Heartbeat_0x704"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x704"], "minimum": 0, "maximum": 255},
                {"id": "controller_heartbeat_rear", "label": "后控制器心跳", "signals": ["Heartbeat_0x703"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x703"], "minimum": 0, "maximum": 255},
            ],
            "drive": [
                {"id": "gear_status", "label": "实际挡位反馈", "signals": ["CCU_Shift_Level_Status"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x51"], "allowed_values": [0, 1, 3]},
                {"id": "drive_mode", "label": "驱动模式反馈", "signals": ["CCU_Drive_Mode"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x51"], "allowed_values": [0, 1, 2, 3]},
            ],
            "steering": [
                {"id": "front_steering", "label": "前转角反馈", "signals": ["SAS_Front_Angle"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0xE1"], "minimum": -168, "maximum": 168},
                {"id": "rear_steering", "label": "后转角反馈", "signals": ["SAS_Rear_Angle"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0xE1"], "minimum": -168, "maximum": 168},
                {"id": "steering_connected", "label": "转向通信状态", "signals": ["Steering_Disconnect_Warning"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x77"], "allowed_values": [0]},
                {"id": "steering_unlocked", "label": "转向锁止状态", "signals": ["Steering_Lock_Warning"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x77"], "allowed_values": [0]},
                {"id": "steering_controllable", "label": "转向可控状态", "signals": ["Steering_Uncontrollable_Warning"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x77"], "allowed_values": [0]},
                {"id": "steering_no_error", "label": "转向故障状态", "signals": ["Steering_Error_Warning"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x77"], "allowed_values": [0]},
            ],
            "brake": [
                {"id": "brake_status", "label": "制动反馈状态", "signals": ["Brake_Status", "SCU_Brake_Signal_Status"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x51"], "allowed_values": [False, True]},
                {"id": "brake_no_error", "label": "制动故障状态", "signals": ["Brake_Error_Warning"], "channel": "CAN1", "max_age_ms": 500, "expected_can_ids": ["0x77"], "allowed_values": [0]},
            ],
        }
    )

class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Literal["dev", "mock", "test", "production"] = "dev"
    host: str = "127.0.0.1"
    port: int = Field(default=8800, ge=1, le=65535)
    station_id: str = "EOL-STATION-01"
    operator: str = "op01"
    software_version: str = "v1.0.2"
    control_channel: str = "CAN2"
    channels: list[ChannelConfig] = Field(default_factory=list)
    manual_speed_limit_kmh: float = 3.0
    steering_limit_default: int = 60
    steering_limit_absolute: int = 120
    vehicle_series: str = "JD"
    require_dbc_for_control: bool = False
    approved_dbc_sha256: str | None = None
    feedback_dependencies: FeedbackDependencyMatrix = Field(default_factory=_default_feedback_dependencies)
    channel_online_timeout_seconds: float = Field(default=2.0, gt=0.1, le=10.0)
    safe_stop_timeout_ms: int = Field(default=1500, ge=500, le=5000)
    safe_stop_retry_ms: int = Field(default=50, ge=10, le=500)
    stopped_speed_threshold_kmh: float = Field(default=0.1, ge=0, le=1.0)
    safe_stop_post_confirm_policy: Literal["stop_transmission", "hold_brake_until_release"] = "stop_transmission"
    safe_stop_hold_period_ms: int = Field(default=50, ge=20, le=500)
    safe_stop_policy_hardware_validated: bool = False
    allowed_tx_can_ids: set[int] = Field(default_factory=lambda: {0x121})
    network_interface_name: str = "loopback-placeholder"
    network_interface_index: int | None = Field(default=None, ge=1)
    network_interface_mac: str | None = None
    test_plan_version: str = "eol-plan-1.0.2"
    data_root: str = str(DATA_DIR)
    printer_name: str | None = None
    printer_required: bool = False
    config_version: str = "repository-default"
    config_trust: Literal["repository-default", "signed-package"] = "repository-default"

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        return str(ipaddress.ip_address(value))

    @model_validator(mode="after")
    def validate_runtime_boundary(self) -> "RuntimeConfig":
        if self.allowed_tx_can_ids != {0x121}:
            raise ValueError("active transmit policy is immutable and permits only CAN ID 0x121")
        control_channels = [item.channel for item in self.channels if item.control_enabled]
        if len(control_channels) > 1:
            raise ValueError("multiple control channels are forbidden")
        if self.profile != "production":
            if not ipaddress.ip_address(self.host).is_loopback:
                raise ValueError(f"{self.profile} profile requires a loopback backend host")
            for channel in self.channels:
                if not ipaddress.ip_address(channel.local_ip).is_loopback:
                    raise ValueError(f"{self.profile} profile requires loopback local_ip: {channel.channel}")
                if not ipaddress.ip_address(channel.device_ip).is_loopback:
                    raise ValueError(f"{self.profile} profile forbids non-loopback device_ip: {channel.channel}")
        else:
            if any(item.protocol.lower() != "udp" for item in self.channels):
                raise ValueError("production profile currently permits UDP only")
            if self.control_channel != "CAN2" or control_channels != ["CAN2"]:
                raise ValueError("production requires CAN2 as the only control-enabled channel")
            if not self.require_dbc_for_control:
                raise ValueError("production profile requires DBC for control")
            digest = (self.approved_dbc_sha256 or "").lower()
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("production profile requires a full approved DBC SHA-256")
            if not self.vehicle_series.strip():
                raise ValueError("production profile requires an approved vehicle series")
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
    safety = _read_yaml(CONFIG_DIR / "safety_interlock.yaml")
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
    loopback_port_base = os.getenv("CHASSIS_TEST_PORT_BASE") if selected_profile == "test" else os.getenv("CHASSIS_LOOPBACK_CAN_PORT_BASE")
    if selected_profile != "production" and loopback_port_base:
        base = int(loopback_port_base)
        if not 1024 <= base <= 65434:
            raise ValueError("loopback CAN port base must be between 1024 and 65434")
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
    dbc_config = station.get("dbc", {}) if isinstance(station.get("dbc"), dict) else {}
    safe_stop = safety.get("safe_stop", {}) if isinstance(safety.get("safe_stop"), dict) else {}
    feedback = safety.get("feedback_dependencies", {})
    runtime = RuntimeConfig(
        profile=selected_profile,
        host=os.getenv("CHASSIS_BACKEND_HOST", str(software.get("backend_host", "127.0.0.1"))),
        port=int(os.getenv("CHASSIS_BACKEND_PORT", str(software.get("backend_port", 8800)))),
        station_id=station_info.get("id", "EOL-STATION-01"),
        vehicle_series=str(dbc_config.get("approved_vehicle_series", station_info.get("default_vehicle_series", "JD"))),
        channels=channels,
        manual_speed_limit_kmh=float(vehicle.get("manual_speed_limit_kmh", 3.0)),
        steering_limit_default=int(steering.get("command_limit_default", 60)),
        steering_limit_absolute=int(steering.get("command_limit_absolute", 120)),
        require_dbc_for_control=(
            bool(dbc_config.get("require_for_control_in_production", True))
            if selected_profile == "production"
            else not bool(dbc_config.get("allow_raw_only_in_nonproduction", True))
        ),
        approved_dbc_sha256=dbc_config.get("approved_sha256"),
        feedback_dependencies=(FeedbackDependencyMatrix.model_validate(feedback) if feedback else _default_feedback_dependencies()),
        safe_stop_timeout_ms=int(thresholds.get("control", {}).get("safe_stop_timeout_ms", 1500)),
        safe_stop_retry_ms=int(safe_stop.get("retry_ms", 50)),
        safe_stop_post_confirm_policy=safe_stop.get("post_confirmation_policy", "stop_transmission"),
        safe_stop_hold_period_ms=int(safe_stop.get("hold_period_ms", 50)),
        safe_stop_policy_hardware_validated=bool(safe_stop.get("hardware_validated", False)),
    )
    active_path = Path(os.getenv("CHASSIS_ACTIVE_CONFIG_PATH", DATA_DIR / "config" / "active-package.json"))
    if selected_profile == "production" and not active_path.exists():
        raise ValueError("production profile requires a locally approved signed active configuration package")
    if active_path.exists():
        from app.configuration.models import SignedConfigurationPackage, verify_package

        key = os.getenv("CHASSIS_CONFIG_SIGNING_KEY", "")
        if len(key) < 32:
            raise ValueError("CHASSIS_CONFIG_SIGNING_KEY is required to verify the active configuration package")
        package = SignedConfigurationPackage.model_validate_json(active_path.read_text(encoding="utf-8"))
        if not verify_package(package, key):
            raise ValueError("active configuration package signature is invalid")
        imported = package.configuration
        if imported.runtime_profile != selected_profile:
            raise ValueError("active configuration package runtime profile does not match CHASSIS_RUNTIME_PROFILE")
        channels = [
            ChannelConfig(
                channel=item.channel,
                protocol=item.protocol,
                local_ip=item.local_ip,
                local_receive_port=item.local_port,
                device_ip=item.device_ip,
                device_port=item.device_port,
                simulated_device_port=item.device_port if selected_profile != "production" else None,
                enabled=item.enabled,
                control_enabled=item.control_enabled,
                validate_source_endpoint=True,
                source_allowlist=[SourceEndpointConfig(ip=source.ip, port=source.port) for source in item.source_allowlist],
            )
            for item in imported.can_endpoints
        ]
        runtime = RuntimeConfig.model_validate(
            {
                **runtime.model_dump(),
                "station_id": imported.station_id,
                "channels": [item.model_dump() for item in channels],
                "control_channel": "CAN2",
                "vehicle_series": imported.vehicle_series,
                "approved_dbc_sha256": imported.approved_dbc_sha256.lower(),
                "require_dbc_for_control": imported.runtime_profile == "production",
                "network_interface_name": imported.network_interface.adapter_name,
                "network_interface_index": imported.network_interface.adapter_index,
                "network_interface_mac": imported.network_interface.mac_address,
                "test_plan_version": imported.test_plan_version,
                "data_root": imported.data_root,
                "printer_name": imported.printer.name,
                "printer_required": imported.printer.required,
                "config_version": imported.config_version,
                "config_trust": "signed-package",
            }
        )
    return runtime
