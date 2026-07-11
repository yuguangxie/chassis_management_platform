from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.control.control_121 import Control121Command, preview
from app.control.safety_interlock import InterlockBlocked
from app.security.auth import Principal, Role, require_role
from app.services.app_state import state
from app.services.audit import record_operator_action

router = APIRouter()


def _command_from_payload(payload: Any | None = None) -> Control121Command:
    if isinstance(payload, Control121Command):
        return payload
    raw = payload if isinstance(payload, dict) else {}
    return Control121Command(
        shift=raw.get("gear", raw.get("shift", "D")),
        drive_mode=raw.get("drive_mode", "Remote"),
        target_speed_kmh=float(raw.get("target_speed", raw.get("target_speed_kmh", 2.0))),
        front_steering_cmd=int(raw.get("front_steer", raw.get("front_steering_cmd", 12))),
        rear_steering_cmd=int(raw.get("rear_steer", raw.get("rear_steering_cmd", 0))),
        brake_enable=bool(raw.get("brake_enable", True)),
        left_light=bool(raw.get("left_turn", raw.get("left_light", False))),
        right_light=bool(raw.get("right_turn", raw.get("right_light", False))),
        position_light=bool(raw.get("position_light", True)),
        low_beam=bool(raw.get("low_beam", True)),
        speed_mode=raw.get("control_mode", "speed") == "speed" or bool(raw.get("speed_mode", False)),
    )


def _interlock_http_error(exc: InterlockBlocked) -> HTTPException:
    return HTTPException(
        409,
        {
            "code": "INTERLOCK_BLOCKED",
            "message": "安全联锁阻止控制",
            "details": exc.evaluation,
        },
    )


def _status_payload() -> dict[str, Any]:
    evaluation = state.safety.evaluate(operation="manual") if state.safety else {"allowed": False, "reasons": []}
    scheduler = state.tx_scheduler
    periodic = bool(scheduler and scheduler.task and not scheduler.task.done())
    return {
        "can_send_allowed": bool(evaluation["allowed"]),
        "control_message": "0x121",
        "period_ms": scheduler.period_ms if scheduler else 20,
        "control_channel": state.config.control_channel,
        "periodic_running": periodic,
        "last_tx_time": scheduler.last_tx_time if scheduler else None,
        "tx_fail_count": scheduler.fail_count if scheduler else 0,
        "emergency_stop": state.emergency_stop,
        "safe_stop_active": state.safe_stop_active,
        "safe_stop_latched": state.safe_stop_latched,
        "interlock": evaluation,
    }


def _interlock_status_payload() -> dict[str, Any]:
    evaluation = state.safety.evaluate(operation="manual") if state.safety else {"allowed": False, "rules": [], "reasons": []}
    items = [
        {
            "key": rule["rule"],
            "label": rule["label"],
            "status": "pass" if rule["status"] == "PASS" else "fail",
            "value": str(rule.get("current")),
        }
        for rule in evaluation.get("rules", [])
    ]
    return {
        "overall": "allow" if evaluation.get("allowed") else "block",
        "items": items,
        "reasons": [rule["label"] for rule in evaluation.get("reasons", [])],
        "evaluation": evaluation,
    }


@router.get("/control/status")
async def status(_principal: Principal = Depends(require_role(Role.VIEWER))):
    return _status_payload()


@router.get("/control/interlock-status")
async def interlock_status(_principal: Principal = Depends(require_role(Role.VIEWER))):
    return _interlock_status_payload()


@router.post("/control/121/preview")
async def control_preview(
    payload: Any = Body(default=None),
    _principal: Principal = Depends(require_role(Role.ENGINEER)),
):
    return preview(_command_from_payload(payload))


@router.post("/control/121/send-once")
async def send_once(
    payload: Any = Body(default=None),
    principal: Principal = Depends(require_role(Role.ENGINEER)),
):
    command = _command_from_payload(payload)
    try:
        result = await state.tx_scheduler.send_once(command)
    except InterlockBlocked as exc:
        record_operator_action(state, principal, "control_send_once", "0x121", command.model_dump(), "BLOCKED")
        raise _interlock_http_error(exc)
    record_operator_action(state, principal, "control_send_once", "0x121", command.model_dump())
    return {**result, "message": "0x121 已发送一次"}


@router.post("/control/121/start-periodic")
async def start_periodic(
    payload: Any = Body(default=None),
    period_ms: int = 20,
    principal: Principal = Depends(require_role(Role.ENGINEER)),
):
    command = _command_from_payload(payload)
    try:
        result = await state.tx_scheduler.start(command, period_ms)
    except InterlockBlocked as exc:
        record_operator_action(state, principal, "control_start_periodic", "0x121", command.model_dump(), "BLOCKED")
        raise _interlock_http_error(exc)
    record_operator_action(state, principal, "control_start_periodic", "0x121", command.model_dump() | {"period_ms": period_ms})
    return {**result, "message": "0x121 周期发送已启动"}


@router.post("/control/121/stop")
async def stop(principal: Principal = Depends(require_role(Role.ENGINEER))):
    result = await state.tx_scheduler.stop()
    record_operator_action(state, principal, "control_stop_periodic", "0x121", {})
    return {**result, "message": "0x121 周期发送已停止"}


