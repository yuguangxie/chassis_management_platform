from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import logging
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml

from app.core.config import ChannelConfig, RuntimeConfig
from app.configuration.diagnostics import (
    adapter_identity_check,
    configuration_post_apply_health,
    configuration_preflight,
    diagnose_network,
)
from app.configuration.models import SignedConfigurationPackage
from app.configuration.service import (
    ConfigurationLifecycleError,
    active_package_path,
    export_signed_package,
    package_diff,
    package_summary,
    persist_active_package,
    restore_active_package,
    runtime_from_package,
    validate_signed_package,
)
from app.core.paths import ASSETS_DIR, CONFIG_DIR, PROJECT_ROOT, DataPaths
from app.core.time import utc_now
from app.core.release_metadata import load_release_metadata
from app.api.data_source import dashboard_metadata
from app.api.errors import get_trace_id
from app.api.models import ChannelSettingsResponse, ChannelSettingsUpdateRequest, SystemDashboardResponse
from app.security.auth import Principal, Role, require_role
from app.services.app_state import state

router = APIRouter()
logger = logging.getLogger(__name__)
SYSTEM_SETTINGS_PATH = CONFIG_DIR / "system_settings.yaml"


class BasicSettingsUpdate(BaseModel):
    station_id: str | None = None
    host_ip: str | None = None
    control_channel: Literal["CAN1", "CAN2"] | None = None
    report_directory: str | None = None
    database_path: str | None = None
    log_directory: str | None = None
    timezone: str | None = None
    language: str | None = None
    auto_save: bool | None = None

    @field_validator("host_ip")
    @classmethod
    def valid_host_ip(cls, value: str | None) -> str | None:
        if value:
            try:
                ipaddress.ip_address(value)
            except ValueError as exc:
                raise ValueError("工控机 IP 无效") from exc
        return value


class StorageSettingsUpdate(BaseModel):
    report_directory: str | None = None
    raw_can_directory: str | None = None
    decoded_signal_directory: str | None = None
    database_path: str | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    max_log_gb: float | None = Field(default=None, gt=0, le=2048)
    auto_cleanup: bool | None = None
    word_enabled: bool | None = None
    pdf_enabled: bool | None = None
    csv_enabled: bool | None = None
    parquet_enabled: bool | None = None


class ThresholdSettingUpdate(BaseModel):
    key: str
    label: str = ""
    value: bool | float | int
    min: float | None = None
    max: float | None = None
    unit: str = ""
    scope: str = ""
    description: str = ""
    dangerous: bool = False


class MaintenanceFeaturesUpdate(BaseModel):
    mock_can_gateway: bool = False
    enable_0x123: bool = False
    enable_0x126: bool = False
    allow_canopen_nmt: bool = False
    enable_pid_debug: bool = False
    dual_control_channel_allowed: bool = False


class SystemConfigUpdate(BaseModel):
    basic: BasicSettingsUpdate | None = None
    storage: StorageSettingsUpdate | None = None
    thresholds: list[ThresholdSettingUpdate] | None = None
    maintenance: MaintenanceFeaturesUpdate | None = None
    control_channels: list[str] | None = None
    role: str = "operator"
    reason: str = "系统设置页面保存"


class MaintenanceEnterRequest(BaseModel):
    confirmation: str
    reason: str = Field(min_length=2, max_length=200)
    role: str = "operator"


class MaintenanceExitRequest(BaseModel):
    role: str = "operator"
    reason: str = "退出维护模式"


class MaintenanceFeatureRequest(MaintenanceFeaturesUpdate):
    steering_angle_speed_deg_s: float | None = Field(default=None, ge=126, le=525)
    confirmation: str = ""
    reason: str = "维护功能调整"
    role: str = "operator"


class RestoreSafeDefaultsRequest(BaseModel):
    confirmation: str
    reason: str = Field(default="恢复安全默认", min_length=2, max_length=200)
    role: str = "operator"


class ConfigImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package: SignedConfigurationPackage
    dry_run: Literal[True] = True


class ConfigApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package: SignedConfigurationPackage
    confirmation: Literal["APPLY"]
    reason: str = Field(min_length=2, max_length=200)


DEFAULT_NETWORK_CONFIG = {
    "local_network": {
        "host_ip": "127.0.0.1",
        "dev_ip": "127.0.0.1",
        "nic_name": "loopback-placeholder",
        "subnet_mask": "not-measured",
        "link_speed": "not-measured",
        "ports": [
            {"port": 8234, "protocol": "UDP", "status": "not-diagnosed"},
            {"port": 8235, "protocol": "UDP", "status": "not-diagnosed"},
        ],
    },
    "channels": [
        {"name": "CAN1", "protocol": "UDP", "local_ip": "127.0.0.1", "local_port": 8234, "device_ip": "127.0.0.1", "device_port": 12341, "enabled": True, "rx_status": "active", "period_ms": 20, "control_enabled": False, "status": "active"},
        {"name": "CAN2", "protocol": "UDP", "local_ip": "127.0.0.1", "local_port": 8235, "device_ip": "127.0.0.1", "device_port": 12342, "enabled": True, "rx_status": "active", "period_ms": 20, "control_enabled": True, "status": "active"},
    ],
}


ROLES = [
    {"role": "viewer", "view": "全部查看", "test": "无", "manual_control": "无", "config": "无", "maintenance": "无", "delete_report": False, "admin_confirmation": False},
    {"role": "operator", "view": "业务页面", "test": "执行检测", "manual_control": "无", "config": "无", "maintenance": "无", "delete_report": False, "admin_confirmation": False},
    {"role": "engineer", "view": "全部业务页", "test": "执行检测", "manual_control": "0x121", "config": "非危险配置", "maintenance": "无", "delete_report": False, "admin_confirmation": False},
    {"role": "admin", "view": "全部", "test": "全部", "manual_control": "全部审批", "config": "全部", "maintenance": "管理员确认", "delete_report": True, "admin_confirmation": True},
]


DBC_OVERRIDES = [
    {"key": "0x121_steering", "label": "0x121 前/后转角", "value": "int8 有符号补码", "status": "active"},
    {"key": "0x102_bool", "label": "0x102 保护状态", "value": "unsigned bool", "status": "active"},
    {"key": "0x101_state", "label": "0x101 充放电状态", "value": "0 idle / 1 charging / 2 discharging / 3 reserved", "status": "active"},
    {"key": "motor_current", "label": "Torque_req / Torque_feed", "value": "电机相电流 raw × 0.1 A，不是 Nm", "status": "active"},
    {"key": "bms_cell_segments", "label": "0x104~0x109", "value": "BMS cell 分段兼容，非固定 24 串", "status": "active"},
]


SAFE_DEFAULTS = [
    {"label": "UI 不直接发送 CAN", "enabled": True},
    {"label": "所有运动控制必须经过安全联锁", "enabled": True},
    {"label": "数据库不可写时禁止开始检测", "enabled": True},
    {"label": "CAN 控制通道默认仅 CAN2", "enabled": True},
    {"label": "0x123 默认禁用", "enabled": True},
    {"label": "0x126 默认禁用", "enabled": True},
    {"label": "CANopen NMT 默认禁用", "enabled": True},
    {"label": "Mock 不伪装真实硬件", "enabled": True},
    {"label": "异常时执行安全停车", "enabled": True},
]


