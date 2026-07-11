from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable

from app.core.time import utc_now
from app.eol.models import AssertionOutcome, TestPlanDocument
from app.storage.database import Database


class PersistenceFailure(RuntimeError):
    pass


class StationBusyPersistence(RuntimeError):
    pass


class EolUnitOfWork:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.before_assertion_insert: Callable[[dict[str, Any]], None] | None = None

    def recover_incomplete_sessions(self) -> list[str]:
        rows = self.database.query(
            "SELECT id FROM test_sessions WHERE status IN ('IDLE','RUNNING','PAUSED','WAITING_OPERATOR')"
        )
        recovered = [str(row["id"]) for row in rows]
        if not recovered:
            return []
        now = utc_now()
        with self.database.transaction() as conn:
            for session_id in recovered:
                conn.execute(
                    "UPDATE test_steps SET status='ABORTED', result='ABORTED', ended_at=?, "
                    "failure_reason='service restart recovery' "
                    "WHERE session_id=? AND status='RUNNING'",
                    (now, session_id),
                )
                conn.execute(
                    "UPDATE test_sessions SET status='ABORTED', overall_result='ABORTED', "
                    "ended_at=?, failure_reason='service restart recovery' WHERE id=?",
                    (now, session_id),
                )
        return recovered

    def create_session(self, session: dict[str, Any], plan: TestPlanDocument) -> None:
        try:
            with self.database.transaction() as conn:
                conn.execute(
                    "INSERT INTO test_sessions("
                    "id,chassis_no,vin,serial_no,operator,station_id,test_plan_id,plan_version,"
                    "vehicle_series,status,overall_result,remarks,dbc_hash,config_hash,software_version,created_at"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        session["id"],
                        session["chassis_no"],
                        session["vin"],
                        session.get("serial_no"),
                        session["operator"],
                        session["station_id"],
                        plan.plan.id,
                        plan.plan.version,
                        plan.plan.default_vehicle_series,
                        session["status"],
                        session.get("overall_result"),
                        session.get("remarks", ""),
                        session.get("dbc_hash"),
                        session.get("config_hash"),
                        session.get("software_version"),
                        session["created_at"],
                    ),
                )
        except sqlite3.Error as exc:
            raise PersistenceFailure(f"failed to create EOL session: {exc}") from exc

    def update_session(self, session: dict[str, Any]) -> None:
        try:
            self.database.execute(
                "UPDATE test_sessions SET status=?, overall_result=?, started_at=?, ended_at=?, "
                "failure_reason=?, safe_stop_json=?, report_id=? WHERE id=?",
                (
                    session["status"],
                    session.get("overall_result"),
                    session.get("started_at"),
                    session.get("ended_at"),
                    session.get("failure_reason", ""),
                    json.dumps(session.get("safe_stop_result"), ensure_ascii=False, default=str)
                    if session.get("safe_stop_result")
                    else None,
                    (session.get("report") or {}).get("id"),
                    session["id"],
                ),
            )
        except sqlite3.Error as exc:
            raise PersistenceFailure(f"failed to update EOL session: {exc}") from exc

    def claim_station_and_start(self, session: dict[str, Any]) -> None:
        try:
            with self.database.transaction() as conn:
                active = conn.execute(
                    "SELECT id FROM test_sessions WHERE station_id=? AND id<>? "
                    "AND status IN ('RUNNING','PAUSED','WAITING_OPERATOR') LIMIT 1",
                    (session["station_id"], session["id"]),
                ).fetchone()
                if active:
                    raise StationBusyPersistence(
                        f"station {session['station_id']} already has active session {active['id']}"
                    )
                conn.execute(
                    "UPDATE test_sessions SET status='RUNNING', started_at=? WHERE id=?",
                    (session.get("started_at"), session["id"]),
                )
        except StationBusyPersistence:
            raise
        except sqlite3.Error as exc:
            raise PersistenceFailure(f"failed to claim EOL station: {exc}") from exc

    def start_step(self, session_id: str, step: dict[str, Any]) -> int:
        try:
            cursor = self.database.execute(
                "INSERT INTO test_steps(session_id,step_id,step_order,name,status,result,started_at,"
                "command_summary,measurement_summary) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    session_id,
                    step["id"],
                    step["order"],
                    step["name"],
                    "RUNNING",
                    None,
                    step["started_at"],
                    json.dumps(step.get("commands", []), ensure_ascii=False, default=str),
                    "{}",
                ),
            )
            return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise PersistenceFailure(f"failed to start EOL step {step['id']}: {exc}") from exc

    def complete_step(
        self,
        session_id: str,
        step: dict[str, Any],
        outcomes: list[AssertionOutcome],
    ) -> None:
        try:
            with self.database.transaction() as conn:
                conn.execute(
                    "UPDATE test_steps SET status=?, result=?, ended_at=?, duration_ms=?, "
                    "failure_reason=?, command_summary=?, measurement_summary=? WHERE id=? AND session_id=?",
                    (
                        step["status"],
                        step.get("result"),
                        step.get("ended_at"),
                        step.get("duration_ms"),
                        step.get("failure_reason", ""),
                        json.dumps(step.get("commands", []), ensure_ascii=False, default=str),
                        json.dumps(step.get("measurements", []), ensure_ascii=False, default=str),
                        step["db_id"],
                        session_id,
                    ),
                )
                for outcome_model in outcomes:
                    outcome = outcome_model.model_dump()
                    if self.before_assertion_insert:
                        self.before_assertion_insert(outcome)
                    conn.execute(
                        "INSERT INTO test_assertions(session_id,step_id,assertion_id,description,"
                        "signal_name,operator,threshold_json,measured_value,unit,result,severity,"
                        "failure_reason,sample_start_at,sample_end_at,quality,source_can_id,"
                        "source_channel,source_timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            session_id,
                            step["id"],
                            outcome["assertion_id"],
                            outcome["description"],
                            outcome["signal_name"],
                            outcome["operator"],
                            json.dumps(outcome.get("threshold"), ensure_ascii=False, default=str),
                            json.dumps(outcome.get("measured_value"), ensure_ascii=False, default=str),
                            outcome.get("unit", ""),
                            outcome["result"],
                            outcome.get("severity", "failure"),
                            outcome.get("failure_reason", ""),
                            outcome.get("sample_started_at"),
                            outcome.get("sample_ended_at"),
                            outcome.get("quality", "unknown"),
                            outcome.get("source_can_id", ""),
                            outcome.get("source_channel", ""),
                            outcome.get("source_timestamp", ""),
                        ),
                    )
        except Exception as exc:
            raise PersistenceFailure(
                f"failed to atomically persist step {step['id']} and assertions: {exc}"
            ) from exc

    def abort_running_steps(self, session_id: str, status: str, reason: str) -> None:
        self.database.execute(
            "UPDATE test_steps SET status=?, result='ABORTED', ended_at=?, failure_reason=? "
            "WHERE session_id=? AND status='RUNNING'",
            (status, utc_now(), reason, session_id),
        )

    def persist_report(self, session: dict[str, Any], report: dict[str, Any]) -> list[str]:
        created: list[str] = []
        with self.database.transaction() as conn:
            for report_type, file_name in report.get("files", {}).items():
                path = Path(file_name)
                report_id = f"{report['id']}-{report_type}"
                digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
                conn.execute(
                    "INSERT OR REPLACE INTO reports(id,session_id,chassis_no,vin,result,report_type,"
                    "file_path,file_size_bytes,file_hash,generation_status,generated_at,generated_by) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        report_id,
                        session["id"],
                        session["chassis_no"],
                        session["vin"],
                        session.get("overall_result") or report.get("result") or "UNKNOWN",
                        report_type,
                        str(path),
                        path.stat().st_size if path.exists() else None,
                        digest,
                        "COMPLETED" if path.exists() else "MISSING",
                        report.get("generated_at") or utc_now(),
                        session.get("operator"),
                    ),
                )
                created.append(report_id)
        return created

    def persist_statistics(self, session_id: str, can_manager: Any) -> None:
        now = utc_now()
        rows: list[tuple[Any, ...]] = []
        for channel, gateway in getattr(can_manager, "gateways", {}).items():
            stats = gateway.stats
            for can_id, message in stats.messages.items():
                rows.append(
                    (
                        session_id,
                        channel,
                        f"0x{can_id:X}",
                        "",
                        None,
                        message.period_ms,
                        message.min_period_ms,
                        message.max_period_ms,
                        max(0.0, message.max_period_ms - message.min_period_ms),
                        stats.fps,
                        message.count,
                        0,
                        stats.error_count,
                        None,
                        now,
                    )
                )
        if rows:
            self.database.executemany(
                "INSERT INTO signal_statistics(session_id,channel,can_id_hex,message_name,"
                "expected_period_ms,avg_period_ms,min_period_ms,max_period_ms,jitter_ms,fps,"
                "rx_count,timeout_count,error_count,window_start_at,window_end_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )

    def persist_current_alarms(
        self, session_id: str, alarms: list[dict[str, Any]], related_step_id: str | None
    ) -> None:
        if not alarms:
            return
        rows = [
            (
                session_id,
                utc_now(),
                alarm.get("channel"),
                alarm.get("can_id_hex"),
                alarm.get("id") or alarm.get("label") or "alarm",
                int(alarm.get("level", 0)),
                alarm.get("label", "Unknown"),
                alarm.get("status", "active"),
                alarm.get("description", ""),
                related_step_id,
            )
            for alarm in alarms
        ]
        self.database.executemany(
            "INSERT INTO alarms(session_id,timestamp_utc,channel,can_id_hex,signal_name,level,"
            "level_label,status,description,related_step_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )

    def persist_system_action(
        self, session_id: str, action_type: str, result: str, payload: dict[str, Any]
    ) -> None:
        self.database.execute(
            "INSERT INTO operator_actions(session_id,timestamp_utc,operator,role,action_type,"
            "target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                session_id,
                utc_now(),
                "eol-engine",
                "system",
                action_type,
                session_id,
                json.dumps(payload, ensure_ascii=False, default=str),
                result,
                "",
            ),
        )

    def ensure_software_version(self, state: Any) -> None:
        dbc = state.dbc.status() if state.dbc else {}
        latest = self.database.query_one(
            "SELECT version, dbc_hash, migration_version FROM software_versions ORDER BY id DESC LIMIT 1"
        )
        if latest and latest == {
            "version": state.config.software_version,
            "dbc_hash": dbc.get("hash"),
            "migration_version": "phase-02",
        }:
            return
        self.database.execute(
            "INSERT INTO software_versions(version,build_time,git_commit,dbc_version,dbc_hash,"
            "config_hash,migration_version) VALUES (?,?,?,?,?,?,?)",
            (
                state.config.software_version,
                utc_now(),
                "not-a-git-worktree",
                dbc.get("version"),
                dbc.get("hash"),
                "runtime-config",
                "phase-02",
            ),
        )

    def session_rows(self, session_id: str) -> dict[str, Any]:
        session = self.database.query_one("SELECT * FROM test_sessions WHERE id=?", (session_id,))
        return {
            "session": session,
            "steps": self.database.query(
                "SELECT * FROM test_steps WHERE session_id=? ORDER BY step_order", (session_id,)
            ),
            "assertions": self.database.query(
                "SELECT * FROM test_assertions WHERE session_id=? ORDER BY id", (session_id,)
            ),
            "reports": self.database.query(
                "SELECT * FROM reports WHERE session_id=? ORDER BY report_type", (session_id,)
            ),
            "counts": self.database.table_counts(session_id),
        }
