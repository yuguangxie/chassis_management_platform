from __future__ import annotations

import json
import logging
from typing import Any

from app.core.time import utc_now
from app.security.auth import Principal, Role

LOGGER = logging.getLogger(__name__)


class AuditPersistenceError(RuntimeError):
    """A required safety/security audit record could not be durably committed."""

    code = "AUDIT_UNAVAILABLE"


def _mark_unwritable(state: Any, message: str) -> None:
    state.db_writable = False
    if getattr(state, "alarms", None) and hasattr(state.alarms, "raise_system_alarm"):
        state.alarms.raise_system_alarm(
            "audit_storage_unhealthy",
            4,
            "Audit Storage Unhealthy",
            message,
        )


def record_operator_action(
    state: Any,
    principal: Principal | None,
    action: str,
    target: str,
    request: dict[str, Any] | None = None,
    result: str = "OK",
    trace_id: str = "",
    *,
    required: bool = False,
) -> bool:
    actor = principal or Principal("system", Role.ADMIN)
    payload = request or {}
    if state.database is None:
        LOGGER.info(
            "operator_action operator=%s role=%s action=%s target=%s result=%s payload=%s",
            actor.username,
            actor.role.value,
            action,
            target,
            result,
            payload,
        )
        if required:
            _mark_unwritable(state, "required operation audit database is unavailable")
            raise AuditPersistenceError("required operation audit database is unavailable")
        return False
    try:
        state.database.execute(
            "INSERT INTO operator_actions(session_id, timestamp_utc, operator, role, action_type, target, request_json, result, trace_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                target if str(target).startswith("EOL-") else None,
                utc_now(),
                actor.username,
                actor.role.value,
                action,
                target,
                json.dumps(payload, ensure_ascii=False, default=str),
                result,
                trace_id,
            ),
        )
        return True
    except Exception as exc:
        LOGGER.exception("failed to persist operator action %s", action)
        if required:
            _mark_unwritable(state, f"required operation audit failed: {type(exc).__name__}")
            raise AuditPersistenceError("required operation audit could not be persisted") from exc
        return False
