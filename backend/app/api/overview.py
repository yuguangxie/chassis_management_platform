from __future__ import annotations

from collections import Counter
from datetime import datetime
import time
from typing import Any

from fastapi import APIRouter

from app.api.data_source import dashboard_metadata
from app.api.errors import get_trace_id
from app.api.models import OverviewDashboardResponse
from app.core.time import utc_now
from app.services.app_state import state


router = APIRouter()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_time(value: str | None) -> str:
    return str(value).replace("T", " ")[:19] if value else "—"


def _session_rows(limit: int = 200) -> list[dict[str, Any]]:
    if state.database is None:
        return []
    rows = state.database.query(
        "SELECT * FROM test_sessions ORDER BY COALESCE(started_at,created_at) DESC LIMIT ?",
        (limit,),
    )
    results = []
    for row in rows:
        report = state.database.query_one(
            "SELECT id FROM reports WHERE session_id=? ORDER BY generated_at DESC LIMIT 1",
            (row["id"],),
        )
        result = str(row.get("overall_result") or row.get("status") or "RUNNING").upper()
        result = {"PASSED": "PASS", "FAILED": "FAIL", "IDLE": "RUNNING"}.get(result, result)
        results.append(
            {
                **row,
                "session_id": row["id"],
                "result": result,
                "report": report["id"] if report else None,
            }
        )
    return results


def _channel_payload(name: str) -> dict[str, Any]:
    status = next(
        (row for row in (state.can.status() if state.can else []) if row.get("channel") == name),
        None,
    )
    config = next((row for row in state.config.channels if row.channel == name), None)
    if status is None:
        return {
            "online": False,
            "local": f"{config.local_ip}:{config.local_receive_port}" if config else "-",
            "device": f"{config.device_ip}:{config.device_port}" if config else "-",
            "protocol": config.protocol.upper() if config else "-",
            "fps": 0,
            "error_frames": 0,
            "last_frame_ms": -1,
            "last_data_hex": "",
        }
    return {
        "online": bool(status.get("online")),
        "local": f'{status.get("local_ip")}:{status.get("local_port")}',
        "device": f'{status.get("device_ip")}:{status.get("device_port")}',
        "protocol": str(status.get("protocol") or "-").upper(),
        "fps": round(float(status.get("fps") or 0)),
        "error_frames": int(status.get("error_count") or 0),
        "last_frame_ms": int(status.get("receive_age_ms")) if status.get("receive_age_ms") is not None else -1,
        "last_data_hex": str(status.get("last_frame_hex") or ""),
    }


