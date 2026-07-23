from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.data_source import dashboard_metadata
from app.api.errors import get_trace_id
from app.api.models import EolDashboardResponse

from app.control.safety_interlock import InterlockBlocked
from app.eol.engine import SessionConflict
from app.eol.models import CreateSessionRequest
from app.security.auth import Principal, Role, require_role
from app.services.app_state import state
from app.services.audit import AuditPersistenceError, record_operator_action
from app.storage.uow import PersistenceFailure


router = APIRouter()
logger = logging.getLogger(__name__)


async def _required_eol_audit(
    principal: Principal,
    action: str,
    sid: str,
    payload: dict[str, Any] | None = None,
    result: str = "OK",
) -> None:
    try:
        record_operator_action(
            state,
            principal,
            action,
            sid,
            payload or {},
            result,
            trace_id=get_trace_id(),
            required=True,
        )
    except AuditPersistenceError:
        state.safe_stop_latched = True
        if state.tx_scheduler:
            await state.tx_scheduler.stop()
        raise


def _latest_session() -> dict[str, Any] | None:
    if state.eol and state.eol.sessions:
        return list(state.eol.sessions.values())[-1] | {"_source": "actual_session"}
    if not state.database:
        return None
    row = state.database.query_one(
        "SELECT * FROM test_sessions ORDER BY created_at DESC, rowid DESC LIMIT 1"
    )
    if not row:
        return None
    step_rows = state.database.query(
        "SELECT * FROM test_steps WHERE session_id=? ORDER BY step_order", (row["id"],)
    )
    assertion_rows = state.database.query(
        "SELECT * FROM test_assertions WHERE session_id=? ORDER BY id", (row["id"],)
    )
    assertions_by_step: dict[str, list[dict[str, Any]]] = {}
    for assertion in assertion_rows:
        try:
            threshold = json.loads(assertion.get("threshold_json") or "null")
        except json.JSONDecodeError:
            threshold = assertion.get("threshold_json")
        try:
            measured = json.loads(assertion.get("measured_value") or "null")
        except json.JSONDecodeError:
            measured = assertion.get("measured_value")
        assertions_by_step.setdefault(str(assertion["step_id"]), []).append(
            {
                "assertion_id": assertion["assertion_id"],
                "description": assertion.get("description", ""),
                "signal_name": assertion.get("signal_name", ""),
                "operator": assertion.get("operator", ""),
                "threshold": threshold,
                "measured_value": measured,
                "unit": assertion.get("unit", ""),
                "result": assertion.get("result", "WAIT"),
                "failure_reason": assertion.get("failure_reason", ""),
                "quality": assertion.get("quality") or "persisted",
                "source_can_id": assertion.get("source_can_id", ""),
                "source_channel": assertion.get("source_channel", ""),
                "source_timestamp": assertion.get("source_timestamp")
                or assertion.get("sample_end_at", ""),
            }
        )
    steps = [
        {
            "id": item["step_id"],
            "order": item["step_order"],
            "name": item["name"],
            "status": item["status"],
            "result": item.get("result"),
            "started_at": item.get("started_at"),
            "ended_at": item.get("ended_at"),
            "duration_ms": item.get("duration_ms"),
            "failure_reason": item.get("failure_reason", ""),
            "assertions": assertions_by_step.get(str(item["step_id"]), []),
        }
        for item in step_rows
    ]
    actions = state.database.query(
        "SELECT timestamp_utc,operator,action_type,result FROM operator_actions "
        "WHERE session_id=? ORDER BY id DESC LIMIT 100",
        (row["id"],),
    )
    return {
        **row,
        "_source": "database_session",
        "steps": steps,
        "logs": [
            {
                "time": item["timestamp_utc"],
                "step": "会话审计",
                "action": item["action_type"],
                "can_command": item["operator"],
                "feedback": "",
                "status": item["result"],
            }
            for item in reversed(actions)
        ],
        "measurements": [
            {
                "name": item.get("description") or item.get("assertion_id", ""),
                "value": item.get("measured_value", "--"),
                "unit": item.get("unit", ""),
                "quality": item.get("quality", "persisted"),
                "source_can_id": item.get("source_can_id", ""),
                "source_timestamp": item.get("source_timestamp", ""),
            }
            for item in (steps[-1].get("assertions", []) if steps else [])
        ],
        "remarks": row.get("remarks", ""),
    }