DEFAULT_CONFIG_HISTORY = [
    {"time": "2026-04-01 10:15:20", "user": "admin", "key": "手动控制速度上限", "old_value": "5", "new_value": "8", "reason": "台架调试", "result": "成功"},
    {"time": "2026-04-01 09:42:12", "user": "engineer01", "key": "报告目录", "old_value": r"D:\Old", "new_value": r"D:\TestLogs\Reports", "reason": "工位迁移", "result": "成功"},
    {"time": "2026-03-31 17:20:05", "user": "admin", "key": "0x121 发送周期", "old_value": "50 ms", "new_value": "20 ms", "reason": "方案版本升级", "result": "成功"},
    {"time": "2026-03-31 15:08:42", "user": "admin", "key": "MockCanGateway", "old_value": "开启", "new_value": "关闭", "reason": "接入真实台架", "result": "成功"},
]


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("failed to read config %s", path)
        return {}


def _display_time(value: Any) -> str:
    return str(value or "").replace("T", " ")[:19]


def _file_time(path: Path) -> str:
    if not path.exists():
        return _display_time(utc_now())
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def _dir_size_gb(path: Path) -> float:
    if not path.exists():
        return 0.0
    try:
        return round(sum(item.stat().st_size for item in path.rglob("*") if item.is_file()) / 1024 ** 3, 3)
    except OSError:
        return 0.0


def _runtime_data_paths() -> DataPaths:
    return state.data_paths or DataPaths.from_root(state.config.data_root)


def _disk_stats() -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(_runtime_data_paths().root)
        total = round(usage.total / 1024 ** 3, 1)
        used = round(usage.used / 1024 ** 3, 1)
        free = round(usage.free / 1024 ** 3, 1)
        percent = round(usage.used / usage.total * 100, 1) if usage.total else 0.0
        return {"disk_total_gb": total, "disk_used_gb": used, "disk_free_gb": free, "disk_used_percent": percent, "measurement_error": None}
    except OSError as exc:
        return {"disk_total_gb": 0.0, "disk_used_gb": 0.0, "disk_free_gb": 0.0, "disk_used_percent": 0.0, "measurement_error": str(exc)}


def _thresholds() -> list[dict[str, Any]]:
    source = _read_yaml(CONFIG_DIR / "thresholds.yaml")
    vehicle = source.get("vehicle", {})
    steering = source.get("steering", {})
    bms = source.get("bms", {})
    alarms = source.get("alarms", {})
    motor = source.get("motor", {})
    control = source.get("control", {})
    bms_total = bms.get("total_voltage_v", {})
    bms_temp = bms.get("ntc_temperature_c", {})
    cell_voltage = bms.get("cell_voltage_v", {})
    return [
        {"key": "control_period_ms", "label": "0x121 发送周期", "value": 20, "min": 10, "max": 100, "unit": "ms", "scope": "CAN/控制", "description": "默认主控制发送周期", "dangerous": False},
        {"key": "can_period_tolerance", "label": "CAN 周期容差", "value": 20, "min": 5, "max": 50, "unit": "%", "scope": "CAN/诊断", "description": "周期抖动允许比例", "dangerous": False},
        {"key": "frame_timeout_multiplier", "label": "报文超时倍数", "value": 3, "min": 1, "max": 10, "unit": "倍", "scope": "CAN/诊断", "description": "期望周期的超时倍数", "dangerous": False},
        {"key": "motor_heartbeat_timeout_ms", "label": "电机心跳超时", "value": motor.get("heartbeat_timeout_ms", 500), "min": 100, "max": 2000, "unit": "ms", "scope": "电机", "description": "0x703 / 0x704 离线阈值", "dangerous": False},
        {"key": "control_response_timeout_ms", "label": "控制响应时间", "value": control.get("command_response_timeout_ms", 500), "min": 100, "max": 2000, "unit": "ms", "scope": "控制", "description": "指令反馈最大响应时间", "dangerous": True},
        {"key": "safe_stop_timeout_ms", "label": "安全停车超时", "value": control.get("safe_stop_timeout_ms", 1500), "min": 500, "max": 5000, "unit": "ms", "scope": "安全", "description": "安全停车完成等待时间", "dangerous": True},
        {"key": "bms_voltage_min", "label": "BMS 总压最小值", "value": bms_total.get("min", 36.0), "min": 0, "max": 1000, "unit": "V", "scope": "BMS", "description": "总压有效下限", "dangerous": False},
        {"key": "bms_voltage_max", "label": "BMS 总压最大值", "value": bms_total.get("max", 72.0), "min": 1, "max": 1000, "unit": "V", "scope": "BMS", "description": "总压有效上限", "dangerous": False},
        {"key": "bms_soc_min", "label": "SOC 最低值", "value": bms.get("soc_percent_min", 30), "min": 0, "max": 100, "unit": "%", "scope": "BMS", "description": "允许检测的最低 SOC", "dangerous": True},
        {"key": "bms_temp_min", "label": "电池温度最小值", "value": bms_temp.get("min", -20), "min": -50, "max": 20, "unit": "°C", "scope": "BMS", "description": "NTC 有效下限", "dangerous": False},
        {"key": "bms_temp_max", "label": "电池温度最大值", "value": bms_temp.get("max", 60), "min": 20, "max": 100, "unit": "°C", "scope": "BMS", "description": "NTC 有效上限", "dangerous": True},
        {"key": "cell_voltage_min", "label": "单体电压最小值", "value": cell_voltage.get("min", 2.8), "min": 0, "max": 5, "unit": "V", "scope": "BMS", "description": "单体电压有效下限", "dangerous": False},
        {"key": "cell_voltage_max", "label": "单体电压最大值", "value": cell_voltage.get("max", 4.25), "min": 0, "max": 5, "unit": "V", "scope": "BMS", "description": "单体电压有效上限", "dangerous": True},
        {"key": "cell_delta_max_mv", "label": "单体压差最大值", "value": round(float(bms.get("cell_delta_v_max", 0.08)) * 1000), "min": 0, "max": 200, "unit": "mV", "scope": "BMS", "description": "单体最大允许压差", "dangerous": False},
        {"key": "manual_speed_limit", "label": "手动控制速度上限", "value": vehicle.get("manual_speed_limit_kmh", 3.0), "min": 0, "max": 8, "unit": "km/h", "scope": "安全", "description": "手动控制保守限速", "dangerous": True},
        {"key": "auto_speed_limit", "label": "自动检测速度上限", "value": vehicle.get("auto_test_drive_speed_kmh", 1.5), "min": 0, "max": 5, "unit": "km/h", "scope": "安全", "description": "一键检测低速限速", "dangerous": True},
        {"key": "front_steer_limit", "label": "前转角限幅", "value": steering.get("command_limit_default", 60), "min": -120, "max": 120, "unit": "raw", "scope": "转向", "description": "int8 补码控制值", "dangerous": True},
        {"key": "rear_steer_limit", "label": "后转角限幅", "value": steering.get("command_limit_default", 60), "min": -120, "max": 120, "unit": "raw", "scope": "转向", "description": "int8 补码控制值", "dangerous": True},
        {"key": "vehicle_speed_error", "label": "车速允许误差", "value": vehicle.get("vehicle_speed_error_kmh", 0.5), "min": 0, "max": 3, "unit": "km/h", "scope": "检测", "description": "目标与反馈允许误差", "dangerous": False},
        {"key": "steering_error", "label": "转角允许误差", "value": steering.get("feedback_error_cmd_units", 8), "min": 0, "max": 20, "unit": "raw", "scope": "检测", "description": "命令与反馈允许偏差", "dangerous": False},
        {"key": "wheel_speed_error", "label": "四轮轮速允许误差", "value": vehicle.get("wheel_speed_error_rpm", 30), "min": 0, "max": 100, "unit": "rpm", "scope": "检测", "description": "四轮反馈一致性阈值", "dangerous": False},
        {"key": "max_alarm_level", "label": "允许最大告警等级", "value": alarms.get("required_max_level_for_pass", 0), "min": 0, "max": 0, "unit": "level", "scope": "安全", "description": "检测与控制必须保持 Normal", "dangerous": True},
        {"key": "allow_warning_release", "label": "人工放行轻微告警", "value": alarms.get("allow_warning_release", False), "min": None, "max": None, "unit": "开关", "scope": "安全", "description": "默认关闭，启用需管理员", "dangerous": True},
    ]


