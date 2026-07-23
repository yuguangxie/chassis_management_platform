from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
import time
from typing import Any
import uuid
import hashlib

from app.control.control_121 import Control121Command
from app.control.intent_service import ControlIntentPersistenceError
from app.control.safety_interlock import InterlockBlocked, SafetyEvaluationContext
from app.core.time import utc_now
from app.core.paths import CONFIG_DIR
from app.core.release_metadata import load_release_metadata
from app.configuration.models import configuration_hash
from app.configuration.service import runtime_configuration
from app.eol.assertions import AssertionContext, AssertionEvaluator
from app.eol.models import (
    AssertionOutcome,
    ControlAction,
    CreateSessionRequest,
    FailurePolicy,
    TestPlanDocument,
    TestStepPlan,
)
from app.eol.plan_loader import load_test_plan, load_thresholds
from app.services.app_state import AppState
from app.security.auth import Principal, Role
from app.storage.uow import EolUnitOfWork, PersistenceFailure, StationBusyPersistence


LOGGER = logging.getLogger(__name__)
TERMINAL_STATES = {"PASSED", "FAILED", "ABORTED", "EMERGENCY_STOPPED"}


class SessionTerminated(Exception):
    pass


class SessionConflict(RuntimeError):
    pass


class ManualStepTimeout(RuntimeError):
    pass


@dataclass
class SessionRuntime:
    resume_event: asyncio.Event = field(default_factory=asyncio.Event)
    manual_event: asyncio.Event = field(default_factory=asyncio.Event)
    manual_result: dict[str, Any] | None = None
    terminal_requested: str | None = None
    terminal_reason: str = ""
    task: asyncio.Task[None] | None = None
    active_command: Control121Command | None = None
    active_period_ms: int = 20

    def __post_init__(self) -> None:
        self.resume_event.set()


