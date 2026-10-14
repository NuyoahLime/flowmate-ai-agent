from typing import Any, Mapping

from flowmate.agent import LLMPlanner
from flowmate.eval import (
    PlannerEvalCase,
    PlannerEvaluator,
    calculate_smart_home_category_metrics,
    load_eval_dataset,
)
from flowmate.schemas import ToolCallStatus


class FakeSmartHomeEvalClient:
    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        if "窗帘" in user_input:
            return {
                "unsupported": True,
                "reason": "Curtain control is unsupported.",
                "plan": None,
            }
        if "下雨" in user_input:
            return {
                "unsupported": False,
                "reason": None,
                "plan": {
                    "goal": "Check weather.",
                    "risk_level": "HIGH",
                    "requires_confirmation": True,
                    "steps": [
                        {
                            "order": 1,
                            "description": "Check weather.",
                            "tool_name": "weather_tool",
                            "arguments": {
                                "location": "current_city",
                                "date": "tomorrow",
                            },
                        }
                    ],
                },
            }
        return {
            "unsupported": False,
            "reason": None,
            "plan": {
                "goal": "Turn off the mock living-room light.",
                "risk_level": "LOW",
                "requires_confirmation": False,
                "steps": [
                    {
                        "order": 1,
                        "description": "Turn off light.",
                        "tool_name": "smart_home_tool",
                        "arguments": {
                            "device_id": "living-room-light",
                            "device_type": "light",
                            "action": "turn_off",
                        },
                    }
                ],
            },
        }


def test_smart_home_dataset_loads_with_expected_categories_and_risk_gold():
    cases = load_eval_dataset("evals/planner_smart_home_v1.json")

    assert len(cases) == 20
    assert sum(case.category == "light_control_supported" for case in cases) == 4
    assert sum(
        case.category == "air_conditioner_control_supported" for case in cases
    ) == 6
    assert sum(case.category == "unsupported_device" for case in cases) == 3
    assert sum(
        case.category == "scheduled_automation_unsupported" for case in cases
    ) == 2
    assert sum(
        case.category == "conditional_automation_unsupported" for case in cases
    ) == 2
    assert sum(case.category == "non_smart_home_minimality" for case in cases) == 3
    smart_home_supported = [
        case for case in cases if case.expected_tools == ["smart_home_tool"]
    ]
    assert len(smart_home_supported) == 10
    assert all(case.expected_risk_level == "MEDIUM" for case in smart_home_supported)
    assert all(case.expected_requires_confirmation is True for case in smart_home_supported)


def test_action_risk_and_category_metrics_are_calculated_without_tool_execution():
    cases = [
        PlannerEvalCase(
            id="smart-supported",
            category="light_control_supported",
            user_input="把客厅灯关掉",
            supported=True,
            expected_tools=["smart_home_tool"],
            expected_arguments={
                "smart_home_tool": {
                    "device_id": "living-room-light",
                    "device_type": "light",
                    "action": "turn_off",
                }
            },
            expected_risk_level="MEDIUM",
            expected_requires_confirmation=True,
        ),
        PlannerEvalCase(
            id="unsupported-device",
            category="unsupported_device",
            user_input="把窗帘关上",
            supported=False,
        ),
        PlannerEvalCase(
            id="minimality",
            category="non_smart_home_minimality",
            user_input="明天会下雨吗？",
            supported=True,
            expected_tools=["weather_tool"],
            expected_arguments={
                "weather_tool": {"location": "current_city", "date": "tomorrow"}
            },
        ),
    ]
    planner = LLMPlanner(FakeSmartHomeEvalClient())

    results, metrics = PlannerEvaluator().evaluate_dataset(planner, cases)
    category_metrics = calculate_smart_home_category_metrics(results, metrics)

    assert metrics.action_risk_accuracy == 1.0
    assert category_metrics.smart_home_supported_recall == 1.0
    assert category_metrics.unsupported_device_recall == 1.0
    assert category_metrics.smart_home_minimality_accuracy == 1.0
    assert all(
        result.predicted_tools != ["smart_home_tool"]
        or result.risk_assessment_correct is True
        for result in results
    )
    assert all(
        result.predicted_tools != ["smart_home_tool"]
        or result.schema_valid
        for result in results
    )

    smart_result = results[0]
    assert smart_result.predicted_risk_level == "MEDIUM"
    assert smart_result.predicted_requires_confirmation is True
    task = planner.plan("把客厅灯关掉")
    assert task.steps[0].tool_call.status == ToolCallStatus.PENDING
    assert task.steps[0].tool_call.result is None