def _config_history(limit: int = 8) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if state.database is not None:
        try:
            rows = state.database.query("SELECT * FROM config_history ORDER BY id DESC LIMIT ?", (limit,))
            items = [
                {"time": _display_time(row.get("timestamp_utc")), "user": row.get("operator") or "-", "key": row.get("config_key") or "-", "old_value": row.get("old_value") or "-", "new_value": row.get("new_value") or "-", "reason": row.get("reason") or "-", "result": "成功"}
                for row in rows
            ]
        except Exception:
            logger.exception("failed to read config history")
    return items[:limit]


def _audit_action(action: str, target: str, payload: dict[str, Any], result: str = "OK", changes: list[dict[str, Any]] | None = None, principal: Principal | None = None) -> None:
    actor = principal or Principal("system", Role.ADMIN)
    if state.database is None:
        state.db_writable = False
        raise HTTPException(
            503,
            {
                "code": "AUDIT_UNAVAILABLE",
                "message": "配置操作审计数据库不可用，操作已拒绝",
                "details": {"action": action, "blocking": True},
            },
        )
    try:
        with state.database.transaction() as conn:
            conn.execute(
                "INSERT INTO operator_actions(timestamp_utc, operator, role, action_type, target, request_json, result, trace_id) VALUES (?,?,?,?,?,?,?,?)",
                (utc_now(), actor.username, actor.role.value, action, target, json.dumps(payload, ensure_ascii=False, default=str), result, get_trace_id()),
            )
            for item in changes or []:
                conn.execute(
                    "INSERT INTO config_history(timestamp_utc, operator, config_key, old_value, new_value, reason, config_hash) VALUES (?,?,?,?,?,?,?)",
                    (utc_now(), actor.username, item["key"], str(item.get("old_value", "")), str(item.get("new_value", "")), payload.get("reason", action), ""),
                )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("failed to audit config action")
        state.db_writable = False
        raise HTTPException(
            503,
            {
                "code": "AUDIT_UNAVAILABLE",
                "message": "配置操作审计写入失败，操作已拒绝",
                "details": {"action": action, "error_type": type(exc).__name__, "blocking": True},
            },
        ) from exc


async def _broadcast(topic: str, payload: dict[str, Any]) -> None:
    ws = getattr(state, "ws", None)
    if ws is not None:
        await ws.broadcast(topic, payload)


def _atomic_write_settings(payload: dict[str, Any]) -> None:
    SYSTEM_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = SYSTEM_SETTINGS_PATH.with_suffix(".yaml.tmp")
    backup_path = SYSTEM_SETTINGS_PATH.with_suffix(".yaml.bak")
    if SYSTEM_SETTINGS_PATH.exists():
        shutil.copy2(SYSTEM_SETTINGS_PATH, backup_path)
    temp_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    yaml.safe_load(temp_path.read_text(encoding="utf-8"))
    os.replace(temp_path, SYSTEM_SETTINGS_PATH)


def _channel_profile_path(profile: str) -> Path:
    return CONFIG_DIR / ("channels.yaml" if profile == "production" else f"channels.{profile}.yaml")


def _stage_channel_profile(config: RuntimeConfig) -> tuple[Path, Path]:
    target = _channel_profile_path(config.profile)
    staged = target.with_suffix(target.suffix + ".tmp")
    payload = {
        "runtime_profile": config.profile,
        "channels": {
            item.channel: {
                "enabled": item.enabled,
                "protocol": item.protocol,
                "local_ip": item.local_ip,
                "local_receive_port": item.local_receive_port,
                "device_ip": item.device_ip,
                "device_port": item.device_port,
                "simulated_device_port": item.simulated_device_port,
                "control_enabled": item.control_enabled,
                "receive_queue_size": item.receive_queue_size,
                "max_frame_age_ms": item.max_frame_age_ms,
            }
            for item in config.channels
        },
    }
    staged.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    yaml.safe_load(staged.read_text(encoding="utf-8"))
    return target, staged


async def _start_enabled_channels(manager, config: RuntimeConfig) -> list[dict[str, Any]]:
    statuses = []
    for item in config.channels:
        if item.enabled:
            statuses.append(await manager.start_channel(item.channel))
    return statuses


async def _restore_manager(old_config: RuntimeConfig, old_manager) -> None:
    state.config = old_config
    state.can = old_manager
    if old_manager is None:
        return
    try:
        await _start_enabled_channels(old_manager, old_config)
    except Exception:
        logger.exception("failed to restore previous CAN manager after reconfiguration error")


def _validate_ip(value: str, field: str) -> None:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise HTTPException(422, {"code": "INVALID_IP", "message": f"{field} 不是有效 IP 地址", "details": {"value": value}, "trace_id": ""}) from exc


def _validate_port(value: int, field: str) -> None:
    if not 1 <= int(value) <= 65535:
        raise HTTPException(422, {"code": "INVALID_PORT", "message": f"{field} 必须在 1..65535", "details": {"value": value}, "trace_id": ""})


def _normalize_channels(payload: dict[str, Any]) -> list[dict[str, Any]]:
    channels = payload.get("channels")
    if not isinstance(channels, list) or not channels:
        raise HTTPException(422, {"code": "INVALID_CHANNELS", "message": "channels 必须是非空数组", "details": {}, "trace_id": ""})
    normalized: list[dict[str, Any]] = []
    for item in channels:
        name = str(item.get("name") or item.get("channel") or "").upper()
        if name not in {"CAN1", "CAN2"}:
            raise HTTPException(422, {"code": "INVALID_CHANNEL", "message": "仅支持 CAN1/CAN2", "details": {"name": name}, "trace_id": ""})
        protocol = str(item.get("protocol") or "UDP").upper()
        if protocol not in {"UDP", "TCP"}:
            raise HTTPException(422, {"code": "INVALID_PROTOCOL", "message": "协议必须是 UDP 或 TCP", "details": {"protocol": protocol}, "trace_id": ""})
        local_ip = str(item.get("local_ip") or DEFAULT_NETWORK_CONFIG["local_network"]["host_ip"])
        device_ip = str(item.get("device_ip") or "")
        local_port = int(item.get("local_port") or 0)
        device_port = int(item.get("device_port") or 0)
        _validate_ip(local_ip, f"{name}.local_ip")
        _validate_ip(device_ip, f"{name}.device_ip")
        _validate_port(local_port, f"{name}.local_port")
        _validate_port(device_port, f"{name}.device_port")
        normalized.append({"name": name, "protocol": protocol, "local_ip": local_ip, "local_port": local_port, "device_ip": device_ip, "device_port": device_port, "enabled": bool(item.get("enabled", True)), "rx_status": str(item.get("rx_status") or "active"), "period_ms": int(item.get("period_ms") or 20), "control_enabled": bool(item.get("control_enabled", False)), "status": str(item.get("status") or "active")})
    if sum(1 for item in normalized if item["control_enabled"]) > 1:
        raise HTTPException(409, {"code": "MULTIPLE_CONTROL_CHANNELS", "message": "不能同时启用多个控制通道", "details": {"channels": [item["name"] for item in normalized if item["control_enabled"]]}, "trace_id": ""})
    return normalized


