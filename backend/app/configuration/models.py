from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConfigurationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NetworkInterfaceConfig(ConfigurationModel):
    adapter_name: str = Field(min_length=1, max_length=128)
    bind_address: str

    @field_validator("bind_address")
    @classmethod
    def validate_bind_address(cls, value: str) -> str:
        return str(ipaddress.ip_address(value))


class SourceEndpoint(ConfigurationModel):
    ip: str
    port: int = Field(ge=1, le=65535)

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        return str(ipaddress.ip_address(value))


class CanEndpointConfig(ConfigurationModel):
    channel: Literal["CAN1", "CAN2"]
    protocol: Literal["udp", "tcp"] = "udp"
    local_ip: str
    local_port: int = Field(ge=1, le=65535)
    device_ip: str
    device_port: int = Field(ge=1, le=65535)
    source_allowlist: list[SourceEndpoint] = Field(min_length=1, max_length=16)
    enabled: bool = True
    control_enabled: bool = False

    @field_validator("local_ip", "device_ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        return str(ipaddress.ip_address(value))

    @model_validator(mode="after")
    def require_device_in_source_allowlist(self) -> "CanEndpointConfig":
        approved = {(item.ip, item.port) for item in self.source_allowlist}
        if (self.device_ip, self.device_port) not in approved:
            raise ValueError(f"{self.channel} device endpoint must be present in source_allowlist")
        return self


class PrinterConfig(ConfigurationModel):
    name: str | None = Field(default=None, max_length=256)
    required: bool = False


class ProductionConfiguration(ConfigurationModel):
    config_version: str = Field(min_length=1, max_length=64)
    runtime_profile: Literal["dev", "mock", "test", "production"]
    network_interface: NetworkInterfaceConfig
    can_endpoints: list[CanEndpointConfig] = Field(min_length=2, max_length=2)
    vehicle_series: str = Field(min_length=1, max_length=32)
    approved_dbc_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    test_plan_version: str = Field(min_length=1, max_length=128)
    data_root: str = Field(min_length=1, max_length=1024)
    station_id: str = Field(min_length=1, max_length=128)
    printer: PrinterConfig = Field(default_factory=PrinterConfig)

    @model_validator(mode="after")
    def validate_safety_boundary(self) -> "ProductionConfiguration":
        if {item.channel for item in self.can_endpoints} != {"CAN1", "CAN2"}:
            raise ValueError("configuration must define exactly CAN1 and CAN2")
        control = [item.channel for item in self.can_endpoints if item.control_enabled]
        if control != ["CAN2"]:
            raise ValueError("CAN2 must be the only control-enabled channel")
        if self.runtime_profile == "production" and set(self.approved_dbc_sha256.lower()) == {"0"}:
            raise ValueError("production approved_dbc_sha256 must not use the template placeholder")
        if self.runtime_profile != "production":
            addresses = [self.network_interface.bind_address]
            for item in self.can_endpoints:
                addresses.extend([item.local_ip, item.device_ip])
                addresses.extend(source.ip for source in item.source_allowlist)
            if any(not ipaddress.ip_address(value).is_loopback for value in addresses):
                raise ValueError(f"{self.runtime_profile} configuration is restricted to loopback addresses")
        return self


class SignedConfigurationPackage(ConfigurationModel):
    schema_version: Literal[1] = 1
    package_id: UUID
    issued_at: datetime
    issuer: str = Field(min_length=1, max_length=128)
    configuration: ProductionConfiguration
    signature_algorithm: Literal["HMAC-SHA256"] = "HMAC-SHA256"
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("issued_at")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            raise ValueError("issued_at must be a UTC timestamp")
        return value


def canonical_package_bytes(package: SignedConfigurationPackage | dict) -> bytes:
    if isinstance(package, SignedConfigurationPackage):
        payload = package.model_dump(mode="json", exclude={"signature"})
    else:
        payload = {key: value for key, value in package.items() if key != "signature"}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_package(package: SignedConfigurationPackage, key: str) -> str:
    return hmac.new(key.encode("utf-8"), canonical_package_bytes(package), hashlib.sha256).hexdigest()


def verify_package(package: SignedConfigurationPackage, key: str) -> bool:
    return hmac.compare_digest(package.signature, sign_package(package, key))


def configuration_hash(configuration: ProductionConfiguration) -> str:
    payload = json.dumps(configuration.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
