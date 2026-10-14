import json
from pathlib import Path
from typing import Any, Mapping

from flowmate.agent import (
    LLMPlanner,
    LLMProviderError,
    PlannerOutputValidationError,
    RuleBasedPlanner,
    ToolArgumentValidationError,
)
from flowmate.eval import PlannerEvalCase, PlannerEvaluator, load_eval_dataset


def supported_case() -> PlannerEvalCase:
    return PlannerEvalCase(
        id="supported-001",
        category="morning_commute",
        user_input="明天早上在公司开会，帮我安排出门",
        supported=True,
        expected_tools=["weather_tool", "navigation_tool"],
        expected_arguments={
            "weather_tool": {"location": "current_city", "date": "tomorrow"},
            "navigation_tool": {
                "origin": "home",
                "destination": "company",
                "departure_time": "tomorrow morning",
            },
        },
    )


def unsupported_case() -> PlannerEvalCase:
    return PlannerEvalCase(
        id="unsupported-001",
        category="unsupported_smart_home",
        user_input="帮我把客厅灯关掉",
        supported=False,
        expected_tools=[],
        expected_arguments={},
    )


class FakeLLMClient:
    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        if "客厅灯" in user_input:
            return {
                "unsupported": True,
                "reason": "smart_home_tool is not available.",
                "plan": None,
            }
        return {
            "unsupported": False,
            "reason": None,
            "plan": {
                "goal": "安排明早通勤",
                "risk_level": "LOW",
                "requires_confirmation": False,
                "steps": [
                    {
                        "order": 1,
                        "description": "检查明早天气",
                        "tool_name": "weather_tool",
                        "arguments": {
                            "location": "current_city",
                            "date": "tomorrow",
                        },
                    },
                    {
                        "order": 2,
                        "description": "计算到公司的通勤时间",
                        "tool_name": "navigation_tool",
                        "arguments": {
                            "origin": "home",
                            "destination": "company",
                            "departure_time": "tomorrow morning",
                        },
                    },
                ],
            },
        }


def test_dataset_loads():
    cases = load_eval_dataset("evals/planner_eval_v1.json")

    assert len(cases) == 22


def test_challenge_dataset_loads():
    cases = load_eval_dataset("evals/planner_challenge_v1.json")

    assert len(cases) == 8


def test_boundary_dataset_loads():
    cases = load_eval_dataset("evals/planner_boundary_v1.json")

    assert len(cases) == 10


def test_minimality_dataset_loads():
    cases = load_eval_dataset("evals/planner_minimality_v1.json")

    assert len(cases) == 12


def test_parameter_dataset_loads():
    cases = load_eval_dataset("evals/planner_parameters_v1.json")

    assert len(cases) == 12


def test_calendar_planner_dataset_loads_with_expected_categories():
    cases = load_eval_dataset("evals/planner_calendar_v1.json")

    assert len(cases) == 15
    assert sum(case.category == "calendar_read_supported" for case in cases) == 7
    assert sum(case.category == "calendar_write_unsupported" for case in cases) == 4
    assert sum(case.category == "dynamic_dependency_unsupported" for case in cases) == 4


def test_calendar_temporal_dataset_loads_with_expected_categories():
    cases = load_eval_dataset("evals/planner_calendar_temporal_v1.json")

    assert len(cases) == 12
    assert sum(case.category == "whole_day" for case in cases) == 3
    assert sum(case.category == "morning" for case in cases) == 3
    assert sum(case.category == "afternoon" for case in cases) == 3
    assert sum(case.category == "evening" for case in cases) == 3


def test_planner_eval_v1_and_v2_load():
    v1_cases = load_eval_dataset("evals/planner_eval_v1.json")
    v2_cases = load_eval_dataset("evals/planner_eval_v2.json")

    assert len(v1_cases) == 22
    assert len(v2_cases) == 22


def test_planner_eval_v1_keeps_historical_calendar_gold():
    cases = load_eval_dataset("evals/planner_eval_v1.json")
    case = next(item for item in cases if item.id == "unsupported-calendar-002")

    assert case.supported is False
    assert case.expected_tools == []


def test_planner_eval_v2_updates_calendar_read_gold():
    cases = load_eval_dataset("evals/planner_eval_v2.json")
    case = next(item for item in cases if item.id == "unsupported-calendar-002")

    assert case.supported is True
    assert case.expected_tools == ["calendar_tool"]
    assert case.expected_arguments == {"calendar_tool": {"date": "next month"}}


def test_planner_eval_v2_keeps_calendar_write_unsupported():
    cases = load_eval_dataset("evals/planner_eval_v2.json")
    write_cases = [
        case for case in cases if case.category == "unsupported_calendar"
    ]

    assert write_cases
    assert all(case.supported is False for case in write_cases)