def _elapsed(started_at: str | None, ended_at: str | None = None) -> str:
    if not started_at:
        return "00:00:00"
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(ended_at) if ended_at else datetime.now(timezone.utc)
        seconds = max(0, int((end - start).total_seconds()))
    except (TypeError, ValueError):
        return "00:00:00"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _remaining(completed: int, elapsed_text: str, total: int) -> str:
    if completed <= 0:
        return "--:--:--"
    hours, minutes, seconds = (int(value) for value in elapsed_text.split(":"))
    elapsed_seconds = hours * 3600 + minutes * 60 + seconds
    remaining_seconds = max(0, round(elapsed_seconds / completed * (total - completed)))
    hours, remainder = divmod(remaining_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _status_for_ui(status: str) -> str:
    return {
        "IDLE": "WAIT",
        "RUNNING": "RUNNING",
        "WAITING_OPERATOR": "RUNNING",
        "PAUSED": "PAUSED",
        "ABORTED": "ABORTED",
        "EMERGENCY_STOPPED": "ABORTED",
        "FAILED": "FAIL",
        "PASSED": "PASS",
    }.get(status, "WAIT")


def _threshold_text(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _charts() -> dict[str, Any]:
    keys = [
        ("CCU_Vehicle_Speed", "车速(km/h)"),
        ("SAS_Front_Angle", "转向角(°)"),
        ("BMS_Voltage", "BMS总压(V)"),
        ("VCU_Max_Warning_Level", "告警级别"),
    ]
    batches = state.signals.timeseries_batch([key for key, _ in keys])
    source = next((batches.get(key, []) for key, _ in keys if batches.get(key)), [])[-40:]
    x_axis = [str(item.get("t", ""))[11:19] for item in source]
    series = []
    for key, label in keys:
        values = [float(item.get("value", 0)) for item in batches.get(key, [])[-40:]]
        if len(values) < len(x_axis):
            values = [0.0] * (len(x_axis) - len(values)) + values
        series.append({"name": label, "data": values[-len(x_axis):] if x_axis else []})
    return {"realtime": {"x_axis": x_axis, "series": series}}


def _dashboard() -> dict[str, Any]:
    runtime = _latest_session()
    plan = state.eol.plan if state.eol else None
    plan_steps = plan.steps if plan else []
    actual_steps = {step["id"]: step for step in (runtime or {}).get("steps", [])}
    ui_steps: list[dict[str, Any]] = []
    for plan_step in plan_steps:
        actual = actual_steps.get(plan_step.id)
        if not actual:
            status = "WAIT"
        elif actual.get("status") == "RUNNING":
            status = "RUNNING"
        else:
            status = actual.get("result") or "WAIT"
        ui_steps.append({"index": plan_step.order, "name": plan_step.name, "status": status})

    completed_steps = [
        step for step in (runtime or {}).get("steps", []) if step.get("status") != "RUNNING"
    ]
    passed = sum(step.get("result") == "PASS" for step in completed_steps)
    failed = sum(step.get("result") == "FAIL" for step in completed_steps)
    current = next(
        (step for step in reversed((runtime or {}).get("steps", [])) if step.get("status") == "RUNNING"),
        completed_steps[-1] if completed_steps else None,
    )
    current_plan = next(
        (step for step in plan_steps if current and step.id == current.get("id")),
        plan_steps[0] if plan_steps else None,
    )
    elapsed = _elapsed(
        (runtime or {}).get("started_at"),
        (runtime or {}).get("ended_at"),
    )
    total = len(plan_steps)
    session = {
        "session_id": (runtime or {}).get("id", ""),
        "chassis_no": (runtime or {}).get("chassis_no", "-"),
        "vin": (runtime or {}).get("vin", ""),
        "serial_no": (runtime or {}).get("serial_no", ""),
        "operator": (runtime or {}).get("operator", state.config.operator),
        "station_id": (runtime or {}).get("station_id", state.config.station_id),
        "vehicle_series": (runtime or {}).get("vehicle_series", state.config.vehicle_series),
        "work_order_id": (runtime or {}).get("work_order_id", ""),
        "test_plan": plan.plan.name if plan else "未加载",
        "remark": (runtime or {}).get("remarks", ""),
        "overall_status": _status_for_ui((runtime or {}).get("status", "IDLE")),
        "elapsed": elapsed,
        "remaining": _remaining(len(completed_steps), elapsed, total),
        "completed": len(completed_steps),
        "passed": passed,
        "failed": failed,
        "waiting": max(0, total - len(completed_steps)),
        "total": total,
        "current_step_index": current.get("order", 0) if current else 0,
        "current_step_key": current.get("id", "") if current else "",
        "current_step_name": current.get("name", "等待开始") if current else "等待开始",
    }
    assertions = []
    for item in (current or {}).get("assertions", []):
        assertions.append(
            {
                "description": item.get("description") or item.get("assertion_id", ""),
                "signal": item.get("signal_name", ""),
                "threshold": _threshold_text(item.get("threshold")),
                "value": _threshold_text(item.get("measured_value")),
                "result": item.get("result", "WAIT"),
                "fail_reason": item.get("failure_reason", "-"),
                "quality": item.get("quality", "unknown"),
                "source_can_id": item.get("source_can_id", ""),
                "source_timestamp": item.get("source_timestamp", ""),
            }
        )
    first_action = current_plan.control_actions[0] if current_plan and current_plan.control_actions else None
    stats = {
        "pass_rate": round(passed / len(completed_steps) * 100, 1) if completed_steps else 0,
        "passed": passed,
        "failed": failed,
        "waiting": max(0, total - len(completed_steps)),
        "total_elapsed": elapsed,
        "avg_step_duration": _remaining(len(completed_steps), elapsed, len(completed_steps) + 1)
        if completed_steps
        else "00:00:00",
    }
    quality = "good" if runtime else "unavailable"
    return {
        **dashboard_metadata(
            "runtime" if runtime and runtime.get("_source") == "actual_session" else "sqlite" if runtime else "idle",
            quality=quality,
        ),
        "source": runtime.get("_source", "idle") if runtime else "idle",
        "runtime_profile": state.config.profile,
        "mock_session_allowed": state.config.profile in {"dev", "mock", "test"},
        "session": session,
        "steps": ui_steps,
        "current_step": {
            "title": current_plan.name if current_plan else "等待开始",
            "description": current_plan.description if current_plan else "尚未创建检测会话。",
            "command": json.dumps(first_action.model_dump(), ensure_ascii=False) if first_action else "无控制动作",
            "period_ms": first_action.period_ms if first_action else 0,
            "timeout_ms": current_plan.timeout_ms if current_plan else 0,
        },
        "measurements": (runtime or {}).get("measurements", []),
        "assertions": assertions,
        "step_logs": (runtime or {}).get("logs", [])[-100:],
        "charts": _charts(),
        "stats": stats,
        "report": (runtime or {}).get("report"),
        "safe_stop": (runtime or {}).get("safe_stop_result"),
    }


@router.get("/eol/dashboard", response_model=EolDashboardResponse)
async def dashboard(_principal: Principal = Depends(require_role(Role.VIEWER))):
    return _dashboard()


@router.post("/eol/sessions")
async def create(
    req: CreateSessionRequest,
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    if not state.eol:
        raise HTTPException(503, {"code": "EOL_UNAVAILABLE", "message": "EOL 引擎未初始化"})
    try:
        session = state.eol.create_session(
            req,
            operator=principal.username,
            operator_role=principal.role.value,
            auth_session_id=principal.session_id,
            station_id=state.config.station_id,
            trace_id=get_trace_id(),
        )
    except ValueError as exc:
        code = "DUPLICATE_VEHICLE_IDENTITY" if "duplicate vehicle identity" in str(exc) else "EOL_SESSION_INVALID"
        raise HTTPException(409 if code.startswith("DUPLICATE") else 422, {"code": code, "message": str(exc), "details": {"blocking": True}}) from exc
    except PersistenceFailure as exc:
        raise HTTPException(
            503, {"code": "DATABASE_UNWRITABLE", "message": str(exc)}
        ) from exc
    return session


@router.post("/eol/sessions/{sid}/start")
async def start(sid: str, principal: Principal = Depends(require_role(Role.OPERATOR))):
    if not state.eol or sid not in state.eol.sessions:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})
    await _required_eol_audit(principal, "eol_start_request", sid, result="PENDING")
    try:
        result = await state.eol.start(sid)
    except InterlockBlocked as exc:
        await _required_eol_audit(principal, "eol_start", sid, result="BLOCKED")
        raise HTTPException(
            409,
            {"code": "INTERLOCK_BLOCKED", "message": "安全联锁阻止开始检测", "details": exc.evaluation},
        ) from exc
    except SessionConflict as exc:
        raise HTTPException(409, {"code": "STATION_BUSY", "message": str(exc)}) from exc
    except PersistenceFailure as exc:
        raise HTTPException(503, {"code": "DATABASE_UNWRITABLE", "message": str(exc)}) from exc
    await _required_eol_audit(principal, "eol_start", sid)
    return result


@router.post("/eol/sessions/{sid}/pause")
async def pause(sid: str, principal: Principal = Depends(require_role(Role.OPERATOR))):
    if not state.eol or sid not in state.eol.sessions:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})
    await _required_eol_audit(principal, "eol_pause_request", sid, result="PENDING")
    result = await state.eol.pause(sid)
    await _required_eol_audit(principal, "eol_pause", sid)
    return result


