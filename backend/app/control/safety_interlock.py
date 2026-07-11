from __future__ import annotations

from typing import Literal

from app.control.control_121 import Control121Command
from app.services.app_state import AppState

Operation = Literal[
    "manual",
    "eol",
    "eol_motion",
    "safe_stop",
    "emergency",
    "release_emergency",
]


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
    ) -> dict:
        config = self.state.config
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
                "< 2000 ms",
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
        if not stop_operation:
            dbc_status = self.state.dbc.status() if self.state.dbc else {"loaded": False}
            dbc_allowed = bool(dbc_status.get("loaded") or not config.require_dbc_for_control)
            self._rule(rules, "dbc_ready", "DBC/覆盖规则可用", dbc_allowed, dbc_status, "loaded or explicitly raw-allowed")

            max_alarm = self.state.alarms.max_level() if self.state.alarms else 0
            self._rule(
                rules,
                "no_severe_alarm",
                "无严重告警",
                max_alarm < 3,
                max_alarm,
                "< 3",
                blocking=operation != "eol",
            )
            self._rule(rules, "database_writable", "数据库可写", self.state.db_writable, self.state.db_writable, True)
            if operation != "release_emergency":
                self._rule(rules, "emergency_released", "急停未锁存", not self.state.emergency_stop, self.state.emergency_stop, False)
                self._rule(rules, "safe_stop_released", "安全停车未锁存", not self.state.safe_stop_latched, self.state.safe_stop_latched, False)

            speed_feedback = self.state.signals.fresh_value(
                "CCU_Vehicle_Speed", "Vehicle_Speed", max_age_seconds=config.channel_online_timeout_seconds
            )
            self._rule(
                rules,
                "critical_feedback_fresh",
                "关键速度反馈新鲜",
                speed_feedback is not None,
                speed_feedback,
                f"age < {config.channel_online_timeout_seconds:.1f}s",
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
            speed = self.state.signals.fresh_value(
                "CCU_Vehicle_Speed", "Vehicle_Speed", max_age_seconds=config.channel_online_timeout_seconds
            )
            max_alarm = self.state.alarms.max_level() if self.state.alarms else 0
            self._rule(rules, "vehicle_stopped", "车辆速度已确认归零", speed is not None and abs(float(speed)) <= config.stopped_speed_threshold_kmh, speed, config.stopped_speed_threshold_kmh)
            self._rule(rules, "no_severe_alarm", "无严重告警", max_alarm < 3, max_alarm, "< 3")

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
            "level": "normal" if allowed else "danger",
            "rules": rules,
            "reasons": [item for item in rules if item["blocking"] and item["status"] != "PASS"],
        }

    def require_allowed(
        self,
        command: Control121Command | None = None,
        *,
        operation: Operation = "manual",
    ) -> dict:
        evaluation = self.evaluate(command, operation=operation)
        if not evaluation["allowed"]:
            raise InterlockBlocked(evaluation)
        return evaluation

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
