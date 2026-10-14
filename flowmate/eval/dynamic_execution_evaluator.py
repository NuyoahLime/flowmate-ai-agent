import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

from flowmate.agent import (
    DynamicTaskOrchestrator,
    ObservationDrivenContinuationPlanner,
    ToolExecutor,
)
from flowmate.schemas import (
    DynamicPlanningFailureType,
    DynamicPlanningPhase,
    PlanStep,
    ToolCall,
)
from flowmate.tools import (
    BaseTool,
    CalendarTool,
    CalendarToolInput,
    CalendarToolResult,
    NavigationTool,
    ToolRegistry,
    WeatherTool,
)


class DynamicExecutionEvalCase(BaseModel):
    id: str
    category: str
    user_input: str
    supported: bool
    expected_continuation_tools: list[str] = Field(default_factory=list)
    expected_executed_continuation_tools: list[str] = Field(default_factory=list)
    expected_destination: str | None = None
    expected_failure_type: DynamicPlanningFailureType | None = None
    mock_calendar_result: dict[str, Any] | None = None
    fail_calendar: bool = False
    fail_weather: bool = False
    fail_navigation: bool = False
    override_navigation_destination: str | None = None
    invalid_navigation_arguments: bool = False


class DynamicExecutionEvalResult(BaseModel):
    case_id: str
    category: str
    user_input: str
    expected_supported: bool
    final_status: DynamicPlanningPhase
    final_success: bool
    selected_event: dict[str, Any] | None = None
    continuation_tools: list[str] = Field(default_factory=list)
    executed_continuation_tools: list[str] = Field(default_factory=list)
    continuation_execution_success: bool | None = None
    execution_order_correct: bool | None = None
    grounded_execution: bool | None = None
    failure_contained: bool | None = None
    failure_type: DynamicPlanningFailureType | None = None
    error: str | None = None


class DynamicExecutionEvalMetrics(BaseModel):
    cases: int
    final_execution_success_rate: float | None
    continuation_execution_accuracy: float | None
    execution_order_accuracy: float | None
    failure_containment_rate: float | None
    grounded_execution_rate: float | None


