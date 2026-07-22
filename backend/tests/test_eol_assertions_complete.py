from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.can_gateway.models import CanFrame
from app.eol.assertions import AssertionContext, AssertionEvaluator
from app.eol.models import AssertionSpec
from app.services.signal_store import SignalStore


def _item(key: str, value, *, can_id: str = "0x51", channel: str = "CAN1", quality: str = "good") -> dict:
    return {
        "key": key,
        "value": value,
        "unit": "",
        "quality": quality,
        "can_id": can_id,
        "channel": channel,
        "updated_at": "2026-07-21T00:00:00+00:00",
        "received_at_monotonic": time.monotonic(),
    }


def _context(
    values: dict[str, object] | None = None,
    *,
    thresholds: dict | None = None,
    observations: list[dict] | None = None,
    can=None,
    report: dict | None = None,
) -> AssertionContext:
    signals = SignalStore()
    for key, value in (values or {}).items():
        signals.update(
            key,
            value,
            CanFrame(channel="CAN1", can_id=0x51, data=[0] * 8),
        )
    state = SimpleNamespace(
        signals=signals,
        can=can,
        database=object(),
        db_writable=True,
        emergency_stop=False,
        dbc=SimpleNamespace(status=lambda: {"loaded": True}),
    )
    return AssertionContext(
        state=state,
        thresholds=thresholds or {},
        session={"report": report or {}},
        step={},
        action_observations=observations or [],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operator", "spec_kwargs", "expected"),
    [
        ("==", {"value": 5}, "PASS"),
        ("!=", {"value": 4}, "PASS"),
        (">=", {"value": 5}, "PASS"),
        ("<=", {"value": 5}, "PASS"),
        (">", {"value": 4}, "PASS"),
        ("<", {"value": 6}, "PASS"),
        ("between", {"value": [4, 6]}, "PASS"),
        ("in", {"values": [3, 5, 7]}, "PASS"),
    ],
)
async def test_all_scalar_operators(operator: str, spec_kwargs: dict, expected: str):
    spec = AssertionSpec(
        id=f"scalar-{operator}",
        signal="SignalA",
        operator=operator,
        timeout_ms=0,
        **spec_kwargs,
    )
    outcome = await AssertionEvaluator().evaluate(spec, _context({"SignalA": 5}))
    assert outcome.result == expected
    assert outcome.quality == "good"


@pytest.mark.asyncio
async def test_multi_signal_all_between_and_no_unexpected_active():
    context = _context(
        {"A": 1, "B": 9, "FlagA": False, "FlagB": False},
        thresholds={"safe": {"min": 0, "max": 10}},
    )
    ranged = await AssertionEvaluator().evaluate(
        AssertionSpec(
            id="all-between",
            signals=["A", "B"],
            operator="all_between",
            threshold_ref="safe",
            timeout_ms=0,
        ),
        context,
    )
    inactive = await AssertionEvaluator().evaluate(
        AssertionSpec(
            id="no-active",
            signals=["FlagA", "FlagB"],
            operator="no_unexpected_active",
            timeout_ms=0,
        ),
        context,
    )
    assert ranged.result == inactive.result == "PASS"


@pytest.mark.asyncio
async def test_all_present_and_all_bool_zero_cover_frame_and_bitmap_operators():
    can = SimpleNamespace(
        latest_items=lambda split_by_channel=True: [
            {"can_id_hex": "0x51", "channel": "CAN1", "last_seen_ms": 5},
            {"can_id_hex": "0x77", "channel": "CAN1", "last_seen_ms": 5},
        ]
    )
    context = _context(can=can)
    present = await AssertionEvaluator().evaluate(
        AssertionSpec(
            id="frames",
            signals=["0x51", "0x77"],
            operator="all_present",
            timeout_ms=0,
        ),
        context,
    )
    context = _context({"BMS_Protect_Bitmap": 0, "BMS_Protect_Bit_00": False})
    for key in ("BMS_Protect_Bitmap", "BMS_Protect_Bit_00"):
        item = context.state.signals.current.pop(key)
        item["channel"] = "CAN2"
        item["can_id"] = "0x102"
        context.state.signals.current[key] = item
        context.state.signals.current_by_source.pop((key, "CAN1"), None)
        context.state.signals.current_by_source[(key, "CAN2")] = item
    bitmap = await AssertionEvaluator().evaluate(
        AssertionSpec(
            id="bitmap",
            message="0x102",
            channel="CAN2",
            operator="all_bool_zero",
            timeout_ms=0,
        ),
        context,
    )
    assert present.result == bitmap.result == "PASS"


