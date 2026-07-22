from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
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


class OverrideService:
    """Persisted dual-control approval; only the severe-alarm rule is overridable."""

    def __init__(self, database) -> None:
        self.database = database

    def create(
        self,
        alarm_id: str,
        request: OverrideCreateRequest,
        principal: Principal,
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
        self.database.execute(
            "INSERT INTO safety_overrides(id,alarm_id,status,requested_by,request_reason,requested_at,session_id,operation,vehicle_id,authorized_user,duration_seconds) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                record.id,
                record.alarm_id,
                record.status.value,
                record.requested_by,
                record.request_reason,
                record.requested_at,
                record.session_id,
                record.operation.value,
                record.vehicle_id,
                record.authorized_user,
                record.duration_seconds,
            ),
        )
        return record

    def approve(
        self,
        override_id: str,
        request: OverrideApprovalRequest,
        principal: Principal,
    ) -> SafetyOverrideRecord:
        record = self.get(override_id)
        if record.status != OverrideStatus.PENDING:
            raise OverrideConflict("OVERRIDE_NOT_PENDING", "仅待审批申请可被批准")
        if record.requested_by == principal.username:
            raise OverrideConflict("SEPARATION_OF_DUTIES", "申请人与批准人必须为不同用户")
        approved_at = datetime.now(timezone.utc)
        expires_at = approved_at + timedelta(seconds=record.duration_seconds)
        self.database.execute(
            "UPDATE safety_overrides SET status=?,approved_by=?,approval_reason=?,approved_at=?,expires_at=? WHERE id=?",
            (
                OverrideStatus.APPROVED.value,
                principal.username,
                request.reason,
                approved_at.isoformat(),
                expires_at.isoformat(),
                override_id,
            ),
        )
        return self.get(override_id)

    def revoke(
        self,
        override_id: str,
        request: OverrideRevokeRequest,
        principal: Principal,
    ) -> SafetyOverrideRecord:
        record = self.get(override_id)
        if record.status not in {OverrideStatus.PENDING, OverrideStatus.APPROVED}:
            raise OverrideConflict("OVERRIDE_NOT_ACTIVE", "申请已撤销、已过期或不存在活动授权")
        self.database.execute(
            "UPDATE safety_overrides SET status=?,revoked_by=?,revoke_reason=?,revoked_at=? WHERE id=?",
            (
                OverrideStatus.REVOKED.value,
                principal.username,
                request.reason,
                utc_now(),
                override_id,
            ),
        )
        return self.get(override_id)

    def get(self, override_id: str) -> SafetyOverrideRecord:
        self._require_database()
        row = self.database.query_one("SELECT * FROM safety_overrides WHERE id=?", (override_id,))
        if not row:
            raise OverrideConflict("OVERRIDE_NOT_FOUND", "人工放行申请不存在")
        record = SafetyOverrideRecord.model_validate(row)
        if record.status == OverrideStatus.APPROVED and self._is_expired(record):
            self.database.execute(
                "UPDATE safety_overrides SET status=? WHERE id=?",
                (OverrideStatus.EXPIRED.value, override_id),
            )
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