@router.post("/eol/sessions/{sid}/resume")
async def resume(sid: str, principal: Principal = Depends(require_role(Role.OPERATOR))):
    if not state.eol or sid not in state.eol.sessions:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})
    await _required_eol_audit(principal, "eol_resume_request", sid, result="PENDING")
    try:
        result = await state.eol.resume(sid)
    except InterlockBlocked as exc:
        await _required_eol_audit(principal, "eol_resume", sid, result="BLOCKED")
        raise HTTPException(
            409,
            {"code": "INTERLOCK_BLOCKED", "message": "安全联锁阻止继续检测", "details": exc.evaluation},
        ) from exc
    await _required_eol_audit(principal, "eol_resume", sid)
    return result


@router.post("/eol/sessions/{sid}/manual-confirm")
async def manual_confirm(
    sid: str,
    payload: dict[str, Any] = Body(...),
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    if not state.eol or sid not in state.eol.sessions:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})
    await _required_eol_audit(
        principal, "eol_manual_confirm_request", sid, payload, "PENDING"
    )
    try:
        result = await state.eol.confirm_manual(
            sid,
            approved=bool(payload.get("approved")),
            note=str(payload.get("note", "")),
            operator=principal.username,
        )
    except RuntimeError as exc:
        raise HTTPException(409, {"code": "MANUAL_STEP_NOT_WAITING", "message": str(exc)}) from exc
    await _required_eol_audit(principal, "eol_manual_confirm", sid, payload)
    return result