def _today_metrics(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    today = datetime.now().date().isoformat()
    today_rows = [row for row in rows if str(row.get("started_at") or row.get("created_at") or "").startswith(today)]
    counts = Counter(row["result"] for row in today_rows)
    passed = counts["PASS"]
    failed = counts["FAIL"]
    durations = []
    for row in today_rows:
        start, end = _parse_time(row.get("started_at")), _parse_time(row.get("ended_at"))
        if start and end:
            durations.append(max(0, int((end - start).total_seconds())))
    average = round(sum(durations) / len(durations)) if durations else 0
    total = len(today_rows)
    kpi = {
        "today_total": total,
        "pass_rate": round(passed / total * 100, 1) if total else 0.0,
        "fail_count": failed,
        "avg_duration": f"{average // 60:02d}:{average % 60:02d}",
        "software_version": state.config.software_version,
    }
    result_chart = {
        "total": total,
        "items": [
            {
                "name": name,
                "value": counts[name],
                "percent": round(counts[name] / total * 100, 1) if total else 0.0,
            }
            for name in ("PASS", "FAIL", "RUNNING", "ABORTED")
        ],
    }
    hourly_counts = Counter()
    for row in today_rows:
        started = _parse_time(row.get("started_at"))
        if started:
            hourly_counts[started.hour] += 1
    hourly = [{"hour": f"{hour:02d}", "value": hourly_counts[hour]} for hour in range(0, 24, 2)]
    return kpi, result_chart, hourly


def _fps_trend() -> list[dict[str, Any]]:
    if state.database is not None:
        rows = state.database.query(
            "SELECT channel,fps,COALESCE(window_end_at,created_at) AS sample_time "
            "FROM signal_statistics ORDER BY id DESC LIMIT 40"
        )
        grouped: dict[str, dict[str, float]] = {}
        for row in reversed(rows):
            label = str(row.get("sample_time") or "")[-8:-3] or "--:--"
            grouped.setdefault(label, {})[str(row["channel"])] = float(row.get("fps") or 0)
        if grouped:
            return [
                {"time": label, "can1": values.get("CAN1", 0), "can2": values.get("CAN2", 0)}
                for label, values in list(grouped.items())[-7:]
            ]
    statuses = state.can.status() if state.can else []
    values = {row["channel"]: float(row.get("fps") or 0) for row in statuses}
    return [{"time": datetime.now().strftime("%H:%M"), "can1": values.get("CAN1", 0), "can2": values.get("CAN2", 0)}]


def _protection_items() -> list[dict[str, str]]:
    mappings = [
        ("过压保护", "BMS_Protect_Over_Voltage"),
        ("欠压保护", "BMS_Protect_Under_Voltage"),
        ("过流保护", "BMS_Protect_Over_Current"),
        ("过温保护", "BMS_Protect_Over_Temperature"),
        ("短路保护", "BMS_Protect_Short_Circuit"),
        ("MOS故障", "BMS_Protect_MOS_Fault"),
        ("预充故障", "BMS_Protect_Precharge_Fault"),
        ("SOC过低", "BMS_SOC"),
    ]
    rows = []
    for label, key in mappings:
        item = state.signals.current.get(key)
        if key == "BMS_SOC":
            status = "无数据" if item is None else "异常" if float(item.get("value") or 0) < 30 else "正常"
        else:
            status = "无数据" if item is None else "触发" if bool(item.get("value")) else "正常"
        rows.append({"name": label, "status": status})
    return rows


def _current_vehicle(rows: list[dict[str, Any]]) -> dict[str, Any]:
    active = None
    if state.eol and state.eol.active_session_id:
        active = state.eol.sessions.get(state.eol.active_session_id)
    row = active or (rows[0] if rows else {})
    session_id = row.get("id") or row.get("session_id") or "-"
    step_name = row.get("current_step_name") or "-"
    if not active and session_id != "-" and state.database:
        step = state.database.query_one(
            "SELECT name FROM test_steps WHERE session_id=? ORDER BY step_order DESC LIMIT 1",
            (session_id,),
        )
        step_name = step["name"] if step else "-"
    return {
        "chassis_no": row.get("chassis_no") or "-",
        "vin": row.get("vin") or "-",
        "serial_no": row.get("serial_no") or "-",
        "test_plan": row.get("plan_name") or row.get("test_plan_id") or "-",
        "operator": row.get("operator") or state.config.operator,
        "current_step": step_name,
        "session_id": session_id,
    }


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": state.config.software_version,
        "database_writable": state.db_writable,
        "dbc": state.dbc.status() if state.dbc else {},
        "trace_id": get_trace_id(),
    }


@router.get("/overview/summary", response_model=OverviewDashboardResponse)
async def overview():
    snapshot = state.snapshot()
    sessions = _session_rows()
    kpi, result_chart, hourly = _today_metrics(sessions)
    recent = [
        {
            "session_id": row["session_id"],
            "chassis_no": row.get("chassis_no") or "-",
            "vin": row.get("vin") or "-",
            "started_at": _format_time(row.get("started_at")),
            "ended_at": _format_time(row.get("ended_at")),
            "result": row["result"],
            "operator": row.get("operator") or "-",
            "report": row.get("report"),
        }
        for row in sessions[:4]
    ]
    signal_quality = state.signals.overall_quality()
    quality = "good" if state.db_writable and signal_quality == "good" else "degraded"
    max_alarm = int(snapshot.get("max_alarm_level") or 0)
    protections = _protection_items()
    return {
        **dashboard_metadata("runtime+sqlite", quality=quality),
        "station": {
            "station_id": snapshot["station_id"],
            "operator": snapshot["operator"],
            "software_version": snapshot["software_version"],
            "dbc_version": snapshot.get("dbc", {}).get("version") or "raw-only",
            "database": {"name": "SQLite", "status": "normal" if state.db_writable else "fault"},
            "control_channel": snapshot["control_channel"],
            "mock_enabled": bool(snapshot["mock_enabled"]),
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "kpi": kpi,
        "channels": {"CAN1": _channel_payload("CAN1"), "CAN2": _channel_payload("CAN2")},
        "current_vehicle": _current_vehicle(sessions),
        "alarm_summary": {
            "max_alarm_level": max_alarm,
            "max_alarm_label": {0: "Normal", 1: "Warning", 2: "Fault", 3: "Critical"}.get(min(3, max_alarm), "Critical"),
            "bms_protect_status": "无数据" if all(item["status"] == "无数据" for item in protections) else "存在触发" if any(item["status"] in {"触发", "异常"} for item in protections) else "全部未触发",
            "emergency_stop": bool(snapshot["emergency_stop"]),
            "protection_items": protections,
        },
        "charts": {"today_result": result_chart, "hourly_output": hourly, "fps_trend": _fps_trend()},
        "recent_sessions": recent,
        "status": snapshot,
        "signals": state.signals.snapshot(),
    }
