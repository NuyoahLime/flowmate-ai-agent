import json
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel

from flowmate.agent import DynamicTaskOrchestrator, ToolExecutor
from flowmate.schemas import DynamicPlanningFailureType, DynamicPlanningPhase
from flowmate.tools import (
    CalendarTool,
    CalendarToolInput,
    CalendarToolResult,
    NavigationTool,
    NotificationTool,
    ToolRegistry,
    WeatherTool,
)


class DynamicNotificationEvalCase(BaseModel):
    id: str
    category: str
    user_input: str
    expected_notification: bool
    action: str = "none"
    expected_failure_type: DynamicPlanningFailureType | None = None


class DynamicNotificationEvalResult(BaseModel):
    case_id: str
    category: str
    expected_notification: bool
    notification_proposed: bool
    pre_confirmation_blocked: bool | None = None
    confirmed_success: bool | None = None
    rejected_contained: bool | None = None
    informational_reexecuted: bool | None = None
    notification_grounded: bool | None = None
    side_effect_minimality_correct: bool | None = None
    final_phase: DynamicPlanningPhase
    failure_type: DynamicPlanningFailureType | None = None
    calendar_executions: int
    weather_executions: int
    navigation_executions: int
    notification_executions: int


class DynamicNotificationEvalMetrics(BaseModel):
    cases: int
    side_effect_proposal_accuracy: float
    pre_confirmation_blocking_rate: float | None
    confirmed_side_effect_success_rate: float | None
    rejected_side_effect_containment_rate: float | None
    informational_reexecution_rate: float | None
    notification_grounding_accuracy: float | None
    side_effect_minimality_accuracy: float | None