def _dbc_dashboard() -> dict[str, Any]:
    raw = state.dbc.status() if state.dbc else {"loaded": False, "raw_only": True, "file": "", "hash": "", "version": "raw-only", "error": "DBC 服务未初始化"}
    messages = state.dbc.messages() if state.dbc else []
    dbc_path = Path(str(raw.get("file"))) if raw.get("file") else None
    filename = dbc_path.name if dbc_path else None
    status = "loaded" if raw.get("loaded") else "raw-only" if raw.get("raw_only") else "failed"
    return {
        "filename": filename,
        "version": raw.get("version") if raw.get("loaded") else None,
        "hash": str(raw.get("hash")) if raw.get("hash") else None,
        "status": status,
        "error": raw.get("error") or (None if raw.get("loaded") else "DBC 未加载"),
        "message_count": len(messages),
        "signal_count": sum(len(item.get("signals", [])) for item in messages),
        "loaded_at": (
            datetime.fromtimestamp(dbc_path.stat().st_mtime, tz=timezone.utc).isoformat()
            if dbc_path and dbc_path.is_file()
            else None
        ),
        "overrides": deepcopy(DBC_OVERRIDES),
    }


def _storage_dashboard() -> dict[str, Any]:
    storage_doc = _read_yaml(CONFIG_DIR / "storage_config.yaml")
    report_doc = _read_yaml(CONFIG_DIR / "report_config.yaml")
    retention = storage_doc.get("retention", {})
    report_cfg = report_doc.get("report", {})
    paths = _runtime_data_paths()
    data = {
        "data_root": str(paths.root),
        "report_directory": str(paths.reports),
        "raw_can_directory": str(paths.raw_can),
        "decoded_signal_directory": str(paths.decoded_signals),
        "database_path": str(paths.database),
        "retention_days": retention.get("raw_can_days", 180),
        "max_log_gb": 50,
        "auto_cleanup": False,
        "word_enabled": bool(report_cfg.get("generate_docx", True)),
        "pdf_enabled": bool(report_cfg.get("generate_pdf", True)),
        "csv_enabled": bool(report_cfg.get("generate_csv_summary", True)),
        "parquet_enabled": storage_doc.get("decoded_signal_logging", {}).get("format") == "parquet",
        **_disk_stats(),
    }
    return data


def _system_version() -> dict[str, Any]:
    package_path = PROJECT_ROOT / "desktop" / "package.json"
    package = json.loads(package_path.read_text(encoding="utf-8")) if package_path.exists() else {}
    electron = package.get("devDependencies", {}).get("electron", package.get("dependencies", {}).get("electron", "compatible"))
    release = load_release_metadata()
    return {
        "software": release.software_version or state.config.software_version,
        "config": state.config.config_version,
        "test_plan": state.config.test_plan_version,
        "python": platform.python_version(),
        "node": f"构建依赖 {package.get('engines', {}).get('node')}" if package.get("engines", {}).get("node") else "不适用",
        "electron": electron,
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        "build_time": release.built_at_utc,
        "commit": release.commit,
        "dirty": release.dirty,
        "release_commit": release.commit,
        "release_hash": release.manifest_sha256,
        "release_label": release.release_label,
        "signed": release.signed,
        "formal_release": release.formal_release,
        "source_dirty": release.dirty,
        "metadata_error": release.error,
    }


def _merge_saved(dashboard: dict[str, Any]) -> None:
    saved = _read_yaml(SYSTEM_SETTINGS_PATH)
    for section in ("basic", "storage"):
        if isinstance(saved.get(section), dict):
            dashboard[section].update(saved[section])
    saved_thresholds = {item.get("key"): item for item in saved.get("thresholds", []) if isinstance(item, dict)}
    for item in dashboard["thresholds"]:
        if item["key"] in saved_thresholds:
            item.update(saved_thresholds[item["key"]])


def _storage_summary() -> dict[str, Any]:
    paths = _runtime_data_paths()
    last_cleanup = None
    if state.database is not None:
        try:
            row = state.database.query_one(
                "SELECT completed_at,status FROM cleanup_jobs ORDER BY created_at DESC LIMIT 1"
            )
            last_cleanup = row.get("completed_at") if row else None
            cleanup_status = row.get("status") if row else "not-run"
        except Exception:
            cleanup_status = "unavailable"
    else:
        cleanup_status = "unavailable"
    healthy = bool(getattr(getattr(state, "storage_health", None), "last", {}).get("healthy", state.db_writable))
    return {
        "current_log_gb": round(_dir_size_gb(paths.app_logs) + _dir_size_gb(paths.decoded_signals), 3),
        "database_gb": round(paths.database.stat().st_size / 1024 ** 3, 4) if paths.database.exists() else 0.0,
        "reports_gb": _dir_size_gb(paths.reports),
        "raw_can_gb": _dir_size_gb(paths.raw_can),
        "last_cleanup": last_cleanup or "-",
        "next_cleanup": "manual-confirmation-required",
        "cleanup_status": cleanup_status,
        "disk_alarm": "normal" if healthy else "critical",
    }


def _system_dashboard() -> dict[str, Any]:
    channels = _read_yaml(CONFIG_DIR / "channels.yaml")
    station = _read_yaml(CONFIG_DIR / "station.yaml")
    station_info = station.get("station", {})
    software = station.get("software", {})
    ipc = channels.get("ipc", {})
    storage = _storage_dashboard()
    basic = {
        "station_id": station_info.get("id", state.config.station_id),
        "host_ip": ipc.get("ip", "127.0.0.1"),
        "control_channel": channels.get("control", {}).get("default_control_channel", state.config.control_channel),
        "report_directory": storage["report_directory"],
        "database_path": storage["database_path"],
        "log_directory": str(_runtime_data_paths().app_logs),
        "timezone": "UTC+08:00" if software.get("timezone", "Asia/Shanghai") == "Asia/Shanghai" else software.get("timezone"),
        "language": "zh-CN",
        "auto_save": True,
    }
    dashboard = {
        **dashboard_metadata(
            "yaml+runtime+filesystem",
            quality="good",
            mock=state.mock_enabled,
        ),
        "save_state": {"dirty": False, "last_saved_at": _file_time(SYSTEM_SETTINGS_PATH), "status": "saved"},
        "runtime_profile": state.config.profile,
        "configuration_authority": "signed-package" if state.config.profile == "production" else "direct-development",
        "auth": {"current_user": state.config.operator, "current_role": state.current_role},
        "basic": basic,
        "dbc": _dbc_dashboard(),
        "storage": storage,
        "thresholds": _thresholds(),
        "roles": deepcopy(ROLES),
        "maintenance": {"maintenance_mode": state.maintenance_mode, **deepcopy(state.maintenance_features), "requires_admin": True},
        "safe_defaults": deepcopy(SAFE_DEFAULTS),
        "version": _system_version(),
        "storage_trend": [{"date": utc_now()[:10], "used_gb": _disk_stats()["disk_used_gb"], "source": "current-measurement"}],
        "storage_summary": _storage_summary(),
        "config_history": _config_history(),
        "hardware_acceptance": (
            state.hardware_acceptance.evaluate()
            if state.hardware_acceptance
            else {
                "allowed": False,
                "applicable": state.config.profile == "production",
                "status": "unavailable",
                "artifact": None,
                "rules": [],
                "reasons": [],
            }
        ),
    }
    _merge_saved(dashboard)
    paths = _runtime_data_paths()
    dashboard["storage"].update({
        "data_root": str(paths.root),
        "report_directory": str(paths.reports),
        "raw_can_directory": str(paths.raw_can),
        "decoded_signal_directory": str(paths.decoded_signals),
        "database_path": str(paths.database),
        "auto_cleanup": False,
    })
    dashboard["basic"].update({
        "report_directory": str(paths.reports),
        "database_path": str(paths.database),
        "log_directory": str(paths.app_logs),
    })
    dashboard["maintenance"]["mock_can_gateway"] = state.mock_enabled
    return dashboard


