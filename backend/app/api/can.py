from __future__ import annotations

import csv
import gzip
from datetime import datetime
from pathlib import Path
import time
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.data_source import (
    dashboard_metadata,
    explicit_mock_enabled,
    require_data_in_production,
)
from app.api.errors import get_trace_id
from app.api.models import (
    ActionResponse,
    CanDecodedResponse,
    CanLatestFramesResponse,
    CanMonitorStatisticsResponse,
    ObjectListResponse,
    ObjectResponse,
    RawLogDeleteRequest,
)
from app.can_gateway.models import CanFrame
from app.can_gateway.usr_can115 import UsrCan115Codec
from app.core.time import now_ns, utc_now
from app.configuration.diagnostics import diagnose_network
from app.dbc.service import DbcService
from app.security.auth import Principal, Role, require_role
from app.services.app_state import state
from app.services.audit import record_operator_action
from app.services.file_access import (
    human_size,
    normalize_allowed_path,
    sha256_file,
    validate_file_id,
)


router = APIRouter()


def decoded_signals_for(can_id: int, data_hex: str) -> list[dict[str, Any]]:
    """Decode details through the same authoritative logic used by the API."""
    try:
        data = bytes.fromhex(data_hex)
    except ValueError as exc:
        raise ValueError("invalid CAN data hex") from exc
    padded = (data + bytes(8))[:8]
    if can_id == 0x102:
        return DbcService._bms_102_details(padded)
    if can_id == 0x121:
        return DbcService._control_121_details(padded)
    if state.dbc:
        frame = CanFrame(
            channel="CAN1",
            direction="query",
            can_id=can_id,
            dlc=min(len(data), 8),
            data=list(padded),
            source="decoded-signals-helper",
        )
        return state.dbc.decode_details(frame)["signals"]
    return DbcService._raw_byte_details(padded)


def _parse_can_id(value: str) -> int | None:
    if not value:
        return None
    text = value.strip().lower()
    try:
        return int(text, 16) if text.startswith("0x") else int(text, 10)
    except ValueError:
        try:
            return int(text, 16)
        except ValueError:
            return None


def _explicit_mock_frames() -> list[dict[str, Any]]:
    now = time.time()
    rows = [
        ("CAN1", 0x77, "00 00 00 00 00 00 00 00", "VCU_Warning_Level"),
        ("CAN2", 0x100, "02 FF FF 83 56 00 00 00", "BMS_Status"),
        ("CAN2", 0x102, "00 00 00 00 00 00 00 00", "BMS_Protect_Status"),
        ("CAN2", 0x121, "81 C4 3C 14 00 40 01 04", "SCU_Control_Command"),
    ]
    return [
        {
            "key": f"{channel}:{can_id:X}",
            "timestamp_ns": int(now * 1_000_000_000),
            "timestamp": datetime.now().strftime("%H:%M:%S.%f") + ".000",
            "channel": channel,
            "direction": "RX",
            "can_id": can_id,
            "can_id_hex": f"0x{can_id:X}",
            "frame_type": "标准帧",
            "dlc": 8,
            "data_hex": data_hex,
            "message_name": name,
            "period_ms": 100,
            "status": "正常",
            "source_session": "MOCK",
            "frame_count": 1,
            "first_seen": now,
            "last_seen": now,
            "last_seen_ms": 0,
        }
        for channel, can_id, data_hex, name in rows
    ]


def _latest_items() -> tuple[list[dict[str, Any]], bool]:
    items = state.can.latest_items(split_by_channel=False) if state.can else []
    if items:
        session_id = state.eol.active_session_id if state.eol else None
        return [
            {**item, "source_session": session_id or item.get("source_session") or "-"}
            for item in items
        ], False
    if explicit_mock_enabled():
        return _explicit_mock_frames(), True
    return [], False


def _filter_latest(
    items: list[dict[str, Any]],
    channel: str,
    can_id: str,
    message_name: str,
    direction: str,
    status: str,
) -> list[dict[str, Any]]:
    target_id = _parse_can_id(can_id)
    filtered = []
    for item in items:
        if channel != "ALL" and item["channel"] != channel:
            continue
        if direction != "ALL" and str(item["direction"]).upper() != direction:
            continue
        if target_id is not None and int(item["can_id"]) != target_id:
            continue
        if message_name and message_name.lower() not in str(item["message_name"]).lower():
            continue
        expected = {"normal": "正常", "timeout": "超时", "error": "错误"}.get(status)
        if status != "all" and str(item["status"]).lower() != str(expected or status).lower():
            continue
        filtered.append(item)
    return filtered


