from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import math
from typing import Any

from app.core.time import utc_now
from app.eol.models import AssertionOutcome, AssertionSpec
from app.eol.plan_loader import resolve_threshold


@dataclass
class AssertionContext:
    state: Any
    thresholds: dict[str, Any]
    session: dict[str, Any]
    step: dict[str, Any]
    action_observations: list[dict[str, Any]] = field(default_factory=list)


class AssertionEvaluator:
    async def evaluate(
        self,
        spec: AssertionSpec,
        context: AssertionContext,
    ) -> AssertionOutcome:
        started_at = utc_now()
        try:
            passed, measured, unit, metadata, threshold = await self._evaluate(spec, context)
            reason = "" if passed else self._reason(spec, measured, threshold, metadata)
        except Exception as exc:
            passed = False
            measured = None
            unit = ""
            metadata = {"quality": "invalid"}
            threshold = self._threshold(spec, context, tolerate_missing=True)
            reason = str(exc)
        return AssertionOutcome(
            assertion_id=spec.id,
            description=spec.description or spec.id,
            signal_name=spec.signal or ",".join(spec.signals) or spec.message or spec.type,
            operator=spec.operator,
            threshold=threshold,
            measured_value=measured,
            unit=unit,
            result="PASS" if passed else "FAIL",
            severity=spec.severity,
            failure_reason=reason,
            sample_started_at=started_at,
            sample_ended_at=utc_now(),
            quality=str(metadata.get("quality", "good")),
            source_can_id=str(metadata.get("can_id", "")),
            source_channel=str(metadata.get("channel", "")),
            source_timestamp=str(metadata.get("updated_at", "")),
        )

    async def _evaluate(
        self,
        spec: AssertionSpec,
        context: AssertionContext,
    ) -> tuple[bool, Any, str, dict[str, Any], Any]:
        threshold = self._threshold(spec, context)
        if spec.type == "system":
            value = self._system_value(spec, context)
            expected = spec.expected if spec.expected is not None else spec.value
            return value == expected, value, "", {"quality": "good"}, expected
        if spec.type == "database":
            value = bool(context.state.database and context.state.db_writable)
            expected = True if spec.expected is None else bool(spec.expected)
            return value is expected, value, "", {"quality": "good"}, expected
        if spec.type == "report":
            report = context.session.get("report") or {}
            files = report.get("files", {})
            missing = [name for name in spec.formats if not files.get(name)]
            return not missing, {"report_id": report.get("id"), "missing": missing}, "", {"quality": "good"}, spec.formats
        if spec.type == "can_statistics":
            status = context.state.can.status() if context.state.can else []
            bad = [row["channel"] for row in status if not row.get("online") or not row.get("queue_healthy")]
            return not bad, {"unhealthy_channels": bad}, "", {"quality": "good"}, "all channels healthy"

        if spec.operator == "all_present":
            return self._all_frames_present(spec, context, threshold)
        if spec.operator == "all_bool_zero":
            return await self._all_bool_zero(spec, context, threshold)
        if spec.operator == "follows_commands":
            return self._shift_follows(spec, context, threshold)
        if spec.operator in {"reaches_near", "follows_target"}:
            return self._reaches_target(spec, context, threshold)
        if spec.operator in {"consistent", "wheel_consistent"}:
            return self._consistent(spec, context, threshold)
        if spec.operator in {"follows_command", "steering_follows"}:
            return self._steering_follows(spec, context, threshold)
        if spec.operator == "follows_commands_or_manual_review":
            return self._lights_follow(spec, context, threshold)
        if spec.operator == "brake_confirmed":
            return self._brake_confirmed(spec, context, threshold)
        if spec.operator == "max_level_equals":
            sample = await self._wait_sample("VCU_Max_Warning_Level", spec, context)
            expected = spec.value
            return int(sample["value"]) == int(expected), sample["value"], sample.get("unit", ""), sample, expected

        if spec.signals:
            samples = [await self._wait_sample(key, spec, context) for key in spec.signals]
            values = [sample["value"] for sample in samples]
            if spec.operator == "all_between":
                lower, upper = self._bounds(threshold)
                passed = all(lower <= float(value) <= upper for value in values)
            elif spec.operator == "no_unexpected_active":
                passed = not any(bool(value) for value in values)
            else:
                raise ValueError(f"unsupported multi-signal operator: {spec.operator}")
            return passed, values, samples[0].get("unit", ""), self._merge_metadata(samples), threshold

        if not spec.signal:
            raise ValueError(f"assertion {spec.id} has no signal source")
        sample = await self._wait_sample(spec.signal, spec, context)
        value = sample["value"]
        expected = threshold if threshold is not None else spec.value
        passed = self._compare(spec.operator, value, expected, spec.values)
        return passed, value, sample.get("unit", ""), sample, expected

    @staticmethod
    def _system_value(spec: AssertionSpec, context: AssertionContext) -> Any:
        channel_rows = context.state.can.status() if context.state.can else []
        channels = {str(row.get("channel")): row for row in channel_rows}
        values = {
            "db_writable": bool(context.state.db_writable),
            "dbc_loaded": bool(context.state.dbc and context.state.dbc.status().get("loaded")),
            "emergency_released": not bool(context.state.emergency_stop),
            "can1_online": bool(channels.get("CAN1", {}).get("online")),
            "can2_online": bool(channels.get("CAN2", {}).get("online")),
        }
        if spec.id not in values:
            raise ValueError(f"unsupported system assertion: {spec.id}")
        return values[spec.id]

    async def _wait_sample(
        self,
        key: str,
        spec: AssertionSpec,
        context: AssertionContext,
    ) -> dict[str, Any]:
        timeout_seconds = self._timeout_ms(spec, context) / 1000
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        last_error = "signal unavailable"
        while True:
            try:
                return context.state.signals.require_sample(
                    key,
                    max_age_seconds=spec.max_age_ms / 1000,
                    channel=spec.channel,
                )
            except (KeyError, ValueError) as exc:
                last_error = str(exc)
            if asyncio.get_running_loop().time() >= deadline:
                raise ValueError(f"{key}: {last_error}")
            await asyncio.sleep(0.02)

    def _all_frames_present(
        self,
        spec: AssertionSpec,
        context: AssertionContext,
        threshold: Any,
    ) -> tuple[bool, Any, str, dict[str, Any], Any]:
        items = context.state.can.latest_items(split_by_channel=True) if context.state.can else []
        found = {
            item.get("can_id_hex")
            for item in items
            if int(item.get("last_seen_ms", 10**9)) <= spec.max_age_ms
            and (spec.channel is None or item.get("channel") == spec.channel)
        }
        required = {self._normalize_can_id(value) for value in spec.signals}
        missing = sorted(required - found)
        return not missing, {"present": sorted(required & found), "missing": missing}, "", {"quality": "good"}, sorted(required)

    async def _all_bool_zero(
        self,
        spec: AssertionSpec,
        context: AssertionContext,
        threshold: Any,
    ) -> tuple[bool, Any, str, dict[str, Any], Any]:
        bitmap = await self._wait_sample("BMS_Protect_Bitmap", spec, context)
        source = (
            {
                key: item
                for (key, channel), item in context.state.signals.current_by_source.items()
                if not spec.channel or channel == spec.channel
            }
            if hasattr(context.state.signals, "current_by_source")
            else context.state.signals.current
        )
        bool_samples = [
            item
            for key, item in source.items()
            if key.startswith("BMS_Protect_") and key != "BMS_Protect_Bitmap"
        ]
        values = {item["key"]: int(bool(item["value"])) for item in bool_samples}
        values["BMS_Protect_Bitmap"] = int(bitmap["value"])
        passed = int(bitmap["value"]) == 0 and all(value == 0 for value in values.values())
        return passed, values, "bool/bitmap", bitmap, 0

    def _shift_follows(self, spec: AssertionSpec, context: AssertionContext, threshold: Any):
        expected_map = {"D": 1, "N": 0, "R": 3}
        comparisons = []
        for observation in context.action_observations:
            command = observation.get("command", {})
            sample = observation.get("samples", {}).get(spec.signal or "CCU_Shift_Level_Status")
            if not sample:
                comparisons.append({"expected": command.get("shift"), "actual": None})
                continue
            expected = expected_map.get(command.get("shift"))
            observed = [
                item.get("value")
                for item in observation.get("windows", {}).get(
                    spec.signal or "CCU_Shift_Level_Status", []
                )
            ]
            actual = sample.get("value")
            comparisons.append(
                {
                    "expected": expected,
                    "actual": actual,
                    "observed": observed,
                    "matched": expected == actual or expected in observed,
                }
            )
        passed = bool(comparisons) and all(row.get("matched") for row in comparisons)
        return passed, comparisons, "", {"quality": "good"}, "feedback follows D/N/R/N"

    def _reaches_target(self, spec: AssertionSpec, context: AssertionContext, threshold: Any):
        tolerance = float(threshold if threshold is not None else 0)
        target = float(spec.target if spec.target is not None else spec.value)
        values = []
        metadata: dict[str, Any] = {"quality": "invalid"}
        for observation in context.action_observations:
            command = observation.get("command", {})
            if float(command.get("target_speed_kmh", 0)) <= 0:
                continue
            sample = observation.get("samples", {}).get(spec.signal or "")
            window_values = [
                float(item["value"])
                for item in observation.get("windows", {}).get(spec.signal or "", [])
            ]
            if window_values:
                values.extend(window_values)
            elif sample:
                values.append(float(sample["value"]))
            if sample:
                metadata = sample
        passed = bool(values) and any(abs(value - target) <= tolerance for value in values)
        return passed, values, metadata.get("unit", ""), metadata, {"target": target, "tolerance": tolerance}

    def _consistent(self, spec: AssertionSpec, context: AssertionContext, threshold: Any):
        tolerance = float(threshold if threshold is not None else 0)
        observed: list[list[float]] = []
        metadata: dict[str, Any] = {"quality": "invalid"}
        for observation in context.action_observations:
            command = observation.get("command", {})
            if float(command.get("target_speed_kmh", 0)) <= 0:
                continue
            samples = observation.get("samples", {})
            row = [float(samples[key]["value"]) for key in spec.signals if key in samples]
            if len(row) == len(spec.signals):
                observed.append(row)
                metadata = samples[spec.signals[0]]
        passed = bool(observed) and all(max(row) - min(row) <= tolerance for row in observed)
        return passed, observed, metadata.get("unit", ""), metadata, {"max_delta": tolerance}

    def _steering_follows(self, spec: AssertionSpec, context: AssertionContext, threshold: Any):
        tolerance = float(threshold if threshold is not None else 0)
        command_field = "front_steering_cmd" if "Front" in (spec.signal or "") else "rear_steering_cmd"
        comparisons = []
        metadata: dict[str, Any] = {"quality": "invalid"}
        for observation in context.action_observations:
            command = observation.get("command", {})
            sample = observation.get("samples", {}).get(spec.signal or "")
            if not sample:
                comparisons.append({"expected": command.get(command_field), "actual": None})
                continue
            expected = float(command.get(command_field, 0))
            observed = [
                float(item["value"])
                for item in observation.get("windows", {}).get(spec.signal or "", [])
            ] or [float(sample["value"])]
            actual = min(observed, key=lambda value: abs(value - expected))
            comparisons.append(
                {
                    "expected": expected,
                    "actual": actual,
                    "error": abs(actual - expected),
                    "sample_count": len(observed),
                }
            )
            metadata = sample
        passed = bool(comparisons) and all(
            row.get("actual") is not None and float(row.get("error", math.inf)) <= tolerance
            for row in comparisons
        )
        return passed, comparisons, metadata.get("unit", ""), metadata, {"max_error": tolerance}

    def _lights_follow(self, spec: AssertionSpec, context: AssertionContext, threshold: Any):
        fields = {
            "Left_Turn_Light_Status": "left_light",
            "Right_Turn_Light_Status": "right_light",
            "Position_Light_Status": "position_light",
            "Low_Beam_Status": "low_beam",
        }
        comparisons = []
        for observation in context.action_observations:
            command = observation.get("command", {})
            samples = observation.get("samples", {})
            active_fields = [key for key, field in fields.items() if command.get(field)]
            if command.get("all_lights_off"):
                active_fields = list(fields)
            for key in active_fields:
                expected = False if command.get("all_lights_off") else bool(command.get(fields[key]))
                observed = [
                    bool(item["value"])
                    for item in observation.get("windows", {}).get(key, [])
                ]
                actual = bool(samples.get(key, {}).get("value")) if key in samples else None
                matched = expected in observed if observed else actual is expected
                comparisons.append(
                    {
                        "signal": key,
                        "expected": expected,
                        "actual": actual,
                        "matched": matched,
                    }
                )
        passed = bool(comparisons) and all(row["matched"] for row in comparisons)
        return passed, comparisons, "bool", {"quality": "good"}, "feedback follows light commands"

    def _brake_confirmed(self, spec: AssertionSpec, context: AssertionContext, threshold: Any):
        samples = []
        observed_values: list[bool] = []
        for observation in context.action_observations:
            if not observation.get("command", {}).get("brake_enable"):
                continue
            sample = observation.get("samples", {}).get(spec.signal or "Brake_Status")
            if sample:
                samples.append(sample)
            observed_values.extend(
                bool(item["value"])
                for item in observation.get("windows", {}).get(
                    spec.signal or "Brake_Status", []
                )
            )
        passed = bool(samples or observed_values) and (
            any(observed_values) or any(bool(sample["value"]) for sample in samples)
        )
        metadata = samples[-1] if samples else {"quality": "invalid"}
        return passed, observed_values or [sample["value"] for sample in samples], "bool", metadata, True

    @staticmethod
    def _compare(operator: str, value: Any, expected: Any, values: list[Any]) -> bool:
        if operator == "==":
            return value == expected
        if operator == "!=":
            return value != expected
        if operator == ">=":
            return float(value) >= float(expected)
        if operator == "<=":
            return float(value) <= float(expected)
        if operator == ">":
            return float(value) > float(expected)
        if operator == "<":
            return float(value) < float(expected)
        if operator == "between":
            lower, upper = AssertionEvaluator._bounds(expected)
            return lower <= float(value) <= upper
        if operator == "in":
            return value in values
        raise ValueError(f"unsupported operator: {operator}")

    @staticmethod
    def _bounds(value: Any) -> tuple[float, float]:
        if isinstance(value, dict) and "min" in value and "max" in value:
            return float(value["min"]), float(value["max"])
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return float(value[0]), float(value[1])
        raise ValueError(f"threshold does not define min/max: {value!r}")

    @staticmethod
    def _normalize_can_id(value: str) -> str:
        return f"0x{int(value, 0):X}"

    @staticmethod
    def _merge_metadata(samples: list[dict[str, Any]]) -> dict[str, Any]:
        first = samples[0] if samples else {}
        return {
            "quality": "good" if samples and all(item.get("quality") == "good" for item in samples) else "invalid",
            "can_id": ",".join(sorted({str(item.get("can_id", "")) for item in samples})),
            "channel": ",".join(sorted({str(item.get("channel", "")) for item in samples})),
            "updated_at": first.get("updated_at", ""),
        }

    def _threshold(self, spec: AssertionSpec, context: AssertionContext, *, tolerate_missing: bool = False) -> Any:
        reference = spec.tolerance_ref or spec.threshold_ref
        try:
            return resolve_threshold(context.thresholds, reference) if reference else None
        except KeyError:
            if tolerate_missing:
                return reference
            raise

    def _timeout_ms(self, spec: AssertionSpec, context: AssertionContext) -> int:
        if spec.timeout_ref:
            return int(resolve_threshold(context.thresholds, spec.timeout_ref))
        return spec.timeout_ms

    @staticmethod
    def _reason(spec: AssertionSpec, measured: Any, threshold: Any, metadata: dict[str, Any]) -> str:
        quality = metadata.get("quality", "unknown")
        return (
            f"assertion {spec.id} failed: measured={measured!r}, "
            f"expected={threshold!r}, quality={quality}"
        )


def pass_assertion(name: str, value: bool = True) -> dict[str, Any]:
    return {"name": name, "result": "PASS" if value else "FAIL", "value": value}
