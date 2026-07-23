from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
import json
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import utc_now
from app.security.auth import Principal


class OverrideOperation(StrEnum):
    MANUAL = "manual"


class OverrideStatus(StrEnum):
    PENDING = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class OverrideCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=500)
    session_id: str = Field(min_length=1, max_length=128)
    operation: OverrideOperation
    vehicle_id: str = Field(min_length=1, max_length=128)
    authorized_user: str = Field(min_length=1, max_length=128)
    duration_seconds: int = Field(default=300, ge=30, le=900)


class OverrideApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: str = Field(pattern="^APPROVE$")
    reason: str = Field(min_length=5, max_length=500)


class OverrideRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=500)


class SafetyOverrideRecord(BaseModel):
    id: str
    alarm_id: str
    status: OverrideStatus
    requested_by: str
    request_reason: str
    requested_at: str
    session_id: str
    operation: OverrideOperation
    vehicle_id: str
    authorized_user: str
    duration_seconds: int
    approved_by: str | None = None
    approval_reason: str | None = None
    approved_at: str | None = None
    expires_at: str | None = None
    revoked_by: str | None = None
    revoke_reason: str | None = None
    revoked_at: str | None = None


class OverrideActionResponse(BaseModel):
    ok: bool = True
    message: str
    trace_id: str = ""
    override: SafetyOverrideRecord


class OverrideListResponse(BaseModel):
    items: list[SafetyOverrideRecord]
    total: int


