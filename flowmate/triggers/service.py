from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from flowmate.schemas import TriggerDefinition
from flowmate.triggers.evaluator import TriggerEvaluationOutcome, TriggerEvaluator
from flowmate.triggers.repository import TriggerRepository
from flowmate.triggers.task_factory import ProactiveTaskFactory


class TriggerTickItemResult(BaseModel):
    trigger_id: str
    outcome: TriggerEvaluationOutcome | None = None
    generated_task_id: str | None = None
    error: str | None = None


class TriggerTickResult(BaseModel):
    evaluated_count: int
    generated_task_ids: list[str] = Field(default_factory=list)
    expired_trigger_ids: list[str] = Field(default_factory=list)
    errors: list[TriggerTickItemResult] = Field(default_factory=list)
    results: list[TriggerTickItemResult] = Field(default_factory=list)


class ProactiveTriggerService:
    def __init__(
        self,
        trigger_repository: TriggerRepository,
        *,
        evaluator: TriggerEvaluator | None = None,
        task_factory: ProactiveTaskFactory | None = None,
    ) -> None:
        self.trigger_repository = trigger_repository
        self.evaluator = evaluator or TriggerEvaluator()
        self.task_factory = task_factory or ProactiveTaskFactory()

    def tick(self, *, now: datetime) -> TriggerTickResult:
        if now.tzinfo is None:
            raise ValueError("Proactive trigger tick requires timezone-aware now.")

        active_triggers = sorted(
            self.trigger_repository.list_active(),
            key=lambda trigger: (trigger.trigger_at, trigger.id),
        )
        results: list[TriggerTickItemResult] = []
        generated_task_ids: list[str] = []
        expired_trigger_ids: list[str] = []
        errors: list[TriggerTickItemResult] = []

        for trigger in active_triggers:
            try:
                item = self._evaluate_one(trigger, now=now)
                results.append(item)
                if item.generated_task_id is not None:
                    generated_task_ids.append(item.generated_task_id)
                if item.outcome == TriggerEvaluationOutcome.EXPIRED:
                    expired_trigger_ids.append(trigger.id)
            except Exception as exc:
                item = TriggerTickItemResult(
                    trigger_id=trigger.id,
                    error=f"{exc.__class__.__name__}: {exc}",
                )
                errors.append(item)
                results.append(item)

        return TriggerTickResult(
            evaluated_count=len(active_triggers),
            generated_task_ids=generated_task_ids,
            expired_trigger_ids=expired_trigger_ids,
            errors=errors,
            results=results,
        )

    def _evaluate_one(
        self,
        trigger: TriggerDefinition,
        *,
        now: datetime,
    ) -> TriggerTickItemResult:
        outcome = self.evaluator.evaluate(trigger, now=now)
        if outcome == TriggerEvaluationOutcome.NOT_DUE:
            self.trigger_repository.mark_evaluated(trigger.id, evaluated_at=now)
            return TriggerTickItemResult(trigger_id=trigger.id, outcome=outcome)

        if outcome == TriggerEvaluationOutcome.EXPIRED:
            self.trigger_repository.mark_expired(trigger.id, expired_at=now)
            return TriggerTickItemResult(trigger_id=trigger.id, outcome=outcome)

        task = self.task_factory.create_task(trigger)
        self.trigger_repository.fire_with_task(trigger, task, fired_at=now)
        return TriggerTickItemResult(
            trigger_id=trigger.id,
            outcome=outcome,
            generated_task_id=task.id,
        )
