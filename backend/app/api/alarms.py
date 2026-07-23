from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.data_source import dashboard_metadata, require_data_in_production
from app.api.errors import get_trace_id
from app.api.models import ActionResponse, AlarmActionRequest, AlarmDashboardResponse, DashboardLayoutRequest, ObjectResponse
from app.control.override_service import (
    OverrideActionResponse,
    OverrideApprovalRequest,
    OverrideConflict,
    OverrideCreateRequest,
    OverrideListResponse,
    OverridePersistenceError,
    OverrideRevokeRequest,
)
from app.core.time import utc_now
from app.security.auth import Principal, Role, require_role
from app.services.app_state import state
from app.services.audit import record_operator_action
from app.services.file_access import normalize_allowed_path, sha256_file, validate_file_id


router = APIRouter()
LEVEL_NAMES = {0: "Normal", 1: "Warning", 2: "Fault", 3: "Critical"}

MATRIX_SIGNALS = [
    ("BMS_SOC", "BMS_SOC", "BMS_SOC_Warning"),
    ("MCU_Disconnect", "MCU掉线", "MCU_Disconnect_Warning"),
    ("MCU_Motor", "电机告警", "MCU_Motor_Warning"),
    ("MCU_Speed", "超速", "MCU_Speed_Warning"),
    ("Steering_Disconnect", "转向掉线", "Steering_Disconnect_Warning"),
    ("Steering_Lock", "转向卡死", "Steering_Lock_Warning"),
    ("Steering_Uncontrollable", "转向失控", "Steering_Uncontrollable_Warning"),
    ("Steering_Error", "角度故障", "Steering_Error_Warning"),
    ("Brake_Error", "刹车故障", "Brake_Error_Warning"),
]

PROTECTION_SIGNALS = [
    ("short_circuit", "短路", "BMS_Protect_Short_Circuit"),
    ("over_current", "过流", "BMS_Protect_Over_Current"),
    ("over_temp", "过温", "BMS_Protect_Over_Temperature"),
    ("under_temp", "欠温", "BMS_Protect_Under_Temperature"),
    ("over_voltage", "过压", "BMS_Protect_Over_Voltage"),
    ("under_voltage", "欠压", "BMS_Protect_Under_Voltage"),
    ("mos_status", "MOS状态", "BMS_Protect_MOS_Fault"),
    ("precharge_status", "预充状态", "BMS_Protect_Precharge_Fault"),
]

DIAGNOSIS_RULES = [
    ("BMS 与通信链路", "检查 CAN1/CAN2 连接、供电和 BMS 报文时效", False, "高"),
    ("BMS 保护状态", "确认 0x102 unsigned 保护位均未触发", False, "高"),
    ("MCU 掉线", "检查 MCU 心跳与供电", False, "高"),
    ("电机系统", "检查电机、逆变器和相电流反馈", False, "中"),
    ("转向系统", "检查转向通信与角度反馈", False, "中"),
    ("刹车系统", "检查制动执行与反馈信号", False, "中"),
    ("超速（速度源）", "校验速度传感器与限速参数", False, "低"),
]


def _signal_value(key: str) -> Any:
    return state.signals.current.get(key, {}).get("value")


def _signal_int(key: str) -> int:
    try:
        return max(0, int(_signal_value(key) or 0))
    except (TypeError, ValueError):
        return 0


def _history_rows(limit: int = 100) -> list[dict[str, Any]]:
    if state.database is None:
        return []
    rows = state.database.query(
        "SELECT * FROM alarms ORDER BY timestamp_utc DESC LIMIT ?", (limit,)
    )
    return [
        {
            "id": str(row["id"]),
            "session_id": row.get("session_id"),
            "time": row["timestamp_utc"],
            "channel": row.get("channel") or "-",
            "can_id": row.get("can_id_hex") or "-",
            "signal": row["signal_name"],
            "level": f'{row["level"]} ({row["level_label"]})',
            "level_value": int(row["level"]),
            "status": row["status"],
            "suggestion": row.get("description") or "按诊断流程复核信号与通信链路",
            "related_step": row.get("related_step_id") or "-",
            "released": bool(row.get("release_reason")),
            "acknowledged_by": row.get("acknowledged_by"),
            "acknowledged_at": row.get("acknowledged_at"),
        }
        for row in rows
    ]


