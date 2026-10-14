from __future__ import annotations

from datetime import datetime
from typing import Protocol

from flowmate.schemas import Task, TriggerDefinition, TriggerStatus


class TriggerRepository(Protocol):
    def save(self, trigger: TriggerDefinition) -> None:
        ...

    def get(self, trigger_id: str) -> TriggerDefinition | None:
        ...

    def get_by_source_event_id(self, source_event_id: str) -> TriggerDefinition | None:
        ...

    def list_active(self) -> list[TriggerDefinition]:
        ...

    def list_due(self, *, now: datetime) -> list[TriggerDefinition]:
        ...

    def list_triggers(
        self,
        *,
        status: TriggerStatus | None = None,
        limit: int = 50,
    ) -> list[TriggerDefinition]:
        ...

    def mark_evaluated(self, trigger_id: str, *, evaluated_at: datetime) -> None:
        ...

    def mark_expired(self, trigger_id: str, *, expired_at: datetime) -> None:
        ...

    def fire_with_task(
        self,
        trigger: TriggerDefinition,
        task: Task,
        *,
        fired_at: datetime,
    ) -> None:
        ...
