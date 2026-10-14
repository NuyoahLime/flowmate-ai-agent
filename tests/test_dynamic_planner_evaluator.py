from flowmate.eval import (
    DynamicPlannerEvalCase,
    DynamicPlannerEvaluator,
    load_dynamic_eval_dataset,
)
from flowmate.schemas import (
    DynamicPlanningFailureType,
    DynamicPlanningPhase,
    DynamicPlanningState,
    PlanStep,
    Task,
    TaskStatus,
    ToolCall,
    ToolObservation,
)


def test_dynamic_dataset_loads_with_expected_categories():
    cases = load_dynamic_eval_dataset("evals/planner_dynamic_morning_v1.json")

    assert len(cases) == 10
    assert sum(case.category == "dynamic_navigation_supported" for case in cases) == 4
    assert (
        sum(case.category == "dynamic_weather_navigation_supported" for case in cases)
        == 2
    )
    assert sum(case.category == "no_event_failure" for case in cases) == 2
    assert sum(case.category == "missing_location_failure" for case in cases) == 2


def test_dynamic_evaluator_scores_supported_navigation_case():
    case = DynamicPlannerEvalCase(
        id="dynamic-test-001",
        category="dynamic_navigation_supported",
        user_input="help me plan tomorrow morning departure",
        supported=True,
        expected_continuation_tools=["navigation_tool"],
        expected_destination="company",
    )

    result = DynamicPlannerEvaluator().evaluate_case(case)

    assert result.initial_plan_correct is True
    assert result.observation_received is True
    assert result.continuation_tools == ["navigation_tool"]
    assert result.observation_grounded is True
    assert result.final_success is True


def test_dynamic_evaluator_scores_weather_navigation_case():
    case = DynamicPlannerEvalCase(
        id="dynamic-test-002",
        category="dynamic_weather_navigation_supported",
        user_input="help me plan tomorrow morning departure and check weather",
        supported=True,
        expected_continuation_tools=["weather_tool", "navigation_tool"],
        expected_destination="company",
    )

    result = DynamicPlannerEvaluator().evaluate_case(case)

    assert result.continuation_tools == ["weather_tool", "navigation_tool"]
    assert result.final_success is True


def test_dynamic_evaluator_records_no_event_safe_failure():
    case = DynamicPlannerEvalCase(
        id="dynamic-test-003",
        category="no_event_failure",
        user_input="help me plan tomorrow morning departure",
        supported=False,
        expected_failure_type=DynamicPlanningFailureType.NO_CALENDAR_EVENT,
        mock_calendar_result={"events": [], "event_count": 0},
    )

    result = DynamicPlannerEvaluator().evaluate_case(case)

    assert result.safe_failure is True
    assert result.continuation_generated is False
    assert result.failure_type == DynamicPlanningFailureType.NO_CALENDAR_EVENT


def test_dynamic_evaluator_records_missing_location_safe_failure():
    case = DynamicPlannerEvalCase(
        id="dynamic-test-004",
        category="missing_location_failure",
        user_input="help me plan tomorrow morning departure",
        supported=False,
        expected_failure_type=DynamicPlanningFailureType.MISSING_EVENT_LOCATION,
        mock_calendar_result={
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
        },
    )

    result = DynamicPlannerEvaluator().evaluate_case(case)

    assert result.safe_failure is True
    assert result.failure_type == DynamicPlanningFailureType.MISSING_EVENT_LOCATION


def test_observation_grounding_mismatch_fails_eval():
    class BadGroundingOrchestrator:
        def execute(self, user_input: str):
            return DynamicPlanningState(
                user_input=user_input,
                phase=DynamicPlanningPhase.COMPLETED,
                iteration_count=2,
                selected_event={
                    "id": "event-1",
                    "title": "Meeting",
                    "start_time": "08:30",
                    "end_time": "09:30",
                    "location": "company",
                },
                observations=[
                    ToolObservation(
                        tool_name="calendar_tool",
                        result={
                            "event_count": 1,
                            "events": [
                                {
                                    "id": "event-1",
                                    "title": "Meeting",
                                    "start_time": "08:30",
                                    "end_time": "09:30",
                                    "location": "company",
                                }
                            ],
                        },
                    )
                ],
                task=Task(
                    id="task-1",
                    user_input=user_input,
                    goal="bad grounding",
                    status=TaskStatus.PLANNED,
                    steps=[
                        PlanStep(
                            id="step-1",
                            order=1,
                            description="calendar",
                            tool_name="calendar_tool",
                            tool_call=ToolCall(
                                tool_name="calendar_tool",
                                arguments={
                                    "date": "tomorrow",
                                    "start_time": "06:00",
                                    "end_time": "12:00",
                                },
                            ),
                        ),
                        PlanStep(
                            id="step-2",
                            order=2,
                            description="navigation",
                            tool_name="navigation_tool",
                            tool_call=ToolCall(
                                tool_name="navigation_tool",
                                arguments={
                                    "origin": "home",
                                    "destination": "office",
                                    "departure_time": "tomorrow morning",
                                },
                            ),
                        ),
                    ],
                ),
            )

    case = DynamicPlannerEvalCase(
        id="dynamic-test-005",
        category="dynamic_navigation_supported",
        user_input="help me plan tomorrow morning departure",
        supported=True,
        expected_continuation_tools=["navigation_tool"],
        expected_destination="company",
    )

    result = DynamicPlannerEvaluator().evaluate_case(case, BadGroundingOrchestrator())

    assert result.observation_grounded is False
    assert result.final_success is False


def test_dynamic_metrics_are_calculated():
    cases = load_dynamic_eval_dataset("evals/planner_dynamic_morning_v1.json")

    results, metrics = DynamicPlannerEvaluator().evaluate_dataset(cases)

    assert results
    assert metrics.cases == 10
    assert metrics.initial_tool_accuracy == 1.0
    assert metrics.observation_grounding_accuracy == 1.0
    assert metrics.continuation_tool_accuracy == 1.0
    assert metrics.dynamic_completion_rate == 1.0
    assert metrics.safe_failure_rate == 1.0