def test_calendar_dataset_keeps_dynamic_dependency_unsupported():
    cases = load_eval_dataset("evals/planner_calendar_v1.json")
    dynamic_cases = [
        case for case in cases if case.category == "dynamic_dependency_unsupported"
    ]

    assert dynamic_cases
    assert all(case.supported is False for case in dynamic_cases)


def test_capability_precision_dataset_loads_with_expected_categories():
    cases = load_eval_dataset("evals/planner_capability_precision_v1.json")

    assert len(cases) == 12
    assert sum(case.supported for case in cases) == 6
    assert sum(not case.supported for case in cases) == 6
    assert {
        case.category for case in cases
    } == {"supported_information_planning", "unsupported_physical_control"}


def test_notification_planner_dataset_loads_with_expected_categories():
    cases = load_eval_dataset("evals/planner_notification_v1.json")

    assert len(cases) == 16
    assert sum(case.category == "immediate_notification_supported" for case in cases) == 6
    assert (
        sum(case.category == "scheduled_notification_unsupported" for case in cases)
        == 4
    )
    assert (
        sum(case.category == "conditional_notification_unsupported" for case in cases)
        == 3
    )
    assert sum(case.category == "non_notification_minimality" for case in cases) == 3


def test_supported_scenario_is_scored_correctly():
    result = PlannerEvaluator().evaluate_case(RuleBasedPlanner(), supported_case())

    assert result.scenario_correct is True
    assert result.tool_selection_correct is True
    assert result.parameter_accuracy == 1.0
    assert result.parameter_completeness == 1.0
    assert result.schema_valid is True


def test_supported_recall_is_one_when_supported_cases_are_correct():
    results, metrics = PlannerEvaluator().evaluate_dataset(
        RuleBasedPlanner(),
        [supported_case()],
    )

    assert results
    assert metrics.supported_recall == 1.0


def test_supported_recall_supports_partial_score():
    evaluator = PlannerEvaluator()
    correct = evaluator.evaluate_case(RuleBasedPlanner(), supported_case())
    failed = evaluator.evaluate_case(RuleBasedPlanner(), supported_case())
    failed.scenario_correct = False

    metrics = evaluator.calculate_metrics([correct, failed])

    assert metrics.supported_recall == 0.5


def test_supported_recall_is_not_applicable_without_supported_cases():
    results, metrics = PlannerEvaluator().evaluate_dataset(
        RuleBasedPlanner(),
        [unsupported_case()],
    )

    assert results
    assert metrics.supported_recall is None


def test_unsupported_scenario_is_scored_correctly():
    result = PlannerEvaluator().evaluate_case(RuleBasedPlanner(), unsupported_case())

    assert result.predicted_supported is False
    assert result.scenario_correct is True
    assert result.tool_selection_correct is True


def test_unsupported_recall_is_one_when_unsupported_cases_are_correct():
    results, metrics = PlannerEvaluator().evaluate_dataset(
        RuleBasedPlanner(),
        [unsupported_case()],
    )

    assert results
    assert metrics.unsupported_recall == 1.0


def test_unsupported_recall_is_not_applicable_without_unsupported_cases():
    results, metrics = PlannerEvaluator().evaluate_dataset(
        RuleBasedPlanner(),
        [supported_case()],
    )

    assert results
    assert metrics.unsupported_recall is None


def test_tool_missing_fails_exact_match():
    case = supported_case()
    case.expected_tools = ["weather_tool"]

    result = PlannerEvaluator().evaluate_case(RuleBasedPlanner(), case)

    assert result.tool_selection_correct is False


def test_extra_tool_fails_exact_match():
    case = supported_case()
    case.expected_tools = ["weather_tool", "navigation_tool", "extra_tool"]

    result = PlannerEvaluator().evaluate_case(RuleBasedPlanner(), case)

    assert result.tool_selection_correct is False


def test_parameter_accuracy_supports_partial_score():
    case = supported_case()
    case.expected_arguments["weather_tool"]["date"] = "today"

    result = PlannerEvaluator().evaluate_case(RuleBasedPlanner(), case)

    assert 0.0 < result.parameter_accuracy < 1.0


def test_parameter_completeness_is_one_when_expected_fields_exist():
    result = PlannerEvaluator().evaluate_case(RuleBasedPlanner(), supported_case())

    assert result.parameter_completeness == 1.0


def test_parameter_completeness_supports_partial_score():
    evaluator = PlannerEvaluator()
    score = evaluator._parameter_completeness(
        {
            "navigation_tool": {
                "origin": "home",
                "destination": "company",
                "departure_time": "tomorrow morning",
            }
        },
        {"navigation_tool": {"origin": "home", "destination": "company"}},
    )

    assert score == 2 / 3


def test_parameter_completeness_is_not_applicable_without_expected_fields():
    evaluator = PlannerEvaluator()

    assert evaluator._parameter_completeness({}, {}) is None