def _changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    for section in ("basic", "storage"):
        for key, value in after.get(section, {}).items():
            old = before.get(section, {}).get(key)
            if old != value:
                changed.append({"key": f"{section}.{key}", "old_value": old, "new_value": value})
    before_thresholds = {item["key"]: item.get("value") for item in before.get("thresholds", [])}
    for item in after.get("thresholds", []):
        if before_thresholds.get(item["key"]) != item.get("value"):
            changed.append({"key": f"thresholds.{item['key']}", "old_value": before_thresholds.get(item["key"]), "new_value": item.get("value")})
    return changed


def _require_admin(principal: Principal) -> None:
    if principal.role is not Role.ADMIN:
        raise HTTPException(403, {"code": "ADMIN_REQUIRED", "message": "该操作需要服务端认证的管理员身份", "details": {"actual_role": principal.role.value}, "trace_id": ""})


@router.get("/config/system-dashboard", response_model=SystemDashboardResponse)
async def system_dashboard(_principal: Principal = Depends(require_role(Role.VIEWER))):
    payload = _system_dashboard()
    payload["auth"] = {"current_user": _principal.username, "current_role": _principal.role.value}
    return payload


@router.get("/config")
async def get_config(_principal: Principal = Depends(require_role(Role.VIEWER))):
    return state.config.model_dump()


@router.put("/config")
async def put_config(payload: SystemConfigUpdate, principal: Principal = Depends(require_role(Role.ENGINEER))):
    if state.config.profile == "production":
        _audit_action(
            "save_system_config_rejected",
            "config.system",
            {"code": "SIGNED_CONFIG_REQUIRED"},
            result="REJECTED",
            principal=principal,
        )
        raise HTTPException(
            409,
            {
                "code": "SIGNED_CONFIG_REQUIRED",
                "message": "生产配置只能通过已签名配置包预检并应用",
                "details": {"required_flow": ["import", "dry-run", "admin-confirm", "apply"], "blocking": True},
            },
        )
    current = _system_dashboard()
    data = payload.model_dump(exclude_none=True)
    data.pop("role", None)
    paths = _runtime_data_paths()
    managed_paths = {
        "basic.report_directory": str(paths.reports),
        "basic.database_path": str(paths.database),
        "basic.log_directory": str(paths.app_logs),
        "storage.report_directory": str(paths.reports),
        "storage.raw_can_directory": str(paths.raw_can),
        "storage.decoded_signal_directory": str(paths.decoded_signals),
        "storage.database_path": str(paths.database),
    }
    supplied = {
        **({f"basic.{key}": value for key, value in payload.basic.model_dump(exclude_none=True).items()} if payload.basic else {}),
        **({f"storage.{key}": value for key, value in payload.storage.model_dump(exclude_none=True).items()} if payload.storage else {}),
    }
    invalid_paths = {
        key: {"supplied": value, "required": managed_paths[key]}
        for key, value in supplied.items()
        if key in managed_paths and str(Path(str(value)).resolve(strict=False)) != str(Path(managed_paths[key]).resolve(strict=False))
    }
    if invalid_paths:
        raise HTTPException(
            422,
            {
                "code": "DERIVED_STORAGE_PATH_IMMUTABLE",
                "message": "database, log and report paths are derived from signed data_root and cannot be edited independently",
                "details": invalid_paths,
            },
        )
    if payload.storage and payload.storage.auto_cleanup:
        raise HTTPException(
            422,
            {
                "code": "UNATTENDED_CLEANUP_FORBIDDEN",
                "message": "cleanup requires an administrator dry-run and explicit confirmation",
                "details": {},
            },
        )
    if payload.control_channels and len(set(payload.control_channels)) > 1:
        raise HTTPException(409, {"code": "MULTIPLE_CONTROL_CHANNELS", "message": "不能同时启用两个控制通道", "details": {"channels": payload.control_channels}, "trace_id": ""})
    dangerous_thresholds = []
    for item in payload.thresholds or []:
        if not isinstance(item.value, bool):
            value = float(item.value)
            if item.min is not None and value < item.min or item.max is not None and value > item.max:
                raise HTTPException(422, {"code": "THRESHOLD_OUT_OF_RANGE", "message": f"{item.label or item.key} 超出允许范围", "details": {"key": item.key, "value": item.value, "min": item.min, "max": item.max}, "trace_id": ""})
        if item.key == "max_alarm_level" and float(item.value) > 0:
            raise HTTPException(422, {"code": "UNSAFE_ALARM_THRESHOLD", "message": "允许最大告警等级不得高于 0 Normal", "details": {"value": item.value}, "trace_id": ""})
        if item.dangerous:
            dangerous_thresholds.append(item.key)
    if dangerous_thresholds:
        _require_admin(principal)
        if len(payload.reason.strip()) < 2:
            raise HTTPException(422, {"code": "CHANGE_REASON_REQUIRED", "message": "危险参数变更必须填写原因", "details": {"keys": dangerous_thresholds}, "trace_id": ""})
    if payload.maintenance:
        requested = payload.maintenance.model_dump()
        if requested.get("dual_control_channel_allowed"):
            raise HTTPException(409, {"code": "DUAL_CONTROL_FORBIDDEN", "message": "双控制通道永久禁止", "details": {}, "trace_id": ""})
        dangerous = any(requested[key] for key in ("enable_0x123", "enable_0x126", "allow_canopen_nmt", "enable_pid_debug"))
        if dangerous and not state.maintenance_mode:
            raise HTTPException(409, {"code": "MAINTENANCE_MODE_REQUIRED", "message": "非维护模式不能启用危险扩展功能", "details": {}, "trace_id": ""})
        if dangerous:
            _require_admin(principal)
    saved = {
        "basic": current["basic"] | (payload.basic.model_dump(exclude_none=True) if payload.basic else {}),
        "storage": current["storage"] | (payload.storage.model_dump(exclude_none=True) if payload.storage else {}),
        "thresholds": [item.model_dump() for item in payload.thresholds] if payload.thresholds is not None else current["thresholds"],
        "maintenance": payload.maintenance.model_dump() if payload.maintenance else current["maintenance"],
    }
    changed = _changes(current, saved)
    _atomic_write_settings(saved)
    if payload.basic:
        update = payload.basic.model_dump(exclude_none=True)
        state.config.station_id = update.get("station_id", state.config.station_id)
        state.config.control_channel = update.get("control_channel", state.config.control_channel)
    _audit_action("save_system_config", "config.system", data, changes=changed, principal=principal)
    response = {"ok": True, "saved": True, "changed_items": changed, "requires_restart": any(item["key"] in {"basic.database_path", "basic.log_directory", "storage.database_path"} for item in changed), "requires_can_reconnect": any(item["key"] in {"basic.host_ip", "basic.control_channel"} for item in changed), "requires_dbc_reload": False, "message": "配置已校验并原子保存"}
    await _broadcast("system.config_changed", response)
    return response


