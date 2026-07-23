from __future__ import annotations

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import json
import platform
import time
from typing import Any

from app.can_gateway.models import CanFrame
from app.can_gateway.usr_can115 import UsrCan115Codec
from app.core.config import ChannelConfig
from app.core.time import utc_now


def _adapter_identities() -> list[dict[str, Any]]:
    """Return local adapter identity without contacting any network endpoint.

    Production provisioning pins all four fields.  The PowerShell query is fixed
    (no package-controlled shell text) and is therefore safe to run during local
    preflight on Windows.  Tests replace this function with deterministic data.
    """
    if platform.system() == "Windows":
        command = (
            "Get-NetIPConfiguration | ForEach-Object { "
            "$a=$_.NetAdapter; $_.IPv4Address | ForEach-Object { "
            "[pscustomobject]@{name=$a.Name;index=$a.ifIndex;mac=$a.MacAddress;ip=$_.IPAddress} } } "
            "| ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            payload = json.loads(result.stdout or "[]")
            rows = payload if isinstance(payload, list) else [payload]
            return [
                {
                    "name": str(row.get("name") or ""),
                    "index": int(row.get("index") or 0),
                    "mac": str(row.get("mac") or "").replace("-", ":").upper(),
                    "ip": str(row.get("ip") or ""),
                }
                for row in rows
                if isinstance(row, dict)
            ]
        except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
            return []
    rows: list[dict[str, Any]] = []
    for index, name in socket.if_nameindex():
        mac_path = Path("/sys/class/net") / name / "address"
        mac = mac_path.read_text(encoding="ascii").strip().upper() if mac_path.exists() else ""
        rows.append({"name": name, "index": index, "mac": mac, "ip": ""})
    return rows


def adapter_identity_check(configuration: Any) -> dict[str, Any]:
    expected = configuration.network_interface
    rows = _adapter_identities()
    matches = [
        row
        for row in rows
        if row["name"] == expected.adapter_name
        and row["index"] == expected.adapter_index
        and row["mac"] == expected.mac_address
        and row["ip"] == expected.bind_address
    ]
    return {
        "rule": "windows_adapter_identity",
        "label": "Windows 网卡身份",
        "passed": bool(matches),
        "blocking": configuration.runtime_profile == "production",
        "current": rows,
        "threshold": expected.model_dump(mode="json"),
    }


def _bind_probe(channel: ChannelConfig, owned_by_runtime: bool) -> tuple[str, bool, str]:
    if owned_by_runtime:
        return "owned_by_runtime", True, "端口由当前后端通道持有"
    sock_type = socket.SOCK_DGRAM if channel.protocol.lower() == "udp" else socket.SOCK_STREAM
    probe = socket.socket(socket.AF_INET, sock_type)
    try:
        probe.bind((channel.local_ip, channel.local_receive_port))
        return "available", True, "地址和端口可绑定"
    except OSError as exc:
        return "occupied_or_unbindable", False, f"{type(exc).__name__}: {exc}"
    finally:
        probe.close()


async def diagnose_network(state: Any, channels: list[ChannelConfig] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    channels = channels or list(state.config.channels)
    status_by_name = {row.get("channel"): row for row in (state.can.status() if state.can else [])}
    rows: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    tcp_measurements: list[float] = []

    for channel in channels:
        step_started = time.perf_counter()
        runtime = status_by_name.get(channel.channel, {})
        gateway = state.can.gateways.get(channel.channel) if state.can else None
        owned = bool(
            gateway
            and gateway.config.local_ip == channel.local_ip
            and gateway.config.local_receive_port == channel.local_receive_port
            and runtime.get("transport_connected")
        )
        bind_status, bind_ok, bind_detail = await asyncio.to_thread(_bind_probe, channel, owned)
        last_age = runtime.get("receive_age_ms")
        tcp_state = "not_applicable"
        endpoint_status = "receive_confirmed" if runtime.get("online") else "unconfirmed"
        endpoint_detail = "最近收到批准来源的数据帧" if runtime.get("online") else "尚未收到新鲜且批准来源的数据帧"
        if channel.protocol.lower() == "tcp":
            if runtime.get("transport_connected"):
                tcp_state = "connected"
                endpoint_status = "connected"
                endpoint_detail = "当前 TCP transport 已连接"
            else:
                tcp_state = "disconnected"
                connect_started = time.perf_counter()
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(channel.device_ip, channel.device_port), timeout=0.35
                    )
                    del reader
                    latency = round((time.perf_counter() - connect_started) * 1000, 3)
                    tcp_measurements.append(latency)
                    writer.close()
                    await writer.wait_closed()
                    tcp_state = "connectable"
                    endpoint_status = "connectable"
                    endpoint_detail = "TCP endpoint 接受连接；未发送 CAN 数据"
                except (TimeoutError, OSError) as exc:
                    endpoint_detail = f"TCP endpoint 不可连接: {type(exc).__name__}"
        source_enforced = bool(channel.validate_source_endpoint and channel.approved_source_endpoints())
        row = {
            "channel": channel.channel,
            "protocol": channel.protocol.upper(),
            "local_endpoint": f"{channel.local_ip}:{channel.local_receive_port}",
            "device_endpoint": f"{channel.device_ip}:{channel.device_port}",
            "bind_status": bind_status,
            "port_in_use": bind_status == "owned_by_runtime" or not bind_ok,
            "endpoint_status": endpoint_status,
            "last_frame_age_ms": last_age,
            "tcp_state": tcp_state,
            "source_allowlist_enforced": source_enforced,
            "approved_sources": [f"{ip}:{port}" for ip, port in sorted(channel.approved_source_endpoints())],
        }
        rows.append(row)
        status = "pass" if bind_ok and source_enforced and endpoint_status in {"receive_confirmed", "connected", "connectable"} else "warning" if bind_ok and source_enforced else "fail"
        steps.append(
            {
                "rule": f"network_{channel.channel.lower()}",
                "status": status,
                "duration_ms": round((time.perf_counter() - step_started) * 1000, 3),
                "details": {**row, "bind_detail": bind_detail, "endpoint_detail": endpoint_detail},
                "recommendation": "确认设备 endpoint、源 allowlist、网卡绑定和最近收帧时间" if status != "pass" else "无需操作",
            }
        )

    codec_started = time.perf_counter()
    codec = UsrCan115Codec()
    sample = CanFrame(channel="CAN1", can_id=0x121, dlc=8, data=[0] * 8)
    encoded = codec.encode_frame(sample)
    decoded = codec.decode_packet(encoded, "CAN1", "rx", "local-codec-self-test")
    codec_ok = decoded.parse_status == "ok" and decoded.can_id == sample.can_id
    steps.append(
        {
            "rule": "usr_can115_codec",
            "status": "pass" if codec_ok else "fail",
            "duration_ms": round((time.perf_counter() - codec_started) * 1000, 3),
            "details": {"packet_bytes": len(encoded), "dlc": decoded.dlc, "can_id": decoded.can_id_hex},
            "recommendation": "检查协议 codec 的 DLC、保留位和长度校验" if not codec_ok else "无需操作",
        }
    )
    statuses = list(status_by_name.values())
    total = sum(int(row.get("rx_count") or 0) for row in statuses)
    errors = sum(int(row.get("error_count") or 0) for row in statuses)
    protocol_rate = round(max(0, total - errors) / total * 100, 3) if total else 0.0
    udp_rows = [row for row in rows if row["protocol"] == "UDP"]
    udp_state = "pass" if udp_rows and all(row["endpoint_status"] == "receive_confirmed" for row in udp_rows) else "unavailable"
    return {
        "ping_latency_ms": min(tcp_measurements) if tcp_measurements else None,
        "udp_loopback": udp_state,
        "protocol_valid_rate": protocol_rate,
        "dlc_check": "pass" if codec_ok else "fail",
        "reserved_bits_check": "pass" if codec_ok else "fail",
        "sticky_half_packets": {"sticky": 0, "half": sum(int(row.get("malformed_datagrams") or 0) for row in statuses)},
        "last_error": "无" if errors == 0 else f"累计 {errors} 个通道/协议错误",
        "channels": rows,
        "steps": steps,
        "data_source": "os-socket+runtime-statistics",
        "mock": False,
        "quality": "good" if all(step["status"] == "pass" for step in steps) else "degraded",
        "updated_at": utc_now(),
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def configuration_preflight(state: Any, configuration: Any) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if configuration.runtime_profile == "production":
        checks.append(adapter_identity_check(configuration))
    bind_consistent = all(
        endpoint.local_ip == configuration.network_interface.bind_address
        for endpoint in configuration.can_endpoints
    )
    checks.append(
        {
            "rule": "bind_address_consistency",
            "label": "签名网卡绑定地址",
            "passed": bind_consistent,
            "blocking": True,
            "current": [endpoint.local_ip for endpoint in configuration.can_endpoints],
            "threshold": configuration.network_interface.bind_address,
        }
    )
    runtime_status = {row.get("channel"): row for row in (state.can.status() if state.can else [])}
    runtime_channels = {item.channel: item for item in state.config.channels}
    for endpoint in configuration.can_endpoints:
        current = runtime_channels.get(endpoint.channel)
        status = runtime_status.get(endpoint.channel, {})
        owned = bool(
            current
            and current.local_ip == endpoint.local_ip
            and current.local_receive_port == endpoint.local_port
            and status.get("transport_connected")
        )
        probe_config = ChannelConfig(
            channel=endpoint.channel,
            protocol=endpoint.protocol,
            local_ip=endpoint.local_ip,
            local_receive_port=endpoint.local_port,
            device_ip=endpoint.device_ip,
            device_port=endpoint.device_port,
            control_enabled=endpoint.control_enabled,
        )
        bind_status, bind_ok, detail = _bind_probe(probe_config, owned)
        checks.append({"rule": f"bind_{endpoint.channel.lower()}", "passed": bind_ok, "blocking": True, "current": bind_status, "threshold": "owned_by_runtime or bindable", "details": detail})
    dbc = state.dbc.status() if state.dbc else {}
    dbc_match = bool(
        dbc.get("loaded")
        and str(dbc.get("hash") or "").lower() == configuration.approved_dbc_sha256.lower()
        and str(dbc.get("vehicle_series") or "").upper() == configuration.vehicle_series.upper()
    )
    production = configuration.runtime_profile == "production"
    checks.append({"rule": "dbc_identity", "passed": dbc_match or not production, "blocking": production, "current": {"loaded": dbc.get("loaded", False), "hash": dbc.get("hash"), "vehicle_series": dbc.get("vehicle_series")}, "threshold": {"hash": configuration.approved_dbc_sha256, "vehicle_series": configuration.vehicle_series}})
    data_path = Path(configuration.data_root)
    parent = next((candidate for candidate in [data_path, *data_path.parents] if candidate.exists()), None)
    writable = bool(parent and os.access(parent, os.W_OK))
    checks.append({"rule": "data_root_writable", "passed": writable, "blocking": True, "current": str(parent) if parent else None, "threshold": "existing writable path or writable parent"})
    checks.append({"rule": "database_writable", "passed": bool(state.db_writable), "blocking": True, "current": bool(state.db_writable), "threshold": True})
    active_session = bool(state.eol and state.eol.active_session_id)
    periodic = bool(state.tx_scheduler and state.tx_scheduler.task and not state.tx_scheduler.task.done())
    checks.append({"rule": "control_idle", "passed": not active_session and not periodic, "blocking": True, "current": {"active_eol_session": active_session, "periodic_control": periodic}, "threshold": {"active_eol_session": False, "periodic_control": False}})
    return checks


def configuration_post_apply_health(state: Any, configuration: Any) -> list[dict[str, Any]]:
    """Blocking checks against the newly active objects, not the staged document."""
    checks = configuration_preflight(state, configuration)
    status = {row.get("channel"): row for row in (state.can.status() if state.can else [])}
    for endpoint in configuration.can_endpoints:
        row = status.get(endpoint.channel, {})
        checks.extend(
            [
                {
                    "rule": f"transport_{endpoint.channel.lower()}",
                    "label": f"{endpoint.channel} 实际 transport",
                    "passed": bool(row.get("transport_connected")),
                    "blocking": True,
                    "current": row.get("transport_connected", False),
                    "threshold": True,
                },
                {
                    "rule": f"approved_source_receive_{endpoint.channel.lower()}",
                    "label": f"{endpoint.channel} 批准来源收帧",
                    "passed": bool(row.get("online")),
                    "blocking": configuration.runtime_profile == "production" and endpoint.enabled,
                    "current": {
                        "online": row.get("online", False),
                        "last_frame_age_ms": row.get("receive_age_ms"),
                        "unauthorized_datagrams": row.get("unauthorized_datagrams", 0),
                    },
                    "threshold": {
                        "online": True,
                        "max_age_ms": int(state.config.channel_online_timeout_seconds * 1000),
                    },
                },
            ]
        )
    return checks
