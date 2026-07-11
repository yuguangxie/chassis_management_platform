from __future__ import annotations

import csv
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.data_source import dashboard_metadata, require_data_in_production
from app.api.errors import get_trace_id
from app.api.models import (
    ActionResponse,
    CurveConfigResponse,
    CurveSelectionRequest,
    CurveTimeseriesResponse,
    DashboardLayoutRequest,
    SignalDashboardResponse,
    WatchlistUpdateRequest,
    ObjectResponse,
)
from app.core.paths import EXPORTS_DIR
from app.core.time import utc_now
from app.security.auth import Principal, Role, require_role
from app.services.app_state import state
from app.services.audit import record_operator_action
from app.services.file_access import normalize_allowed_path, sha256_file, validate_file_id


router = APIRouter()


def _identity(value: float) -> float:
    return value


def _rpm_to_kmh(value: float) -> float:
    return value / 50.0


SIGNAL_CATALOG: list[dict[str, Any]] = [
    {"name": "SCU_Target_Speed", "source": "SCU_Target_Speed_Feedback", "can_id": "0x7F1", "unit": "km/h", "color": "#21C55D", "group": "speed", "selected": True, "transform": _identity},
    {"name": "Vehicle_Speed", "source": "CCU_Vehicle_Speed", "can_id": "0x51", "unit": "km/h", "color": "#2F80FF", "group": "speed", "selected": True, "transform": _identity},
    {"name": "FL_Wheel_Speed", "source": "Wheel_Speed_Front_Left_RPM", "can_id": "0x168", "unit": "km/h", "color": "#7DD3FC", "group": "wheel", "selected": True, "transform": _rpm_to_kmh},
    {"name": "FR_Wheel_Speed", "source": "Wheel_Speed_Front_Right_RPM", "can_id": "0x168", "unit": "km/h", "color": "#60A5FA", "group": "wheel", "selected": True, "transform": _rpm_to_kmh},
    {"name": "RL_Wheel_Speed", "source": "Wheel_Speed_Rear_Left_RPM", "can_id": "0x168", "unit": "km/h", "color": "#A78BFA", "group": "wheel", "selected": True, "transform": _rpm_to_kmh},
    {"name": "RR_Wheel_Speed", "source": "Wheel_Speed_Rear_Right_RPM", "can_id": "0x168", "unit": "km/h", "color": "#F472B6", "group": "wheel", "selected": True, "transform": _rpm_to_kmh},
    {"name": "Front_Steer_Cmd", "source": "SCU_Steering_Angle_Front", "can_id": "0x121", "unit": "deg/raw", "color": "#F6C343", "group": "steering", "selected": True, "transform": _identity},
    {"name": "Front_Steer_Fdbk", "source": "SAS_Front_Angle", "can_id": "0xE1", "unit": "deg", "color": "#2F80FF", "group": "steering", "selected": True, "transform": _identity},
    {"name": "Rear_Steer_Cmd", "source": "SCU_Steering_Angle_Rear", "can_id": "0x121", "unit": "deg/raw", "color": "#22D3EE", "group": "steering", "selected": True, "transform": _identity},
    {"name": "Rear_Steer_Fdbk", "source": "SAS_Rear_Angle", "can_id": "0xE1", "unit": "deg", "color": "#21C55D", "group": "steering", "selected": True, "transform": _identity},
    {"name": "BMS_Total_Voltage", "source": "BMS_Voltage", "can_id": "0x100", "unit": "V", "color": "#F6C343", "group": "bms", "selected": True, "transform": _identity},
    {"name": "BMS_Current", "source": "BMS_Current", "can_id": "0x100", "unit": "A", "color": "#F472B6", "group": "bms", "selected": True, "transform": _identity},
    {"name": "SOC", "source": "BMS_SOC", "can_id": "0x100", "unit": "%", "color": "#22D3EE", "group": "bms", "selected": True, "transform": _identity},
    {"name": "Motor_Speed", "source": "Speed_feed_left", "can_id": "0x284", "unit": "rpm", "color": "#F97316", "group": "motor", "selected": True, "transform": _identity},
    {"name": "Motor_Current_A", "source": "Torque_feed_left", "can_id": "0x384", "unit": "A", "color": "#2F80FF", "group": "motor", "selected": True, "transform": _identity},
    {"name": "Alarm_Level", "source": "VCU_Max_Warning_Level", "can_id": "0x77", "unit": "level", "color": "#EF4444", "group": "alarm", "selected": True, "transform": _identity},
]

