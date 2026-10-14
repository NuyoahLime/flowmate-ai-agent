from __future__ import annotations

from hashlib import sha256

from flowmate.agent.dynamic_task_orchestrator import ObservationDrivenContinuationPlanner
from flowmate.schemas import RiskLevel, Task, TaskStatus, TriggerDefinition


class ProactiveTaskFactory:
    def __init__(
        self,
        continuation_planner: ObservationDrivenContinuationPlanner | None = None,
    ) -> None:
        self.continuation_planner = continuation_planner or ObservationDrivenContinuationPlanner()

    def create_task(self, trigger: TriggerDefinition) -> Task:
        user_input = self._synthetic_input(trigger)
        selected_event = {
            "title": trigger.source_event_summary or "Calendar Event",
            "start_time": trigger.source_event_start.isoformat(),
            "location": trigger.source_event_location,
        }
        steps = self.continuation_planner.build_continuation_steps(
            user_input=user_input,
            selected_event=selected_event,
            start_order=1,
        )
        return Task(
            id=self._task_id(trigger),
            user_input=user_input,
            goal="Prepare a departure plan for an upcoming calendar event.",
            status=TaskStatus.PLANNED,
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            steps=steps,
        )

    def _synthetic_input(self, trigger: TriggerDefinition) -> str:
        summary = trigger.source_event_summary or "Calendar Event"
        return (
            "Prepare a departure plan for the upcoming calendar event. "
            f"Event: {summary}. "
            f"Location: {trigger.source_event_location}. "
            f"Start: {trigger.source_event_start.isoformat()}. "
            "Check weather and route."
        )

    def _task_id(self, trigger: TriggerDefinition) -> str:
        digest = sha256(trigger.id.encode("utf-8")).hexdigest()[:12]
        return f"task-proactive-{digest}"