def test_temporal_constraint_preservation_rate_is_one_when_all_preserved():
    case = PlannerEvalCase(
        id="calendar-temporal-test",
        category="morning",
        user_input="calendar morning",
        supported=True,
        expected_tools=["calendar_tool"],
        expected_arguments={
            "calendar_tool": {
                "date": "tomorrow",
                "start_time": "06:00",
                "end_time": "12:00",
            }
        },
    )
    result = PlannerEvaluator().evaluate_case(
        LLMPlanner(
            FakeLLMClient()
        ),
        case,
    )

    result.predicted_tools = ["calendar_tool"]
    result.predicted_arguments = {
        "calendar_tool": {
            "date": "tomorrow",
            "start_time": "06:00",
            "end_time": "12:00",
        }
    }
    result.temporal_constraint_preserved = True

    metrics = PlannerEvaluator().calculate_metrics([result])

    assert metrics.temporal_constraint_preservation_rate == 1.0


def test_temporal_constraint_preservation_rate_supports_partial_score():
    evaluator = PlannerEvaluator()
    preserved = evaluator.evaluate_case(RuleBasedPlanner(), supported_case())
    missed = evaluator.evaluate_case(RuleBasedPlanner(), supported_case())
    preserved.temporal_constraint_preserved = True
    missed.temporal_constraint_preserved = False

    metrics = evaluator.calculate_metrics([preserved, missed])

    assert metrics.temporal_constraint_preservation_rate == 0.5


def test_temporal_constraint_preservation_rate_is_not_applicable_without_temporal_cases():
    result = PlannerEvaluator().evaluate_case(RuleBasedPlanner(), supported_case())

    metrics = PlannerEvaluator().calculate_metrics([result])

    assert metrics.temporal_constraint_preservation_rate is None


def test_parameter_validation_error_is_recorded():
    class BadArgumentPlanner:
        def plan(self, user_input: str):
            raise ToolArgumentValidationError(
                "Invalid arguments for navigation_tool",
                tool_name="navigation_tool",
                arguments={"origin": "home", "destination": "company"},
            )

    result = PlannerEvaluator().evaluate_case(BadArgumentPlanner(), supported_case())

    assert result.failure_type == "tool_argument_validation_error"
    assert result.failure_stage == "tool_argument_validation"
    assert result.predicted_supported is True
    assert result.parameter_completeness == 2 / 5


def test_llm_schema_error_is_recorded():
    class BadSchemaPlanner:
        def plan(self, user_input: str):
            raise PlannerOutputValidationError("Invalid LLM planner output")

    result = PlannerEvaluator().evaluate_case(BadSchemaPlanner(), supported_case())

    assert result.failure_type == "llm_schema_error"
    assert result.failure_stage == "llm_plan_validation"


def test_provider_parse_error_is_recorded_with_stage():
    class ProviderErrorPlanner:
        def plan(self, user_input: str):
            raise LLMProviderError(
                "DeepSeek response parsing failed at json_decode stage.",
                stage="json_decode",
                error_type="provider_invalid_json",
            )

    result = PlannerEvaluator().evaluate_case(ProviderErrorPlanner(), supported_case())

    assert result.failure_type == "provider_invalid_json"
    assert result.failure_stage == "json_decode"
    assert result.provider_error_type == "provider_invalid_json"


def test_extra_tool_rate_counts_supported_cases_with_extra_tools():
    evaluator = PlannerEvaluator()
    results = [
        evaluator.evaluate_case(
            RuleBasedPlanner(),
            supported_case(),
        )
    ]
    results[0].extra_tool_case = True

    metrics = evaluator.calculate_metrics(results)

    assert metrics.extra_tool_rate == 1.0


def test_unsupported_accuracy_is_not_applicable_without_unsupported_cases():
    results, metrics = PlannerEvaluator().evaluate_dataset(
        RuleBasedPlanner(),
        [supported_case()],
    )

    assert results
    assert metrics.unsupported_accuracy is None


def test_unsupported_accuracy_is_calculated_when_unsupported_cases_exist():
    results, metrics = PlannerEvaluator().evaluate_dataset(
        RuleBasedPlanner(),
        [supported_case(), unsupported_case()],
    )

    assert results
    assert metrics.unsupported_accuracy == 1.0


def test_minimality_result_marks_unsupported_accuracy_as_not_applicable():
    result_path = Path("evals/results/llm_planner_minimality_v1.json")
    payload = json.loads(result_path.read_text(encoding="utf-8"))

    assert payload["metrics"]["unsupported_accuracy"] is None


def test_planner_error_is_recorded():
    case = supported_case()
    case.user_input = "不支持的输入"

    result = PlannerEvaluator().evaluate_case(RuleBasedPlanner(), case)

    assert result.schema_valid is False
    assert result.error


def test_evaluator_does_not_execute_tools():
    results, metrics = PlannerEvaluator().evaluate_dataset(
        LLMPlanner(FakeLLMClient()),
        [supported_case(), unsupported_case()],
    )

    assert all(result.predicted_tools for result in results if result.expected_supported)
    assert metrics.cases == 2
