from __future__ import annotations

import json
import logging
from typing import Any

from app.core.time import utc_now
from app.security.auth import Principal, Role

LOGGER = logging.getLogger(__name__)


def record_operator_action(
    state: Any,
    principal: Principal | None,
    action: str,
    target: str,
    request: dict[str, Any] | None = None,
    result: str = "OK",
    trace_id: str = "",
) -> None:
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
        return
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
    except Exception:
        LOGGER.exception("failed to persist operator action %s", action)