@router.post("/eol/sessions/{sid}/abort")
async def abort(sid: str, principal: Principal = Depends(require_role(Role.OPERATOR))):
    if not state.eol or sid not in state.eol.sessions:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})
    session = await state.eol.abort(sid, "operator abort")
    stop_result = await state.safe_stop.execute(
        emergency=False, principal=principal, reason=f"EOL abort {sid}"
    )
    session = state.eol.attach_safe_stop_result(sid, stop_result)
    await _required_eol_audit(
        principal,
        "eol_abort",
        sid,
        {"stop": stop_result},
        "OK" if stop_result["ok"] else stop_result["code"],
    )
    if not stop_result["ok"]:
        raise HTTPException(
            409 if stop_result["code"] == "INTERLOCK_BLOCKED" else 504,
            {**stop_result, "session": session},
        )
    return {**session, "safe_stop": stop_result}


@router.post("/eol/sessions/{sid}/emergency-stop")
async def emergency_stop(
    sid: str, principal: Principal = Depends(require_role(Role.OPERATOR))
):
    if not state.eol or sid not in state.eol.sessions:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})
    session = await state.eol.emergency_stop(sid, "EOL emergency stop")
    stop_result = await state.safe_stop.execute(
        emergency=True, principal=principal, reason=f"EOL emergency {sid}"
    )
    session = state.eol.attach_safe_stop_result(sid, stop_result)
    await _required_eol_audit(
        principal,
        "eol_emergency_stop",
        sid,
        {"stop": stop_result},
        "OK" if stop_result["ok"] else stop_result["code"],
    )
    if not stop_result["ok"]:
        raise HTTPException(
            409 if stop_result["code"] == "INTERLOCK_BLOCKED" else 504,
            {**stop_result, "session": session},
        )
    return {"ok": True, "session": session, "stop": stop_result}


