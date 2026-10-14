from __future__ import annotations

import json
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from flowmate.agent import RiskPolicy, TaskConfirmationService
from flowmate.cross_device import (
    CrossDeviceAuthorizationError,
    CrossDeviceConflictError,
    CrossDeviceValidationError,
    DeviceCapability,
    DeviceRegistryService,
    DeviceRouter,
    DeviceType,
    HandoffService,
    SQLiteCrossDeviceRepository,
    TaskDeviceStateService,
    seed_demo_devices,
)
from flowmate.cross_device.demo import build_cross_device_commute_task
from flowmate.persistence import TaskPersistenceService
from flowmate.schemas import PlanStep, RiskLevel, Task, TaskStatus, ToolCall


EVAL_NOW = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)


@dataclass
class EvalContext:
    db_path: Path
    repository: SQLiteCrossDeviceRepository
    registry: DeviceRegistryService
    states: TaskDeviceStateService
    task: Task


class CrossDeviceEvaluator:
    metric_categories = {
        "device_registration_accuracy": None,
        "routing_accuracy": {"routing_success", "routing_deterministic", "routing_reason", "offline_route", "missing_capability_route"},
        "capability_match_accuracy": {"routing_success", "routing_deterministic", "routing_reason", "missing_capability_route", "missing_capability_handoff"},
        "offline_device_rejection": {"offline_route", "offline_handoff"},
        "handoff_creation_accuracy": {"duplicate_handoff", "duplicate_after_restart", "accept_idempotency", "version_conflict", "reject", "restart_persistence"},
        "duplicate_handoff_prevention": {"duplicate_handoff", "duplicate_after_restart"},
        "handoff_acceptance_accuracy": {"accept_idempotency", "restart_persistence"},
        "wrong_user_isolation": {"wrong_user_handoff", "wrong_user_confirmation"},
        "restart_persistence": {"duplicate_after_restart", "restart_persistence"},
        "confirmation_consistency": {"wrong_user_confirmation", "confirmation_consistency"},
        "state_sync_accuracy": {"accept_idempotency", "reject", "restart_persistence"},
    }

    def evaluate(self, dataset_path: str | Path) -> dict:
        cases = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
        results = []
        with tempfile.TemporaryDirectory(prefix="flowmate-cross-device-eval-") as directory:
            root = Path(directory)
            for index, case in enumerate(cases):
                try:
                    passed = self._run_case(case["scenario"], root / f"case-{index}.db")
                    error = None
                except Exception as exc:  # evaluator records a deterministic failure
                    passed = False
                    error = f"{type(exc).__name__}: {exc}"
                results.append({**case, "passed": passed, "error": error})

        metrics = {"cases": len(results)}
        for metric, categories in self.metric_categories.items():
            relevant = results if categories is None else [
                result for result in results if result["scenario"] in categories
            ]
            metrics[metric] = (
                sum(1 for result in relevant if result["passed"]) / len(relevant)
                if relevant
                else None
            )
        return {"metrics": metrics, "results": results}

    def _prepare(self, db_path: Path) -> EvalContext:
        repository = SQLiteCrossDeviceRepository(db_path)
        seed_demo_devices(repository, now=EVAL_NOW)
        registry = DeviceRegistryService(repository)
        registry.update_presence("phone_001", now=EVAL_NOW)
        registry.update_presence("car_001", now=EVAL_NOW)
        task = build_cross_device_commute_task(f"eval-{db_path.stem}")
        TaskPersistenceService(db_path=db_path).persist(task)
        states = TaskDeviceStateService(repository, db_path=db_path)
        states.initialize(
            task_id=task.id,
            owner_user_id="demo_user",
            origin_device_id="phone_001",
            now=EVAL_NOW,
        )
        return EvalContext(db_path, repository, registry, states, task)

    def _pending(self, context: EvalContext):
        state = context.states.get(context.task.id)
        service = HandoffService(context.repository, db_path=context.db_path)
        handoff = service.create_handoff(
            task_id=context.task.id,
            user_id="demo_user",
            source_device_id="phone_001",
            target_device_id="car_001",
            required_capability=DeviceCapability.NAVIGATION,
            expected_version=state.version,
            now=EVAL_NOW + timedelta(seconds=1),
        )
        return service, handoff, context.states.get(context.task.id)

    def _run_case(self, scenario: str, db_path: Path) -> bool:
        context = self._prepare(db_path)
        router = DeviceRouter(context.repository, db_path=db_path)
        if scenario in {"routing_success", "routing_reason", "routing_deterministic"}:
            first = router.recommend(context.task.id, now=EVAL_NOW)
            second = router.recommend(context.task.id, now=EVAL_NOW)
            return (
                first.recommended_device == "car_001"
                and first.available
                and "NAVIGATION" in first.reason
                and (scenario != "routing_deterministic" or first == second)
            )
        if scenario == "offline_route":
            context.registry.mark_offline("car_001")
            decision = router.recommend(context.task.id, now=EVAL_NOW)
            return decision.recommended_device == "phone_001" and not decision.available
        if scenario == "offline_handoff":
            context.registry.mark_offline("car_001")
            return self._raises_create(context, CrossDeviceConflictError)
        if scenario == "missing_capability_route":
            self._disable_navigation(context)
            return not router.recommend(context.task.id, now=EVAL_NOW).available
        if scenario == "missing_capability_handoff":
            self._disable_navigation(context)
            return self._raises_create(context, CrossDeviceValidationError)
        if scenario in {"duplicate_handoff", "duplicate_after_restart"}:
            _, _, state = self._pending(context)
            repository = (
                SQLiteCrossDeviceRepository(db_path)
                if scenario == "duplicate_after_restart"
                else context.repository
            )
            service = HandoffService(repository, db_path=db_path)
            try:
                service.create_handoff(
                    task_id=context.task.id,
                    user_id="demo_user",
                    source_device_id="phone_001",
                    target_device_id="car_001",
                    required_capability=DeviceCapability.NAVIGATION,
                    expected_version=state.version,
                    now=EVAL_NOW + timedelta(seconds=2),
                )
            except CrossDeviceConflictError:
                return len(repository.list_handoffs(task_id=context.task.id)) == 1
            return False
        if scenario == "accept_idempotency":
            service, handoff, state = self._pending(context)
            _, accepted_state, changed = service.accept_handoff(
                handoff.id,
                target_device_id="car_001",
                expected_version=state.version,
                now=EVAL_NOW + timedelta(seconds=2),
            )
            _, duplicate_state, duplicate_changed = service.accept_handoff(
                handoff.id,
                target_device_id="car_001",
                expected_version=state.version,
                now=EVAL_NOW + timedelta(seconds=3),
            )
            return changed and not duplicate_changed and duplicate_state == accepted_state
        if scenario == "version_conflict":
            return self._raises_create(context, CrossDeviceConflictError, expected_version=99)
        if scenario == "wrong_user_handoff":
            self._add_other_user(context)
            try:
                HandoffService(context.repository, db_path=db_path).create_handoff(
                    task_id=context.task.id,
                    user_id="demo_user",
                    source_device_id="phone_001",
                    target_device_id="car_002",
                    required_capability=DeviceCapability.NAVIGATION,
                    expected_version=1,
                    now=EVAL_NOW,
                )
            except CrossDeviceAuthorizationError:
                return True
            return False
        if scenario == "wrong_user_confirmation":
            self._add_other_user(context)
            task, state = self._pending_confirmation(context, "wrong-user-confirm")
            try:
                context.states.claim_confirmation(
                    task_id=task.id,
                    device_id="car_002",
                    expected_version=state.version,
                    confirmed=True,
                    now=EVAL_NOW,
                )
            except CrossDeviceAuthorizationError:
                return True
            return False
        if scenario == "reject":
            service, handoff, state = self._pending(context)
            rejected, final_state = service.reject_handoff(
                handoff.id,
                target_device_id="car_001",
                expected_version=state.version,
                now=EVAL_NOW + timedelta(seconds=2),
            )
            return rejected.status.value == "REJECTED" and final_state.current_device_id == "phone_001"
        if scenario == "restart_persistence":
            service, handoff, state = self._pending(context)
            service.accept_handoff(
                handoff.id,
                target_device_id="car_001",
                expected_version=state.version,
                now=EVAL_NOW + timedelta(seconds=2),
            )
            reopened = SQLiteCrossDeviceRepository(db_path)
            return (
                reopened.get_handoff(handoff.id).status.value == "ACCEPTED"
                and reopened.get_task_device_state(context.task.id).current_device_id == "car_001"
            )
        if scenario == "confirmation_consistency":
            task, state = self._pending_confirmation(context, "confirmation-consistency")
            context.states.claim_confirmation(
                task_id=task.id,
                device_id="phone_001",
                expected_version=state.version,
                confirmed=True,
                now=EVAL_NOW,
            )
            try:
                context.states.claim_confirmation(
                    task_id=task.id,
                    device_id="car_001",
                    expected_version=state.version,
                    confirmed=True,
                    now=EVAL_NOW,
                )
            except CrossDeviceConflictError:
                return True
            return False
        raise ValueError(f"Unknown cross-device eval scenario: {scenario}")

    def _raises_create(
        self,
        context: EvalContext,
        error_type,
        *,
        expected_version: int = 1,
    ) -> bool:
        try:
            HandoffService(context.repository, db_path=context.db_path).create_handoff(
                task_id=context.task.id,
                user_id="demo_user",
                source_device_id="phone_001",
                target_device_id="car_001",
                required_capability=DeviceCapability.NAVIGATION,
                expected_version=expected_version,
                now=EVAL_NOW,
            )
        except error_type:
            return True
        return False

    @staticmethod
    def _disable_navigation(context: EvalContext) -> None:
        with closing(sqlite3.connect(context.db_path)) as connection:
            with connection:
                connection.execute(
                    "UPDATE device_capabilities SET enabled = 0 WHERE device_id = ? AND capability = ?",
                    ("car_001", DeviceCapability.NAVIGATION.value),
                )

    @staticmethod
    def _add_other_user(context: EvalContext) -> None:
        context.registry.register_user("demo_user_2", "Other User", now=EVAL_NOW)
        context.registry.register_device(
            device_id="car_002",
            user_id="demo_user_2",
            device_type=DeviceType.CAR,
            display_name="Other Car",
            capabilities=[DeviceCapability.NAVIGATION],
            now=EVAL_NOW,
        )
        context.registry.update_presence("car_002", now=EVAL_NOW)

    @staticmethod
    def _pending_confirmation(context: EvalContext, task_id: str):
        task = Task(
            id=task_id,
            user_input="解锁我的车",
            goal="Mock vehicle unlock",
            status=TaskStatus.PLANNED,
            risk_level=RiskLevel.LOW,
            steps=[
                PlanStep(
                    id=f"{task_id}-step",
                    order=1,
                    description="Unlock mock vehicle.",
                    tool_name="vehicle_tool",
                    tool_call=ToolCall(
                        tool_name="vehicle_tool",
                        arguments={"vehicle_id": "my-car", "action": "unlock"},
                    ),
                )
            ],
        )
        RiskPolicy().apply_to_task(task)
        TaskConfirmationService().request_confirmation(task)
        TaskPersistenceService(db_path=context.db_path).persist(task)
        state = context.states.initialize(
            task_id=task.id,
            owner_user_id="demo_user",
            origin_device_id="phone_001",
            now=EVAL_NOW,
        )
        return task, state
