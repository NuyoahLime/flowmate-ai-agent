from flowmate.eval import DynamicExecutionEvaluator, load_dynamic_execution_dataset
from flowmate.schemas import DynamicPlanningFailureType


def test_dynamic_execution_dataset_loads_with_expected_categories():
    cases = load_dynamic_execution_dataset("evals/dynamic_execution_v1.json")

    assert len(cases) == 10
    assert sum(case.category == "calendar_navigation_success" for case in cases) == 4
    assert (
        sum(case.category == "calendar_weather_navigation_success" for case in cases)
        == 2
    )
    assert sum(case.category == "calendar_failure" for case in cases) == 1
    assert (
        sum(case.category == "continuation_validation_failure" for case in cases)
        == 1
    )
    assert sum(case.category == "continuation_tool_failure" for case in cases) == 1
    assert sum(case.category == "grounding_failure" for case in cases) == 1


def test_dynamic_execution_evaluator_scores_success_case():
    case = next(
        item
        for item in load_dynamic_execution_dataset("evals/dynamic_execution_v1.json")
        if item.id == "execution-nav-001"
    )

    result = DynamicExecutionEvaluator().evaluate_case(case)

    assert result.final_success is True
    assert result.continuation_tools == ["navigation_tool"]
    assert result.executed_continuation_tools == ["navigation_tool"]
    assert result.grounded_execution is True


def test_dynamic_execution_evaluator_scores_weather_navigation_case():
    case = next(
        item
        for item in load_dynamic_execution_dataset("evals/dynamic_execution_v1.json")
        if item.id == "execution-weather-nav-001"
    )

    result = DynamicExecutionEvaluator().evaluate_case(case)

    assert result.final_success is True
    assert result.continuation_tools == ["weather_tool", "navigation_tool"]
    assert result.executed_continuation_tools == ["weather_tool", "navigation_tool"]
    assert result.execution_order_correct is True


def test_dynamic_execution_evaluator_records_calendar_failure_containment():
    case = next(
        item
        for item in load_dynamic_execution_dataset("evals/dynamic_execution_v1.json")
        if item.id == "execution-calendar-failure-001"
    )

    result = DynamicExecutionEvaluator().evaluate_case(case)

    assert result.failure_contained is True
    assert result.failure_type == DynamicPlanningFailureType.TOOL_EXECUTION_ERROR
    assert result.executed_continuation_tools == []


def test_dynamic_execution_evaluator_records_grounding_failure_containment():
    case = next(
        item
        for item in load_dynamic_execution_dataset("evals/dynamic_execution_v1.json")
        if item.id == "execution-grounding-failure-001"
    )

    result = DynamicExecutionEvaluator().evaluate_case(case)

    assert result.failure_contained is True
    assert result.failure_type == DynamicPlanningFailureType.OBSERVATION_GROUNDING_ERROR
    assert result.executed_continuation_tools == []


def test_dynamic_execution_metrics_are_calculated():
    cases = load_dynamic_execution_dataset("evals/dynamic_execution_v1.json")

    results, metrics = DynamicExecutionEvaluator().evaluate_dataset(cases)

    assert results
    assert metrics.cases == 10
    assert metrics.final_execution_success_rate == 1.0
    assert metrics.continuation_execution_accuracy == 1.0
    assert metrics.execution_order_accuracy == 1.0
    assert metrics.failure_containment_rate == 1.0
    assert metrics.grounded_execution_rate == 1.0