@router.post("/config/import")
async def import_config(payload: ConfigImportRequest, principal: Principal = Depends(require_role(Role.ADMIN))):
    try:
        validate_signed_package(payload.package, state.config.profile)
        checks = configuration_preflight(state, payload.package.configuration)
    except ConfigurationLifecycleError as exc:
        _audit_action("config_import_rejected", "config.package", {"code": exc.code}, result="REJECTED", principal=principal)
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.message, "details": exc.details}) from exc
    blocking = [item for item in checks if item["blocking"] and not item["passed"]]
    result = {
        "ok": not blocking,
        "dry_run": True,
        "signature_valid": True,
        "schema_valid": True,
        "compatible": not blocking,
        "summary": package_summary(payload.package),
        "diff": package_diff(state.config, payload.package),
        "health_checks": checks,
        "blocking_checks": blocking,
        "message": "配置包已完成签名、schema、版本、差异和健康预检；尚未应用" if not blocking else "配置包预检存在阻断项，禁止应用",
    }
    _audit_action(
        "config_import_dry_run",
        "config.package",
        {"summary": result["summary"], "blocking_rules": [item["rule"] for item in blocking]},
        result="OK" if not blocking else "REJECTED",
        principal=principal,
    )
    return result


@router.get("/config/export")
async def export_config(principal: Principal = Depends(require_role(Role.ADMIN))):
    try:
        package = export_signed_package(state.config, principal.username)
    except ConfigurationLifecycleError as exc:
        _audit_action("config_export_rejected", "config.package", {"code": exc.code}, result="REJECTED", principal=principal)
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.message, "details": exc.details}) from exc
    summary = package_summary(package)
    _audit_action("config_export_signed", "config.package", summary, principal=principal)
    return {
        "ok": True,
        "format": "json",
        "filename": f"chassis-config-{summary['config_version']}-{utc_now()[:10]}.json",
        "package": package.model_dump(mode="json"),
        "summary": summary,
        "message": "已生成与当前运行配置一致的签名配置包",
    }


@router.post("/config/apply")
async def apply_config(payload: ConfigApplyRequest, principal: Principal = Depends(require_role(Role.ADMIN))):
    summary = package_summary(payload.package)
    try:
        validate_signed_package(payload.package, state.config.profile)
    except ConfigurationLifecycleError as exc:
        _audit_action("config_apply_rejected", "config.package", {"summary": summary, "code": exc.code}, result="REJECTED", principal=principal)
        raise HTTPException(exc.status_code, {"code": exc.code, "message": exc.message, "details": exc.details}) from exc
    checks = configuration_preflight(state, payload.package.configuration)
    blocking = [item for item in checks if item["blocking"] and not item["passed"]]
    if blocking:
        _audit_action("config_apply_rejected", "config.package", {"summary": summary, "blocking_rules": [item["rule"] for item in blocking], "reason": payload.reason}, result="REJECTED", principal=principal)
        raise HTTPException(409, {"code": "CONFIG_HEALTH_CHECK_FAILED", "message": "配置包健康预检失败，未执行应用", "details": {"checks": checks}})

    _audit_action(
        "config_apply_authorized",
        "config.package",
        {"summary": summary, "reason": payload.reason},
        result="AUTHORIZED",
        principal=principal,
    )

    old_config = state.config
    old_manager = state.can
    active_path = active_package_path()
    previous_package = active_path.read_bytes() if active_path.exists() else None
    new_config = runtime_from_package(old_config, payload.package)
    from app.can_gateway.manager import CanGatewayManager
    from app.services.lifecycle import on_can_security_event, on_frame

    new_manager = CanGatewayManager(new_config, on_frame, on_can_security_event)
    try:
        if state.tx_scheduler:
            await state.tx_scheduler.stop()
        if old_manager:
            await old_manager.stop_all()
        state.config = new_config
        state.can = new_manager
        await _start_enabled_channels(new_manager, new_config)
        post_status = new_manager.status()
        failed_transports = [item["channel"] for item in post_status if not item.get("transport_connected")]
        if failed_transports:
            raise RuntimeError(f"transport did not start: {failed_transports}")
        if new_config.profile == "production":
            deadline = asyncio.get_running_loop().time() + new_config.channel_online_timeout_seconds
            while asyncio.get_running_loop().time() < deadline:
                post_status = new_manager.status()
                if all(item.get("online") for item in post_status if item.get("enabled", True)):
                    break
                await asyncio.sleep(0.05)
            unavailable = [item["channel"] for item in new_manager.status() if item.get("enabled", True) and not item.get("online")]
            if unavailable:
                raise RuntimeError(f"approved-source receive health check failed: {unavailable}")
        post_checks = configuration_post_apply_health(state, payload.package.configuration)
        post_blocking = [
            item for item in post_checks if item.get("blocking") and not item.get("passed")
        ]
        if post_blocking:
            raise RuntimeError(
                "post-apply blocking health failed: "
                + ",".join(str(item.get("rule")) for item in post_blocking)
            )
        persist_active_package(payload.package)
        changed = package_diff(old_config, payload.package)
        _audit_action(
            "config_apply_succeeded",
            "config.package",
            {
                "summary": summary,
                "reason": payload.reason,
                "requires_restart": old_config.data_root != new_config.data_root,
            },
            changes=[
                {
                    "key": item["path"],
                    "old_value": item["current"],
                    "new_value": item["proposed"],
                }
                for item in changed
            ],
            principal=principal,
        )
    except Exception as exc:
        await new_manager.stop_all()
        await _restore_manager(old_config, old_manager)
        restore_active_package(previous_package)
        try:
            _audit_action("config_apply_rolled_back", "config.package", {"summary": summary, "reason": payload.reason, "error_type": type(exc).__name__}, result="ROLLED_BACK", principal=principal)
        except HTTPException:
            logger.exception("configuration rollback audit was unavailable")
        if isinstance(exc, HTTPException) and isinstance(exc.detail, dict) and exc.detail.get("code") == "AUDIT_UNAVAILABLE":
            raise exc
        raise HTTPException(503, {"code": "CONFIG_APPLY_ROLLED_BACK", "message": "配置应用或健康检查失败，已回滚运行配置和持久化配置包", "details": {"error_type": type(exc).__name__}}) from exc

    response = {
        "ok": True,
        "applied": True,
        "rolled_back": False,
        "summary": summary,
        "diff": changed,
        "health_checks": post_checks,
        "requires_restart": old_config.data_root != new_config.data_root,
        "message": "签名配置包已应用并完成通道启动健康检查",
    }
    await _broadcast("system.config_changed", response)
    await _broadcast("can.channel_status", state.can.status())
    return response


@router.get("/config/history")
async def config_history(_principal: Principal = Depends(require_role(Role.VIEWER))):
    return _config_history(100)