async def _run_stop(
    *, emergency: bool, principal: Principal, payload: dict[str, Any]
) -> dict:
    if state.safe_stop is None:
        raise HTTPException(503, {"code": "STOP_SERVICE_UNAVAILABLE", "message": "停车服务未初始化"})
    result = await state.safe_stop.execute(
        emergency=emergency,
        principal=principal,
        reason=str(payload.get("reason") or ("manual emergency stop" if emergency else "manual safe stop")),
        timeout_ms=payload.get("timeout_ms"),
    )
    if not result["ok"]:
        status_code = 409 if result["code"] == "INTERLOCK_BLOCKED" else 504
        raise HTTPException(status_code, result)
    return result


@router.post("/control/safe-stop")
async def safe_stop(
    payload: dict[str, Any] = Body(default_factory=dict),
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    return await _run_stop(emergency=False, principal=principal, payload=payload)


@router.post("/control/emergency-stop")
async def emergency_stop(
    payload: dict[str, Any] = Body(default_factory=dict),
    principal: Principal = Depends(require_role(Role.OPERATOR)),
):
    if state.eol:
        for session_id, session in list(state.eol.sessions.items()):
            if session.get("status") in {"RUNNING", "PAUSED"}:
                await state.eol.emergency_stop(session_id, "control API emergency stop")
    return await _run_stop(emergency=True, principal=principal, payload=payload)


@router.post("/control/emergency-stop/release")
async def release(
    payload: dict[str, Any] = Body(default_factory=dict),
    principal: Principal = Depends(require_role(Role.ENGINEER)),
):
    result = await state.safe_stop.release_emergency(
        principal,
        confirmation=str(payload.get("confirmation") or ""),
        reason=str(payload.get("reason") or "manual confirmation"),
    )
    if not result["ok"]:
        raise HTTPException(409, result)
    return result


@router.post("/control/reset-defaults")
async def reset_defaults(principal: Principal = Depends(require_role(Role.ENGINEER))):
    if state.emergency_stop:
        raise HTTPException(409, {"code": "EMERGENCY_LATCHED", "message": "急停锁存时不能恢复发送默认值"})
    speed = state.signals.fresh_value(
        "CCU_Vehicle_Speed", "Vehicle_Speed", max_age_seconds=state.config.channel_online_timeout_seconds
    )
    brake = state.signals.fresh_value("Brake_Status", max_age_seconds=state.config.channel_online_timeout_seconds)
    severe_alarm = bool(state.alarms and state.alarms.max_level() >= 3)
    if speed is None or abs(float(speed)) > state.config.stopped_speed_threshold_kmh or brake is not True or severe_alarm:
        raise HTTPException(409, {"code": "STOP_NOT_CONFIRMED", "message": "需要速度归零、制动反馈有效且无严重告警，才能解除安全停车锁存"})
    state.safe_stop_latched = False
    record_operator_action(state, principal, "control_reset_defaults", "0x121", {})
    return {"ok": True, "message": "控制默认值已恢复，安全停车锁存已解除"}


@router.get("/control/manual-feedback")
async def manual_feedback(_principal: Principal = Depends(require_role(Role.VIEWER))):
    speed = state.signals.fresh_value("CCU_Vehicle_Speed", "Vehicle_Speed", max_age_seconds=2.0)
    gear = state.signals.freshest("CCU_Shift_Level_Status", max_age_seconds=2.0)
    front = state.signals.fresh_value("SAS_Front_Angle", max_age_seconds=2.0)
    rear = state.signals.fresh_value("SAS_Rear_Angle", max_age_seconds=2.0)
    brake = state.signals.fresh_value("Brake_Status", max_age_seconds=2.0)
    return {
        "gear": str(gear.get("label", "-") if gear else "-"),
        "vehicle_speed": float(speed or 0),
        "front_steer_feedback": float(front or 0),
        "rear_steer_feedback": float(rear or 0),
        "wheel_speeds": "-",
        "light_feedback": "-",
        "brake_status": "已制动" if brake else "未制动",
        "alarm_status": "无告警" if not state.alarms or state.alarms.max_level() == 0 else "存在告警",
        "mock": speed is None,
        "updated_at": datetime.now().isoformat(timespec="milliseconds"),
    }


@router.get("/control/manual-curves")
async def manual_curves(_principal: Principal = Depends(require_role(Role.VIEWER))):
    speed_points = state.signals.timeseries_batch(["CCU_Vehicle_Speed", "Vehicle_Speed"])
    target_points = state.signals.timeseries_batch(["SCU_Target_Speed_Feedback"])
    return {
        "speed": {
            "x_axis": [item["t"][-12:-4] for item in speed_points.get("CCU_Vehicle_Speed", [])[-30:]],
            "target_speed": [item["value"] for item in target_points.get("SCU_Target_Speed_Feedback", [])[-30:]],
            "feedback_speed": [item["value"] for item in speed_points.get("CCU_Vehicle_Speed", [])[-30:]],
        },
        "steering": {
            "x_axis": [],
            "front_cmd": [],
            "front_feedback": [],
            "rear_cmd": [],
            "rear_feedback": [],
        },
    }