def _charts(history: list[dict[str, Any]]) -> dict[str, Any]:
    chronological = list(reversed(history[:60]))
    x_axis = [str(row["time"])[11:19] for row in chronological]
    timeline = {
        "x_axis": x_axis,
        "series": [
            {
                "name": f"{level} {label}",
                "data": [row["level_value"] if row["level_value"] == level else None for row in chronological],
            }
            for level, label in LEVEL_NAMES.items()
        ],
    }
    counts = Counter(int(row["level_value"]) for row in history)
    total = sum(counts.values())
    distribution = [
        {
            "name": label,
            "value": counts[level],
            "percent": round(counts[level] / total * 100, 1) if total else 0.0,
        }
        for level, label in LEVEL_NAMES.items()
    ]
    return {"level_timeline": timeline, "category_distribution": distribution}


def _dashboard_payload() -> dict[str, Any]:
    matrix = []
    for key, label, signal in MATRIX_SIGNALS:
        value = min(3, _signal_int(signal))
        matrix.append({"key": key, "label": label, "value": value, "status": LEVEL_NAMES[value]})

    protection_items = []
    for key, label, signal in PROTECTION_SIGNALS:
        triggered = bool(_signal_value(signal))
        item = {"key": key, "label": label, "triggered": triggered}
        if key in {"mos_status", "precharge_status"}:
            item["status"] = "故障" if triggered else "正常"
        protection_items.append(item)
    balance = _signal_int("Balance_symbol_cell16") & 0xFFFF
    bitmap_bits = [(balance >> bit) & 1 for bit in range(15, -1, -1)]

    current = state.alarms.current() if state.alarms else []
    history = _history_rows()
    max_level = min(
        3,
        max(
            [int(item.get("level", 0)) for item in current]
            + [int(item["value"]) for item in matrix]
            + [0]
        ),
    )
    has_runtime = bool(state.signals.current)
    has_database = bool(history)
    quality = "good" if has_runtime else "degraded" if has_database else "unavailable"
    require_data_in_production(has_runtime or has_database, "alarm dashboard")
    return {
        **dashboard_metadata("runtime+sqlite", quality=quality),
        "summary": {
            "max_level": max_level,
            "max_label": LEVEL_NAMES[max_level],
            "current_count": len(current),
            "severe_locked": max_level >= 2,
            "recommendation": "无处理中告警" if not current else "请按诊断建议逐项复核",
        },
        "warning_matrix_0x77": matrix,
        "bms_protect_0x102": {
            "items": protection_items,
            "bitmap_bits": bitmap_bits,
            "bit_order": "High -> Low",
            "source_can_id": "0x102",
            "semantics": "unsigned bool / unsigned bitmap",
        },
        "diagnosis_suggestions": [
            {
                "check_item": check,
                "suggestion": suggestion,
                "allow_override": allow,
                "priority": priority,
            }
            for check, suggestion, allow, priority in DIAGNOSIS_RULES
        ],
        "history": history,
        "charts": _charts(history),
    }


def _alarm_exists(alarm_id: str) -> bool:
    if state.database and alarm_id.isdigit():
        return bool(state.database.query_one("SELECT id FROM alarms WHERE id=?", (int(alarm_id),)))
    return bool(state.alarms and any(str(item.get("id")) == alarm_id for item in state.alarms.current()))


def _export_response(path: Path, message: str) -> dict[str, Any]:
    return {
        "ok": True,
        "message": message,
        "trace_id": get_trace_id(),
        "details": {
            "file_name": path.name,
            "file_size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "download_url": f"/alarms/exports/{path.name}",
        },
    }


@router.get("/alarms/dashboard", response_model=AlarmDashboardResponse)
async def dashboard():
    return _dashboard_payload()


