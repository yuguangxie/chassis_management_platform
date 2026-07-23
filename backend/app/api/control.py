from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError

from app.api.models import SafetyOverrideUseRequest
from app.control.control_121 import Control121Command, preview
from app.control.intent_service import ControlIntentPersistenceError
from app.control.safe_stop import safe_stop_command
from app.control.safety_interlock import InterlockBlocked, SafetyEvaluationContext
from app.security.auth import Principal, Role, require_role
from app.services.app_state import state
from app.services.audit import AuditPersistenceError, record_operator_action
from app.api.errors import get_trace_id
from app.core.time import utc_now

router = APIRouter()


def _chart_time_label(value: Any) -> str:
    """Return a readable HH:MM:SS label from the stored UTC ISO8601 timestamp."""
    text = str(value or "")
    if "T" in text:
        return text.split("T", 1)[1][:8]
    if len(text) >= 19 and text[10] == " ":
        return text[11:19]
    return text[-8:]


def _command_from_payload(payload: Any | None = None) -> Control121Command:
    if isinstance(payload, Control121Command):
        return payload
    raw = payload if isinstance(payload, dict) else {}
    return Control121Command(
        shift=raw.get("gear", raw.get("shift", "N")),
        drive_mode=raw.get("drive_mode", "Remote"),
        target_speed_kmh=float(raw.get("target_speed", raw.get("target_speed_kmh", 0.0))),
        front_steering_cmd=int(raw.get("front_steer", raw.get("front_steering_cmd", 0))),
        rear_steering_cmd=int(raw.get("rear_steer", raw.get("rear_steering_cmd", 0))),
        brake_enable=bool(raw.get("brake_enable", True)),
        left_light=bool(raw.get("left_turn", raw.get("left_light", False))),
        right_light=bool(raw.get("right_turn", raw.get("right_light", False))),
        position_light=bool(raw.get("position_light", False)),
        low_beam=bool(raw.get("low_beam", False)),
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


def _persistence_http_error(exc: Exception) -> HTTPException:
    return HTTPException(
        503,
        {
            "code": getattr(exc, "code", "AUDIT_UNAVAILABLE"),
            "message": "危险控制动作的可靠审计不可写，已锁存存储故障并拒绝继续控制",
            "details": {"error_type": type(exc).__name__, "blocking": True},
        },
    )


def _create_intent(
    principal: Principal,
    operation: str,
    command: Control121Command,
    context: SafetyEvaluationContext,
) -> str:
    evaluation = state.safety.require_allowed(
        command, operation=operation, context=context
    )
    return state.control_intents.create_authorized(
        principal,
        operation=f"control_{operation}",
        target="CAN2:0x121",
        command=command.model_dump(),
        safety_evaluation=evaluation,
        trace_id=get_trace_id(),
        vehicle_id=context.vehicle_id,
        eol_session_id=context.session_id,
    )


def _safety_context(payload: Any, principal: Principal) -> SafetyEvaluationContext:
    raw = payload.get("safety_context") if isinstance(payload, dict) else None
    if raw is None:
        return SafetyEvaluationContext(actor=principal.username)
    try:
        override = SafetyOverrideUseRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            422,
            {
                "code": "INVALID_SAFETY_CONTEXT",
                "message": "人工放行使用范围不完整",
                "details": exc.errors(include_url=False),
            },
        ) from exc
    return SafetyEvaluationContext(
        actor=principal.username,
        override_id=override.override_id,
        session_id=override.session_id,
        vehicle_id=override.vehicle_id,
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


@router.get("/control/hardware-acceptance")
async def hardware_acceptance(
    _principal: Principal = Depends(require_role(Role.VIEWER)),
):
    if state.hardware_acceptance is None:
        return {
            "allowed": False,
            "applicable": state.config.profile == "production",
            "status": "unavailable",
            "artifact": None,
            "rules": [],
            "reasons": [
                {
                    "rule": "hardware_acceptance_service",
                    "label": "硬件验收服务",
                    "current": None,
                    "threshold": "initialized",
                    "blocking": True,
                    "status": "FAIL",
                }
            ],
        }
    return state.hardware_acceptance.evaluate()


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
    context = _safety_context(payload, principal)
    try:
        intent_id = _create_intent(principal, "manual", command, context)
        result = await state.tx_scheduler.send_once(command, context=context)
    except InterlockBlocked as exc:
        raise _interlock_http_error(exc)
    except (ControlIntentPersistenceError, AuditPersistenceError) as exc:
        raise _persistence_http_error(exc) from exc
    except Exception as exc:
        if "intent_id" in locals():
            try:
                state.control_intents.mark(intent_id, "FAILED", error_code=type(exc).__name__)
            except ControlIntentPersistenceError:
                pass
        raise
    try:
        state.control_intents.mark(intent_id, "SENT")
    except ControlIntentPersistenceError as exc:
        await state.control_intents.compensate_after_send_failure(intent_id, exc)
        raise _persistence_http_error(exc) from exc
    return {
        **result,
        "intent_id": intent_id,
        "delivery_status": "SENT_NOT_HARDWARE_CONFIRMED",
        "message": "0x121 已提交传输；硬件执行状态需由反馈确认",
    }


@router.post("/control/121/start-periodic")
async def start_periodic(
    payload: Any = Body(default=None),
    period_ms: int = 20,
    principal: Principal = Depends(require_role(Role.ENGINEER)),
):
    command = _command_from_payload(payload)
    context = _safety_context(payload, principal)
    try:
        intent_id = _create_intent(principal, "manual", command, context)
        result = await state.tx_scheduler.start(command, period_ms, context=context)
    except InterlockBlocked as exc:
        raise _interlock_http_error(exc)
    except (ControlIntentPersistenceError, AuditPersistenceError) as exc:
        raise _persistence_http_error(exc) from exc
    except Exception as exc:
        if "intent_id" in locals():
            try:
                state.control_intents.mark(intent_id, "FAILED", error_code=type(exc).__name__)
            except ControlIntentPersistenceError:
                pass
        raise
    try:
        state.control_intents.mark(intent_id, "SENT")
    except ControlIntentPersistenceError as exc:
        await state.control_intents.compensate_after_send_failure(intent_id, exc)
        raise _persistence_http_error(exc) from exc
    return {**result, "intent_id": intent_id, "message": "0x121 周期发送已启动"}


@router.post("/control/121/stop")
async def stop(principal: Principal = Depends(require_role(Role.ENGINEER))):
    result = await state.tx_scheduler.stop()
    try:
        record_operator_action(
            state, principal, "control_stop_periodic", "0x121", {}, required=True
        )
    except AuditPersistenceError as exc:
        raise _persistence_http_error(exc) from exc
    return {**result, "message": "0x121 周期发送已停止"}


async def _run_stop(
    *, emergency: bool, principal: Principal, payload: dict[str, Any]
) -> dict:
    if state.safe_stop is None:
        raise HTTPException(503, {"code": "STOP_SERVICE_UNAVAILABLE", "message": "停车服务未初始化"})
    operation = "emergency" if emergency else "safe_stop"
    command = safe_stop_command()
    context = SafetyEvaluationContext(actor=principal.username)
    try:
        intent_id = _create_intent(principal, operation, command, context)
        result = await state.safe_stop.execute(
            emergency=emergency,
            principal=principal,
            reason=str(payload.get("reason") or ("manual emergency stop" if emergency else "manual safe stop")),
            timeout_ms=payload.get("timeout_ms"),
        )
        state.control_intents.mark(
            intent_id,
            "CONFIRMED" if result["ok"] else "FAILED",
            error_code=None if result["ok"] else result.get("code"),
        )
    except (ControlIntentPersistenceError, AuditPersistenceError) as exc:
        if "intent_id" in locals():
            await state.control_intents.compensate_after_send_failure(intent_id, exc)
        raise _persistence_http_error(exc) from exc
    if not result["ok"]:
        status_code = 409 if result["code"] == "INTERLOCK_BLOCKED" else 504
        raise HTTPException(status_code, result)
    return {**result, "intent_id": intent_id}


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
    try:
        state.safety.require_allowed(operation="release_emergency")
    except InterlockBlocked as exc:
        record_operator_action(
            state,
            principal,
            "control_reset_defaults",
            "0x121",
            {"reasons": exc.evaluation["reasons"]},
            "BLOCKED",
        )
        raise _interlock_http_error(exc)
    await state.tx_scheduler.stop()
    state.safe_stop_latched = False
    try:
        record_operator_action(
            state, principal, "control_reset_defaults", "0x121", {}, required=True
        )
    except AuditPersistenceError as exc:
        state.safe_stop_latched = True
        raise _persistence_http_error(exc) from exc
    return {"ok": True, "message": "控制默认值已恢复，安全停车锁存已解除"}


@router.get("/control/manual-feedback")
async def manual_feedback(_principal: Principal = Depends(require_role(Role.VIEWER))):
    evaluation = (
        state.safety.evaluate(Control121Command(), operation="manual")
        if state.safety
        else {"allowed": False, "rules": [], "reasons": []}
    )
    feedback_rules = [
        rule for rule in evaluation.get("rules", [])
        if str(rule.get("rule", "")).startswith("feedback_")
    ]
    by_rule = {str(rule["rule"]): rule for rule in feedback_rules}

    def value(rule_name: str, default: Any = None) -> Any:
        current = by_rule.get(rule_name, {}).get("current")
        return current.get("value", default) if isinstance(current, dict) else default

    fields = []
    for rule in feedback_rules:
        current = rule.get("current") if isinstance(rule.get("current"), dict) else {}
        fields.append(
            {
                "rule": rule["rule"],
                "label": rule["label"],
                "status": "valid" if rule.get("status") == "PASS" else "invalid",
                "present": bool(current.get("checks", {}).get("present")),
                "age_ms": current.get("age_ms"),
                "quality": current.get("quality", "missing"),
                "channel": current.get("channel"),
                "can_id": current.get("can_id"),
                "value": current.get("value"),
                "checks": current.get("checks", {}),
                "threshold": rule.get("threshold", {}),
                "blocking": bool(rule.get("blocking", True)),
            }
        )

    speed = value("feedback_base_vehicle_speed")
    gear = value("feedback_drive_gear_status")
    front = value("feedback_steering_front_steering")
    rear = value("feedback_steering_rear_steering")
    brake = value("feedback_brake_brake_status")
    return {
        "gear": "-" if gear is None else str(gear),
        "vehicle_speed": float(speed or 0),
        "front_steer_feedback": float(front or 0),
        "rear_steer_feedback": float(rear or 0),
        "wheel_speeds": "-",
        "light_feedback": "-",
        "brake_status": "未知" if brake is None else ("已制动" if brake else "未制动"),
        "alarm_status": "无告警" if not state.alarms or state.alarms.max_level() == 0 else "存在告警",
        "fields": fields,
        "overall": "valid" if fields and all(item["status"] == "valid" for item in fields) else "invalid",
        "mock": bool(state.mock_enabled),
        "stale": not fields or any(not item["checks"].get("fresh", False) for item in fields),
        "updated_at": utc_now(),
    }


@router.get("/control/manual-curves")
async def manual_curves(_principal: Principal = Depends(require_role(Role.VIEWER))):
    speed_points = state.signals.timeseries_batch(["CCU_Vehicle_Speed", "Vehicle_Speed"])
    target_points = state.signals.timeseries_batch(["SCU_Target_Speed_Feedback"])
    return {
        "speed": {
            "x_axis": [_chart_time_label(item["t"]) for item in speed_points.get("CCU_Vehicle_Speed", [])[-30:]],
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
