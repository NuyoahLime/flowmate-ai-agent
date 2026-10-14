import json
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from flowmate.agent import LLMPlanner, UnsupportedPlanningScenarioError
from flowmate.eval import (
    PlannerEvalChangeType,
    PlannerEvaluator,
    calculate_planner_v3_capability_metrics,
    load_eval_dataset,
    load_planner_eval_audit,
)
from flowmate.schemas import PlanStep, RiskLevel, Task, TaskStatus, ToolCall


V2_SHA256 = "000991cbfa56e4a38d1e6e7e79b8081b73b13e0cab5af4418d0cffc6e1fcad0f"
V3_CATEGORIES = {
    "weather_supported",
    "navigation_supported",
    "calendar_read_supported",
    "notification_immediate_supported",
    "smart_home_supported",
    "vehicle_supported",
    "scheduled_automation_unsupported",
    "conditional_automation_unsupported",
    "unsupported_smart_home",
    "unsupported_vehicle_movement",
    "unsupported_vehicle_action_or_telemetry",
    "calendar_write_unsupported",
}
PLANNER_TOOLS = {
    "weather_tool",
    "navigation_tool",
    "calendar_tool",
    "notification_tool",
    "smart_home_tool",
    "vehicle_tool",
}


class UnusedLLMClient:
    def generate_plan(self, user_input: str, system_prompt: str):
        raise AssertionError("This client should not be called.")


class GoldPlanner:
    def __init__(self, cases):
        self.cases = {case.user_input: case for case in cases}

    def plan(self, user_input: str) -> Task:
        case = self.cases[user_input]
        if not case.supported:
            raise UnsupportedPlanningScenarioError("Gold case is unsupported.")

        return Task(
            id=f"task-{uuid4()}",
            user_input=user_input,
            goal="Return the V3 gold static plan.",
            status=TaskStatus.PLANNED,
            risk_level=case.expected_risk_level or RiskLevel.LOW,
            requires_confirmation=case.expected_requires_confirmation or False,
            steps=[
                PlanStep(
                    id=f"step-{uuid4()}",
                    order=order,
                    description=f"Use {tool_name}.",
                    tool_name=tool_name,
                    tool_call=ToolCall(
                        tool_name=tool_name,
                        arguments=case.expected_arguments[tool_name],
                    ),
                )
                for order, tool_name in enumerate(case.expected_tools, start=1)
            ],
        )


def load_v3():
    return load_eval_dataset("evals/planner_eval_v3.json")


def test_v3_dataset_loads_with_unique_ids_and_expected_categories():
    cases = load_v3()

    assert len(cases) == 38
    assert len({case.id for case in cases}) == 38
    assert {case.category for case in cases} == V3_CATEGORIES
    assert sum(case.supported for case in cases) == 26
    assert sum(not case.supported for case in cases) == 12


def test_v3_expected_tools_are_current_planner_authorized_tools():
    planner = LLMPlanner(UnusedLLMClient())
    cases = load_v3()

    assert planner.allowed_tools == PLANNER_TOOLS
    assert all(
        tool_name in planner.allowed_tools
        for case in cases
        for tool_name in case.expected_tools
    )


def test_v3_current_smart_home_gold_matches_stage_18_1_contract():
    case = next(case for case in load_v3() if case.id == "unsupported-smart-home-001")

    assert case.supported is True
    assert case.expected_tools == ["smart_home_tool"]
    assert case.expected_arguments == {
        "smart_home_tool": {
            "device_id": "living-room-light",
            "device_type": "light",
            "action": "turn_off",
        }
    }
    assert case.expected_risk_level == RiskLevel.MEDIUM
    assert case.expected_requires_confirmation is True


def test_v3_vehicle_supported_actions_match_current_contract():
    cases = [case for case in load_v3() if case.category == "vehicle_supported"]

    actions = {
        case.expected_arguments["vehicle_tool"]["action"] for case in cases
    }
    assert actions == {"get_status", "start_climate", "stop_climate", "lock", "unlock"}
    assert len(cases) == 6


def test_v3_navigation_preserves_explicit_time_and_location_constraints():
    cases = {case.id: case for case in load_v3()}

    assert cases["v3-navigation-explicit-constraints-001"].expected_arguments == {
        "navigation_tool": {
            "origin": "心理所",
            "destination": "人民广场",
            "departure_time": "tomorrow 09:00",
        }
    }
    assert cases["v3-navigation-explicit-constraints-002"].expected_arguments == {
        "navigation_tool": {
            "origin": "学校",
            "destination": "company",
            "departure_time": "tomorrow 18:00",
        }
    }