@router.get("/alarms/current", response_model=ObjectResponse)
async def current():
    items = state.alarms.current() if state.alarms else []
    return {"items": items, **dashboard_metadata("runtime", quality="good" if state.signals.current else "unavailable")}


@router.get("/alarms/history", response_model=ObjectResponse)
async def history():
    items = _history_rows()
    return {"items": items, "total": len(items), **dashboard_metadata("sqlite", quality="good" if state.database else "unavailable")}


@router.put("/alarms/dashboard-layout", response_model=ActionResponse)
async def save_dashboard_layout(
    payload: DashboardLayoutRequest,
    principal: Principal = Depends(require_role(Role.ENGINEER)),
):
    if state.preferences is None:
        raise HTTPException(503, {"code": "PREFERENCES_UNAVAILABLE", "message": "用户配置服务不可用", "details": {}})
    state.preferences.set("alarm_dashboard_layout", payload.layout)
    record_operator_action(state, principal, "save_alarm_dashboard_layout", "alarms.dashboard", payload.model_dump(), trace_id=get_trace_id())
    return {"ok": True, "message": "告警诊断布局已保存", "trace_id": get_trace_id(), "details": {"layout": payload.layout}}


@router.post("/alarms/export-diagnosis", response_model=ActionResponse)
async def export_diagnosis(
    payload: AlarmActionRequest = Body(default_factory=AlarmActionRequest),
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    root = state.data_paths.exports
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"alarm_diagnosis_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    path.write_text(
        json.dumps(
            {"generated_at": utc_now(), "requested_by": principal.username, "dashboard": _dashboard_payload(), "request": payload.model_dump()},
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    record_operator_action(state, principal, "export_alarm_diagnosis", path.name, payload.model_dump(), trace_id=get_trace_id())
    return _export_response(path, "告警诊断已导出")


@router.get("/alarms/exports/{file_id}")
async def download_alarm_export(file_id: str, _principal: Principal = Depends(require_role(Role.VIEWER))):
    validate_file_id(file_id)
    root = state.data_paths.exports
    path = normalize_allowed_path(root / file_id, [root], expect_file=True)
    return FileResponse(path, filename=path.name, media_type="application/json", headers={"X-Trace-Id": get_trace_id()})


@router.post("/alarms/jump-can-frame", response_model=ActionResponse)
async def jump_can_frame(
    payload: AlarmActionRequest = Body(default_factory=AlarmActionRequest),
    principal: Principal = Depends(require_role(Role.VIEWER)),
):
    can_id = str(payload.can_id or "0x77")
    try:
        parsed = int(can_id, 16) if can_id.lower().startswith("0x") else int(can_id)
    except ValueError as exc:
        raise HTTPException(422, {"code": "INVALID_CAN_ID", "message": "CAN ID 格式错误", "details": {"can_id": can_id}}) from exc
    latest = state.can.latest_items() if state.can else []
    if not any(int(item["can_id"]) == parsed for item in latest):
        raise HTTPException(404, {"code": "CAN_FRAME_NOT_FOUND", "message": "未找到关联 CAN 帧", "details": {"can_id": can_id}})
    record_operator_action(state, principal, "jump_alarm_can_frame", can_id, payload.model_dump(), trace_id=get_trace_id())
    return {"ok": True, "message": "已定位关联 CAN 报文", "trace_id": get_trace_id(), "details": {"can_id": f"0x{parsed:X}", "route": f"/can-monitor?can_id=0x{parsed:X}"}}


@router.post("/alarms/{alarm_id}/ack", response_model=ActionResponse)
async def ack(
    alarm_id: str,
    payload: AlarmActionRequest = Body(default_factory=AlarmActionRequest),
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    if alarm_id == "current-summary" and not (state.alarms and state.alarms.current()):
        return {"ok": True, "message": "当前没有活动告警需要确认", "trace_id": get_trace_id(), "details": {"acked": None}}
    if not _alarm_exists(alarm_id):
        raise HTTPException(404, {"code": "ALARM_NOT_FOUND", "message": "告警记录不存在", "details": {"alarm_id": alarm_id}})
    if state.alarms:
        state.alarms.acked.add(alarm_id)
    if state.database and alarm_id.isdigit():
        state.database.execute(
            "UPDATE alarms SET acknowledged_by=?, acknowledged_at=? WHERE id=?",
            (principal.username, utc_now(), int(alarm_id)),
        )
    record_operator_action(state, principal, "ack_alarm", alarm_id, payload.model_dump(), trace_id=get_trace_id())
    return {"ok": True, "message": "当前告警状态已确认", "trace_id": get_trace_id(), "details": {"acked": alarm_id}}


def _override_http_error(exc: OverrideConflict) -> HTTPException:
    status = 404 if exc.code == "OVERRIDE_NOT_FOUND" else 409
    return HTTPException(status, {"code": exc.code, "message": exc.message, "details": {}})


def _override_persistence_http_error(exc: OverridePersistenceError) -> HTTPException:
    return HTTPException(503, {"code": exc.code, "message": str(exc), "details": {"blocking": True}})


@router.get("/alarms/overrides", response_model=OverrideListResponse)
async def list_overrides(
    _principal: Principal = Depends(require_role(Role.VIEWER)),
):
    items = state.overrides.list() if state.overrides else []
    return {"items": items, "total": len(items)}


@router.post("/alarms/overrides/{override_id}/approve", response_model=OverrideActionResponse)
async def approve_override(
    override_id: str,
    payload: OverrideApprovalRequest,
    principal: Principal = Depends(require_role(Role.ADMIN)),
):
    try:
        record = state.overrides.approve(override_id, payload, principal, trace_id=get_trace_id())
    except OverrideConflict as exc:
        record_operator_action(state, principal, "alarm_override_approve", override_id, payload.model_dump(), exc.code, trace_id=get_trace_id(), required=True)
        raise _override_http_error(exc)
    except OverridePersistenceError as exc:
        raise _override_persistence_http_error(exc)
    return {"ok": True, "message": "人工放行申请已由独立管理员批准", "trace_id": get_trace_id(), "override": record}


@router.post("/alarms/overrides/{override_id}/revoke", response_model=OverrideActionResponse)
async def revoke_override(
    override_id: str,
    payload: OverrideRevokeRequest,
    principal: Principal = Depends(require_role(Role.ADMIN)),
):
    try:
        record = state.overrides.revoke(override_id, payload, principal, trace_id=get_trace_id())
    except OverrideConflict as exc:
        record_operator_action(state, principal, "alarm_override_revoke", override_id, payload.model_dump(), exc.code, trace_id=get_trace_id(), required=True)
        raise _override_http_error(exc)
    except OverridePersistenceError as exc:
        raise _override_persistence_http_error(exc)
    return {"ok": True, "message": "人工放行授权已撤销", "trace_id": get_trace_id(), "override": record}


@router.post("/alarms/{alarm_id}/override-request", response_model=OverrideActionResponse)
async def override(
    alarm_id: str,
    payload: OverrideCreateRequest,
    principal: Principal = Depends(require_role(Role.ENGINEER)),
):
    if not _alarm_exists(alarm_id):
        raise HTTPException(404, {"code": "ALARM_NOT_FOUND", "message": "告警记录不存在", "details": {"alarm_id": alarm_id}})
    if state.overrides is None:
        raise HTTPException(503, {"code": "OVERRIDE_SERVICE_UNAVAILABLE", "message": "人工放行服务不可用", "details": {}})
    try:
        record = state.overrides.create(alarm_id, payload, principal, trace_id=get_trace_id())
    except OverrideConflict as exc:
        record_operator_action(state, principal, "alarm_override_request", alarm_id, payload.model_dump(), exc.code, trace_id=get_trace_id(), required=True)
        raise _override_http_error(exc)
    except OverridePersistenceError as exc:
        raise _override_persistence_http_error(exc)
    return {"ok": True, "message": "人工放行申请已提交，等待独立管理员审批", "trace_id": get_trace_id(), "override": record}
