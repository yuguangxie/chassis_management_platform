from __future__ import annotations

import json
from typing import Any

from app.core.time import utc_now

from .database import Database


class Repositories:
    def __init__(self, db: Database) -> None:
        self.db = db

    def action(
        self,
        action_type: str,
        target: str,
        request: dict,
        result: str = "OK",
        operator: str = "op01",
        trace_id: str = "",
        session_id: str | None = None,
        role: str | None = None,
    ) -> None:
        self.db.execute(
            "INSERT INTO operator_actions(session_id,timestamp_utc,operator,role,action_type,target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                session_id,
                utc_now(),
                operator,
                role,
                action_type,
                target,
                json.dumps(request, ensure_ascii=False, default=str),
                result,
                trace_id,
            ),
        )

    def report(self, report_id: str) -> dict[str, Any] | None:
        return self.db.query_one("SELECT * FROM reports WHERE id=?", (report_id,))

    def reports_for_session(self, session_id: str) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM reports WHERE session_id=? ORDER BY generated_at DESC,report_type",
            (session_id,),
        )

    def session(self, session_id: str) -> dict[str, Any] | None:
        return self.db.query_one("SELECT * FROM test_sessions WHERE id=?", (session_id,))

    def session_bundle(self, session_id: str) -> dict[str, Any] | None:
        session = self.session(session_id)
        if session is None:
            return None
        steps = self.db.query(
            "SELECT * FROM test_steps WHERE session_id=? ORDER BY step_order", (session_id,)
        )
        assertions = self.db.query(
            "SELECT * FROM test_assertions WHERE session_id=? ORDER BY id", (session_id,)
        )
        by_step: dict[str, list[dict[str, Any]]] = {}
        for assertion in assertions:
            normalized = dict(assertion)
            for key in ("threshold_json", "measured_value"):
                value = normalized.get(key)
                try:
                    normalized["threshold" if key == "threshold_json" else key] = json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    normalized["threshold" if key == "threshold_json" else key] = value
            normalized["assertion_id"] = normalized.get("assertion_id") or str(normalized.get("id"))
            by_step.setdefault(str(assertion["step_id"]), []).append(normalized)
        normalized_steps = []
        for step in steps:
            normalized_steps.append(
                {
                    "id": step["step_id"],
                    "order": step["step_order"],
                    "name": step["name"],
                    "status": step["status"],
                    "result": step.get("result"),
                    "started_at": step.get("started_at"),
                    "ended_at": step.get("ended_at"),
                    "duration_ms": step.get("duration_ms"),
                    "failure_reason": step.get("failure_reason"),
                    "command_summary": step.get("command_summary"),
                    "measurement_summary": step.get("measurement_summary"),
                    "assertions": by_step.get(str(step["step_id"]), []),
                }
            )
        return {
            "session": {
                **session,
                "plan_id": session.get("test_plan_id"),
                "remarks": session.get("remarks") or "",
            },
            "steps": normalized_steps,
            "assertions": assertions,
            "alarms": self.db.query(
                "SELECT * FROM alarms WHERE session_id=? ORDER BY timestamp_utc", (session_id,)
            ),
            "operator_actions": self.db.query(
                "SELECT * FROM operator_actions WHERE session_id=? ORDER BY timestamp_utc", (session_id,)
            ),
            "reports": self.reports_for_session(session_id),
        }
