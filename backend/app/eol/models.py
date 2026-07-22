from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


AssertionOperator = Literal[
    "==",
    "!=",
    ">=",
    "<=",
    ">",
    "<",
    "between",
    "in",
    "all_present",
    "all_bool_zero",
    "follows_commands",
    "reaches_near",
    "follows_target",
    "consistent",
    "wheel_consistent",
    "follows_command",
    "steering_follows",
    "follows_commands_or_manual_review",
    "brake_confirmed",
    "max_level_equals",
    "all_between",
    "no_unexpected_active",
    "no_critical_timeout",
]


class CreateSessionRequest(BaseModel):
    chassis_no: str = "YL-JD-001"
    vin: str = "L000000000000001"
    serial_no: str = "SN-20260401-001"
    operator: str = "op01"
    station_id: str = "EOL-STATION-01"
    plan_id: str = "default_chassis_eol_v1"
    remarks: str = ""


class FailurePolicy(str, Enum):
    FAIL = "fail"
    SAFE_STOP_AND_FAIL = "safe_stop_and_fail"
    CONTINUE = "continue"


class AssertionSpec(BaseModel):
    id: str
    description: str = ""
    type: Literal["signal", "system", "database", "report", "can_statistics"] = "signal"
    signal: str | None = None
    signals: list[str] = Field(default_factory=list)
    message: str | None = None
    channel: Literal["CAN1", "CAN2"] | None = None
    operator: AssertionOperator = "=="
    value: Any = None
    expected: Any = None
    values: list[Any] = Field(default_factory=list)
    target: float | None = None
    threshold_ref: str | None = None
    tolerance_ref: str | None = None
    timeout_ref: str | None = None
    timeout_ms: int = Field(default=1000, ge=0, le=120_000)
    max_age_ms: int = Field(default=1500, ge=50, le=10_000)
    severity: Literal["info", "warning", "failure", "critical"] = "failure"
    formats: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source(self) -> "AssertionSpec":
        source_free = self.type in {"system", "database", "report", "can_statistics"}
        if not source_free and not (self.signal or self.signals or self.message):
            raise ValueError(f"assertion {self.id} requires signal, signals, or message")
        return self


class ControlAction(BaseModel):
    type: Literal["control_121"] = "control_121"
    shift: Literal["D", "N", "R"] = "N"
    drive_mode: Literal["Manual", "Remote", "Auto"] = "Remote"
    target_speed_kmh: float = Field(default=0, ge=0, le=8)
    front_steering_cmd: int = Field(default=0, ge=-120, le=120)
    rear_steering_cmd: int = Field(default=0, ge=-120, le=120)
    brake_enable: bool = True
    left_light: bool = False
    right_light: bool = False
    position_light: bool = False
    low_beam: bool = False
    all_lights_off: bool = False
    speed_mode: bool = True
    duration_ms: int = Field(default=250, ge=20, le=30_000)
    period_ms: int = Field(default=20, ge=10, le=100)


class SystemAction(BaseModel):
    type: Literal["generate_report", "wait"]
    duration_ms: int = Field(default=0, ge=0, le=120_000)


class ManualAction(BaseModel):
    prompt: str
    confirmation_label: str = "确认完成"
    timeout_ms: int = Field(default=30_000, ge=1000, le=600_000)
    require_note: bool = False


class TestStepPlan(BaseModel):
    id: str
    order: int = Field(ge=1, le=100)
    name: str
    description: str = ""
    preconditions: list[AssertionSpec]
    control_actions: list[ControlAction]
    system_actions: list[SystemAction]
    sample_window_ms: int = Field(ge=0, le=30_000)
    assertions: list[AssertionSpec]
    timeout_ms: int = Field(ge=100, le=300_000)
    failure_policy: FailurePolicy
    cleanup_actions: list[ControlAction]
    safe_stop_on_fail: bool
    manual_action: ManualAction | None = None
    requires_motion: bool = False

    @model_validator(mode="after")
    def validate_timeout_budget(self) -> "TestStepPlan":
        action_budget = sum(action.duration_ms for action in self.control_actions)
        action_budget += sum(action.duration_ms for action in self.system_actions)
        if self.manual_action:
            action_budget += self.manual_action.timeout_ms
        if self.timeout_ms < action_budget:
            raise ValueError(
                f"step {self.id} timeout_ms={self.timeout_ms} is below action budget {action_budget}"
            )
        if self.requires_motion and not self.control_actions:
            raise ValueError(f"motion step {self.id} requires at least one 0x121 action")
        return self


class TestPlanMetadata(BaseModel):
    id: str
    name: str
    version: str
    default_vehicle_series: str = "JD"
    control_message: Literal["0x121"] = "0x121"
    extension_messages_enabled: bool = False
    on_severe_error: FailurePolicy = FailurePolicy.SAFE_STOP_AND_FAIL
    generate_report_on_failure: bool = True

    @model_validator(mode="after")
    def reject_extension_messages(self) -> "TestPlanMetadata":
        if self.extension_messages_enabled:
            raise ValueError("EOL plans may not enable 0x123/0x126 extension messages")
        return self


class TestPlanDocument(BaseModel):
    plan: TestPlanMetadata
    steps: list[TestStepPlan]

    @model_validator(mode="after")
    def validate_steps(self) -> "TestPlanDocument":
        orders = [step.order for step in self.steps]
        ids = [step.id for step in self.steps]
        if len(self.steps) != 12:
            raise ValueError("production EOL plan must contain exactly 12 steps")
        if orders != list(range(1, 13)):
            raise ValueError("EOL step order must be contiguous 1..12")
        if len(set(ids)) != len(ids):
            raise ValueError("EOL step ids must be unique")
        return self


class AssertionOutcome(BaseModel):
    assertion_id: str
    description: str
    signal_name: str = ""
    operator: str
    threshold: Any = None
    measured_value: Any = None
    unit: str = ""
    result: Literal["PASS", "FAIL"]
    severity: str = "failure"
    failure_reason: str = ""
    sample_started_at: str | None = None
    sample_ended_at: str | None = None
    quality: str = "unknown"
    source_can_id: str = ""
    source_channel: str = ""
    source_timestamp: str = ""