class DynamicExecutionEvaluator:
    def evaluate_case(self, case: DynamicExecutionEvalCase) -> DynamicExecutionEvalResult:
        orchestrator = self._build_orchestrator(case)
        state = orchestrator.execute(case.user_input)
        continuation_steps = state.task.steps[1:] if state.task else []
        continuation_tools = [step.tool_name for step in continuation_steps]
        executed_tools = [
            observation.tool_name for observation in state.continuation_observations
        ]
        successful_executed_tools = [
            observation.tool_name
            for observation in state.continuation_observations
            if observation.error is None
        ]

        continuation_execution_success = None
        if case.supported:
            continuation_execution_success = (
                successful_executed_tools == case.expected_continuation_tools
            )

        execution_order_correct = None
        expected_order = case.expected_executed_continuation_tools or (
            case.expected_continuation_tools if case.supported else []
        )
        if len(expected_order) > 1:
            execution_order_correct = executed_tools == expected_order

        grounded_execution = self._grounded_execution(state)

        failure_contained = None
        if not case.supported:
            failure_contained = (
                state.phase == DynamicPlanningPhase.FAILED
                and state.failure_type == case.expected_failure_type
                and executed_tools == case.expected_executed_continuation_tools
            )

        final_success = (
            case.supported
            and state.phase == DynamicPlanningPhase.COMPLETED
            and continuation_tools == case.expected_continuation_tools
            and continuation_execution_success is True
            and (grounded_execution is True or "navigation_tool" not in executed_tools)
        )

        return DynamicExecutionEvalResult(
            case_id=case.id,
            category=case.category,
            user_input=case.user_input,
            expected_supported=case.supported,
            final_status=state.phase,
            final_success=final_success,
            selected_event=state.selected_event,
            continuation_tools=continuation_tools,
            executed_continuation_tools=executed_tools,
            continuation_execution_success=continuation_execution_success,
            execution_order_correct=execution_order_correct,
            grounded_execution=grounded_execution,
            failure_contained=failure_contained,
            failure_type=state.failure_type,
            error=state.error,
        )

    def evaluate_dataset(
        self,
        cases: Iterable[DynamicExecutionEvalCase],
    ) -> tuple[list[DynamicExecutionEvalResult], DynamicExecutionEvalMetrics]:
        results = [self.evaluate_case(case) for case in cases]
        return results, self.calculate_metrics(results)

    def calculate_metrics(
        self,
        results: list[DynamicExecutionEvalResult],
    ) -> DynamicExecutionEvalMetrics:
        supported_results = [result for result in results if result.expected_supported]
        failure_results = [result for result in results if not result.expected_supported]
        order_results = [
            result for result in results if result.execution_order_correct is not None
        ]
        grounded_results = [
            result for result in results if result.grounded_execution is not None
        ]

        return DynamicExecutionEvalMetrics(
            cases=len(results),
            final_execution_success_rate=self._optional_ratio(
                sum(result.final_success for result in supported_results),
                len(supported_results),
            ),
            continuation_execution_accuracy=self._optional_ratio(
                sum(
                    result.continuation_execution_success
                    for result in supported_results
                    if result.continuation_execution_success is not None
                ),
                len(supported_results),
            ),
            execution_order_accuracy=self._optional_ratio(
                sum(result.execution_order_correct for result in order_results),
                len(order_results),
            ),
            failure_containment_rate=self._optional_ratio(
                sum(result.failure_contained for result in failure_results),
                len(failure_results),
            ),
            grounded_execution_rate=self._optional_ratio(
                sum(result.grounded_execution for result in grounded_results),
                len(grounded_results),
            ),
        )

    def _build_orchestrator(
        self,
        case: DynamicExecutionEvalCase,
    ) -> DynamicTaskOrchestrator:
        registry = ToolRegistry()
        registry.register(_EvalWeatherTool(should_fail=case.fail_weather))
        registry.register(_EvalNavigationTool(should_fail=case.fail_navigation))
        if case.fail_calendar:
            registry.register(_FailingCalendarTool())
        elif case.mock_calendar_result is None:
            registry.register(CalendarTool())
        else:
            registry.register(_EvalCalendarTool(case.mock_calendar_result))

        planner: ObservationDrivenContinuationPlanner | None = None
        if case.override_navigation_destination is not None:
            planner = _OverrideDestinationPlanner(case.override_navigation_destination)
        elif case.invalid_navigation_arguments:
            planner = _InvalidNavigationArgumentsPlanner()

        return DynamicTaskOrchestrator(
            ToolExecutor(registry),
            continuation_planner=planner,
        )

    def _grounded_execution(self, state) -> bool | None:
        if state.selected_event is None:
            return None

        expected_destination = state.selected_event.get("location")
        for observation in state.continuation_observations:
            if observation.tool_name == "navigation_tool" and observation.error is None:
                return observation.result.get("destination") == expected_destination
        return None

    def _optional_ratio(self, numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None


class _EvalCalendarTool(BaseTool[CalendarToolInput, CalendarToolResult]):
    name = "calendar_tool"
    description = "Eval-only calendar fixture tool."
    input_schema = CalendarToolInput

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    def execute(self, input_data: CalendarToolInput) -> CalendarToolResult:
        payload = {"date": input_data.date, **self.result}
        return CalendarToolResult.model_validate(payload)


class _FailingCalendarTool(CalendarTool):
    def execute(self, input_data: CalendarToolInput) -> CalendarToolResult:
        raise RuntimeError("calendar unavailable")


class _EvalWeatherTool(WeatherTool):
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def execute(self, input_data):
        if self.should_fail:
            raise RuntimeError("weather unavailable")
        return super().execute(input_data)


class _EvalNavigationTool(NavigationTool):
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def execute(self, input_data):
        if self.should_fail:
            raise RuntimeError("navigation unavailable")
        return super().execute(input_data)


class _OverrideDestinationPlanner(ObservationDrivenContinuationPlanner):
    def __init__(self, destination: str) -> None:
        self.destination = destination

    def build_continuation_steps(self, *, user_input, selected_event, start_order):
        steps = super().build_continuation_steps(
            user_input=user_input,
            selected_event=selected_event,
            start_order=start_order,
        )
        for step in steps:
            if step.tool_name == "navigation_tool" and step.tool_call is not None:
                step.tool_call.arguments["destination"] = self.destination
        return steps


class _InvalidNavigationArgumentsPlanner(ObservationDrivenContinuationPlanner):
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


def load_dynamic_execution_dataset(
    path: str | Path,
) -> list[DynamicExecutionEvalCase]:
    with Path(path).open("r", encoding="utf-8") as file:
        raw_cases = json.load(file)
    return [DynamicExecutionEvalCase.model_validate(case) for case in raw_cases]
