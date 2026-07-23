from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Literal
from uuid import uuid4

from app.control.safe_stop import safe_stop_command
from app.core.time import utc_now
from app.security.auth import Principal


LOGGER = logging.getLogger(__name__)
IntentStatus = Literal[
    "PENDING", "AUTHORIZED", "SENT", "CONFIRMED", "FAILED", "AUDIT_FAILED", "CANCELLED"
]


class ControlIntentPersistenceError(RuntimeError):
    code = "CONTROL_INTENT_PERSISTENCE_FAILED"


def _canonical(value: Any) -> tuple[str, str]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


class ControlIntentService:
    """SQLite authority for safety-relevant actions before and after transmission."""

    def __init__(self, state: Any) -> None:
        self.state = state

    def create_authorized(
        self,
        principal: Principal,
        *,
        operation: str,
        target: str,
        command: dict[str, Any],
        safety_evaluation: dict[str, Any],
        trace_id: str,
        vehicle_id: str | None = None,
        eol_session_id: str | None = None,
    ) -> str:
        if not self.state.db_writable or self.state.database is None:
            self._fail_closed("control intent database is unavailable")
        intent_id = f"INT-{uuid4().hex}"
        command_json, command_hash = _canonical(command)
        safety_json, safety_hash = _canonical(safety_evaluation)
        now = utc_now()
        try:
            with self.state.database.transaction() as conn:
                conn.execute(
                    "INSERT INTO control_intents(id,status,principal,role,auth_session_id,vehicle_id,"
                    "eol_session_id,operation,target,command_json,command_hash,safety_evaluation_json,"
                    "safety_evaluation_hash,trace_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        intent_id,
                        "AUTHORIZED",
                        principal.username,
                        principal.role.value,
                        principal.session_id,
                        vehicle_id,
                        eol_session_id,
                        operation,
                        target,
                        command_json,
                        command_hash,
                        safety_json,
                        safety_hash,
                        trace_id,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    "INSERT INTO operator_actions(session_id,timestamp_utc,operator,role,action_type,"
                    "target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        eol_session_id,
                        now,
                        principal.username,
                        principal.role.value,
                        f"{operation}_intent",
                        target,
                        json.dumps(
                            {
                                "intent_id": intent_id,
                                "command_hash": command_hash,
                                "safety_evaluation_hash": safety_hash,
                                "vehicle_id": vehicle_id,
                            },
                            ensure_ascii=False,
                        ),
                        "AUTHORIZED",
                        trace_id,
                    ),
                )
        except Exception as exc:
            self._fail_closed(f"control intent authorization failed: {type(exc).__name__}", exc)
        return intent_id

    def mark(
        self,
        intent_id: str,
        status: IntentStatus,
        *,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> None:
        now = utc_now()
        sent_at = now if status == "SENT" else None
        confirmed_at = now if status == "CONFIRMED" else None
        try:
            with self.state.database.transaction() as conn:
                cursor = conn.execute(
                    "UPDATE control_intents SET status=?,updated_at=?,sent_at=COALESCE(?,sent_at),"
                    "confirmed_at=COALESCE(?,confirmed_at),error_code=?,error_detail=? WHERE id=?",
                    (status, now, sent_at, confirmed_at, error_code, error_detail, intent_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("control intent not found")
                row = conn.execute(
                    "SELECT principal,role,eol_session_id,operation,target,trace_id FROM control_intents WHERE id=?",
                    (intent_id,),
                ).fetchone()
                conn.execute(
                    "INSERT INTO operator_actions(session_id,timestamp_utc,operator,role,action_type,"
                    "target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        row["eol_session_id"],
                        now,
                        row["principal"],
                        row["role"],
                        f"{row['operation']}_intent_status",
                        row["target"],
                        json.dumps({"intent_id": intent_id, "error_code": error_code}, ensure_ascii=False),
                        status,
                        row["trace_id"],
                    ),
                )
        except Exception as exc:
            self._fail_closed(f"control intent result persistence failed: {type(exc).__name__}", exc)

    def recover_unfinished(self) -> list[str]:
        if self.state.database is None:
            return []
        rows = self.state.database.query(
            "SELECT id,status FROM control_intents WHERE status IN ('PENDING','AUTHORIZED','SENT')"
        )
        if not rows:
            return []
        now = utc_now()
        ids = [str(row["id"]) for row in rows]
        with self.state.database.transaction() as conn:
            for row in rows:
                previous = str(row["status"])
                terminal = "AUDIT_FAILED" if previous == "SENT" else "CANCELLED"
                conn.execute(
                    "UPDATE control_intents SET status=?,updated_at=?,recovery_note=? WHERE id=?",
                    (terminal, now, f"service restart recovered unfinished {previous}", row["id"]),
                )
        return ids

    async def compensate_after_send_failure(self, intent_id: str, cause: Exception) -> None:
        """Stop ordinary periodic TX and issue one bounded 0x121 stop attempt.

        This never reports success and does not assume that hardware accepted the frame.
        The still-AUTHORIZED/SENT intent is deliberately recoverable on restart.
        """
        self._latch_storage_failure(
            f"post-send audit failure for {intent_id}: {type(cause).__name__}"
        )
        self.state.safe_stop_latched = True
        if self.state.tx_scheduler:
            await self.state.tx_scheduler.stop()
            try:
                await self.state.tx_scheduler.send_priority(
                    safe_stop_command(), operation="safe_stop"
                )
            except Exception:
                LOGGER.exception("bounded safe-stop compensation failed for intent %s", intent_id)

    def _fail_closed(self, message: str, cause: Exception | None = None) -> None:
        self._latch_storage_failure(message)
        if cause is not None:
            raise ControlIntentPersistenceError(message) from cause
        raise ControlIntentPersistenceError(message)

    def _latch_storage_failure(self, message: str) -> None:
        self.state.db_writable = False
        if getattr(self.state, "alarms", None):
            self.state.alarms.raise_system_alarm(
                "control_intent_storage_unhealthy",
                4,
                "Control Intent Storage Unhealthy",
                message,
            )
