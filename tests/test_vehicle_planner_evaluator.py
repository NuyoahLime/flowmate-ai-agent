from typing import Any, Mapping

from flowmate.agent import LLMPlanner
from flowmate.eval import (
    PlannerEvalCase,
    PlannerEvaluator,
    calculate_vehicle_category_metrics,
    load_eval_dataset,
)
from flowmate.schemas import ToolCallStatus


class FakeVehicleEvalClient:
    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        if "开到" in user_input:
            return {
                "unsupported": True,
                "reason": "Vehicle movement is unsupported.",
                "plan": None,
            }
        if "路线" in user_input:
            return {
                "unsupported": False,
                "reason": None,
                "plan": {
                    "goal": "Plan route to company.",
                    "risk_level": "HIGH",
                    "requires_confirmation": True,
                    "steps": [
                        {
                            "order": 1,
                            "description": "Plan route.",
                            "tool_name": "navigation_tool",
                            "arguments": {
                                "origin": "home",
                                "destination": "company",
                                "departure_time": "tomorrow morning",
                            },
                        }
                    ],
                },
            }

        action = "unlock" if "解锁" in user_input else "get_status"
        return {
            "unsupported": False,
            "reason": None,
            "plan": {
                "goal": "Use explicit mock vehicle capability.",
                "risk_level": "LOW" if action == "unlock" else "HIGH",
                "requires_confirmation": action != "unlock",
                "steps": [
                    {
                        "order": 1,
                        "description": "Use mock vehicle tool.",
                        "tool_name": "vehicle_tool",
                        "arguments": {"vehicle_id": "my-car", "action": action},
                    }
                ],
            },
        }


def test_vehicle_dataset_loads_with_expected_categories_and_risk_gold():
    cases = load_eval_dataset("evals/planner_vehicle_v1.json")

    assert len(cases) == 24
    assert sum(case.category == "vehicle_status_supported" for case in cases) == 4
    assert sum(case.category == "vehicle_climate_supported" for case in cases) == 6
    assert sum(case.category == "vehicle_lock_supported" for case in cases) == 3
    assert sum(case.category == "vehicle_unlock_supported" for case in cases) == 3
    assert sum(case.category == "vehicle_movement_unsupported" for case in cases) == 3
    assert sum(case.category == "unsupported_vehicle_action" for case in cases) == 2
    assert sum(
        case.category == "scheduled_conditional_unsupported" for case in cases
    ) == 2
    assert sum(case.category == "non_vehicle_minimality" for case in cases) == 1

    vehicle_supported = [
        case for case in cases if case.expected_tools == ["vehicle_tool"]
    ]
    assert len(vehicle_supported) == 16
    assert all(case.expected_risk_level is not None for case in vehicle_supported)
    assert all(
        case.expected_requires_confirmation is not None
        for case in vehicle_supported
    )


def test_vehicle_category_and_high_risk_metrics_do_not_execute_tools():
    cases = [
        PlannerEvalCase(
            id="status",
            category="vehicle_status_supported",
            user_input="查看我的车状态",
            supported=True,
            expected_tools=["vehicle_tool"],
            expected_arguments={
                "vehicle_tool": {"vehicle_id": "my-car", "action": "get_status"}
            },
            expected_risk_level="LOW",
            expected_requires_confirmation=False,
        ),
        PlannerEvalCase(
            id="unlock",
            category="vehicle_unlock_supported",
            user_input="把我的车解锁",
            supported=True,
            expected_tools=["vehicle_tool"],
            expected_arguments={
                "vehicle_tool": {"vehicle_id": "my-car", "action": "unlock"}
            },
            expected_risk_level="HIGH",
            expected_requires_confirmation=True,
        ),
        PlannerEvalCase(
            id="movement",
            category="vehicle_movement_unsupported",
            user_input="把车开到楼下",
            supported=False,
        ),
        PlannerEvalCase(
            id="minimality",
            category="non_vehicle_minimality",
            user_input="我自己开车去公司，帮我规划路线",
            supported=True,
            expected_tools=["navigation_tool"],
            expected_arguments={
                "navigation_tool": {
                    "origin": "home",
                    "destination": "company",
                    "departure_time": "tomorrow morning",
                }
            },
        ),
    ]
    planner = LLMPlanner(FakeVehicleEvalClient())

    results, metrics = PlannerEvaluator().evaluate_dataset(planner, cases)
    category_metrics = calculate_vehicle_category_metrics(results, metrics)

    assert metrics.action_risk_accuracy == 1.0
    assert category_metrics.high_risk_classification_accuracy == 1.0
    assert category_metrics.vehicle_status_supported_recall == 1.0
    assert category_metrics.vehicle_unlock_supported_recall == 1.0
    assert category_metrics.vehicle_movement_unsupported_recall == 1.0
    assert category_metrics.vehicle_minimality_accuracy == 1.0
    assert all(result.schema_valid for result in results)

    planned_status = planner.plan("查看我的车状态")
    planned_unlock = planner.plan("把我的车解锁")
    assert planned_status.steps[0].tool_call.status == ToolCallStatus.PENDING
    assert planned_status.steps[0].tool_call.result is None
    assert planned_unlock.steps[0].tool_call.status == ToolCallStatus.PENDING
    assert planned_unlock.steps[0].tool_call.result is None
