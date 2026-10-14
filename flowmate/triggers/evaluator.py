from __future__ import annotations

from datetime import datetime
from enum import Enum

from flowmate.schemas import TriggerDefinition, TriggerStatus
from flowmate.triggers.errors import TriggerEvaluationError


class TriggerEvaluationOutcome(str, Enum):
    NOT_DUE = "NOT_DUE"
    DUE = "DUE"
    EXPIRED = "EXPIRED"


class TriggerEvaluator:
    def evaluate(
        self,
        trigger: TriggerDefinition,
        *,
        now: datetime,
    ) -> TriggerEvaluationOutcome:
        if now.tzinfo is None:
            raise TriggerEvaluationError("Trigger evaluation clock must be timezone-aware.")
        if trigger.status != TriggerStatus.ACTIVE:
            return TriggerEvaluationOutcome.NOT_DUE
        normalized_now = now.astimezone(trigger.source_event_start.tzinfo)
        if normalized_now >= trigger.source_event_start:
            return TriggerEvaluationOutcome.EXPIRED
        if trigger.trigger_at <= normalized_now < trigger.source_event_start:
            return TriggerEvaluationOutcome.DUE
        return TriggerEvaluationOutcome.NOT_DUE