@router.post("/config/restore-safe-defaults")
async def restore_safe_defaults(payload: RestoreSafeDefaultsRequest, principal: Principal = Depends(require_role(Role.ADMIN))):
    if state.config.profile == "production":
        _audit_action(
            "restore_safe_defaults_rejected",
            "config.safety",
            {"code": "SIGNED_CONFIG_REQUIRED"},
            result="REJECTED",
            principal=principal,
        )
        raise HTTPException(
            409,
            {
                "code": "SIGNED_CONFIG_REQUIRED",
                "message": "生产安全配置只能通过已签名配置包预检并应用",
                "details": {"blocking": True},
            },
        )
    if payload.confirmation != "RESTORE":
        raise HTTPException(422, {"code": "CONFIRMATION_MISMATCH", "message": "请输入 RESTORE 确认恢复安全默认", "details": {}, "trace_id": ""})
    before = _system_dashboard()
    state.maintenance_mode = False
    state.mock_enabled = False
    state.maintenance_features = {key: False for key in state.maintenance_features}
    state.config.control_channel = "CAN2"
    state.config.manual_speed_limit_kmh = 3.0
    state.config.steering_limit_default = 60
    thresholds = before["thresholds"]
    safe_values = {"manual_speed_limit": 3.0, "auto_speed_limit": 1.5, "front_steer_limit": 60, "rear_steer_limit": 60, "max_alarm_level": 0, "allow_warning_release": False, "control_period_ms": 20}
    for item in thresholds:
        if item["key"] in safe_values:
            item["value"] = safe_values[item["key"]]
    saved = {"basic": before["basic"] | {"control_channel": "CAN2"}, "storage": before["storage"], "thresholds": thresholds, "maintenance": {"maintenance_mode": False, **state.maintenance_features}}
    _atomic_write_settings(saved)
    changed = [{"key": key, "old_value": "custom", "new_value": value} for key, value in safe_values.items()] + [{"key": "maintenance.dangerous_features", "old_value": "custom", "new_value": "全部关闭"}]
    request = payload.model_dump(exclude={"role"})
    _audit_action("restore_safe_defaults", "config.safety", request, changes=changed, principal=principal)
    response = {"ok": True, "restored": True, "changed_items": changed, "message": "安全参数已恢复，工位号与存储路径保持不变"}
    await _broadcast("system.config_changed", response)
    await _broadcast("system.maintenance_changed", {"maintenance_mode": False, **state.maintenance_features})
    return response


@router.get("/config/channels", response_model=ChannelSettingsResponse)
async def channels_config(_principal: Principal = Depends(require_role(Role.VIEWER))):
    diagnostic = await diagnose_network(state)
    adapter_check = (
        adapter_identity_check(runtime_configuration(state.config))
        if state.config.profile == "production"
        else None
    )
    diagnostic_by_channel = {item["channel"]: item for item in diagnostic["channels"]}
    channels = [
        {
            "name": item.channel,
            "protocol": item.protocol.upper(),
            "local_ip": item.local_ip,
            "local_port": item.local_receive_port,
            "device_ip": item.device_ip,
            "device_port": item.simulated_device_port or item.device_port,
            "enabled": item.enabled,
            "rx_status": diagnostic_by_channel.get(item.channel, {}).get("endpoint_status", "unconfirmed"),
            "period_ms": 20,
            "control_enabled": item.control_enabled,
            "status": "active" if item.enabled else "disabled",
            "bind_status": diagnostic_by_channel.get(item.channel, {}).get("bind_status", "not_diagnosed"),
            "last_frame_age_ms": diagnostic_by_channel.get(item.channel, {}).get("last_frame_age_ms"),
            "tcp_state": diagnostic_by_channel.get(item.channel, {}).get("tcp_state", "not_applicable"),
            "source_allowlist_enforced": diagnostic_by_channel.get(item.channel, {}).get("source_allowlist_enforced", False),
            "approved_sources": diagnostic_by_channel.get(item.channel, {}).get("approved_sources", []),
        }
        for item in state.config.channels
    ]
    local_ip = state.config.channels[0].local_ip if state.config.channels else "127.0.0.1"
    ports = [
        {
            "port": item.local_receive_port,
            "protocol": item.protocol.upper(),
            "status": diagnostic_by_channel.get(item.channel, {}).get("bind_status", "not_diagnosed"),
        }
        for item in state.config.channels
    ]
    return {
        "local_network": {
            "host_ip": local_ip,
            "dev_ip": "127.0.0.1" if ipaddress.ip_address(local_ip).is_loopback else "not-applicable",
            "nic_name": state.config.network_interface_name,
            "adapter_index": state.config.network_interface_index,
            "mac_address": state.config.network_interface_mac,
            "bind_address": local_ip,
            "adapter_identity_status": (
                "matched" if adapter_check and adapter_check["passed"] else "drift"
                if adapter_check
                else "not_applicable"
            ),
            "adapter_identity_rule": adapter_check,
            "subnet_mask": "not-measured",
            "link_speed": "not-measured",
            "ports": ports,
            "diagnostic_source": diagnostic["data_source"],
            "diagnosed_at": diagnostic["updated_at"],
        },
        "channels": channels,
        "runtime_profile": state.config.profile,
        "configuration_authority": "signed-package" if state.config.profile == "production" else "direct-development",
        "read_only": state.config.profile == "production",
        "active_transmit_policy": {
            "control_channel": "CAN2",
            "allowed_can_ids": ["0x121"],
            "can1_transmit_locked": True,
            "configurable": False,
        },
        "trace_id": get_trace_id(),
    }


@router.put("/config/channels", response_model=ChannelSettingsResponse)
async def update_channels(payload: ChannelSettingsUpdateRequest, principal: Principal = Depends(require_role(Role.ADMIN))):
    if state.config.profile == "production":
        _audit_action(
            "update_channels_rejected",
            "config.channels",
            {"code": "SIGNED_CONFIG_REQUIRED"},
            result="REJECTED",
            principal=principal,
        )
        raise HTTPException(
            409,
            {
                "code": "SIGNED_CONFIG_REQUIRED",
                "message": "生产环境通道配置只能通过已签名配置包导入、预检并应用",
                "details": {"required_flow": ["import", "dry-run", "admin-confirm", "apply"], "blocking": True},
            },
        )
    payload_data = payload.model_dump()
    channels = _normalize_channels(payload_data)
    if state.config.profile != "production" and any(not ipaddress.ip_address(item["local_ip"]).is_loopback or not ipaddress.ip_address(item["device_ip"]).is_loopback for item in channels):
        raise HTTPException(409, {"code": "PROFILE_NETWORK_BOUNDARY", "message": "开发/Mock profile 只允许 loopback 地址", "details": {"profile": state.config.profile}})
    old_by_name = {item.channel: item for item in state.config.channels}
    channel_models = []
    for item in channels:
        previous = old_by_name.get(item["name"])
        channel_models.append(
            ChannelConfig(
                channel=item["name"],
                protocol=item["protocol"].lower(),
                local_ip=item["local_ip"],
                local_receive_port=item["local_port"],
                device_ip=item["device_ip"],
                device_port=item["device_port"],
                simulated_device_port=item["device_port"] if state.config.profile != "production" else None,
                enabled=item["enabled"],
                control_enabled=item["control_enabled"],
                receive_queue_size=previous.receive_queue_size if previous else 512,
                max_frame_age_ms=previous.max_frame_age_ms if previous else 500,
            )
        )
    control_channel = next((item["name"] for item in channels if item["control_enabled"]), state.config.control_channel)
    new_config = RuntimeConfig.model_validate(
        {**state.config.model_dump(), "channels": [item.model_dump() for item in channel_models], "control_channel": control_channel}
    )
    target, staged = _stage_channel_profile(new_config)
    old_config = state.config
    old_manager = state.can
    from app.can_gateway.manager import CanGatewayManager
    from app.services.lifecycle import on_can_security_event, on_frame

    new_manager = CanGatewayManager(new_config, on_frame, on_can_security_event)
    try:
        if state.tx_scheduler:
            await state.tx_scheduler.stop()
        if old_manager:
            await old_manager.stop_all()
        state.config = new_config
        state.can = new_manager
        await _start_enabled_channels(new_manager, new_config)
        if target.exists():
            shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
        os.replace(staged, target)
    except Exception as exc:
        await new_manager.stop_all()
        await _restore_manager(old_config, old_manager)
        staged.unlink(missing_ok=True)
        raise HTTPException(
            503,
            {
                "code": "CHANNEL_RECONFIGURE_FAILED",
                "message": "通道配置未生效，已回滚到上一运行配置",
                "details": {"error_type": type(exc).__name__, "protocols": {item["name"]: item["protocol"] for item in channels}},
            },
        ) from exc
    response = {
        "saved": True,
        "reconnected": True,
        "message": "通道配置已原子保存并按所选协议重新连接",
        "local_network": payload_data.get("local_network") or DEFAULT_NETWORK_CONFIG["local_network"],
        "channels": channels,
        "runtime_profile": new_config.profile,
        "configuration_authority": "direct-development",
        "read_only": False,
        "active_transmit_policy": {
            "control_channel": "CAN2",
            "allowed_can_ids": ["0x121"],
            "can1_transmit_locked": True,
            "configurable": False,
        },
        "trace_id": get_trace_id(),
    }
    _audit_action("update_channels", "config.channels", response, changes=[{"key": "channels", "old_value": "runtime", "new_value": channels}], principal=principal)
    await _broadcast("system.config_changed", response)
    await _broadcast("can.channel_status", state.can.status())
    return response


