from typing import Any

import pytest

from flowmate.agent import (
    DynamicTaskOrchestrator,
    ObservationDrivenContinuationPlanner,
    ToolExecutor,
)
from flowmate.schemas import (
    DynamicPlanningFailureType,
    DynamicPlanningPhase,
    DynamicPlanningState,
    PlanStep,
    TaskStatus,
    ToolCall,
    ToolCallStatus,
    ToolObservation,
)
from flowmate.tools import (
    BaseTool,
    CalendarToolInput,
    CalendarToolResult,
    NavigationTool,
    ToolRegistry,
    WeatherTool,
    create_default_registry,
)


class FixtureCalendarTool(BaseTool[CalendarToolInput, CalendarToolResult]):
    name = "calendar_tool"
    description = "Test calendar fixture."
    input_schema = CalendarToolInput

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.call_count = 0

    def execute(self, input_data: CalendarToolInput) -> CalendarToolResult:
        self.call_count += 1
        payload = {"date": input_data.date, **self.result}
        return CalendarToolResult.model_validate(payload)


class CountingWeatherTool(WeatherTool):
    def __init__(self, execution_log: list[str] | None = None) -> None:
        self.call_count = 0
        self.execution_log = execution_log

    def execute(self, input_data):
        self.call_count += 1
        if self.execution_log is not None:
            self.execution_log.append(self.name)
        return super().execute(input_data)


class CountingNavigationTool(NavigationTool):
    def __init__(self, execution_log: list[str] | None = None) -> None:
        self.call_count = 0
        self.execution_log = execution_log

    def execute(self, input_data):
        self.call_count += 1
        if self.execution_log is not None:
            self.execution_log.append(self.name)
        return super().execute(input_data)


class FailingWeatherTool(CountingWeatherTool):
    def execute(self, input_data):
        self.call_count += 1
        if self.execution_log is not None:
            self.execution_log.append(self.name)
        raise RuntimeError("weather unavailable")


class FailingNavigationTool(CountingNavigationTool):
    def execute(self, input_data):
        self.call_count += 1
        if self.execution_log is not None:
            self.execution_log.append(self.name)
        raise RuntimeError("navigation unavailable")


def create_orchestrator_with_calendar(
    result: dict[str, Any],
) -> tuple[DynamicTaskOrchestrator, FixtureCalendarTool, CountingWeatherTool, CountingNavigationTool]:
    calendar = FixtureCalendarTool(result)
    weather = CountingWeatherTool()
    navigation = CountingNavigationTool()
    registry = ToolRegistry()
    registry.register(weather)
    registry.register(navigation)
    registry.register(calendar)
    return DynamicTaskOrchestrator(ToolExecutor(registry)), calendar, weather, navigation


def create_orchestrator_with_custom_tools(
    *,
    calendar_result: dict[str, Any],
    weather: WeatherTool | None = None,
    navigation: NavigationTool | None = None,
    continuation_planner: ObservationDrivenContinuationPlanner | None = None,
) -> DynamicTaskOrchestrator:
    registry = ToolRegistry()
    registry.register(weather or CountingWeatherTool())
    registry.register(navigation or CountingNavigationTool())
    registry.register(FixtureCalendarTool(calendar_result))
    return DynamicTaskOrchestrator(
        ToolExecutor(registry),
        continuation_planner=continuation_planner,
    )


class BadGroundingPlanner(ObservationDrivenContinuationPlanner):
    def build_continuation_steps(self, *, user_input, selected_event, start_order):
        return [
            PlanStep(
                id="step-bad-navigation",
                order=start_order,
                description="Bad navigation",
                tool_name="navigation_tool",
                tool_call=ToolCall(
                    tool_name="navigation_tool",
                    arguments={
                        "origin": "home",
                        "destination": "office",
                        "departure_time": "tomorrow morning",
                    },
                ),
            )
        ]


class InvalidNavigationArgumentsPlanner(ObservationDrivenContinuationPlanner):
    def build_continuation_steps(self, *, user_input, selected_event, start_order):
        return [
            PlanStep(
                id="step-invalid-navigation",
                order=start_order,
                description="Invalid navigation",
                tool_name="navigation_tool",
                tool_call=ToolCall(
                    tool_name="navigation_tool",
                    arguments={"origin": "home", "destination": selected_event["location"]},
                ),
            )
        ]


