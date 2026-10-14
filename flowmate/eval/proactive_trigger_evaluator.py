from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo
import json

from pydantic import BaseModel

from flowmate.persistence import SQLiteTaskRepository
from flowmate.triggers import (
    CalendarTriggerRegistrationService,
    CalendarTriggerSourceEvent,
    ProactiveTriggerService,
    SQLiteTriggerRepository,
)


class ProactiveTriggerEvalCase(BaseModel):
    id: str
    category: str
    source_event_id: str
    summary: str
    start: str | None
    timezone: str = "Asia/Shanghai"
    location: str | None = None
    all_day: bool = False
    lead_time_minutes: int = 60
    now: str
    expected_registered: bool
    expected_generated_tasks: int
    expected_status: str | None = None
    duplicate_register: bool = False
    duplicate_tick: bool = False
    restart_tick: bool = False


class ProactiveTriggerEvalResult(BaseModel):
    case_id: str
    category: str
    registered_correct: bool
    due_detection_correct: bool
    expiration_correct: bool | None = None
    duplicate_registration_correct: bool | None = None
    duplicate_fire_correct: bool | None = None
    restart_idempotency_correct: bool | None = None
    task_creation_correct: bool
    side_effect_contained: bool
    error: str | None = None


class ProactiveTriggerEvalMetrics(BaseModel):
    cases: int
    registration_accuracy: float
    due_detection_accuracy: float
    expiration_accuracy: float | None
    duplicate_trigger_prevention: float | None
    duplicate_fire_prevention: float | None
    restart_idempotency: float | None
    task_creation_accuracy: float
    side_effect_containment: float


class ProactiveTriggerEvaluator:
    def evaluate_case(self, case: ProactiveTriggerEvalCase) -> ProactiveTriggerEvalResult:
        try:
            with TemporaryDirectory() as directory:
                db_path = Path(directory) / "proactive_trigger_eval.db"
                trigger_repository = SQLiteTriggerRepository(db_path)
                task_repository = SQLiteTaskRepository(db_path)
                registration = CalendarTriggerRegistrationService(
                    trigger_repository,
                    lead_time_minutes=case.lead_time_minutes,
                )
                event = self._source_event(case)
                now = self._parse_datetime(case.now, case.timezone)
                trigger = registration.register_event(event, now=now)
                if case.duplicate_register:
                    registration.register_event(event, now=now)

                service = ProactiveTriggerService(trigger_repository)
                tick_result = service.tick(now=now)
                if case.duplicate_tick:
                    service.tick(now=now)
                if case.restart_tick:
                    ProactiveTriggerService(SQLiteTriggerRepository(db_path)).tick(now=now)

                triggers = trigger_repository.list_triggers()
                generated_tasks = task_repository.list_tasks()
                registered_correct = (trigger is not None) == case.expected_registered
                task_creation_correct = len(generated_tasks) == case.expected_generated_tasks
                due_detection_correct = len(tick_result.generated_task_ids) == case.expected_generated_tasks
                expiration_correct = None
                if case.expected_status == "EXPIRED":
                    expiration_correct = bool(triggers) and triggers[0].status.value == "EXPIRED"
                duplicate_registration_correct = None
                if case.duplicate_register:
                    duplicate_registration_correct = len(triggers) == 1
                duplicate_fire_correct = None
                if case.duplicate_tick:
                    duplicate_fire_correct = len(generated_tasks) == case.expected_generated_tasks
                restart_idempotency_correct = None
                if case.restart_tick:
                    restart_idempotency_correct = len(generated_tasks) == case.expected_generated_tasks

                return ProactiveTriggerEvalResult(
                    case_id=case.id,
                    category=case.category,
                    registered_correct=registered_correct,
                    due_detection_correct=due_detection_correct,
                    expiration_correct=expiration_correct,
                    duplicate_registration_correct=duplicate_registration_correct,
                    duplicate_fire_correct=duplicate_fire_correct,
                    restart_idempotency_correct=restart_idempotency_correct,
                    task_creation_correct=task_creation_correct,
                    side_effect_contained=True,
                )
        except Exception as exc:
            return ProactiveTriggerEvalResult(
                case_id=case.id,
                category=case.category,
                registered_correct=False,
                due_detection_correct=False,
                task_creation_correct=False,
                side_effect_contained=True,
                error=f"{exc.__class__.__name__}: {exc}",
            )

    def evaluate_dataset(
        self,
        cases: list[ProactiveTriggerEvalCase],
    ) -> tuple[list[ProactiveTriggerEvalResult], ProactiveTriggerEvalMetrics]:
        results = [self.evaluate_case(case) for case in cases]
        return results, self.calculate_metrics(results)

    def calculate_metrics(
        self,
        results: list[ProactiveTriggerEvalResult],
    ) -> ProactiveTriggerEvalMetrics:
        return ProactiveTriggerEvalMetrics(
            cases=len(results),
            registration_accuracy=self._ratio(
                [result.registered_correct for result in results]
            ),
            due_detection_accuracy=self._ratio(
                [result.due_detection_correct for result in results]
            ),
            expiration_accuracy=self._optional_ratio(
                [result.expiration_correct for result in results]
            ),
            duplicate_trigger_prevention=self._optional_ratio(
                [result.duplicate_registration_correct for result in results]
            ),
            duplicate_fire_prevention=self._optional_ratio(
                [result.duplicate_fire_correct for result in results]
            ),
            restart_idempotency=self._optional_ratio(
                [result.restart_idempotency_correct for result in results]
            ),
            task_creation_accuracy=self._ratio(
                [result.task_creation_correct for result in results]
            ),
            side_effect_containment=self._ratio(
                [result.side_effect_contained for result in results]
            ),
        )

    def _source_event(self, case: ProactiveTriggerEvalCase) -> CalendarTriggerSourceEvent:
        return CalendarTriggerSourceEvent(
            id=case.source_event_id,
            summary=case.summary,
            start=self._parse_datetime(case.start, case.timezone) if case.start else None,
            location=case.location,
            all_day=case.all_day,
        )

    def _parse_datetime(self, value: str, timezone: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
        return parsed

    def _ratio(self, values: list[bool]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _optional_ratio(self, values: list[bool | None]) -> float | None:
        applicable = [value for value in values if value is not None]
        return sum(applicable) / len(applicable) if applicable else None


def load_proactive_trigger_eval_dataset(
    path: str | Path,
) -> list[ProactiveTriggerEvalCase]:
    with Path(path).open("r", encoding="utf-8") as file:
        raw_cases = json.load(file)
    return [ProactiveTriggerEvalCase.model_validate(case) for case in raw_cases]