class DynamicNotificationEvaluator:
    def evaluate_case(
        self,
        case: DynamicNotificationEvalCase,
    ) -> DynamicNotificationEvalResult:
        orchestrator, calendar, weather, navigation, notification = (
            self._create_orchestrator()
        )
        state = orchestrator.execute(case.user_input)
        proposed = state.notification_task is not None
        before_counts = (
            calendar.execution_count,
            weather.execution_count,
            navigation.execution_count,
        )

        pre_confirmation_blocked = None
        confirmed_success = None
        rejected_contained = None
        informational_reexecuted = None

        if case.expected_notification:
            pre_confirmation_blocked = (
                state.phase == DynamicPlanningPhase.WAITING_CONFIRMATION
                and notification.execution_count == 0
            )

        if case.action == "confirm" and proposed:
            state = orchestrator.confirm_side_effect(state)
            confirmed_success = (
                state.phase == DynamicPlanningPhase.COMPLETED
                and notification.execution_count == 1
            )
            informational_reexecuted = before_counts != (
                calendar.execution_count,
                weather.execution_count,
                navigation.execution_count,
            )
        elif case.action == "reject" and proposed:
            state = orchestrator.reject_side_effect(state)
            rejected_contained = (
                state.phase == DynamicPlanningPhase.CANCELLED
                and notification.execution_count == 0
            )
            informational_reexecuted = before_counts != (
                calendar.execution_count,
                weather.execution_count,
                navigation.execution_count,
            )

        notification_grounded = self._notification_grounded(state) if proposed else None
        side_effect_minimality_correct = None
        if not case.expected_notification:
            side_effect_minimality_correct = not proposed

        return DynamicNotificationEvalResult(
            case_id=case.id,
            category=case.category,
            expected_notification=case.expected_notification,
            notification_proposed=proposed,
            pre_confirmation_blocked=pre_confirmation_blocked,
            confirmed_success=confirmed_success,
            rejected_contained=rejected_contained,
            informational_reexecuted=informational_reexecuted,
            notification_grounded=notification_grounded,
            side_effect_minimality_correct=side_effect_minimality_correct,
            final_phase=state.phase,
            failure_type=state.failure_type,
            calendar_executions=calendar.execution_count,
            weather_executions=weather.execution_count,
            navigation_executions=navigation.execution_count,
            notification_executions=notification.execution_count,
        )

    def evaluate_dataset(
        self,
        cases: Iterable[DynamicNotificationEvalCase],
    ) -> tuple[list[DynamicNotificationEvalResult], DynamicNotificationEvalMetrics]:
        results = [self.evaluate_case(case) for case in cases]
        return results, self.calculate_metrics(results)

    def calculate_metrics(
        self,
        results: list[DynamicNotificationEvalResult],
    ) -> DynamicNotificationEvalMetrics:
        proposal_correct = [
            result.notification_proposed == result.expected_notification
            for result in results
        ]
        pre_confirmation_results = [
            result
            for result in results
            if result.pre_confirmation_blocked is not None
        ]
        confirmed_results = [
            result for result in results if result.confirmed_success is not None
        ]
        rejected_results = [
            result for result in results if result.rejected_contained is not None
        ]
        reexecution_results = [
            result for result in results if result.informational_reexecuted is not None
        ]
        grounding_results = [
            result for result in results if result.notification_grounded is not None
        ]
        minimality_results = [
            result
            for result in results
            if result.side_effect_minimality_correct is not None
        ]

        return DynamicNotificationEvalMetrics(
            cases=len(results),
            side_effect_proposal_accuracy=sum(proposal_correct) / len(proposal_correct),
            pre_confirmation_blocking_rate=self._optional_ratio(
                sum(result.pre_confirmation_blocked for result in pre_confirmation_results),
                len(pre_confirmation_results),
            ),
            confirmed_side_effect_success_rate=self._optional_ratio(
                sum(result.confirmed_success for result in confirmed_results),
                len(confirmed_results),
            ),
            rejected_side_effect_containment_rate=self._optional_ratio(
                sum(result.rejected_contained for result in rejected_results),
                len(rejected_results),
            ),
            informational_reexecution_rate=self._optional_ratio(
                sum(result.informational_reexecuted for result in reexecution_results),
                len(reexecution_results),
            ),
            notification_grounding_accuracy=self._optional_ratio(
                sum(result.notification_grounded for result in grounding_results),
                len(grounding_results),
            ),
            side_effect_minimality_accuracy=self._optional_ratio(
                sum(result.side_effect_minimality_correct for result in minimality_results),
                len(minimality_results),
            ),
        )

    def _notification_grounded(self, state) -> bool:
        if state.side_effect_proposal is None or state.selected_event is None:
            return False
        message = state.side_effect_proposal.arguments.get("message", "")
        event = state.selected_event
        return all(
            str(event[field]) in message
            for field in ("title", "start_time", "location")
        )

    def _optional_ratio(self, numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    def _create_orchestrator(self):
        calendar = _CountingCalendarTool()
        weather = _CountingWeatherTool()
        navigation = _CountingNavigationTool()
        notification = _CountingNotificationTool()
        registry = ToolRegistry()
        registry.register(weather)
        registry.register(navigation)
        registry.register(calendar)
        registry.register(notification)
        return (
            DynamicTaskOrchestrator(ToolExecutor(registry)),
            calendar,
            weather,
            navigation,
            notification,
        )


class _CountingCalendarTool(CalendarTool):
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, input_data: CalendarToolInput) -> CalendarToolResult:
        self.execution_count += 1
        return super().execute(input_data)


class _CountingWeatherTool(WeatherTool):
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, input_data):
        self.execution_count += 1
        return super().execute(input_data)


class _CountingNavigationTool(NavigationTool):
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, input_data):
        self.execution_count += 1
        return super().execute(input_data)


class _CountingNotificationTool(NotificationTool):
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, input_data):
        self.execution_count += 1
        return super().execute(input_data)


def load_dynamic_notification_dataset(
    path: str | Path,
) -> list[DynamicNotificationEvalCase]:
    with Path(path).open("r", encoding="utf-8") as file:
        raw_cases = json.load(file)
    return [DynamicNotificationEvalCase.model_validate(case) for case in raw_cases]