GROUP_LABELS = {
    "speed": "速度",
    "wheel": "轮速",
    "steering": "转向",
    "bms": "BMS",
    "motor": "电机",
    "alarm": "告警",
    "custom": "自定义",
}


def _catalog_item(name: str) -> dict[str, Any] | None:
    return next((item for item in SIGNAL_CATALOG if item["name"] == name), None)


def _current_value(item: dict[str, Any]) -> float | None:
    source = state.signals.current.get(item["source"])
    if not source or source.get("quality") != "good":
        return None
    try:
        return round(float(item["transform"](float(source["value"]))), 4)
    except (TypeError, ValueError):
        return None


def _curve_config_payload() -> dict[str, Any]:
    selected = set(state.preferences.get("curve_selection") or []) if state.preferences else set()
    groups = [
        {
            "key": key,
            "label": label,
            "count": sum(1 for item in SIGNAL_CATALOG if item["group"] == key),
        }
        for key, label in GROUP_LABELS.items()
    ]
    signals = [
        {
            "name": item["name"],
            "source_signal": item["source"],
            "can_id": item["can_id"],
            "unit": item["unit"],
            "color": item["color"],
            "current_value": _current_value(item),
            "selected": item["name"] in selected if selected else bool(item["selected"]),
            "quality": state.signals.current.get(item["source"], {}).get("quality", "unavailable"),
        }
        for item in SIGNAL_CATALOG
    ]
    quality = state.signals.overall_quality()
    return {
        **dashboard_metadata("runtime", quality=quality),
        "groups": groups,
        "signals": signals,
        "default_window": "5分钟",
        "default_sample_rate": "100 Hz",
        "default_downsample": "平均值",
        "default_playback_speed": "1.0x",
    }


