from typing import Any

from flowmate.agent import DynamicTaskOrchestrator, NotificationFormatter, ToolExecutor
from flowmate.schemas import DynamicPlanningFailureType, DynamicPlanningPhase, TaskStatus
from flowmate.tools import (
    CalendarTool,
    CalendarToolInput,
    CalendarToolResult,
    NavigationTool,
    NotificationTool,
    ToolRegistry,
    WeatherTool,
)


class CountingCalendarTool(CalendarTool):
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, input_data: CalendarToolInput) -> CalendarToolResult:
        self.execution_count += 1
        return super().execute(input_data)


class CountingWeatherTool(WeatherTool):
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, input_data):
        self.execution_count += 1
        return super().execute(input_data)


class CountingNavigationTool(NavigationTool):
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, input_data):
        self.execution_count += 1
        return super().execute(input_data)


class CountingNotificationTool(NotificationTool):
    def __init__(self, should_fail: bool = False) -> None:
        self.execution_count = 0
        self.should_fail = should_fail

    def execute(self, input_data):
        self.execution_count += 1
        if self.should_fail:
            raise RuntimeError("notification unavailable")
        return super().execute(input_data)


def create_orchestrator(notification_should_fail: bool = False):
    calendar = CountingCalendarTool()
    weather = CountingWeatherTool()
    navigation = CountingNavigationTool()
    notification = CountingNotificationTool(should_fail=notification_should_fail)
    registry = ToolRegistry()
    registry.register(weather)
    registry.register(navigation)
    registry.register(calendar)
    registry.register(notification)
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(registry))
    return orchestrator, calendar, weather, navigation, notification


def test_dynamic_notification_waits_for_confirmation_before_execution():
    orchestrator, calendar, weather, navigation, notification = create_orchestrator()

    state = orchestrator.execute(
        "help me plan tomorrow morning departure and notify me when ready"
    )

    assert state.phase == DynamicPlanningPhase.WAITING_CONFIRMATION
    assert state.notification_task is not None
    assert state.notification_task.risk_level == "MEDIUM"
    assert state.notification_task.requires_confirmation is True
    assert state.notification_task.status == TaskStatus.WAITING_CONFIRMATION
    assert [step.tool_name for step in state.task.steps[1:]] == ["navigation_tool"]
    assert notification.execution_count == 0
    assert calendar.execution_count == 1
    assert weather.execution_count == 0
    assert navigation.execution_count == 1


def test_confirm_executes_notification_once_without_reexecuting_information_tools():
    orchestrator, calendar, weather, navigation, notification = create_orchestrator()
    state = orchestrator.execute(
        "help me plan tomorrow morning departure and notify me when ready"
    )

    confirmed = orchestrator.confirm_side_effect(state)

    assert confirmed.phase == DynamicPlanningPhase.COMPLETED
    assert confirmed.notification_result["status"] == "mock_delivered"
    assert notification.execution_count == 1
    assert calendar.execution_count == 1
    assert weather.execution_count == 0
    assert navigation.execution_count == 1


def test_reject_never_executes_notification_and_preserves_information_results():
    orchestrator, calendar, weather, navigation, notification = create_orchestrator()
    state = orchestrator.execute(
        "help me plan tomorrow morning departure and notify me when ready"
    )

    rejected = orchestrator.reject_side_effect(state)

    assert rejected.phase == DynamicPlanningPhase.CANCELLED
    assert rejected.side_effect_status == "rejected"
    assert rejected.final_result.navigation_result is not None
    assert notification.execution_count == 0
    assert calendar.execution_count == 1
    assert weather.execution_count == 0
    assert navigation.execution_count == 1


def test_weather_navigation_notification_flow_executes_information_first():
    orchestrator, calendar, weather, navigation, notification = create_orchestrator()

    state = orchestrator.execute(
        "help me plan tomorrow morning departure, check weather, and notify me when ready"
    )
    confirmed = orchestrator.confirm_side_effect(state)

    assert confirmed.phase == DynamicPlanningPhase.COMPLETED
    assert calendar.execution_count == 1
    assert weather.execution_count == 1
    assert navigation.execution_count == 1
    assert notification.execution_count == 1


def test_dynamic_without_notification_does_not_enter_confirmation():
    orchestrator, _, _, _, notification = create_orchestrator()

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.COMPLETED
    assert state.notification_task is None
    assert state.side_effect_proposal is None
    assert notification.execution_count == 0


def test_scheduled_dynamic_notification_is_unsupported():
    orchestrator, calendar, weather, navigation, notification = create_orchestrator()

    state = orchestrator.execute(
        "help me plan tomorrow morning route and notify me at 7 tomorrow"
    )

    assert state.phase == DynamicPlanningPhase.FAILED
    assert (
        state.failure_type
        == DynamicPlanningFailureType.UNSUPPORTED_SCHEDULED_NOTIFICATION
    )
    assert calendar.execution_count == 0
    assert weather.execution_count == 0
    assert navigation.execution_count == 0
    assert notification.execution_count == 0


def test_conditional_dynamic_notification_is_unsupported():
    orchestrator, _, _, _, notification = create_orchestrator()

    state = orchestrator.execute(
        "help me plan tomorrow morning departure and if it rains notify me"
    )

    assert state.phase == DynamicPlanningPhase.FAILED
    assert (
        state.failure_type
        == DynamicPlanningFailureType.UNSUPPORTED_CONDITIONAL_NOTIFICATION
    )
    assert notification.execution_count == 0


def test_notification_formatter_is_deterministic_and_grounded():
    orchestrator, _, _, _, _ = create_orchestrator()
    state = orchestrator.execute(
        "help me plan tomorrow morning departure, check weather, and notify me when ready"
    )
    formatter = NotificationFormatter()

    first = formatter.build_proposal(state)
    second = formatter.build_proposal(state)

    assert first == second
    message = first.arguments["message"]
    assert "Product Weekly Meeting" in message
    assert "08:30" in message
    assert "company" in message
    assert "rain" in message
    assert "42 minutes" in message


def test_notification_failure_preserves_information_results():
    orchestrator, calendar, weather, navigation, notification = create_orchestrator(
        notification_should_fail=True
    )
    state = orchestrator.execute(
        "help me plan tomorrow morning departure and notify me when ready"
    )

    failed = orchestrator.confirm_side_effect(state)

    assert failed.phase == DynamicPlanningPhase.FAILED
    assert failed.failure_type == DynamicPlanningFailureType.SIDE_EFFECT_EXECUTION_ERROR
    assert failed.final_result.navigation_result is not None
    assert notification.execution_count == 1
    assert calendar.execution_count == 1
    assert weather.execution_count == 0
    assert navigation.execution_count == 1


def test_confirmation_does_not_increase_planning_iteration_count():
    orchestrator, _, _, _, _ = create_orchestrator()
    state = orchestrator.execute(
        "help me plan tomorrow morning departure and notify me when ready"
    )

    confirmed = orchestrator.confirm_side_effect(state)

    assert confirmed.iteration_count == 2