class ReverseOrderedContinuationPlanner(ObservationDrivenContinuationPlanner):
    def build_continuation_steps(self, *, user_input, selected_event, start_order):
        return [
            PlanStep(
                id="step-navigation",
                order=3,
                description="Navigation",
                tool_name="navigation_tool",
                tool_call=ToolCall(
                    tool_name="navigation_tool",
                    arguments={
                        "origin": "home",
                        "destination": selected_event["location"],
                        "departure_time": "tomorrow morning",
                    },
                ),
            ),
            PlanStep(
                id="step-weather",
                order=2,
                description="Weather",
                tool_name="weather_tool",
                tool_call=ToolCall(
                    tool_name="weather_tool",
                    arguments={"location": "current_city", "date": "tomorrow"},
                ),
            ),
        ]


def test_dynamic_planning_state_creation_is_valid():
    state = DynamicPlanningState(user_input="plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.INITIAL_PLANNING
    assert state.iteration_count == 0
    assert state.max_iterations == 2
    assert state.observations == []


def test_tool_observation_schema_supports_success_and_error():
    success = ToolObservation(
        tool_name="calendar_tool",
        step_id="step-1",
        result={"event_count": 1},
    )
    failure = ToolObservation(
        tool_name="calendar_tool",
        result={},
        error="calendar failed",
    )

    assert success.result["event_count"] == 1
    assert failure.error == "calendar failed"


def test_weather_query_does_not_enter_dynamic_path():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    assert orchestrator.is_dynamic_request("will it rain tomorrow?") is False


def test_static_calendar_read_does_not_enter_dynamic_path():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    assert orchestrator.is_dynamic_request("check my calendar tomorrow afternoon") is False


def test_calendar_to_navigation_initially_generates_only_calendar_tool():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.task is not None
    assert state.task.steps[0].tool_name == "calendar_tool"
    assert state.task.steps[0].tool_call.arguments == {
        "date": "tomorrow",
        "start_time": "06:00",
        "end_time": "12:00",
    }


def test_initial_planning_does_not_guess_navigation_arguments_before_observation():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    state = orchestrator.execute("help me plan tomorrow morning departure")

    calendar_step = state.task.steps[0]
    assert calendar_step.tool_name == "calendar_tool"
    assert "destination" not in calendar_step.tool_call.arguments
    assert "departure_time" not in calendar_step.tool_call.arguments


def test_calendar_tool_mock_execution_produces_observation():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.observations
    assert state.observations[0].tool_name == "calendar_tool"
    assert state.observations[0].result["event_count"] == 1
    assert state.observations[0].result["events"][0]["title"] == "Product Weekly Meeting"
    assert state.task.steps[0].status == ToolCallStatus.SUCCESS


def test_earliest_event_is_selected_deterministically():
    result = {
        "events": [
            {
                "id": "event-2",
                "title": "Later Meeting",
                "start_time": "10:30",
                "end_time": "11:00",
                "location": "company",
            },
            {
                "id": "event-1",
                "title": "Earlier Meeting",
                "start_time": "08:15",
                "end_time": "09:00",
                "location": "client_site",
            },
        ],
        "event_count": 2,
    }
    orchestrator, _, _, _ = create_orchestrator_with_calendar(result)

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.selected_event["id"] == "event-1"


def test_selected_event_location_enters_navigation_destination():
    result = {
        "events": [
            {
                "id": "event-1",
                "title": "Client Meeting",
                "start_time": "08:30",
                "end_time": "09:30",
                "location": "client_site",
            }
        ],
        "event_count": 1,
    }
    orchestrator, _, _, _ = create_orchestrator_with_calendar(result)

    state = orchestrator.execute("help me plan tomorrow morning departure")
    navigation_step = state.task.steps[1]

    assert navigation_step.tool_name == "navigation_tool"
    assert navigation_step.tool_call.arguments["destination"] == "client_site"
    assert navigation_step.tool_call.status == ToolCallStatus.SUCCESS
    assert navigation_step.tool_call.result["destination"] == "client_site"


def test_selected_event_time_is_not_faked_as_departure_time():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    state = orchestrator.execute("help me plan tomorrow morning departure")
    navigation_step = state.task.steps[1]

    assert state.selected_event["start_time"] == "08:30"
    assert navigation_step.tool_call.arguments["departure_time"] == "tomorrow morning"


def test_calendar_to_navigation_continuation_generates_only_navigation_tool():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert [step.tool_name for step in state.task.steps] == [
        "calendar_tool",
        "navigation_tool",
    ]
    assert state.task.steps[1].tool_call.status == ToolCallStatus.SUCCESS
    assert state.final_result.navigation_result["destination"] == "company"


def test_registry_install_does_not_dynamically_authorize_smart_home_tool():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    state = orchestrator.execute("turn off living-room-light")

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.UNSUPPORTED_DYNAMIC_GOAL
    assert state.task is None
    assert state.side_effect_proposal is None
    assert state.notification_task is None


def test_registry_install_does_not_dynamically_authorize_vehicle_tool():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    state = orchestrator.execute("unlock my-car")

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.UNSUPPORTED_DYNAMIC_GOAL
    assert state.task is None
    assert state.side_effect_proposal is None
    assert state.notification_task is None


def test_calendar_to_weather_navigation_generates_minimal_requested_tool_set():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    state = orchestrator.execute(
        "help me plan tomorrow morning departure and check weather"
    )

    assert [step.tool_name for step in state.task.steps] == [
        "calendar_tool",
        "weather_tool",
        "navigation_tool",
    ]
    assert state.task.steps[1].tool_call.status == ToolCallStatus.SUCCESS
    assert state.task.steps[2].tool_call.status == ToolCallStatus.SUCCESS
    assert state.final_result.weather_result["condition"] == "rain"
    assert state.final_result.navigation_result["traffic"] == "heavy"


def test_no_event_safe_failure_does_not_execute_navigation():
    orchestrator, _, weather, navigation = create_orchestrator_with_calendar(
        {"events": [], "event_count": 0}
    )

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.NO_CALENDAR_EVENT
    assert len(state.task.steps) == 1
    assert state.final_result.failure_type == DynamicPlanningFailureType.NO_CALENDAR_EVENT
    assert navigation.call_count == 0
    assert weather.call_count == 0


def test_missing_location_safe_failure_does_not_execute_navigation():
    result = {
        "events": [
            {
                "id": "event-1",
                "title": "Private Meeting",
                "start_time": "08:30",
                "end_time": "09:30",
                "location": None,
            }
        ],
        "event_count": 1,
    }
    orchestrator, _, weather, navigation = create_orchestrator_with_calendar(result)

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.MISSING_EVENT_LOCATION
    assert len(state.task.steps) == 1
    assert (
        state.final_result.failure_type
        == DynamicPlanningFailureType.MISSING_EVENT_LOCATION
    )
    assert navigation.call_count == 0
    assert weather.call_count == 0


def test_max_iterations_exceeded_is_reported():
    orchestrator = DynamicTaskOrchestrator(
        ToolExecutor(create_default_registry()),
        max_iterations=1,
    )

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.MAX_ITERATIONS_EXCEEDED
    assert state.iteration_count == 1


def test_unsupported_dynamic_goal_fails_without_tool_execution():
    orchestrator, calendar, _, _ = create_orchestrator_with_calendar(
        {"events": [], "event_count": 0}
    )

    state = orchestrator.execute("turn off living room light")

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.UNSUPPORTED_DYNAMIC_GOAL
    assert state.task is None
    assert calendar.call_count == 0


def test_invalid_max_iterations_is_rejected():
    with pytest.raises(ValueError):
        DynamicTaskOrchestrator(ToolExecutor(create_default_registry()), max_iterations=0)


def test_successful_continuation_marks_dynamic_task_completed():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.COMPLETED
    assert state.task.status == TaskStatus.COMPLETED
    assert state.final_result.status == DynamicPlanningPhase.COMPLETED


def test_calendar_to_navigation_executes_navigation_tool_once():
    result = {
        "events": [
            {
                "id": "event-1",
                "title": "Meeting",
                "start_time": "08:30",
                "end_time": "09:30",
                "location": "company",
            }
        ],
        "event_count": 1,
    }
    orchestrator, _, weather, navigation = create_orchestrator_with_calendar(result)

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.COMPLETED
    assert weather.call_count == 0
    assert navigation.call_count == 1


def test_calendar_to_weather_navigation_executes_both_tools_once():
    result = {
        "events": [
            {
                "id": "event-1",
                "title": "Meeting",
                "start_time": "08:30",
                "end_time": "09:30",
                "location": "company",
            }
        ],
        "event_count": 1,
    }
    orchestrator, _, weather, navigation = create_orchestrator_with_calendar(result)

    state = orchestrator.execute(
        "help me plan tomorrow morning departure and check weather"
    )

    assert state.phase == DynamicPlanningPhase.COMPLETED
    assert weather.call_count == 1
    assert navigation.call_count == 1


def test_continuation_execution_follows_step_order_not_list_order():
    execution_log: list[str] = []
    result = {
        "events": [
            {
                "id": "event-1",
                "title": "Meeting",
                "start_time": "08:30",
                "end_time": "09:30",
                "location": "company",
            }
        ],
        "event_count": 1,
    }
    orchestrator = create_orchestrator_with_custom_tools(
        calendar_result=result,
        weather=CountingWeatherTool(execution_log),
        navigation=CountingNavigationTool(execution_log),
        continuation_planner=ReverseOrderedContinuationPlanner(),
    )

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.COMPLETED
    assert execution_log == ["weather_tool", "navigation_tool"]


def test_grounding_mismatch_fails_before_navigation_execution():
    execution_log: list[str] = []
    result = {
        "events": [
            {
                "id": "event-1",
                "title": "Meeting",
                "start_time": "08:30",
                "end_time": "09:30",
                "location": "company",
            }
        ],
        "event_count": 1,
    }
    orchestrator = create_orchestrator_with_custom_tools(
        calendar_result=result,
        navigation=CountingNavigationTool(execution_log),
        continuation_planner=BadGroundingPlanner(),
    )

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.OBSERVATION_GROUNDING_ERROR
    assert execution_log == []
    assert state.continuation_observations == []


def test_invalid_navigation_arguments_fail_through_tool_executor():
    result = {
        "events": [
            {
                "id": "event-1",
                "title": "Meeting",
                "start_time": "08:30",
                "end_time": "09:30",
                "location": "company",
            }
        ],
        "event_count": 1,
    }
    orchestrator = create_orchestrator_with_custom_tools(
        calendar_result=result,
        continuation_planner=InvalidNavigationArgumentsPlanner(),
    )

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.CONTINUATION_EXECUTION_ERROR
    assert "navigation_tool failed" in state.error
    assert state.continuation_observations[0].tool_name == "navigation_tool"
    assert state.continuation_observations[0].error


def test_weather_failure_stops_navigation_fail_fast():
    execution_log: list[str] = []
    result = {
        "events": [
            {
                "id": "event-1",
                "title": "Meeting",
                "start_time": "08:30",
                "end_time": "09:30",
                "location": "company",
            }
        ],
        "event_count": 1,
    }
    orchestrator = create_orchestrator_with_custom_tools(
        calendar_result=result,
        weather=FailingWeatherTool(execution_log),
        navigation=CountingNavigationTool(execution_log),
    )

    state = orchestrator.execute(
        "help me plan tomorrow morning departure and check weather"
    )

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.CONTINUATION_EXECUTION_ERROR
    assert execution_log == ["weather_tool"]
    assert len(state.continuation_observations) == 1


def test_navigation_failure_marks_dynamic_task_failed():
    execution_log: list[str] = []
    result = {
        "events": [
            {
                "id": "event-1",
                "title": "Meeting",
                "start_time": "08:30",
                "end_time": "09:30",
                "location": "company",
            }
        ],
        "event_count": 1,
    }
    orchestrator = create_orchestrator_with_custom_tools(
        calendar_result=result,
        navigation=FailingNavigationTool(execution_log),
    )

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.CONTINUATION_EXECUTION_ERROR
    assert execution_log == ["navigation_tool"]


def test_calendar_failure_does_not_call_continuation_planner():
    class CountingContinuationPlanner(ObservationDrivenContinuationPlanner):
        def __init__(self):
            self.call_count = 0

        def build_continuation_steps(self, *, user_input, selected_event, start_order):
            self.call_count += 1
            return super().build_continuation_steps(
                user_input=user_input,
                selected_event=selected_event,
                start_order=start_order,
            )

    planner = CountingContinuationPlanner()
    orchestrator = create_orchestrator_with_custom_tools(
        calendar_result={"events": [], "event_count": 1},
        continuation_planner=planner,
    )

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.FAILED
    assert state.failure_type == DynamicPlanningFailureType.TOOL_EXECUTION_ERROR
    assert planner.call_count == 0


def test_continuation_execution_does_not_increase_planning_iteration_count():
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(create_default_registry()))

    state = orchestrator.execute(
        "help me plan tomorrow morning departure and check weather"
    )

    assert state.phase == DynamicPlanningPhase.COMPLETED
    assert state.iteration_count == 2
    assert len(state.continuation_observations) == 2