def _parse_numeric(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _live_points(source: str) -> list[tuple[str, float]]:
    return [
        (str(row["t"]), float(row["value"]))
        for row in state.signals.timeseries.get(source, [])
        if row.get("quality") == "good" and _parse_numeric(row.get("value")) is not None
    ]


def _history_points(session_id: str, source: str) -> list[tuple[str, float]]:
    if state.database is None:
        return []
    rows = state.database.query(
        "SELECT timestamp_utc, physical_value FROM decoded_signals "
        "WHERE session_id=? AND signal_name=? AND quality='good' ORDER BY timestamp_utc",
        (session_id, source),
    )
    points = []
    for row in rows:
        value = _parse_numeric(row.get("physical_value"))
        if value is not None:
            points.append((str(row["timestamp_utc"]), value))
    return points


def _bucket_reduce(values: list[float], method: str) -> float:
    if method == "最大值":
        return max(values)
    if method == "最小值":
        return min(values)
    if method == "最后值":
        return values[-1]
    return sum(values) / len(values)


def _lttb(points: list[tuple[str, float]], threshold: int) -> list[tuple[str, float]]:
    if threshold >= len(points) or threshold < 3:
        return points
    sampled = [points[0]]
    every = (len(points) - 2) / (threshold - 2)
    anchor = 0
    for index in range(threshold - 2):
        avg_start = int(math.floor((index + 1) * every)) + 1
        avg_end = min(int(math.floor((index + 2) * every)) + 1, len(points))
        average_x = sum(range(avg_start, avg_end)) / max(1, avg_end - avg_start)
        average_y = sum(point[1] for point in points[avg_start:avg_end]) / max(1, avg_end - avg_start)
        range_start = int(math.floor(index * every)) + 1
        range_end = min(int(math.floor((index + 1) * every)) + 1, len(points) - 1)
        anchor_y = points[anchor][1]
        best_area = -1.0
        best_index = range_start
        for candidate in range(range_start, range_end):
            area = abs((anchor - average_x) * (points[candidate][1] - anchor_y) - (anchor - candidate) * (average_y - anchor_y))
            if area > best_area:
                best_area = area
                best_index = candidate
        sampled.append(points[best_index])
        anchor = best_index
    sampled.append(points[-1])
    return sampled


def _downsample(points: list[tuple[str, float]], method: str, limit: int = 180) -> list[tuple[str, float]]:
    if len(points) <= limit:
        return points
    if method == "LTTB":
        return _lttb(points, limit)
    bucket_size = math.ceil(len(points) / limit)
    result = []
    for offset in range(0, len(points), bucket_size):
        bucket = points[offset : offset + bucket_size]
        result.append((bucket[-1][0], _bucket_reduce([row[1] for row in bucket], method)))
    return result


def _series_payload(item: dict[str, Any], points: list[tuple[str, float]]) -> dict[str, Any]:
    transform: Callable[[float], float] = item["transform"]
    return {
        "name": item["name"],
        "unit": item["unit"],
        "color": item["color"],
        "data": [round(float(transform(value)), 4) for _, value in points],
    }


def _chart(items: list[dict[str, Any]], points_by_name: dict[str, list[tuple[str, float]]]) -> dict[str, Any]:
    longest = max((points_by_name.get(item["name"], []) for item in items), key=len, default=[])
    return {
        "x_axis": [timestamp[11:19] if "T" in timestamp else timestamp[-12:-4] for timestamp, _ in longest],
        "series": [_series_payload(item, points_by_name.get(item["name"], [])) for item in items],
    }


def _timeseries_payload(
    session_id: str | None,
    mode: str,
    downsample: str,
    *,
    enforce_available: bool = True,
) -> dict[str, Any]:
    points_by_name: dict[str, list[tuple[str, float]]] = {}
    for item in SIGNAL_CATALOG:
        raw = _history_points(session_id, item["source"]) if mode == "history" and session_id else _live_points(item["source"])
        points_by_name[item["name"]] = _downsample(raw, downsample)

    def items(*names: str) -> list[dict[str, Any]]:
        return [item for name in names if (item := _catalog_item(name))]

    alarm_item = _catalog_item("Alarm_Level")
    alarm_points = points_by_name.get("Alarm_Level", [])
    alarm_chart = {
        "x_axis": [timestamp[11:19] if "T" in timestamp else timestamp[-12:-4] for timestamp, _ in alarm_points],
        "series": [
            {
                "name": label,
                "unit": "level",
                "color": color,
                "data": [value if int(value) == level else None for _, value in alarm_points],
            }
            for level, label, color in (
                (0, "正常", "#21C55D"),
                (1, "提示", "#2F80FF"),
                (2, "次要", "#F6C343"),
                (3, "严重", "#EF4444"),
            )
        ],
    } if alarm_item else {"x_axis": [], "series": []}
    charts = {
        "speed_vs_vehicle": _chart(items("SCU_Target_Speed", "Vehicle_Speed"), points_by_name),
        "speed_vs_wheels": _chart(items("SCU_Target_Speed", "FL_Wheel_Speed", "FR_Wheel_Speed", "RL_Wheel_Speed", "RR_Wheel_Speed"), points_by_name),
        "steering": _chart(items("Front_Steer_Cmd", "Front_Steer_Fdbk", "Rear_Steer_Cmd", "Rear_Steer_Fdbk"), points_by_name),
        "bms": _chart(items("BMS_Total_Voltage", "BMS_Current", "SOC"), points_by_name),
        "motor": _chart(items("Motor_Speed", "Motor_Current_A"), points_by_name),
        "alarm_timeline": alarm_chart,
    }
    point_count = sum(len(points) for points in points_by_name.values())
    quality = "good" if point_count else "unavailable"
    if enforce_available:
        require_data_in_production(point_count > 0, "signal timeseries")
    return {
        **dashboard_metadata("sqlite" if mode == "history" else "runtime", quality=quality),
        "mode": mode,
        "charts": charts,
    }


def live_timeseries_batch() -> dict[str, Any]:
    """Runtime payload shared by the REST endpoint and the 10 Hz WebSocket publisher."""
    return _timeseries_payload(None, "live", "平均值", enforce_available=False)


def _save_json_export(prefix: str, payload: Any) -> Path:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORTS_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def _action_file(path: Path, message: str) -> dict[str, Any]:
    return {
        "ok": True,
        "message": message,
        "trace_id": get_trace_id(),
        "details": {
            "file_name": path.name,
            "file_size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "download_url": f"/signals/exports/{path.name}",
        },
    }


@router.get("/signals/current", response_model=ObjectResponse)
async def current():
    snapshot = state.signals.snapshot()
    return {**snapshot, **dashboard_metadata("runtime", quality=snapshot["quality"], updated_at=snapshot["updated_at"])}


@router.get("/signals/dashboard", response_model=SignalDashboardResponse)
async def dashboard():
    watchlist = state.preferences.get("watchlist") if state.preferences else state.signals.watchlist
    payload = state.signals.dashboard_summary(watchlist)
    quality = payload["status"]["quality"]
    require_data_in_production(quality != "unavailable", "signal dashboard")
    return {**dashboard_metadata("runtime", quality=quality, updated_at=payload["status"]["updated_at"]), **payload}


@router.get("/signals/watchlist", response_model=ObjectResponse)
async def watchlist():
    keys = state.preferences.get("watchlist") if state.preferences else state.signals.watchlist
    return {"items": state.signals.watchlist_rows(keys), **dashboard_metadata("runtime+preferences", quality=state.signals.overall_quality())}


@router.post("/signals/watchlist", response_model=ActionResponse)
@router.put("/signals/watchlist", response_model=ActionResponse)
async def save_watchlist(
    payload: WatchlistUpdateRequest,
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    unknown = [key for key in payload.signals if key not in state.signals.current and key not in {item["source"] for item in SIGNAL_CATALOG}]
    if unknown:
        raise HTTPException(422, {"code": "UNKNOWN_SIGNAL", "message": "关注列表包含未知信号", "details": {"signals": unknown}})
    if state.preferences:
        state.preferences.set("watchlist", payload.signals)
    state.signals.watchlist = list(payload.signals)
    record_operator_action(state, principal, "save_signal_watchlist", "signals.watchlist", payload.model_dump(), trace_id=get_trace_id())
    return {"ok": True, "message": "关注信号已保存", "trace_id": get_trace_id(), "details": {"count": len(payload.signals)}}


@router.get("/signals/curve-config", response_model=CurveConfigResponse)
async def curve_config():
    payload = _curve_config_payload()
    require_data_in_production(payload["quality"] != "unavailable", "curve configuration current values")
    return payload


@router.get("/signals/timeseries", response_model=CurveTimeseriesResponse)
async def timeseries(
    session_id: str | None = None,
    group: str = "speed",
    signals: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    window: str = "5分钟",
    sample_rate: str = "100 Hz",
    downsample: str = Query(default="平均值", pattern="^(平均值|最大值|最小值|最后值|LTTB)$"),
    mode: str = Query(default="live", pattern="^(live|history)$"),
):
    _ = (group, signals, start_time, end_time, window, sample_rate)
    if mode == "history" and not session_id:
        raise HTTPException(422, {"code": "SESSION_REQUIRED", "message": "历史曲线需要 session_id", "details": {}})
    if mode == "history" and state.database and not state.database.query_one("SELECT id FROM test_sessions WHERE id=?", (session_id,)):
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在", "details": {"session_id": session_id}})
    return _timeseries_payload(session_id, mode, downsample)


@router.post("/signals/snapshot", response_model=ActionResponse)
async def snapshot(principal: Principal = Depends(require_role(Role.OPERATOR))):
    path = _save_json_export("signal_snapshot", {"snapshot": state.signals.snapshot(), "timeseries": state.signals.timeseries_batch(), "created_at": utc_now()})
    record_operator_action(state, principal, "export_signal_snapshot", path.name, {}, trace_id=get_trace_id())
    return _action_file(path, "信号快照已保存")


@router.post("/signals/export-csv", response_model=ActionResponse)
async def export_csv(
    payload: CurveSelectionRequest,
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORTS_DIR / f"signal_curve_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["signal", "timestamp", "value", "unit", "quality", "can_id", "channel"])
        for name in payload.signals:
            item = _catalog_item(name)
            source = item["source"] if item else name
            for row in state.signals.timeseries.get(source, []):
                writer.writerow([name, row.get("t"), row.get("value"), item["unit"] if item else row.get("unit"), row.get("quality"), row.get("can_id"), row.get("channel")])
    record_operator_action(state, principal, "export_signal_csv", path.name, payload.model_dump(), trace_id=get_trace_id())
    return _action_file(path, "曲线 CSV 已导出")


@router.get("/signals/exports/{file_id}")
async def download_signal_export(file_id: str, _principal: Principal = Depends(require_role(Role.VIEWER))):
    validate_file_id(file_id)
    path = normalize_allowed_path(EXPORTS_DIR / file_id, [EXPORTS_DIR], expect_file=True)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream", headers={"X-Trace-Id": get_trace_id()})


@router.put("/signals/curve-selection", response_model=ActionResponse)
async def curve_selection(
    payload: CurveSelectionRequest,
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    unknown = [name for name in payload.signals if _catalog_item(name) is None]
    if unknown:
        raise HTTPException(422, {"code": "UNKNOWN_CURVE_SIGNAL", "message": "曲线选择包含未知信号", "details": {"signals": unknown}})
    if state.preferences:
        state.preferences.set("curve_selection", payload.signals)
    record_operator_action(state, principal, "save_curve_selection", "signals.curves", payload.model_dump(), trace_id=get_trace_id())
    return {"ok": True, "message": "曲线信号选择已保存", "trace_id": get_trace_id(), "details": {"count": len(payload.signals)}}


@router.get("/signals/threshold-status", response_model=ObjectResponse)
async def thresholds():
    return {"items": state.signals.threshold_status(), **dashboard_metadata("runtime", quality=state.signals.overall_quality())}


@router.put("/signals/dashboard-layout", response_model=ActionResponse)
async def save_dashboard_layout(
    payload: DashboardLayoutRequest,
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    if state.preferences:
        state.preferences.set("signal_dashboard_layout", payload.layout)
    record_operator_action(state, principal, "save_signal_dashboard_layout", "signals.dashboard", payload.model_dump(), trace_id=get_trace_id())
    return {"ok": True, "message": "仪表盘布局已保存", "trace_id": get_trace_id(), "details": {}}


@router.post("/signals/dashboard-layout/reset", response_model=ActionResponse)
async def reset_dashboard_layout(principal: Principal = Depends(require_role(Role.OPERATOR))):
    if state.preferences:
        state.preferences.set("signal_dashboard_layout", {})
    record_operator_action(state, principal, "reset_signal_dashboard_layout", "signals.dashboard", {}, trace_id=get_trace_id())
    return {"ok": True, "message": "仪表盘布局已重置", "trace_id": get_trace_id(), "details": {}}