class OverrideConflict(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OverridePersistenceError(RuntimeError):
    code = "OVERRIDE_PERSISTENCE_FAILED"


class OverrideService:
    """Persisted dual-control approval; only the severe-alarm rule is overridable."""

    def __init__(self, database, state=None) -> None:
        self.database = database
        self.state = state

    def create(
        self,
        alarm_id: str,
        request: OverrideCreateRequest,
        principal: Principal,
        *,
        trace_id: str = "",
    ) -> SafetyOverrideRecord:
        self._require_database()
        record = SafetyOverrideRecord(
            id=f"OVR-{uuid4().hex}",
            alarm_id=alarm_id,
            status=OverrideStatus.PENDING,
            requested_by=principal.username,
            request_reason=request.reason,
            requested_at=utc_now(),
            session_id=request.session_id,
            operation=request.operation,
            vehicle_id=request.vehicle_id,
            authorized_user=request.authorized_user,
            duration_seconds=request.duration_seconds,
        )
        try:
            with self.database.transaction() as conn:
                conn.execute(
                    "INSERT INTO safety_overrides(id,alarm_id,status,requested_by,request_reason,requested_at,session_id,operation,vehicle_id,authorized_user,duration_seconds) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        record.id, record.alarm_id, record.status.value, record.requested_by,
                        record.request_reason, record.requested_at, record.session_id,
                        record.operation.value, record.vehicle_id, record.authorized_user,
                        record.duration_seconds,
                    ),
                )
                self._audit(conn, principal, "alarm_override_request", record.id, request.model_dump(mode="json"), record.status.value, trace_id)
        except Exception as exc:
            self._persistence_failed(exc)
        return record

    def approve(
        self,
        override_id: str,
        request: OverrideApprovalRequest,
        principal: Principal,
        *,
        trace_id: str = "",
    ) -> SafetyOverrideRecord:
        record = self.get(override_id)
        if record.status != OverrideStatus.PENDING:
            raise OverrideConflict("OVERRIDE_NOT_PENDING", "仅待审批申请可被批准")
        if record.requested_by == principal.username:
            raise OverrideConflict("SEPARATION_OF_DUTIES", "申请人与批准人必须为不同用户")
        approved_at = datetime.now(timezone.utc)
        expires_at = approved_at + timedelta(seconds=record.duration_seconds)
        try:
            with self.database.transaction() as conn:
                conn.execute(
                    "UPDATE safety_overrides SET status=?,approved_by=?,approval_reason=?,approved_at=?,expires_at=? WHERE id=?",
                    (OverrideStatus.APPROVED.value, principal.username, request.reason, approved_at.isoformat(), expires_at.isoformat(), override_id),
                )
                self._audit(conn, principal, "alarm_override_approve", override_id, request.model_dump(mode="json"), "APPROVED", trace_id)
        except Exception as exc:
            self._persistence_failed(exc)
        return self.get(override_id)

    def revoke(
        self,
        override_id: str,
        request: OverrideRevokeRequest,
        principal: Principal,
        *,
        trace_id: str = "",
    ) -> SafetyOverrideRecord:
        record = self.get(override_id)
        if record.status not in {OverrideStatus.PENDING, OverrideStatus.APPROVED}:
            raise OverrideConflict("OVERRIDE_NOT_ACTIVE", "申请已撤销、已过期或不存在活动授权")
        try:
            with self.database.transaction() as conn:
                conn.execute(
                    "UPDATE safety_overrides SET status=?,revoked_by=?,revoke_reason=?,revoked_at=? WHERE id=?",
                    (OverrideStatus.REVOKED.value, principal.username, request.reason, utc_now(), override_id),
                )
                self._audit(conn, principal, "alarm_override_revoke", override_id, request.model_dump(mode="json"), "REVOKED", trace_id)
        except Exception as exc:
            self._persistence_failed(exc)
        return self.get(override_id)

    def get(self, override_id: str) -> SafetyOverrideRecord:
        self._require_database()
        row = self.database.query_one("SELECT * FROM safety_overrides WHERE id=?", (override_id,))
        if not row:
            raise OverrideConflict("OVERRIDE_NOT_FOUND", "人工放行申请不存在")
        record = SafetyOverrideRecord.model_validate(row)
        if record.status == OverrideStatus.APPROVED and self._is_expired(record):
            try:
                with self.database.transaction() as conn:
                    conn.execute("UPDATE safety_overrides SET status=? WHERE id=?", (OverrideStatus.EXPIRED.value, override_id))
                    conn.execute(
                        "INSERT INTO operator_actions(timestamp_utc,operator,role,action_type,target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?)",
                        (utc_now(), "system", "admin", "alarm_override_expired", override_id, "{}", "EXPIRED", ""),
                    )
            except Exception as exc:
                self._persistence_failed(exc)
            record = SafetyOverrideRecord.model_validate(
                self.database.query_one("SELECT * FROM safety_overrides WHERE id=?", (override_id,))
            )
        return record

    def list(self, limit: int = 100) -> list[SafetyOverrideRecord]:
        self._require_database()
        rows = self.database.query(
            "SELECT id FROM safety_overrides ORDER BY requested_at DESC LIMIT ?", (limit,)
        )
        return [self.get(str(row["id"])) for row in rows]

    def validate_for_interlock(
        self,
        override_id: str,
        *,
        actor: str | None,
        session_id: str | None,
        operation: str,
        vehicle_id: str | None,
        critical_alarm_ids: list[str],
    ) -> dict:
        try:
            record = self.get(override_id)
        except OverrideConflict as exc:
            return {"used": True, "allowed": False, "code": exc.code, "message": exc.message}
        checks = {
            "approved": record.status == OverrideStatus.APPROVED,
            "not_expired": not self._is_expired(record),
            "actor_match": bool(actor and actor == record.authorized_user),
            "session_match": bool(session_id and session_id == record.session_id),
            "operation_match": operation == record.operation.value,
            "vehicle_match": bool(vehicle_id and vehicle_id == record.vehicle_id),
            "single_alarm_match": critical_alarm_ids == [record.alarm_id],
            "dual_control": bool(record.approved_by and record.approved_by != record.requested_by),
        }
        return {
            "used": True,
            "allowed": all(checks.values()),
            "override_id": record.id,
            "alarm_id": record.alarm_id,
            "status": record.status.value,
            "expires_at": record.expires_at,
            "checks": checks,
        }

    @staticmethod
    def _is_expired(record: SafetyOverrideRecord) -> bool:
        if not record.expires_at:
            return False
        return datetime.fromisoformat(record.expires_at) <= datetime.now(timezone.utc)

    def _require_database(self) -> None:
        if self.database is None:
            raise OverrideConflict("DATABASE_UNAVAILABLE", "数据库不可用，人工放行默认拒绝")

    @staticmethod
    def _audit(conn, principal: Principal, action: str, target: str, payload: dict, result: str, trace_id: str) -> None:
        conn.execute(
            "INSERT INTO operator_actions(timestamp_utc,operator,role,action_type,target,request_json,result,trace_id) VALUES (?,?,?,?,?,?,?,?)",
            (utc_now(), principal.username, principal.role.value, action, target, json.dumps(payload, ensure_ascii=False), result, trace_id),
        )

    def _persistence_failed(self, exc: Exception) -> None:
        if self.state is not None:
            self.state.db_writable = False
        raise OverridePersistenceError("人工放行状态与审计未能原子持久化，操作已回滚") from exc
