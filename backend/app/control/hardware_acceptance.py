from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.configuration.models import configuration_hash
from app.configuration.service import runtime_configuration
from app.core.paths import CONFIG_DIR
from app.core.release_metadata import load_release_metadata


class AcceptanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PhysicalChecklist(AcceptanceModel):
    emergency_stop_verified: bool
    plc_interlock_verified: bool
    propulsion_relay_verified: bool
    steering_relay_verified: bool
    brake_relay_verified: bool


class EvidenceFile(AcceptanceModel):
    name: str = Field(min_length=1, max_length=256)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class HardwareAcceptanceArtifact(AcceptanceModel):
    artifact_version: Literal[1] = 1
    station_id: str = Field(min_length=1, max_length=128)
    vehicle_series: str = Field(min_length=1, max_length=32)
    controller: str = Field(min_length=1, max_length=128)
    firmware: str = Field(min_length=1, max_length=128)
    release_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    dbc_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    test_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    physical_checklist: PhysicalChecklist
    watchdog_policy: str = Field(min_length=5, max_length=1000)
    safe_stop_policy: str = Field(min_length=5, max_length=1000)
    evidence_files: list[EvidenceFile] = Field(min_length=1, max_length=128)
    requester: str = Field(min_length=1, max_length=128)
    approvers: list[str] = Field(min_length=2, max_length=2)
    valid_from: datetime
    valid_to: datetime
    revoked_at: datetime | None = None
    revoke_reason: str | None = Field(default=None, max_length=500)
    signature_algorithm: Literal["HMAC-SHA256"] = "HMAC-SHA256"
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("valid_from", "valid_to", "revoked_at")
    @classmethod
    def require_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value)):
            raise ValueError("hardware acceptance timestamps must be UTC")
        return value

    @model_validator(mode="after")
    def validate_approval(self) -> "HardwareAcceptanceArtifact":
        if self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be later than valid_from")
        if self.revoked_at and not self.revoke_reason:
            raise ValueError("revoked artifact requires revoke_reason")
        return self


def _canonical_bytes(artifact: HardwareAcceptanceArtifact) -> bytes:
    return json.dumps(
        artifact.model_dump(mode="json", exclude={"signature"}),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sign_acceptance_artifact(artifact: HardwareAcceptanceArtifact, key: str) -> str:
    return hmac.new(key.encode("utf-8"), _canonical_bytes(artifact), hashlib.sha256).hexdigest()


class HardwareAcceptanceService:
    """Read-only production motion gate with an independent local trust root."""

    def __init__(self, state: Any) -> None:
        self.state = state

    def artifact_path(self) -> Path:
        configured = os.getenv("CHASSIS_HARDWARE_ACCEPTANCE_PATH", "").strip()
        if configured:
            return Path(configured).resolve(strict=False)
        return (self.state.data_paths.config / "hardware-acceptance.json").resolve(strict=False)

    def evaluate(self) -> dict[str, Any]:
        if self.state.config.profile != "production":
            return {
                "allowed": True,
                "applicable": False,
                "status": "not_required_nonproduction",
                "rules": [],
            }
        artifact, load_rule = self._load()
        rules = [load_rule]
        if artifact is None:
            return self._result(rules, None)
        key = os.getenv("CHASSIS_HARDWARE_ACCEPTANCE_KEY", "")
        signature_ok = len(key) >= 32 and hmac.compare_digest(
            artifact.signature, sign_acceptance_artifact(artifact, key)
        )
        self._rule(rules, "artifact_signature", "硬件验收签名", signature_ok, signature_ok, True)
        identities = [artifact.requester, *artifact.approvers]
        self._rule(
            rules,
            "artifact_separation_of_duties",
            "申请人与两名批准人相互分离",
            len(set(identities)) == 3,
            identities,
            "three distinct identities",
        )
        now = datetime.now(timezone.utc)
        self._rule(rules, "artifact_validity", "硬件验收有效期", artifact.valid_from <= now < artifact.valid_to, now.isoformat(), {"from": artifact.valid_from.isoformat(), "to": artifact.valid_to.isoformat()})
        self._rule(rules, "artifact_revocation", "硬件验收未撤销", artifact.revoked_at is None, artifact.revoked_at.isoformat() if artifact.revoked_at else None, None)
        checklist = artifact.physical_checklist.model_dump()
        self._rule(rules, "physical_checklist", "物理急停/PLC/继电器检查", all(checklist.values()), checklist, {key: True for key in checklist})

        release = load_release_metadata()
        plan_path = CONFIG_DIR / "test_plan.yaml"
        plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest() if plan_path.is_file() else None
        dbc = self.state.dbc.status() if self.state.dbc else {}
        try:
            config_digest = configuration_hash(runtime_configuration(self.state.config))
        except Exception:
            config_digest = None
        expected = {
            "station_id": self.state.config.station_id,
            "vehicle_series": self.state.config.vehicle_series,
            "release_hash": release.manifest_sha256,
            "config_hash": config_digest,
            "dbc_hash": str(dbc.get("hash") or "").lower() or None,
            "test_plan_hash": plan_hash,
        }
        for field, threshold in expected.items():
            current = getattr(artifact, field)
            self._rule(rules, f"artifact_scope_{field}", f"验收范围 {field}", bool(threshold and str(current).lower() == str(threshold).lower()), current, threshold)
        self._rule(rules, "release_formal", "发布包签名且工作树干净", release.formal_release and release.dirty is False, release.model_dump(), {"formal_release": True, "dirty": False})
        return self._result(rules, artifact)

    def _load(self) -> tuple[HardwareAcceptanceArtifact | None, dict[str, Any]]:
        path = self.artifact_path()
        try:
            artifact = HardwareAcceptanceArtifact.model_validate_json(path.read_text(encoding="utf-8"))
            return artifact, self._rule_value("artifact_present", "硬件验收文件", True, str(path), "valid signed artifact")
        except FileNotFoundError:
            return None, self._rule_value("artifact_present", "硬件验收文件", False, None, "valid signed artifact")
        except Exception as exc:
            return None, self._rule_value("artifact_schema", "硬件验收 schema", False, type(exc).__name__, "valid strict schema")

    @staticmethod
    def _rule_value(rule: str, label: str, passed: bool, current: Any, threshold: Any) -> dict[str, Any]:
        return {"rule": rule, "label": label, "status": "PASS" if passed else "FAIL", "current": current, "threshold": threshold, "blocking": True}

    def _rule(self, rules: list[dict[str, Any]], rule: str, label: str, passed: bool, current: Any, threshold: Any) -> None:
        rules.append(self._rule_value(rule, label, passed, current, threshold))

    @staticmethod
    def _result(rules: list[dict[str, Any]], artifact: HardwareAcceptanceArtifact | None) -> dict[str, Any]:
        reasons = [item for item in rules if item["blocking"] and item["status"] != "PASS"]
        return {
            "allowed": not reasons,
            "applicable": True,
            "status": "approved" if not reasons else "blocked",
            "artifact": artifact.model_dump(mode="json", exclude={"signature"}) if artifact else None,
            "rules": rules,
            "reasons": reasons,
        }