def test_v3_unsupported_boundaries_remain_unsupported():
    cases = load_v3()
    unsupported_categories = {
        "scheduled_automation_unsupported",
        "conditional_automation_unsupported",
        "unsupported_smart_home",
        "unsupported_vehicle_movement",
        "unsupported_vehicle_action_or_telemetry",
        "calendar_write_unsupported",
    }
    boundary_cases = [case for case in cases if case.category in unsupported_categories]

    assert boundary_cases
    assert all(case.supported is False for case in boundary_cases)
    assert all(case.expected_tools == [] for case in boundary_cases)
    telemetry = next(case for case in cases if case.id == "unsupported-vehicle-002")
    assert "油" in telemetry.user_input
    assert telemetry.supported is False


def test_v3_tool_minimality_gold_covers_all_six_tools():
    cases = {case.id: case for case in load_v3()}
    minimality_gold = {
        "v3-weather-001": ["weather_tool"],
        "v3-navigation-001": ["navigation_tool"],
        "v3-calendar-001": ["calendar_tool"],
        "v3-notification-001": ["notification_tool"],
        "unsupported-smart-home-001": ["smart_home_tool"],
        "v3-vehicle-001": ["vehicle_tool"],
    }

    assert {
        case_id: cases[case_id].expected_tools for case_id in minimality_gold
    } == minimality_gold


def test_v2_file_is_preserved_byte_for_byte():
    payload = Path("evals/planner_eval_v2.json").read_bytes()

    assert sha256(payload).hexdigest() == V2_SHA256
    assert len(load_eval_dataset("evals/planner_eval_v2.json")) == 22


def test_manifest_marks_v2_historical_and_v3_current():
    manifest = json.loads(Path("evals/manifest.json").read_text(encoding="utf-8"))
    datasets = manifest["datasets"]

    assert datasets["planner_eval_v1.json"]["status"] == "historical_baseline"
    assert (
        datasets["planner_eval_v2.json"]["status"]
        == "historical_capability_baseline"
    )
    assert datasets["planner_eval_v3.json"]["status"] == "current_capability_baseline"


def test_v2_to_v3_audit_covers_all_v2_cases_and_allowed_change_types():
    records = load_planner_eval_audit("evals/planner_eval_v2_to_v3_audit.json")
    v2_cases = load_eval_dataset("evals/planner_eval_v2.json")

    assert len(records) == len(v2_cases) == 22
    assert {record.case_id for record in records} == {case.id for case in v2_cases}
    assert all(
        record.change_type
        in {
            PlannerEvalChangeType.UNCHANGED,
            PlannerEvalChangeType.CAPABILITY_DRIVEN_RELABEL,
            PlannerEvalChangeType.CAPABILITY_DRIVEN_PARAMETER_UPDATE,
        }
        for record in records
    )


def test_audit_has_one_capability_relabel_and_no_model_driven_change():
    records = load_planner_eval_audit("evals/planner_eval_v2_to_v3_audit.json")
    changed = [
        record for record in records if record.change_type != PlannerEvalChangeType.UNCHANGED
    ]

    assert [record.case_id for record in changed] == ["unsupported-smart-home-001"]
    record = changed[0]
    assert record.change_type == PlannerEvalChangeType.CAPABILITY_DRIVEN_RELABEL
    assert record.v2_supported is False
    assert record.v2_expected_tools == []
    assert record.v3_supported is True
    assert record.v3_expected_tools == ["smart_home_tool"]
    assert record.source_stage == "Stage 18.1"


def test_generic_planner_evaluator_scores_complete_v3_gold_baseline():
    cases = load_v3()

    results, metrics = PlannerEvaluator().evaluate_dataset(GoldPlanner(cases), cases)
    capability_metrics = calculate_planner_v3_capability_metrics(results)

    assert metrics.cases == 38
    assert metrics.scenario_accuracy == 1.0
    assert metrics.supported_recall == 1.0
    assert metrics.unsupported_recall == 1.0
    assert metrics.tool_selection_accuracy == 1.0
    assert metrics.parameter_accuracy == 1.0
    assert metrics.parameter_completeness == 1.0
    assert metrics.schema_valid_rate == 1.0
    assert metrics.extra_tool_rate == 0.0
    assert metrics.action_risk_accuracy == 1.0
    assert capability_metrics.current_capability_accuracy == 1.0
    assert all(
        value == 1.0
        for value in capability_metrics.model_dump().values()
    )