@router.post("/config/channels/restore-defaults", response_model=ChannelSettingsResponse)
async def restore_channels_defaults(principal: Principal = Depends(require_role(Role.ADMIN))):
    if state.config.profile == "production":
        _audit_action(
            "restore_channels_defaults_rejected",
            "config.channels",
            {"code": "SIGNED_CONFIG_REQUIRED"},
            result="REJECTED",
            principal=principal,
        )
        raise HTTPException(
            409,
            {
                "code": "SIGNED_CONFIG_REQUIRED",
                "message": "生产环境不能通过普通接口恢复通道默认值，请应用已签名配置包",
                "details": {"blocking": True},
            },
        )
    host_ip = "127.0.0.1"
    defaults = ChannelSettingsUpdateRequest(
        local_network=DEFAULT_NETWORK_CONFIG["local_network"] | {"host_ip": host_ip},
        channels=[
            {
                "name": "CAN1", "protocol": "UDP", "local_ip": host_ip, "local_port": 8234,
                "device_ip": "127.0.0.1",
                "device_port": 12341, "enabled": True, "control_enabled": False,
            },
            {
                "name": "CAN2", "protocol": "UDP", "local_ip": host_ip, "local_port": 8235,
                "device_ip": "127.0.0.1",
                "device_port": 12342, "enabled": True, "control_enabled": True,
            },
        ],
    )
    result = await update_channels(defaults, principal)
    result["restored"] = True
    result["message"] = "当前运行 profile 的安全通道默认值已恢复并重新连接"
    _audit_action("restore_defaults", "config.channels", result, principal=principal)
    return result


@router.get("/system/version")
async def system_version(_principal: Principal = Depends(require_role(Role.VIEWER))):
    return _system_version()


@router.get("/auth/roles")
async def auth_roles(principal: Principal = Depends(require_role(Role.VIEWER))):
    return {"current_user": principal.username, "current_role": principal.role.value, "roles": deepcopy(ROLES)}


@router.post("/maintenance/enter")
async def enter_maintenance(payload: MaintenanceEnterRequest, principal: Principal = Depends(require_role(Role.ADMIN))):
    if payload.confirmation != "MAINTENANCE":
        raise HTTPException(422, {"code": "CONFIRMATION_MISMATCH", "message": "请输入 MAINTENANCE 确认进入维护模式", "details": {}, "trace_id": ""})
    if state.emergency_stop:
        raise HTTPException(409, {"code": "EMERGENCY_STOP_ACTIVE", "message": "急停触发时不能进入维护模式", "details": {}, "trace_id": ""})
    state.maintenance_mode = True
    request = payload.model_dump(exclude={"role"})
    _audit_action("enter_maintenance", "maintenance.mode", request, changes=[{"key": "maintenance_mode", "old_value": False, "new_value": True}], principal=principal)
    response = {"ok": True, "maintenance_mode": True, "message": "已进入维护模式，危险扩展仍保持关闭"}
    await _broadcast("system.maintenance_changed", {"maintenance_mode": True, **state.maintenance_features})
    return response


@router.post("/maintenance/exit")
async def exit_maintenance(payload: MaintenanceExitRequest, principal: Principal = Depends(require_role(Role.ADMIN))):
    state.maintenance_mode = False
    state.maintenance_features.update({"enable_0x123": False, "enable_0x126": False, "allow_canopen_nmt": False, "enable_pid_debug": False, "dual_control_channel_allowed": False})
    request = payload.model_dump(exclude={"role"})
    _audit_action("exit_maintenance", "maintenance.mode", request, changes=[{"key": "maintenance_mode", "old_value": True, "new_value": False}], principal=principal)
    response = {"ok": True, "maintenance_mode": False, "features": deepcopy(state.maintenance_features), "message": "已退出维护模式，危险扩展已关闭"}
    await _broadcast("system.maintenance_changed", {"maintenance_mode": False, **state.maintenance_features})
    return response


@router.put("/maintenance/features")
async def maintenance_features(payload: MaintenanceFeatureRequest, principal: Principal = Depends(require_role(Role.ADMIN))):
    requested = payload.model_dump(exclude={"confirmation", "reason", "role", "steering_angle_speed_deg_s"})
    old = deepcopy(state.maintenance_features)
    if requested.get("dual_control_channel_allowed"):
        raise HTTPException(409, {"code": "DUAL_CONTROL_FORBIDDEN", "message": "双控制通道永久禁止", "details": {}, "trace_id": ""})
    dangerous_enable = any(requested[key] and not old.get(key, False) for key in ("enable_0x123", "enable_0x126", "allow_canopen_nmt", "enable_pid_debug"))
    if dangerous_enable and not state.maintenance_mode:
        raise HTTPException(409, {"code": "MAINTENANCE_MODE_REQUIRED", "message": "未进入维护模式，不能启用 0x123、0x126、NMT 或 PID 调试", "details": {}, "trace_id": ""})
    mock_changed = requested.get("mock_can_gateway") != old.get("mock_can_gateway")
    expected_confirmation = "MAINTENANCE" if dangerous_enable else "MOCK" if mock_changed else payload.confirmation
    if (dangerous_enable or mock_changed) and payload.confirmation != expected_confirmation:
        raise HTTPException(422, {"code": "CONFIRMATION_MISMATCH", "message": f"请输入 {expected_confirmation} 确认功能变更", "details": {}, "trace_id": ""})
    state.maintenance_features.update(requested)
    state.maintenance_features["dual_control_channel_allowed"] = False
    state.mock_enabled = requested["mock_can_gateway"]
    changes = [{"key": f"maintenance.{key}", "old_value": old.get(key, False), "new_value": value} for key, value in requested.items() if old.get(key) != value]
    request = payload.model_dump(exclude={"role"})
    _audit_action("update_maintenance_features", "maintenance.features", request, changes=changes, principal=principal)
    response = {"ok": True, "maintenance_mode": state.maintenance_mode, "features": deepcopy(state.maintenance_features), "message": "维护功能状态已更新并写入审计"}
    await _broadcast("system.maintenance_changed", {"maintenance_mode": state.maintenance_mode, **state.maintenance_features})
    return response
