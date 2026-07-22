from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.configuration.models import (
    CanEndpointConfig,
    NetworkInterfaceConfig,
    PrinterConfig,
    ProductionConfiguration,
    SignedConfigurationPackage,
    SourceEndpoint,
    configuration_hash,
    sign_package,
    verify_package,
)
from app.core.config import ChannelConfig, RuntimeConfig, SourceEndpointConfig
from app.core.paths import DATA_DIR


class ConfigurationLifecycleError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 422, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def signing_key() -> str:
    key = os.getenv("CHASSIS_CONFIG_SIGNING_KEY", "")
    if len(key) < 32:
        raise ConfigurationLifecycleError(
            "CONFIG_SIGNING_KEY_REQUIRED",
            "配置签名密钥未在本机安全运行环境中提供",
            status_code=503,
        )
    return key


def runtime_configuration(config: RuntimeConfig) -> ProductionConfiguration:
    endpoints = []
    for channel in config.channels:
        sources = channel.approved_source_endpoints()
        endpoints.append(
            CanEndpointConfig(
                channel=channel.channel,
                protocol=channel.protocol.lower(),
                local_ip=channel.local_ip,
                local_port=channel.local_receive_port,
                device_ip=channel.device_ip,
                device_port=channel.simulated_device_port or channel.device_port,
                source_allowlist=[SourceEndpoint(ip=ip, port=port) for ip, port in sorted(sources)],
                enabled=channel.enabled,
                control_enabled=channel.control_enabled,
            )
        )
    bind_address = endpoints[0].local_ip if endpoints else "127.0.0.1"
    digest = config.approved_dbc_sha256 or "0" * 64
    return ProductionConfiguration(
        config_version=config.config_version,
        runtime_profile=config.profile,
        network_interface=NetworkInterfaceConfig(
            adapter_name=config.network_interface_name,
            bind_address=bind_address,
        ),
        can_endpoints=endpoints,
        vehicle_series=config.vehicle_series,
        approved_dbc_sha256=digest,
        test_plan_version=config.test_plan_version,
        data_root=config.data_root,
        station_id=config.station_id,
        printer=PrinterConfig(name=config.printer_name, required=config.printer_required),
    )


def export_signed_package(config: RuntimeConfig, issuer: str) -> SignedConfigurationPackage:
    key = signing_key()
    unsigned = SignedConfigurationPackage(
        package_id=uuid4(),
        issued_at=datetime.now(timezone.utc),
        issuer=issuer,
        configuration=runtime_configuration(config),
        signature="0" * 64,
    )
    return unsigned.model_copy(update={"signature": sign_package(unsigned, key)})


def validate_signed_package(package: SignedConfigurationPackage, expected_profile: str) -> None:
    key = signing_key()
    if not verify_package(package, key):
        raise ConfigurationLifecycleError("CONFIG_SIGNATURE_INVALID", "配置包签名校验失败", status_code=422)
    if package.configuration.runtime_profile != expected_profile:
        raise ConfigurationLifecycleError(
            "CONFIG_PROFILE_MISMATCH",
            "配置包 runtime profile 与当前进程不一致，禁止热切换",
            status_code=409,
            details={"expected": expected_profile, "actual": package.configuration.runtime_profile},
        )


def runtime_from_package(current: RuntimeConfig, package: SignedConfigurationPackage) -> RuntimeConfig:
    imported = package.configuration
    channels = [
        ChannelConfig(
            channel=item.channel,
            protocol=item.protocol,
            local_ip=item.local_ip,
            local_receive_port=item.local_port,
            device_ip=item.device_ip,
            device_port=item.device_port,
            simulated_device_port=item.device_port if imported.runtime_profile != "production" else None,
            enabled=item.enabled,
            control_enabled=item.control_enabled,
            validate_source_endpoint=True,
            source_allowlist=[SourceEndpointConfig(ip=source.ip, port=source.port) for source in item.source_allowlist],
        )
        for item in imported.can_endpoints
    ]
    return RuntimeConfig.model_validate(
        {
            **current.model_dump(),
            "profile": imported.runtime_profile,
            "station_id": imported.station_id,
            "control_channel": "CAN2",
            "channels": [item.model_dump() for item in channels],
            "vehicle_series": imported.vehicle_series,
            "approved_dbc_sha256": imported.approved_dbc_sha256.lower(),
            "require_dbc_for_control": imported.runtime_profile == "production",
            "network_interface_name": imported.network_interface.adapter_name,
            "test_plan_version": imported.test_plan_version,
            "data_root": imported.data_root,
            "printer_name": imported.printer.name,
            "printer_required": imported.printer.required,
            "config_version": imported.config_version,
            "config_trust": "signed-package",
        }
    )


def package_diff(current: RuntimeConfig, package: SignedConfigurationPackage) -> list[dict[str, Any]]:
    before = _flatten(runtime_configuration(current).model_dump(mode="json"))
    after = _flatten(package.configuration.model_dump(mode="json"))
    return [
        {"path": path, "current": before.get(path), "proposed": after.get(path)}
        for path in sorted(before.keys() | after.keys())
        if before.get(path) != after.get(path)
    ]


def active_package_path() -> Path:
    return Path(os.getenv("CHASSIS_ACTIVE_CONFIG_PATH", DATA_DIR / "config" / "active-package.json"))


def persist_active_package(package: SignedConfigurationPackage) -> tuple[Path, bytes | None]:
    path = active_package_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_bytes() if path.exists() else None
    staged = path.with_suffix(path.suffix + ".tmp")
    staged.write_text(package.model_dump_json(indent=2), encoding="utf-8")
    loaded = SignedConfigurationPackage.model_validate_json(staged.read_text(encoding="utf-8"))
    validate_signed_package(loaded, package.configuration.runtime_profile)
    os.replace(staged, path)
    return path, previous


def restore_active_package(previous: bytes | None) -> None:
    path = active_package_path()
    if previous is None:
        path.unlink(missing_ok=True)
        return
    staged = path.with_suffix(path.suffix + ".rollback")
    staged.write_bytes(previous)
    os.replace(staged, path)


def package_summary(package: SignedConfigurationPackage) -> dict[str, Any]:
    return {
        "schema_version": package.schema_version,
        "package_id": str(package.package_id),
        "issued_at": package.issued_at.isoformat(),
        "issuer": package.issuer,
        "config_version": package.configuration.config_version,
        "configuration_hash": configuration_hash(package.configuration),
        "signature_algorithm": package.signature_algorithm,
    }


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            result.update(_flatten(item, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.update(_flatten(item, f"{prefix}[{index}]"))
    else:
        result[prefix] = value
    return result
