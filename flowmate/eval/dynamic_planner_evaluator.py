import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

from flowmate.agent.dynamic_task_orchestrator import DynamicTaskOrchestrator
from flowmate.agent.tool_executor import ToolExecutor
from flowmate.schemas import DynamicPlanningFailureType, DynamicPlanningPhase
from flowmate.tools import (
    BaseTool,
    CalendarTool,
    CalendarToolInput,
    CalendarToolResult,
    NavigationTool,
    ToolRegistry,
    WeatherTool,
)


class DynamicPlannerEvalCase(BaseModel):
    id: str
    category: str
    user_input: str
    supported: bool
    expected_initial_tool: str = "calendar_tool"
    expected_continuation_tools: list[str] = Field(default_factory=list)
    expected_destination: str | None = None
    expected_failure_type: DynamicPlanningFailureType | None = None
    mock_calendar_result: dict[str, Any] | None = None


class DynamicPlannerEvalResult(BaseModel):
    case_id: str
    category: str
    user_input: str
    expected_supported: bool
    initial_plan_correct: bool
    initial_tool: str | None = None
    observation_received: bool
    selected_event: dict[str, Any] | None = None
    continuation_generated: bool
    expected_continuation_tools: list[str] = Field(default_factory=list)
    continuation_tools: list[str] = Field(default_factory=list)
    observation_grounded: bool | None = None
    final_success: bool
    safe_failure: bool | None = None
    failure_type: DynamicPlanningFailureType | None = None
    error: str | None = None
    iteration_count: int


class DynamicPlannerEvalMetrics(BaseModel):
    cases: int
    initial_tool_accuracy: float
    observation_grounding_accuracy: float | None
    continuation_tool_accuracy: float | None
    dynamic_completion_rate: float | None
    safe_failure_rate: float | None


class DynamicPlannerEvaluator:
    def evaluate_case(
        self,
        case: DynamicPlannerEvalCase,
        orchestrator: DynamicTaskOrchestrator | None = None,
    ) -> DynamicPlannerEvalResult:
        orchestrator = orchestrator or self._build_orchestrator(case)
        state = orchestrator.execute(case.user_input)
        initial_tool = state.task.steps[0].tool_name if state.task and state.task.steps else None
        continuation_steps = state.task.steps[1:] if state.task else []
        continuation_tools = [step.tool_name for step in continuation_steps]
        selected_event = state.selected_event
        destination = self._navigation_destination(continuation_steps)

        observation_received = bool(state.observations and state.observations[0].result)
        continuation_generated = bool(continuation_steps)
        observation_grounded = None
        if case.supported:
            observation_grounded = (
                selected_event is not None
                and destination == selected_event.get("location")
                and destination == case.expected_destination
            )

        safe_failure = None
        if not case.supported:
            safe_failure = (
                state.phase == DynamicPlanningPhase.FAILED
                and state.failure_type == case.expected_failure_type
                and not continuation_generated
            )

        final_success = (
            case.supported
            and state.phase == DynamicPlanningPhase.COMPLETED
            and continuation_tools == case.expected_continuation_tools
            and observation_grounded is True
        )

        return DynamicPlannerEvalResult(
            case_id=case.id,
            category=case.category,
            user_input=case.user_input,
            expected_supported=case.supported,
            initial_plan_correct=initial_tool == case.expected_initial_tool,
            initial_tool=initial_tool,
            observation_received=observation_received,
            selected_event=selected_event,
            continuation_generated=continuation_generated,
            expected_continuation_tools=case.expected_continuation_tools,
            continuation_tools=continuation_tools,
            observation_grounded=observation_grounded,
            final_success=final_success,
            safe_failure=safe_failure,
            failure_type=state.failure_type,
            error=state.error,
            iteration_count=state.iteration_count,
        )

    def evaluate_dataset(
        self,
        cases: Iterable[DynamicPlannerEvalCase],
        orchestrator: DynamicTaskOrchestrator | None = None,
    ) -> tuple[list[DynamicPlannerEvalResult], DynamicPlannerEvalMetrics]:
        results = [self.evaluate_case(case, orchestrator) for case in cases]
        return results, self.calculate_metrics(results)

    def calculate_metrics(
        self,
        results: list[DynamicPlannerEvalResult],
    ) -> DynamicPlannerEvalMetrics:
        total = len(results)
        supported_results = [result for result in results if result.expected_supported]
        unsupported_results = [
            result for result in results if not result.expected_supported
        ]
        grounding_results = [
            result
            for result in supported_results
            if result.observation_grounded is not None
        ]

        return DynamicPlannerEvalMetrics(
            cases=total,
            initial_tool_accuracy=self._ratio(
                sum(result.initial_plan_correct for result in results),
                total,
            ),
            observation_grounding_accuracy=self._optional_ratio(
                sum(result.observation_grounded for result in grounding_results),
                len(grounding_results),
            ),
            continuation_tool_accuracy=self._optional_ratio(
                sum(
                    result.continuation_tools == result.expected_continuation_tools
                    for result in supported_results
                ),
                len(supported_results),
            ),
            dynamic_completion_rate=self._optional_ratio(
                sum(result.final_success for result in supported_results),
                len(supported_results),
            ),
            safe_failure_rate=self._optional_ratio(
                sum(result.safe_failure for result in unsupported_results),
                len(unsupported_results),
            ),
        )

    def _navigation_destination(self, continuation_steps: list[Any]) -> str | None:
        for step in continuation_steps:
            if step.tool_name == "navigation_tool" and step.tool_call is not None:
                return step.tool_call.arguments.get("destination")
        return None

    def _ratio(self, numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0

    def _optional_ratio(self, numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    def _build_orchestrator(
        self,
        case: DynamicPlannerEvalCase,
    ) -> DynamicTaskOrchestrator:
        registry = ToolRegistry()
        registry.register(WeatherTool())
        registry.register(NavigationTool())
        if case.mock_calendar_result is None:
            registry.register(CalendarTool())
        else:
            registry.register(_EvalCalendarTool(case.mock_calendar_result))
        return DynamicTaskOrchestrator(
            ToolExecutor(registry),
            execute_continuation_tools=False,
        )


class _EvalCalendarTool(BaseTool[CalendarToolInput, CalendarToolResult]):
    name = "calendar_tool"
    description = "Eval-only calendar fixture tool."
    input_schema = CalendarToolInput

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    def execute(self, input_data: CalendarToolInput) -> CalendarToolResult:
        payload = {"date": input_data.date, **self.result}
        return CalendarToolResult.model_validate(payload)


def load_dynamic_eval_dataset(path: str | Path) -> list[DynamicPlannerEvalCase]:
    with Path(path).open("r", encoding="utf-8") as file:
        raw_cases = json.load(file)
    return [DynamicPlannerEvalCase.model_validate(case) for case in raw_cases]