@router.post("/eol/sessions/{sid}/report")
async def report(sid: str, principal: Principal = Depends(require_role(Role.OPERATOR))):
    if not state.eol or sid not in state.eol.sessions:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})
    await _required_eol_audit(
        principal, "eol_generate_report_request", sid, result="PENDING"
    )
    try:
        generated = await state.eol.generate_report(sid)
    except Exception as exc:
        raise HTTPException(500, {"code": "REPORT_GENERATION_FAILED", "message": str(exc)}) from exc
    await _required_eol_audit(principal, "eol_generate_report", sid)
    return {"ok": True, "message": "报告已生成", "report": generated}


@router.get("/eol/sessions/{sid}")
async def get(sid: str, _principal: Principal = Depends(require_role(Role.VIEWER))):
    if state.eol and sid in state.eol.sessions:
        return state.eol.session_snapshot(sid)
    if state.eol_uow:
        rows = state.eol_uow.session_rows(sid)
        if rows["session"]:
            return rows
    raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})


@router.get("/eol/sessions/{sid}/logs")
async def logs(sid: str, _principal: Principal = Depends(require_role(Role.VIEWER))):
    if state.eol and sid in state.eol.sessions:
        return {"session_id": sid, "items": state.eol.sessions[sid].get("logs", [])}
    raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})


@router.get("/eol/sessions/{sid}/assertions")
async def assertions(sid: str, _principal: Principal = Depends(require_role(Role.VIEWER))):
    if state.eol and sid in state.eol.sessions:
        items = [
            assertion
            for step in state.eol.sessions[sid].get("steps", [])
            for assertion in step.get("assertions", [])
        ]
        return {"session_id": sid, "items": items}
    if state.eol_uow:
        rows = state.eol_uow.session_rows(sid)
        if rows["session"]:
            return {"session_id": sid, "items": rows["assertions"]}
    raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})


@router.get("/eol/sessions/{sid}/charts")
async def charts(sid: str, _principal: Principal = Depends(require_role(Role.VIEWER))):
    if not state.eol or sid not in state.eol.sessions:
        raise HTTPException(404, {"code": "SESSION_NOT_FOUND", "message": "检测会话不存在"})
    return {"session_id": sid, "charts": _charts()}