@pytest.mark.asyncio
async def test_command_follow_and_window_aggregation_operators():
    shift = _item("CCU_Shift_Level_Status", 1)
    speed = _item("Speed", 1.4)
    wheel = {key: _item(key, value, can_id="0x168") for key, value in zip(("FL", "FR", "RL", "RR"), (100, 102, 101, 99))}
    steer = _item("SAS_Front_Angle", 29.0, can_id="0xE1")
    light = _item("Left_Turn_Light_Status", True)
    brake = _item("Brake_Status", True)
    observations = [
        {
            "command": {"shift": "D", "target_speed_kmh": 1.5, "front_steering_cmd": 30, "left_light": True, "brake_enable": True},
            "samples": {
                "CCU_Shift_Level_Status": shift,
                "Speed": speed,
                **wheel,
                "SAS_Front_Angle": steer,
                "Left_Turn_Light_Status": light,
                "Brake_Status": brake,
            },
            "windows": {
                "CCU_Shift_Level_Status": [shift],
                "Speed": [_item("Speed", 0.5), speed],
                "SAS_Front_Angle": [_item("SAS_Front_Angle", 20.0), steer],
                "Left_Turn_Light_Status": [light],
                "Brake_Status": [brake],
            },
        }
    ]
    context = _context(
        observations=observations,
        thresholds={"speed_tol": 0.2, "wheel_tol": 5, "steer_tol": 2},
    )
    specs = [
        AssertionSpec(id="shift", signal="CCU_Shift_Level_Status", operator="follows_commands"),
        AssertionSpec(id="speed", signal="Speed", operator="reaches_near", target=1.5, tolerance_ref="speed_tol"),
        AssertionSpec(id="speed-alias", signal="Speed", operator="follows_target", target=1.5, tolerance_ref="speed_tol"),
        AssertionSpec(id="wheel", signals=["FL", "FR", "RL", "RR"], operator="consistent", tolerance_ref="wheel_tol"),
        AssertionSpec(id="wheel-alias", signals=["FL", "FR", "RL", "RR"], operator="wheel_consistent", tolerance_ref="wheel_tol"),
        AssertionSpec(id="steer", signal="SAS_Front_Angle", operator="follows_command", tolerance_ref="steer_tol"),
        AssertionSpec(id="steer-alias", signal="SAS_Front_Angle", operator="steering_follows", tolerance_ref="steer_tol"),
        AssertionSpec(id="light", signals=["Left_Turn_Light_Status"], operator="follows_commands_or_manual_review"),
        AssertionSpec(id="brake", signal="Brake_Status", operator="brake_confirmed"),
    ]
    outcomes = [await AssertionEvaluator().evaluate(spec, context) for spec in specs]
    assert [outcome.result for outcome in outcomes] == ["PASS"] * len(specs)
    assert len(outcomes[1].measured_value) == 2
    assert outcomes[5].measured_value[0]["sample_count"] == 2


@pytest.mark.asyncio
async def test_max_level_system_database_report_and_can_statistics_types():
    context = _context({"VCU_Max_Warning_Level": 0}, report={"id": "R1", "files": {"json": "a", "docx": "b"}})
    context.state.can = SimpleNamespace(
        status=lambda: [
            {"channel": "CAN1", "online": True, "queue_healthy": True},
            {"channel": "CAN2", "online": True, "queue_healthy": True},
        ]
    )
    specs = [
        AssertionSpec(id="warning", message="0x77", operator="max_level_equals", value=0, timeout_ms=0),
        AssertionSpec(id="db_writable", type="system", expected=True),
        AssertionSpec(id="database", type="database", expected=True),
        AssertionSpec(id="report", type="report", formats=["json", "docx"]),
        AssertionSpec(id="can", type="can_statistics", operator="no_critical_timeout"),
    ]
    outcomes = [await AssertionEvaluator().evaluate(spec, context) for spec in specs]
    assert [outcome.result for outcome in outcomes] == ["PASS"] * len(specs)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "stale", "invalid_quality", "wrong_channel"])
async def test_missing_stale_invalid_and_wrong_source_fail_with_invalid_quality(failure: str):
    context = _context({"SignalA": 5})
    item = context.state.signals.current.get("SignalA")
    if failure == "missing":
        context.state.signals.current.clear()
        context.state.signals.current_by_source.clear()
    elif failure == "stale":
        item["received_at_monotonic"] -= 2
    elif failure == "invalid_quality":
        item["quality"] = "invalid"
    else:
        context.state.signals.current_by_source.pop(("SignalA", "CAN1"))
        item["channel"] = "CAN2"
        context.state.signals.current_by_source[("SignalA", "CAN2")] = item
    outcome = await AssertionEvaluator().evaluate(
        AssertionSpec(id=failure, signal="SignalA", channel="CAN1", operator="==", value=5, timeout_ms=0, max_age_ms=50),
        context,
    )
    assert outcome.result == "FAIL"
    assert outcome.quality == "invalid"
    assert outcome.failure_reason


@pytest.mark.asyncio
async def test_non_finite_value_reversed_bounds_and_missing_threshold_are_invalid_failures():
    nan_outcome = await AssertionEvaluator().evaluate(
        AssertionSpec(id="nan", signal="SignalA", operator="==", value=5, timeout_ms=0),
        _context({"SignalA": float("nan")}),
    )
    bounds_outcome = await AssertionEvaluator().evaluate(
        AssertionSpec(id="bounds", signal="SignalA", operator="between", value=[10, 1], timeout_ms=0),
        _context({"SignalA": 5}),
    )
    threshold_outcome = await AssertionEvaluator().evaluate(
        AssertionSpec(id="threshold", signal="SignalA", operator=">=", threshold_ref="missing.path", timeout_ms=0),
        _context({"SignalA": 5}),
    )
    for outcome in (nan_outcome, bounds_outcome, threshold_outcome):
        assert outcome.result == "FAIL"
        assert outcome.quality == "invalid"
        assert outcome.failure_reason


def test_unsupported_operator_is_rejected_during_plan_validation():
    with pytest.raises(ValidationError):
        AssertionSpec(id="bad-op", signal="SignalA", operator="approximately")