def _sort_latest(items: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    if sort == "can_id_asc":
        return sorted(items, key=lambda item: int(item["can_id"]))
    if sort == "can_id_desc":
        return sorted(items, key=lambda item: int(item["can_id"]), reverse=True)
    return sorted(items, key=lambda item: int(item.get("last_seen_ms", 0)))


def _frame_from_item(item: dict[str, Any]) -> CanFrame:
    try:
        data = list(bytes.fromhex(str(item.get("data_hex") or "")))
    except ValueError as exc:
        raise HTTPException(
            422,
            {
                "code": "INVALID_FRAME_DATA",
                "message": "最新帧十六进制数据无效",
                "details": {"data_hex": item.get("data_hex")},
            },
        ) from exc
    return CanFrame(
        timestamp_ns=int(item.get("timestamp_ns") or now_ns()),
        channel=str(item.get("channel") or "CAN1"),
        direction="query",
        can_id=int(item["can_id"]),
        is_extended=str(item.get("frame_type")) == "扩展帧",
        dlc=int(item.get("dlc") or len(data)),
        data=(data + [0] * 8)[:8],
        message_name=item.get("message_name"),
        source="latest-frame-query",
    )


def _raw_log_rows() -> list[dict[str, Any]]:
    rows = []
    root = state.data_paths.raw_can
    for path in sorted(root.glob("raw_can_*.csv*"), key=lambda item: item.stat().st_mtime, reverse=True):
        session_id = path.name.removeprefix("raw_can_").split("_")[0]
        rows.append(
            {
                "file_id": path.name,
                "file_name": path.name,
                "session_id": session_id,
                "started_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "size": human_size(path.stat().st_size),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "download_url": f"/logs/raw-can-files/{path.name}/download",
            }
        )
    return rows


def _monitor_payload() -> dict[str, Any]:
    items, is_mock = _latest_items()
    total_count = sum(int(item.get("frame_count", 0)) for item in items)
    distribution = [
        {
            "can_id_hex": item["can_id_hex"],
            "count": int(item.get("frame_count", 0)),
            "percent": round(int(item.get("frame_count", 0)) / total_count * 100, 1)
            if total_count
            else 0.0,
        }
        for item in sorted(items, key=lambda row: int(row.get("frame_count", 0)), reverse=True)[:10]
    ]
    statuses = state.can.status() if state.can else []
    now_label = datetime.now().strftime("%H:%M:%S")
    fps = {str(row.get("channel")): float(row.get("fps") or 0) for row in statuses}

    jitter_row: dict[str, Any] = {"time": now_label, "id_121": 0.0, "id_51": 0.0, "id_100": 0.0}
    if state.can:
        for can_id, key in ((0x121, "id_121"), (0x51, "id_51"), (0x100, "id_100")):
            values = []
            for gateway in state.can.gateways.values():
                message = gateway.stats.messages.get(can_id)
                if message and message.period_ms:
                    values.append(message.max_period_ms - message.min_period_ms)
            jitter_row[key] = round(max(values, default=0.0), 3)

    errors = {
        "timeout_count": sum(int(row.get("stale_dropped") or 0) for row in statuses),
        "error_frame_count": sum(int(row.get("error_count") or 0) for row in statuses),
        "protocol_error_count": sum(
            int(row.get("malformed_datagrams") or 0) + int(row.get("processing_errors") or 0)
            for row in statuses
        ),
    }
    started = min(
        [gateway.stats.started_monotonic for gateway in state.can.gateways.values()],
        default=time.monotonic(),
    ) if state.can else time.monotonic()
    elapsed = max(0, int(time.monotonic() - started))
    footer = {
        "recording": bool(state.telemetry and state.telemetry.healthy),
        "uptime": f"{elapsed // 3600:02d}:{elapsed % 3600 // 60:02d}:{elapsed % 60:02d}",
        "buffer_usage": round(
            sum(int(row.get("queue_depth") or 0) for row in statuses)
            / max(1, sum(int(row.get("queue_capacity") or 0) for row in statuses))
            * 100
        ),
        "rx_fps": round(sum(float(row.get("fps") or 0) for row in statuses)),
        "tx_fps": sum(int(row.get("tx_count") or 0) for row in statuses),
    }
    quality = "good" if items else "unavailable"
    return {
        **dashboard_metadata("runtime+sqlite", quality=quality, mock=is_mock),
        "can_id_distribution": distribution,
        "fps_trend": [{"time": now_label, "can1": fps.get("CAN1", 0), "can2": fps.get("CAN2", 0)}],
        "period_jitter": [jitter_row],
        "error_summary": errors,
        "history_files": _raw_log_rows(),
        "footer_status": footer,
    }


@router.get("/can/channels/status", response_model=ObjectListResponse)
async def channel_status():
    return state.can.status() if state.can else []


@router.get("/can/runtime-metrics", response_model=ObjectResponse)
async def runtime_metrics(_principal: Principal = Depends(require_role(Role.VIEWER))):
    """Operational metrics for bounded receive, persistence, and WebSocket queues."""
    can_metrics = state.can.statistics() if state.can else {}
    telemetry_metrics = state.telemetry.metrics() if state.telemetry else {}
    websocket_metrics = state.ws.snapshot() if state.ws else {}
    return {
        "can": can_metrics,
        "telemetry": telemetry_metrics,
        "websocket": websocket_metrics,
        **dashboard_metadata("runtime", quality="good" if state.can else "unavailable"),
    }


@router.post("/can/channels/{channel}/connect", response_model=ObjectResponse)
async def connect(channel: str, principal: Principal = Depends(require_role(Role.ENGINEER))):
    channel = channel.upper()
    if channel not in {"CAN1", "CAN2"}:
        raise HTTPException(404, {"code": "CHANNEL_NOT_FOUND", "message": "仅支持 CAN1/CAN2", "details": {"channel": channel}})
    try:
        result = await state.can.start_channel(channel)
    except Exception as exc:
        raise HTTPException(503, {"code": "CHANNEL_CONNECT_FAILED", "message": f"{channel} 启动失败", "details": {"error": str(exc)}}) from exc
    record_operator_action(state, principal, "can_channel_connect", channel, {}, trace_id=get_trace_id())
    return {"connected": True, "message": f"{channel} 已启动", "channel": channel, "status": result, "trace_id": get_trace_id()}


@router.post("/can/channels/{channel}/disconnect", response_model=ObjectResponse)
async def disconnect(channel: str, principal: Principal = Depends(require_role(Role.ENGINEER))):
    channel = channel.upper()
    if channel not in {"CAN1", "CAN2"}:
        raise HTTPException(404, {"code": "CHANNEL_NOT_FOUND", "message": "仅支持 CAN1/CAN2", "details": {"channel": channel}})
    try:
        result = await state.can.stop_channel(channel)
    except Exception as exc:
        raise HTTPException(503, {"code": "CHANNEL_DISCONNECT_FAILED", "message": f"{channel} 停止失败", "details": {"error": str(exc)}}) from exc
    record_operator_action(state, principal, "can_channel_disconnect", channel, {}, trace_id=get_trace_id())
    return {"disconnected": True, "message": f"{channel} 已停止", "channel": channel, "status": result, "trace_id": get_trace_id()}


@router.post("/can/channels/self-test", response_model=ObjectResponse)
async def self_test(_principal: Principal = Depends(require_role(Role.ENGINEER))):
    return {**await diagnose_network(state), "trace_id": get_trace_id()}


@router.post("/can/channels/stop-all", response_model=ObjectResponse)
async def stop_all(principal: Principal = Depends(require_role(Role.ENGINEER))):
    try:
        await state.can.stop_all()
    except Exception as exc:
        raise HTTPException(503, {"code": "CHANNEL_STOP_ALL_FAILED", "message": "停止全部通道失败", "details": {"error": str(exc)}}) from exc
    record_operator_action(state, principal, "can_channels_stop_all", "CAN1,CAN2", {}, trace_id=get_trace_id())
    return {"stopped": True, "message": "所有 CAN 通道已停止", "trace_id": get_trace_id()}


@router.get("/can/frames/latest", response_model=CanLatestFramesResponse)
async def latest_frames(
    channel: str = Query("ALL"),
    can_id: str = "",
    message_name: str = "",
    direction: str = Query("ALL"),
    status: str = Query("all"),
    sort: str = Query("last_seen_desc"),
):
    items, is_mock = _latest_items()
    require_data_in_production(bool(items), "CAN latest frames")
    filtered = _sort_latest(
        _filter_latest(items, channel.upper(), can_id, message_name, direction.upper(), status),
        sort,
    )
    return {
        **dashboard_metadata("runtime", quality="good" if items else "unavailable", mock=is_mock),
        "items": filtered,
        "total": len(filtered),
    }


@router.get("/can/frames/latest/{can_id}/decoded", response_model=CanDecodedResponse)
async def latest_decoded(can_id: str, channel: str | None = None):
    parsed = _parse_can_id(can_id)
    if parsed is None:
        raise HTTPException(422, {"code": "INVALID_CAN_ID", "message": "CAN ID 格式错误", "details": {"can_id": can_id}})
    items, is_mock = _latest_items()
    frame_item = next(
        (
            item
            for item in items
            if int(item["can_id"]) == parsed
            and (not channel or str(item["channel"]).upper() == channel.upper())
        ),
        None,
    )
    if frame_item is None:
        raise HTTPException(404, {"code": "CAN_ID_NOT_FOUND", "message": "未找到 CAN ID 最新帧", "details": {"can_id": can_id, "channel": channel}})
    detail = state.dbc.decode_details(_frame_from_item(frame_item))
    return {
        **dashboard_metadata("runtime+dbc", quality="good" if not detail["raw_only"] else "degraded", mock=is_mock),
        "frame": frame_item,
        "signals": detail["signals"],
        "dbc_status": "raw-only" if detail["raw_only"] else "decoded",
    }


@router.get("/can/frames", response_model=ObjectListResponse)
async def frames(limit: int = Query(default=200, ge=1, le=2000)):
    return [frame.ui_dict() for frame in list(state.can.recent_frames)[:limit]] if state.can else []


@router.get("/can/frames/{frame_id}/decoded", response_model=CanDecodedResponse)
async def decoded(frame_id: str):
    row = None
    if state.database and frame_id.isdigit():
        row = state.database.query_one("SELECT * FROM raw_can_frames WHERE id=?", (int(frame_id),))
    if row:
        item = {
            "timestamp_ns": now_ns(),
            "timestamp": row["timestamp_utc"],
            "channel": row["channel"],
            "direction": row["direction"].upper(),
            "can_id": int(str(row["can_id_hex"]), 16),
            "can_id_hex": row["can_id_hex"],
            "frame_type": "扩展帧" if row["is_extended"] else "标准帧",
            "dlc": row["dlc"],
            "data_hex": row["data_hex"],
            "message_name": row.get("message_name") or "Unknown",
            "period_ms": row.get("period_ms") or 0,
            "status": "正常" if row["parse_status"] == "ok" else "错误",
            "source_session": row.get("session_id") or "-",
            "frame_count": 1,
            "last_seen_ms": 0,
        }
        detail = state.dbc.decode_details(_frame_from_item(item))
        return {**dashboard_metadata("sqlite+dbc"), "frame": item, "signals": detail["signals"], "dbc_status": "raw-only" if detail["raw_only"] else "decoded"}
    return await latest_decoded(frame_id)


@router.get("/can/statistics", response_model=ObjectResponse)
async def statistics():
    return state.can.statistics() if state.can else {"channels": [], "frames": []}


@router.get("/can/statistics/monitor", response_model=CanMonitorStatisticsResponse)
async def monitor_statistics():
    payload = _monitor_payload()
    require_data_in_production(bool(payload["can_id_distribution"]), "CAN monitor statistics")
    return payload


@router.post("/can/frames/clear-display", response_model=ActionResponse)
async def clear_display(principal: Principal = Depends(require_role(Role.OPERATOR))):
    if state.can:
        state.can.latest_frames.clear()
        state.can.recent_frames.clear()
    record_operator_action(state, principal, "clear_can_monitor_display", "can.monitor", {}, trace_id=get_trace_id())
    return {"ok": True, "message": "CAN 监控显示缓存已清空", "trace_id": get_trace_id(), "details": {}}


def _write_recent_raw_export() -> Path:
    root = state.data_paths.exports
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"raw_can_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.bin"
    codec = UsrCan115Codec()
    with path.open("wb") as stream:
        for frame in reversed(list(state.can.recent_frames) if state.can else []):
            stream.write(frame.raw_packet or codec.encode_frame(frame))
    return path


def _write_recent_csv_export() -> Path:
    root = state.data_paths.exports
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"can_frames_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.csv"
    columns = ["timestamp_ns", "channel", "direction", "can_id_hex", "dlc", "data_hex", "message_name", "parse_status", "source"]
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for frame in reversed(list(state.can.recent_frames) if state.can else []):
            item = frame.ui_dict()
            writer.writerow({key: item.get(key, "") for key in columns})
    return path


def _export_response(path: Path, message: str) -> dict[str, Any]:
    return {
        "ok": True,
        "message": message,
        "trace_id": get_trace_id(),
        "data_source": "runtime",
        "mock": False,
        "details": {
            "file_name": path.name,
            "file_size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "download_url": f"/logs/exports/{path.name}",
        },
    }


@router.post("/logs/export/raw-can", response_model=ActionResponse)
async def export_raw_can(principal: Principal = Depends(require_role(Role.OPERATOR))):
    path = _write_recent_raw_export()
    record_operator_action(state, principal, "export_raw_can", path.name, {"size": path.stat().st_size}, trace_id=get_trace_id())
    return _export_response(path, "原始 CAN 日志已导出")


@router.post("/logs/export/csv", response_model=ActionResponse)
async def export_csv(principal: Principal = Depends(require_role(Role.OPERATOR))):
    path = _write_recent_csv_export()
    record_operator_action(state, principal, "export_can_csv", path.name, {"size": path.stat().st_size}, trace_id=get_trace_id())
    return _export_response(path, "CAN CSV 已导出")


@router.get("/logs/exports/{file_id}")
async def download_export(file_id: str, _principal: Principal = Depends(require_role(Role.VIEWER))):
    validate_file_id(file_id)
    root = state.data_paths.exports
    path = normalize_allowed_path(root / file_id, [root], expect_file=True)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream", headers={"X-Trace-Id": get_trace_id()})


@router.get("/logs/raw-can-files", response_model=ObjectResponse)
async def raw_can_files():
    rows = _raw_log_rows()
    return {"items": rows, "total": len(rows), **dashboard_metadata("filesystem", quality="good")}


@router.get("/logs/raw-can-files/{file_id}/download")
async def download_raw_can_file(file_id: str, _principal: Principal = Depends(require_role(Role.VIEWER))):
    validate_file_id(file_id)
    root = state.data_paths.raw_can
    path = normalize_allowed_path(root / file_id, [root], expect_file=True)
    media_type = "application/gzip" if path.suffix == ".gz" else "text/csv"
    return FileResponse(path, filename=path.name, media_type=media_type, headers={"X-Trace-Id": get_trace_id()})


@router.post("/logs/load-history", response_model=ActionResponse)
async def load_history(
    payload: dict[str, Any] = Body(default_factory=dict),
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    file_id = validate_file_id(str(payload.get("file_id") or ""))
    root = state.data_paths.raw_can
    path = normalize_allowed_path(root / file_id, [root], expect_file=True)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
            row_count = sum(1 for _ in stream) - 1
    else:
        with path.open("r", encoding="utf-8", newline="") as stream:
            row_count = sum(1 for _ in stream) - 1
    record_operator_action(state, principal, "load_can_history", file_id, {"rows": max(0, row_count)}, trace_id=get_trace_id())
    return {"ok": True, "message": "历史 CAN 文件已载入索引", "trace_id": get_trace_id(), "details": {"file_id": file_id, "rows": max(0, row_count)}}


@router.delete("/logs/raw-can-files/{file_id}", response_model=ActionResponse)
async def delete_raw_can_file(
    file_id: str,
    payload: RawLogDeleteRequest,
    principal: Principal = Depends(require_role(Role.ADMIN)),
):
    validate_file_id(file_id)
    root = state.data_paths.raw_can
    path = normalize_allowed_path(root / file_id, [root], expect_file=True)
    quarantine = state.data_paths.temp / "manual-delete" / file_id
    quarantine.parent.mkdir(parents=True, exist_ok=True)
    path.replace(quarantine)
    try:
        state.database.execute(
            "INSERT INTO operator_actions(timestamp_utc,operator,role,action_type,target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?)",
            (utc_now(), principal.username, principal.role.value, "delete_raw_can_file", file_id, payload.model_dump_json(), "OK", get_trace_id()),
        )
    except Exception:
        quarantine.replace(path)
        raise
    quarantine.unlink()
    return {"ok": True, "message": "原始 CAN 历史文件已删除", "trace_id": get_trace_id(), "details": {"file_id": file_id}}
