from __future__ import annotations

import math
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.control.control_121 import Control121Command
from app.core.config import FeedbackRequirement
from app.services.app_state import AppState
from app.services.audit import record_operator_action

Operation = Literal[
    "manual",
    "eol",
    "eol_motion",
    "safe_stop",
    "emergency",
    "release_emergency",
]


class SafetyEvaluationContext(BaseModel):
    """Non-secret scope carried through every periodic interlock evaluation."""

    model_config = ConfigDict(extra="forbid")

    actor: str | None = None
    session_id: str | None = None
    vehicle_id: str | None = None
    override_id: str | None = None


class InterlockBlocked(RuntimeError):
    def __init__(self, evaluation: dict) -> None:
        super().__init__("safety interlock blocked operation")
        self.evaluation = evaluation


class SafetyInterlockService:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def evaluate(
        self,
        command: Control121Command | None = None,
        *,
        operation: Operation = "manual",
        context: SafetyEvaluationContext | None = None,
    ) -> dict:
        config = self.state.config
        profile = str(getattr(config, "profile", "test"))
        channel_rows = self.state.can.status() if self.state.can else []
        channels = {str(row.get("channel")): row for row in channel_rows}
        rules: list[dict] = []

        required_channels = ["CAN1", "CAN2"] if operation in {"eol", "eol_motion"} else [config.control_channel]
        for channel in required_channels:
            status = channels.get(channel, {})
            self._rule(
                rules,
                f"{channel.lower()}_online",
                f"{channel} 原始接收在线",
                bool(status.get("online")),
                status.get("receive_age_ms"),
                f"< {config.channel_online_timeout_seconds * 1000:.0f} ms",
            )
            self._rule(
                rules,
                f"{channel.lower()}_queue_healthy",
                f"{channel} 接收队列健康",
                bool(status.get("queue_healthy")),
                status.get("queue_depth"),
                f"< {status.get('queue_capacity', 0)}",
            )

        control_channels = [item.channel for item in config.channels if item.control_enabled]
        unique_control = config.control_channel == "CAN2" and control_channels == ["CAN2"]
        self._rule(
            rules,
            "single_control_channel",
            "唯一控制通道为 CAN2",
            unique_control,
            control_channels or [config.control_channel],
            ["CAN2"],
        )

        stop_operation = operation in {"safe_stop", "emergency"}
        degraded_mode = False
        feedback_groups: list[str] = []
        if not stop_operation:
            dbc_status = self.state.dbc.status() if self.state.dbc else {"loaded": False}
            if profile == "production":
                hash_match = bool(
                    dbc_status.get("hash")
                    and str(dbc_status.get("hash")).lower() == str(config.approved_dbc_sha256).lower()
                )
                vehicle_match = bool(
                    dbc_status.get("vehicle_series")
                    and str(dbc_status.get("vehicle_series")).upper() == config.vehicle_series.upper()
                )
                dbc_allowed = bool(dbc_status.get("loaded") and hash_match and vehicle_match)
                dbc_threshold = {
                    "loaded": True,
                    "sha256": config.approved_dbc_sha256,
                    "vehicle_series": config.vehicle_series,
                }
            else:
                dbc_allowed = bool(dbc_status.get("loaded") or not config.require_dbc_for_control)
                degraded_mode = not bool(dbc_status.get("loaded"))
                hash_match = None
                vehicle_match = None
                dbc_threshold = "loaded or explicit non-production raw-only mode"
            self._rule(
                rules,
                "dbc_ready",
                "DBC、完整哈希与车型匹配",
                dbc_allowed,
                dbc_status | {"hash_match": hash_match, "vehicle_match": vehicle_match},
                dbc_threshold,
            )

            policy_validated = bool(getattr(config, "safe_stop_policy_hardware_validated", False))
            acceptance = (
                self.state.hardware_acceptance.evaluate()
                if profile == "production"
                and getattr(self.state, "hardware_acceptance", None)
                else {
                    "allowed": profile != "production",
                    "status": "not_required_nonproduction",
                    "reasons": [],
                }
            )
            policy_allowed = profile != "production" or bool(acceptance.get("allowed"))
            self._rule(
                rules,
                "hardware_acceptance_artifact",
                "硬件验收批准文件有效且范围完全匹配",
                policy_allowed,
                {
                    "policy": getattr(config, "safe_stop_post_confirm_policy", "stop_transmission"),
                    "legacy_hardware_validated": policy_validated,
                    "acceptance": acceptance,
                },
                {"signed_artifact": True, "scope_match": True, "not_revoked": True},
            )

            max_alarm = self.state.alarms.max_level() if self.state.alarms else 0
            alarm_current = (
                self.state.alarms.current()
                if self.state.alarms and hasattr(self.state.alarms, "current")
                else []
            )
            critical_alarm_ids = [
                str(item.get("id")) for item in alarm_current if int(item.get("level", 0)) >= 3
            ]
            alarm_allowed = max_alarm < 3
            override_details: dict = {"used": False}
            if not alarm_allowed and context and context.override_id and getattr(self.state, "overrides", None):
                override_details = self.state.overrides.validate_for_interlock(
                    context.override_id,
                    actor=context.actor,
                    session_id=context.session_id,
                    operation=operation,
                    vehicle_id=context.vehicle_id,
                    critical_alarm_ids=critical_alarm_ids,
                )
                alarm_allowed = bool(override_details.get("allowed"))
            self._rule(
                rules,
                "no_severe_alarm",
                "无严重告警或存在精确范围的双人批准",
                alarm_allowed,
                {"max_level": max_alarm, "critical_alarm_ids": critical_alarm_ids, "override": override_details},
                "< 3 or one active, scoped and approved alarm override",
            )
            self._rule(rules, "database_writable", "数据库可写", self.state.db_writable, self.state.db_writable, True)
            if operation != "release_emergency":
                self._rule(rules, "emergency_released", "急停未锁存", not self.state.emergency_stop, self.state.emergency_stop, False)
                self._rule(rules, "safe_stop_released", "安全停车未锁存", not self.state.safe_stop_latched, self.state.safe_stop_latched, False)

            if operation in {"manual", "eol", "eol_motion", "release_emergency"}:
                feedback_groups = (
                    ["base", "brake"]
                    if operation == "release_emergency"
                    else self._required_feedback_groups(command, operation)
                )
                for group in feedback_groups:
                    for requirement in getattr(config.feedback_dependencies, group):
                        passed, current, threshold = self.evaluate_feedback(requirement)
                        self._rule(
                            rules,
                            f"feedback_{group}_{requirement.id}",
                            requirement.label,
                            passed,
                            current,
                            threshold,
                        )
        else:
            self._rule(
                rules,
                "stop_command_shape",
                "停车命令为零速、N挡并制动",
                self.is_safe_stop_command(command),
                command.model_dump() if command else None,
                {"shift": "N", "target_speed_kmh": 0, "brake_enable": True},
            )

        if operation == "release_emergency":
            speed_requirement = config.feedback_dependencies.base[0]
            brake_requirement = config.feedback_dependencies.brake[0]
            speed_ok, speed, speed_threshold = self.evaluate_feedback(speed_requirement)
            brake_ok, brake, brake_threshold = self.evaluate_feedback(brake_requirement)
            speed_value = speed.get("value") if speed_ok else None
            brake_value = brake.get("value") if brake_ok else None
            self._rule(
                rules,
                "vehicle_stopped",
                "车辆速度已可信归零",
                speed_ok and speed_value is not None and abs(float(speed_value)) <= config.stopped_speed_threshold_kmh,
                speed,
                speed_threshold | {"stopped_abs_max": config.stopped_speed_threshold_kmh},
            )
            self._rule(
                rules,
                "brake_confirmed",
                "制动反馈已可信激活",
                brake_ok and brake_value is True,
                brake,
                brake_threshold | {"required_value": True},
            )

        if command is not None and operation in {"manual", "eol_motion"}:
            self._rule(
                rules,
                "speed_limit",
                "目标速度不超过安全上限",
                command.target_speed_kmh <= config.manual_speed_limit_kmh,
                command.target_speed_kmh,
                config.manual_speed_limit_kmh,
            )
            angle_ok = (
                abs(command.front_steering_cmd) <= config.steering_limit_absolute
                and abs(command.rear_steering_cmd) <= config.steering_limit_absolute
            )
            self._rule(
                rules,
                "steering_limit",
                "前后转角在安全范围内",
                angle_ok,
                [command.front_steering_cmd, command.rear_steering_cmd],
                [-config.steering_limit_absolute, config.steering_limit_absolute],
            )

        allowed = all(item["status"] == "PASS" for item in rules if item["blocking"])
        return {
            "allowed": allowed,
            "operation": operation,
            "profile": profile,
            "degraded_mode": degraded_mode,
            "feedback_groups": feedback_groups,
            "level": "normal" if allowed else "danger",
            "rules": rules,
            "reasons": [item for item in rules if item["blocking"] and item["status"] != "PASS"],
        }

    def require_allowed(
        self,
        command: Control121Command | None = None,
        *,
        operation: Operation = "manual",
        context: SafetyEvaluationContext | None = None,
    ) -> dict:
        evaluation = self.evaluate(command, operation=operation, context=context)
        if not evaluation["allowed"]:
            record_operator_action(
                self.state,
                None,
                "safety_interlock_reject",
                context.session_id if context and context.session_id else "control.0x121",
                {
                    "operation": operation,
                    "command": command.model_dump() if command else None,
                    "context": context.model_dump(exclude_none=True) if context else {},
                    "reasons": evaluation["reasons"],
                },
                "BLOCKED",
                required=True,
            )
            raise InterlockBlocked(evaluation)
        return evaluation

    def _required_feedback_groups(
        self, command: Control121Command | None, operation: Operation
    ) -> list[str]:
        if command is None or operation == "eol":
            return ["base", "drive", "steering", "brake"]
        groups = ["base"]
        if command.shift != "N" or command.target_speed_kmh > 0:
            groups.append("drive")
        if command.front_steering_cmd != 0 or command.rear_steering_cmd != 0:
            groups.append("steering")
        if command.brake_enable:
            groups.append("brake")
        return groups

    def evaluate_feedback(
        self, requirement: FeedbackRequirement
    ) -> tuple[bool, dict, dict]:
        now = time.monotonic()
        exact = [
            self.state.signals.current_by_source.get((key, requirement.channel))
            for key in requirement.signals
        ]
        candidates = [item for item in exact if item]
        if candidates:
            item = max(candidates, key=lambda row: float(row.get("received_at_monotonic", 0) or 0))
        else:
            fallback = [self.state.signals.current.get(key) for key in requirement.signals]
            candidates = [item for item in fallback if item]
            item = max(candidates, key=lambda row: float(row.get("received_at_monotonic", 0) or 0)) if candidates else None

        present = item is not None
        received = float(item.get("received_at_monotonic", 0) or 0) if item else 0.0
        age_ms = max(0.0, (now - received) * 1000) if received > 0 else None
        quality = str(item.get("quality", "invalid")) if item else "missing"
        channel = str(item.get("channel", "")) if item else ""
        can_id = str(item.get("can_id", "")) if item else ""
        value = item.get("value") if item else None
        source_ok = bool(
            present
            and channel == requirement.channel
            and can_id
            and (not requirement.expected_can_ids or can_id in requirement.expected_can_ids)
        )
        age_ok = age_ms is not None and age_ms <= requirement.max_age_ms
        quality_ok = quality == "good"
        finite = not isinstance(value, (int, float)) or isinstance(value, bool) or math.isfinite(float(value))
        allowed_ok = not requirement.allowed_values or value in requirement.allowed_values
        range_ok = finite
        if range_ok and requirement.minimum is not None:
            try:
                range_ok = float(value) >= requirement.minimum
            except (TypeError, ValueError):
                range_ok = False
        if range_ok and requirement.maximum is not None:
            try:
                range_ok = float(value) <= requirement.maximum
            except (TypeError, ValueError):
                range_ok = False
        checks = {
            "present": present,
            "fresh": age_ok,
            "quality_valid": quality_ok,
            "source_valid": source_ok,
            "value_valid": allowed_ok and range_ok,
        }
        current = {
            "signals": requirement.signals,
            "selected_signal": item.get("key") if item else None,
            "value": value,
            "quality": quality,
            "age_ms": round(age_ms, 3) if age_ms is not None else None,
            "received_at_monotonic": received if received > 0 else None,
            "channel": channel or None,
            "can_id": can_id or None,
            "checks": checks,
        }
        threshold = {
            "max_age_ms": requirement.max_age_ms,
            "qualities": ["good"],
            "channel": requirement.channel,
            "can_ids": sorted(requirement.expected_can_ids),
            "allowed_values": requirement.allowed_values,
            "minimum": requirement.minimum,
            "maximum": requirement.maximum,
        }
        return all(checks.values()), current, threshold

    @staticmethod
    def is_safe_stop_command(command: Control121Command | None) -> bool:
        return bool(
            command
            and command.shift == "N"
            and command.target_speed_kmh == 0
            and command.front_steering_cmd == 0
            and command.rear_steering_cmd == 0
            and command.brake_enable
        )

    @staticmethod
    def _rule(
        rules: list[dict],
        key: str,
        label: str,
        passed: bool,
        current,
        threshold,
        blocking: bool = True,
    ) -> None:
        rules.append(
            {
                "rule": key,
                "label": label,
                "status": "PASS" if passed else "FAIL",
                "current": current,
                "threshold": threshold,
                "blocking": blocking,
            }
        )