class EolEngine:
    def __init__(
        self,
        state: AppState,
        *,
        plan: TestPlanDocument | None = None,
        thresholds: dict[str, Any] | None = None,
        evaluator: AssertionEvaluator | None = None,
        uow: EolUnitOfWork | None = None,
        step_delay_seconds: float | None = None,
    ) -> None:
        self.state = state
        self.plan = plan or load_test_plan()
        self.thresholds = thresholds or load_thresholds()
        self.evaluator = evaluator or AssertionEvaluator()
        self.uow = uow or getattr(state, "eol_uow", None)
        self.sessions: dict[str, dict[str, Any]] = {}
        self.runtimes: dict[str, SessionRuntime] = {}
        self.active_by_station: dict[str, str] = {}
        self.step_delay_seconds = step_delay_seconds
        self.recovered_sessions = self.uow.recover_incomplete_sessions() if self.uow else []

    @property
    def active_session_id(self) -> str | None:
        for session_id, session in self.sessions.items():
            if session.get("status") in {"RUNNING", "PAUSED", "WAITING_OPERATOR"}:
                return session_id
        return None

    def create_session(
        self,
        request: CreateSessionRequest,
        *,
        operator: str,
        operator_role: str,
        auth_session_id: str,
        station_id: str,
        trace_id: str = "",
    ) -> dict[str, Any]:
        if request.plan_id != self.plan.plan.id:
            raise ValueError(
                f"unknown test plan {request.plan_id!r}; loaded plan is {self.plan.plan.id!r}"
            )
        if request.vehicle_series.upper() != self.state.config.vehicle_series.upper():
            raise ValueError(
                f"vehicle series {request.vehicle_series!r} does not match active configuration"
            )
        if self.state.config.profile == "production" and request.mock_session:
            raise ValueError("production profile forbids mock EOL sessions")
        duplicate = None
        if self.state.database:
            duplicate = self.state.database.query_one(
                "SELECT id,status,created_at FROM test_sessions WHERE vin=? OR chassis_no=? OR serial_no=? "
                "ORDER BY created_at DESC LIMIT 1",
                (request.vin, request.chassis_no, request.serial_no),
            )
        if duplicate and request.duplicate_policy == "reject":
            raise ValueError(
                f"duplicate vehicle identity already exists in session {duplicate['id']}"
            )
        session_id = f"EOL-{uuid.uuid4().hex[:12].upper()}"
        dbc = self.state.dbc.status() if getattr(self.state, "dbc", None) else {}
        release = load_release_metadata()
        plan_path = CONFIG_DIR / "test_plan.yaml"
        plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest() if plan_path.is_file() else None
        try:
            config_digest = configuration_hash(runtime_configuration(self.state.config))
        except Exception:
            config_digest = None
        session = request.model_dump(exclude={"mock_session"}) | {
            "id": session_id,
            "operator": operator,
            "operator_role": operator_role,
            "auth_session_id": auth_session_id,
            "station_id": station_id,
            "status": "IDLE",
            "overall_result": None,
            "steps": [],
            "logs": [],
            "measurements": [],
            "created_at": utc_now(),
            "plan_name": self.plan.plan.name,
            "plan_version": self.plan.plan.version,
            "dbc_hash": dbc.get("hash"),
            "config_hash": config_digest,
            "config_version": getattr(self.state.config, "config_version", None),
            "software_version": release.software_version or self.state.config.software_version,
            "release_hash": release.manifest_sha256,
            "test_plan_hash": plan_hash,
            "duplicate_of_session_id": duplicate.get("id") if duplicate else None,
            "trace_id": trace_id,
        }
        if self.uow:
            self.uow.create_session(session, self.plan)
        self.sessions[session_id] = session
        self.runtimes[session_id] = SessionRuntime()
        return session

    async def start(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        runtime = self.runtimes.setdefault(session_id, SessionRuntime())
        if runtime.task and not runtime.task.done():
            return session
        if session["status"] in TERMINAL_STATES:
            raise RuntimeError("terminal EOL session cannot be restarted")
        active = self.active_by_station.get(session["station_id"])
        if active and active != session_id:
            other = self.sessions.get(active)
            if other and other.get("status") not in TERMINAL_STATES:
                raise SessionConflict(
                    f"station {session['station_id']} already has active session {active}"
                )
        self.state.safety.require_allowed(operation="eol")
        if getattr(self.state, "telemetry", None) and not self.state.telemetry.healthy:
            raise PersistenceFailure(self.state.telemetry.last_error or "telemetry recorder is unhealthy")
        runtime.terminal_requested = None
        runtime.terminal_reason = ""
        runtime.resume_event.set()
        session["status"] = "RUNNING"
        session["started_at"] = session.get("started_at") or utc_now()
        if self.uow:
            try:
                self.uow.claim_station_and_start(session)
            except StationBusyPersistence as exc:
                session["status"] = "IDLE"
                raise SessionConflict(str(exc)) from exc
        else:
            self._persist_session(session)
        self.active_by_station[session["station_id"]] = session_id
        runtime.task = asyncio.create_task(
            self._run(session, runtime), name=f"eol-session-{session_id}"
        )
        return session

    async def _run(self, session: dict[str, Any], runtime: SessionRuntime) -> None:
        failure_reason = ""
        failed_step: dict[str, Any] | None = None
        try:
            for step_plan in self.plan.steps:
                await self._checkpoint(session, runtime)
                if step_plan.requires_motion and self._severe_alarm_active():
                    step = await self._record_skipped_motion_step(session, step_plan)
                    await self._broadcast(
                        "test.step_update", {"session_id": session["id"], "step": step}
                    )
                    continue
                step = await self._execute_step(session, runtime, step_plan)
                await self._broadcast(
                    "test.step_update", {"session_id": session["id"], "step": step}
                )
                await self._broadcast("test.session_progress", self.session_snapshot(session["id"]))
                if step["result"] == "FAIL":
                    failed_step = step
                    failure_reason = step.get("failure_reason") or f"step {step['id']} failed"
                    if step_plan.failure_policy != FailurePolicy.CONTINUE:
                        break
            await self._checkpoint(session, runtime)
            if failed_step:
                await self._fail_session(session, failed_step, failure_reason)
            else:
                self._finish(session, "PASSED", "PASS", "")
                self._persist_session(session)
                await self._finalize_session_artifacts(session)
        except (SessionTerminated, asyncio.CancelledError):
            self._apply_requested_terminal(session, runtime)
        except InterlockBlocked as exc:
            failed_step = failed_step or (session.get("steps") or [None])[-1]
            reasons = ", ".join(item["label"] for item in exc.evaluation["reasons"])
            await self._fail_session(session, failed_step, f"安全联锁阻止 EOL: {reasons}")
        except PersistenceFailure as exc:
            failed_step = failed_step or (session.get("steps") or [None])[-1]
            self.state.db_writable = False
            await self._fail_session(session, failed_step, f"EOL persistence failure: {exc}")
        except Exception as exc:
            failed_step = failed_step or (session.get("steps") or [None])[-1]
            LOGGER.exception("EOL session %s failed", session["id"])
            await self._fail_session(session, failed_step, f"EOL engine error: {exc}")
        finally:
            await self.state.tx_scheduler.stop()
            if runtime.terminal_requested:
                self._apply_requested_terminal(session, runtime)
            self.active_by_station.pop(session["station_id"], None)
            try:
                self._persist_session(session)
            except PersistenceFailure:
                self.state.db_writable = False
            await self._broadcast("test.session_progress", self.session_snapshot(session["id"]))

    async def _execute_step(
        self,
        session: dict[str, Any],
        runtime: SessionRuntime,
        plan: TestStepPlan,
    ) -> dict[str, Any]:
        started_monotonic = time.monotonic()
        step: dict[str, Any] = {
            "id": plan.id,
            "order": plan.order,
            "name": plan.name,
            "description": plan.description,
            "status": "RUNNING",
            "result": None,
            "started_at": utc_now(),
            "assertions": [],
            "commands": [],
            "measurements": [],
        }
        session["steps"].append(step)
        session["current_step_id"] = plan.id
        session["current_step_name"] = plan.name
        if self.uow:
            step["db_id"] = self.uow.start_step(session["id"], step)
        else:
            step["db_id"] = -1
        self._append_log(session, step, "步骤开始", "", "", "RUNNING")
        await self._broadcast("test.step_update", {"session_id": session["id"], "step": step})

        observations: list[dict[str, Any]] = []
        outcomes: list[AssertionOutcome] = []
        try:
            async with asyncio.timeout(plan.timeout_ms / 1000):
                pre_context = AssertionContext(
                    self.state, self.thresholds, session, step, observations
                )
                for spec in plan.preconditions:
                    outcome = await self.evaluator.evaluate(spec, pre_context)
                    outcomes.append(outcome)
                    if outcome.result == "FAIL":
                        break
                if all(item.result == "PASS" for item in outcomes):
                    for action in plan.control_actions:
                        await self._checkpoint(session, runtime)
                        observations.append(
                            await self._execute_control_action(session, runtime, step, action, plan)
                        )
                    for action in plan.system_actions:
                        await self._checkpoint(session, runtime)
                        if action.type == "generate_report":
                            step["status"] = "DONE"
                            step["result"] = "PASS"
                            try:
                                await self._generate_report(
                                    session, intended_result="PASS", persist=False
                                )
                            finally:
                                step["status"] = "RUNNING"
                                step["result"] = None
                        elif action.type == "wait" and action.duration_ms:
                            await self._sleep_active(
                                session, runtime, action.duration_ms / 1000
                            )
                    if plan.manual_action:
                        await self._wait_for_manual_action(session, runtime, step, plan)
                    if plan.sample_window_ms:
                        await self._sleep_active(
                            session, runtime, self._duration(plan.sample_window_ms)
                        )
                    context = AssertionContext(
                        self.state, self.thresholds, session, step, observations
                    )
                    for spec in plan.assertions:
                        await self._checkpoint(session, runtime)
                        outcomes.append(await self.evaluator.evaluate(spec, context))
                await self.state.tx_scheduler.stop()
                for action in plan.cleanup_actions:
                    await self._execute_control_action(
                        session, runtime, step, action, plan, cleanup=True
                    )
        except TimeoutError:
            outcomes.append(
                AssertionOutcome(
                    assertion_id=f"{plan.id}_timeout",
                    description=f"{plan.name} 步骤超时",
                    operator="timeout",
                    threshold=plan.timeout_ms,
                    measured_value=round((time.monotonic() - started_monotonic) * 1000),
                    unit="ms",
                    result="FAIL",
                    severity="critical",
                    failure_reason=f"step timeout after {plan.timeout_ms} ms",
                    quality="invalid",
                )
            )
        except InterlockBlocked as exc:
            reasons = ", ".join(
                item["label"] for item in exc.evaluation.get("reasons", [])
            )
            outcomes.append(
                AssertionOutcome(
                    assertion_id=f"{plan.id}_interlock",
                    description=f"{plan.name} 安全联锁",
                    operator="interlock",
                    threshold="allowed",
                    measured_value=exc.evaluation,
                    result="FAIL",
                    severity="critical",
                    failure_reason=f"安全联锁阻止步骤: {reasons}",
                    quality="invalid",
                )
            )
        except ManualStepTimeout as exc:
            outcomes.append(
                AssertionOutcome(
                    assertion_id=f"{plan.id}_manual",
                    description=f"{plan.name} 人工步骤",
                    operator="operator_confirmation",
                    threshold="confirmed before timeout",
                    measured_value=None,
                    result="FAIL",
                    severity="failure",
                    failure_reason=str(exc),
                    quality="invalid",
                )
            )
        except (SessionTerminated, asyncio.CancelledError, PersistenceFailure):
            raise
        except Exception as exc:
            outcomes.append(
                AssertionOutcome(
                    assertion_id=f"{plan.id}_execution",
                    description=f"{plan.name} 执行异常",
                    operator="execution",
                    threshold="completed without error",
                    measured_value=None,
                    result="FAIL",
                    severity="critical",
                    failure_reason=str(exc),
                    quality="invalid",
                )
            )
        finally:
            await self.state.tx_scheduler.stop()

        failed = [item for item in outcomes if item.result == "FAIL"]
        for observation in observations:
            intent_id = observation.get("intent_id")
            if not intent_id or not self.state.control_intents:
                continue
            try:
                self.state.control_intents.mark(
                    intent_id,
                    "FAILED" if failed else "CONFIRMED",
                    error_code="EOL_ASSERTION_FAILED" if failed else None,
                )
            except ControlIntentPersistenceError as exc:
                await self.state.control_intents.compensate_after_send_failure(
                    intent_id, exc
                )
                raise PersistenceFailure(str(exc)) from exc
        step["status"] = "DONE"
        step["result"] = "FAIL" if failed else "PASS"
        step["ended_at"] = utc_now()
        step["duration_ms"] = round((time.monotonic() - started_monotonic) * 1000)
        step["failure_reason"] = "; ".join(item.failure_reason for item in failed)
        step["assertions"] = [item.model_dump() for item in outcomes]
        step["commands"] = [item.get("command", {}) for item in observations]
        step["measurements"] = self._measurements_from_outcomes(outcomes)
        session["measurements"] = step["measurements"]
        if self.uow:
            self.uow.complete_step(session["id"], step, outcomes)
        self._append_log(
            session,
            step,
            "步骤完成",
            self._command_summary(step),
            self._feedback_summary(step),
            step["result"],
        )
        return step

    async def _execute_control_action(
        self,
        session: dict[str, Any],
        runtime: SessionRuntime,
        step: dict[str, Any],
        action: ControlAction,
        plan: TestStepPlan,
        *,
        cleanup: bool = False,
    ) -> dict[str, Any]:
        command = self._command_from_action(action)
        runtime.active_command = command
        runtime.active_period_ms = action.period_ms
        operation = "eol_motion"
        context = SafetyEvaluationContext(
            actor=session["operator"],
            session_id=session["id"],
            vehicle_id=session["vin"],
        )
        evaluation = self.state.safety.require_allowed(
            command, operation=operation, context=context
        )
        principal = Principal(
            session["operator"],
            Role(session.get("operator_role", "operator")),
            session.get("auth_session_id", ""),
        )
        try:
            intent_id = self.state.control_intents.create_authorized(
                principal,
                operation="eol_control",
                target="CAN2:0x121",
                command=command.model_dump(),
                safety_evaluation=evaluation,
                trace_id="",
                vehicle_id=session["vin"],
                eol_session_id=session["id"],
            )
        except ControlIntentPersistenceError as exc:
            raise PersistenceFailure(str(exc)) from exc
        action_started = time.monotonic()
        try:
            await self.state.tx_scheduler.start(
                command, action.period_ms, operation=operation, context=context
            )
            self.state.control_intents.mark(intent_id, "SENT")
        except ControlIntentPersistenceError as exc:
            await self.state.control_intents.compensate_after_send_failure(intent_id, exc)
            raise PersistenceFailure(str(exc)) from exc
        except Exception as exc:
            try:
                self.state.control_intents.mark(
                    intent_id, "FAILED", error_code=type(exc).__name__
                )
            except ControlIntentPersistenceError:
                pass
            raise
        try:
            await self._sleep_active(
                session,
                runtime,
                self._duration(action.duration_ms),
                restart_command=command,
                period_ms=action.period_ms,
            )
            samples, windows = self._capture_action_samples(plan, action_started)
        finally:
            await self.state.tx_scheduler.stop()
            runtime.active_command = None
        observation = {
            "intent_id": intent_id,
            "cleanup": cleanup,
            "timestamp": utc_now(),
            "command": command.model_dump(),
            "samples": samples,
            "windows": windows,
        }
        self._append_log(
            session,
            step,
            "清理动作" if cleanup else "下发 0x121",
            json.dumps(command.model_dump(), ensure_ascii=False),
            json.dumps(
                {key: value.get("value") for key, value in samples.items()},
                ensure_ascii=False,
            ),
            "PASS",
        )
        return observation

    async def _sleep_active(
        self,
        session: dict[str, Any],
        runtime: SessionRuntime,
        seconds: float,
        *,
        restart_command: Control121Command | None = None,
        period_ms: int = 20,
    ) -> None:
        remaining = seconds
        while remaining > 0:
            await self._checkpoint(session, runtime)
            started = time.monotonic()
            await asyncio.sleep(min(0.05, remaining))
            if runtime.resume_event.is_set():
                remaining -= time.monotonic() - started
            else:
                await self.state.tx_scheduler.stop()
                await self._checkpoint(session, runtime)
                if restart_command:
                    self.state.safety.require_allowed(
                        restart_command, operation="eol_motion"
                    )
                    await self.state.tx_scheduler.start(
                        restart_command, period_ms, operation="eol_motion"
                    )

    async def _wait_for_manual_action(
        self,
        session: dict[str, Any],
        runtime: SessionRuntime,
        step: dict[str, Any],
        plan: TestStepPlan,
    ) -> None:
        manual = plan.manual_action
        assert manual is not None
        runtime.manual_result = None
        runtime.manual_event.clear()
        session["status"] = "WAITING_OPERATOR"
        session["manual_action"] = {
            "step_id": plan.id,
            "prompt": manual.prompt,
            "confirmation_label": manual.confirmation_label,
        }
        self._persist_session(session)
        await self._broadcast("test.session_progress", self.session_snapshot(session["id"]))
        deadline = time.monotonic() + manual.timeout_ms / 1000
        while not runtime.manual_event.is_set():
            await self._checkpoint(session, runtime)
            if time.monotonic() >= deadline:
                raise ManualStepTimeout(f"manual action timed out: {manual.prompt}")
            await asyncio.sleep(0.05)
        result = runtime.manual_result or {}
        if not result.get("approved"):
            raise ManualStepTimeout(result.get("note") or "manual action was rejected")
        if manual.require_note and not str(result.get("note", "")).strip():
            raise ManualStepTimeout("manual action requires an operator note")
        session["status"] = "RUNNING"
        session.pop("manual_action", None)
        self._append_log(
            session,
            step,
            "人工步骤确认",
            result.get("operator", ""),
            result.get("note", ""),
            "PASS",
        )
        self._persist_session(session)

    async def confirm_manual(
        self,
        session_id: str,
        *,
        approved: bool,
        note: str,
        operator: str,
    ) -> dict[str, Any]:
        session = self._session(session_id)
        runtime = self.runtimes[session_id]
        if session.get("status") != "WAITING_OPERATOR":
            raise RuntimeError("session is not waiting for an operator action")
        runtime.manual_result = {
            "approved": approved,
            "note": note,
            "operator": operator,
            "confirmed_at": utc_now(),
        }
        runtime.manual_event.set()
        return session

    async def generate_report(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        intended = "PASS" if session.get("overall_result") == "PASS" else "FAIL"
        report = await self._generate_report(session, intended_result=intended)
        self._persist_session(session)
        return report

    def attach_safe_stop_result(
        self, session_id: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        session = self._session(session_id)
        session["safe_stop_result"] = result
        self._persist_session(session)
        return session

    async def pause(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        runtime = self.runtimes[session_id]
        if session["status"] != "RUNNING":
            return session
        runtime.resume_event.clear()
        await self.state.tx_scheduler.stop()
        session["status"] = "PAUSED"
        self._persist_session(session)
        await self._broadcast("test.session_progress", self.session_snapshot(session_id))
        return session

    async def resume(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        runtime = self.runtimes[session_id]
        if session["status"] != "PAUSED" or runtime.terminal_requested:
            return session
        self.state.safety.require_allowed(operation="eol")
        session["status"] = "RUNNING"
        runtime.resume_event.set()
        self._persist_session(session)
        await self._broadcast("test.session_progress", self.session_snapshot(session_id))
        return session

    async def abort(self, session_id: str, reason: str = "operator abort") -> dict[str, Any]:
        return await self._request_terminal(session_id, "ABORTED", reason)

    async def emergency_stop(
        self, session_id: str, reason: str = "emergency stop"
    ) -> dict[str, Any]:
        return await self._request_terminal(session_id, "EMERGENCY_STOPPED", reason)

    async def _request_terminal(
        self, session_id: str, status: str, reason: str
    ) -> dict[str, Any]:
        session = self._session(session_id)
        runtime = self.runtimes[session_id]
        if session["status"] in TERMINAL_STATES:
            return session
        runtime.terminal_requested = status
        runtime.terminal_reason = reason
        runtime.resume_event.set()
        runtime.manual_event.set()
        await self.state.tx_scheduler.stop()
        task = runtime.task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._apply_requested_terminal(session, runtime)
        if self.uow:
            self.uow.abort_running_steps(session_id, status, reason)
        self._persist_session(session)
        await self._broadcast("test.session_progress", self.session_snapshot(session_id))
        return session

    async def shutdown(self) -> None:
        for runtime in self.runtimes.values():
            task = runtime.task
            if task and not task.done():
                runtime.terminal_requested = "ABORTED"
                runtime.terminal_reason = "service shutdown"
                runtime.resume_event.set()
                runtime.manual_event.set()
                task.cancel()
        pending = [runtime.task for runtime in self.runtimes.values() if runtime.task]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for session in self.sessions.values():
            if session.get("status") in {"RUNNING", "PAUSED", "WAITING_OPERATOR"}:
                session["status"] = "ABORTED"
                session["overall_result"] = "ABORTED"
                session["failure_reason"] = "service shutdown"
                session["ended_at"] = utc_now()
                try:
                    self._persist_session(session)
                except PersistenceFailure:
                    pass

    async def _fail_session(
        self,
        session: dict[str, Any],
        failed_step: dict[str, Any] | None,
        reason: str,
    ) -> None:
        if session.get("status") in {"ABORTED", "EMERGENCY_STOPPED"}:
            return
        stop_result: dict[str, Any] | None = None
        should_stop = True
        if failed_step:
            plan = next(
                (item for item in self.plan.steps if item.id == failed_step.get("id")), None
            )
            should_stop = bool(plan and plan.safe_stop_on_fail)
        if should_stop and getattr(self.state, "safe_stop", None):
            stop_result = await self.state.safe_stop.execute(
                emergency=False,
                principal=None,
                reason=f"EOL failure {session['id']}: {reason}",
            )
        session["safe_stop_result"] = stop_result
        self._finish(session, "FAILED", "FAIL", reason)
        try:
            self._persist_session(session)
        except PersistenceFailure:
            self.state.db_writable = False
        if self.plan.plan.generate_report_on_failure and getattr(self.state, "reports", None):
            try:
                await self._generate_report(session, intended_result="FAIL")
            except Exception as exc:
                session["report_error"] = str(exc)
        await self._finalize_session_artifacts(session)

    async def _generate_report(
        self,
        session: dict[str, Any],
        *,
        intended_result: str,
        persist: bool = True,
    ) -> dict[str, Any]:
        if not getattr(self.state, "reports", None):
            raise RuntimeError("report generator is unavailable")
        prior = session.get("overall_result")
        session["overall_result"] = intended_result
        metadata = {
            "software_version": session.get("software_version"),
            "release_hash": session.get("release_hash"),
            "dbc_hash": session.get("dbc_hash"),
            "config_hash": session.get("config_hash"),
            "config_version": session.get("config_version"),
            "config_profile": self.state.config.profile,
            "test_plan_id": self.plan.plan.id,
            "test_plan_version": self.plan.plan.version,
            "test_plan_hash": session.get("test_plan_hash"),
            "operator": session.get("operator"),
            "station_id": session.get("station_id"),
            "vehicle_series": session.get("vehicle_series"),
            "work_order_id": session.get("work_order_id"),
        }
        report = self.state.reports.generate(
            session, session["steps"], metadata=metadata
        )
        session["report"] = report
        if self.uow and persist:
            report["database_ids"] = self.uow.persist_report(session, report)
        if prior is None and session.get("status") == "RUNNING":
            session["overall_result"] = None
        return report

    async def _finalize_session_artifacts(self, session: dict[str, Any]) -> None:
        if getattr(self.state, "telemetry", None):
            await self.state.telemetry.drain(session["id"])
            if not self.state.telemetry.healthy:
                self.state.db_writable = False
                session["telemetry_error"] = self.state.telemetry.last_error
                if session.get("status") == "PASSED":
                    raise PersistenceFailure(
                        self.state.telemetry.last_error
                        or "telemetry persistence did not complete"
                    )
        if self.uow and getattr(self.state, "can", None):
            report = session.get("report") or {}
            if report and not report.get("database_ids"):
                report["database_ids"] = self.uow.persist_report(session, report)
            self.uow.persist_statistics(session["id"], self.state.can)
            self.uow.persist_current_alarms(
                session["id"],
                self.state.alarms.current() if self.state.alarms else [],
                session.get("current_step_id"),
            )
            self.uow.persist_system_action(
                session["id"],
                "eol_session_finalized",
                session.get("overall_result") or session.get("status", "UNKNOWN"),
                {
                    "status": session.get("status"),
                    "failure_reason": session.get("failure_reason", ""),
                    "report_id": (session.get("report") or {}).get("id"),
                    "safe_stop": session.get("safe_stop_result"),
                },
            )
            self._persist_session(session)

    async def _record_skipped_motion_step(
        self, session: dict[str, Any], plan: TestStepPlan
    ) -> dict[str, Any]:
        step = {
            "id": plan.id,
            "order": plan.order,
            "name": plan.name,
            "description": plan.description,
            "status": "DONE",
            "result": "SKIPPED",
            "started_at": utc_now(),
            "ended_at": utc_now(),
            "duration_ms": 0,
            "failure_reason": "active severe alarm: motion stimulus conservatively skipped",
            "assertions": [],
            "commands": [],
            "measurements": [],
        }
        session["steps"].append(step)
        if self.uow:
            step["db_id"] = self.uow.start_step(session["id"], step)
            self.uow.complete_step(session["id"], step, [])
        self._append_log(
            session,
            step,
            "运动步骤跳过",
            "",
            "严重告警存在，禁止运动刺激",
            "SKIPPED",
        )
        return step

    def _capture_action_samples(
        self, plan: TestStepPlan, since_monotonic: float
    ) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        names: set[str] = set()
        channels: dict[str, str | None] = {}
        for spec in [*plan.preconditions, *plan.assertions]:
            if spec.signal:
                names.add(spec.signal)
                channels[spec.signal] = spec.channel
            names.update(value for value in spec.signals if not value.startswith("0x"))
            for value in spec.signals:
                if not value.startswith("0x"):
                    channels[value] = spec.channel
        names.update(
            {
                "CCU_Shift_Level_Status",
                "CCU_Vehicle_Speed",
                "Brake_Status",
                "SAS_Front_Angle",
                "SAS_Rear_Angle",
            }
        )
        samples: dict[str, dict[str, Any]] = {}
        windows: dict[str, list[dict[str, Any]]] = {}
        for name in names:
            try:
                samples[name] = self.state.signals.require_sample(
                    name,
                    max_age_seconds=self.state.config.channel_online_timeout_seconds,
                    channel=channels.get(name) or "CAN1",
                )
            except (KeyError, ValueError):
                continue
            windows[name] = self.state.signals.window(
                name,
                since_monotonic=since_monotonic,
                channel=channels.get(name) or "CAN1",
            )
        return samples, windows

    @staticmethod
    def _command_from_action(action: ControlAction) -> Control121Command:
        return Control121Command(
            shift=action.shift,
            drive_mode=action.drive_mode,
            target_speed_kmh=action.target_speed_kmh,
            front_steering_cmd=action.front_steering_cmd,
            rear_steering_cmd=action.rear_steering_cmd,
            brake_enable=action.brake_enable,
            left_light=False if action.all_lights_off else action.left_light,
            right_light=False if action.all_lights_off else action.right_light,
            position_light=False if action.all_lights_off else action.position_light,
            low_beam=False if action.all_lights_off else action.low_beam,
            speed_mode=action.speed_mode,
        )

    def _severe_alarm_active(self) -> bool:
        return bool(self.state.alarms and self.state.alarms.max_level() >= 3)

    async def _checkpoint(self, session: dict[str, Any], runtime: SessionRuntime) -> None:
        if runtime.terminal_requested:
            raise SessionTerminated
        await runtime.resume_event.wait()
        if runtime.terminal_requested or session["status"] in TERMINAL_STATES:
            raise SessionTerminated
        if getattr(self.state, "telemetry", None) and not self.state.telemetry.healthy:
            raise PersistenceFailure(self.state.telemetry.last_error)

    def _finish(
        self, session: dict[str, Any], status: str, result: str, reason: str
    ) -> None:
        if session["status"] in {"ABORTED", "EMERGENCY_STOPPED"}:
            return
        session["status"] = status
        session["overall_result"] = result
        session["failure_reason"] = reason
        session["ended_at"] = utc_now()

    def _apply_requested_terminal(
        self, session: dict[str, Any], runtime: SessionRuntime
    ) -> None:
        if not runtime.terminal_requested:
            return
        session["status"] = runtime.terminal_requested
        session["overall_result"] = "ABORTED"
        session["failure_reason"] = runtime.terminal_reason
        session["ended_at"] = session.get("ended_at") or utc_now()
        for step in reversed(session.get("steps", [])):
            if step.get("status") == "RUNNING":
                step["status"] = runtime.terminal_requested
                step["result"] = "ABORTED"
                step["ended_at"] = utc_now()
                break

    def _persist_session(self, session: dict[str, Any]) -> None:
        if self.uow:
            self.uow.update_session(session)

    def _duration(self, milliseconds: int) -> float:
        seconds = milliseconds / 1000
        if self.step_delay_seconds is not None:
            return min(seconds, self.step_delay_seconds)
        return seconds

    def _session(self, session_id: str) -> dict[str, Any]:
        if session_id not in self.sessions:
            raise KeyError(session_id)
        return self.sessions[session_id]

    def _append_log(
        self,
        session: dict[str, Any],
        step: dict[str, Any],
        action: str,
        command: str,
        feedback: str,
        status: str,
    ) -> None:
        session["logs"].append(
            {
                "time": utc_now(),
                "step": f"{step['order']} {step['name']}",
                "action": action,
                "can_command": command,
                "feedback": feedback,
                "status": status,
            }
        )

    @staticmethod
    def _measurements_from_outcomes(
        outcomes: list[AssertionOutcome],
    ) -> list[dict[str, Any]]:
        return [
            {
                "name": item.description,
                "value": item.measured_value if item.measured_value is not None else "--",
                "unit": item.unit,
                "quality": item.quality,
                "source_can_id": item.source_can_id,
                "source_timestamp": item.source_timestamp,
            }
            for item in outcomes
        ]

    @staticmethod
    def _command_summary(step: dict[str, Any]) -> str:
        return json.dumps(step.get("commands", []), ensure_ascii=False, default=str)

    @staticmethod
    def _feedback_summary(step: dict[str, Any]) -> str:
        return json.dumps(step.get("measurements", []), ensure_ascii=False, default=str)

    def session_snapshot(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        return json.loads(json.dumps(session, ensure_ascii=False, default=str))

    async def _broadcast(self, topic: str, payload: dict[str, Any]) -> None:
        if getattr(self.state, "ws", None):
            await self.state.ws.broadcast(topic, payload)
