import pytest

from flowmate.agent import (
    RuleBasedPlanner,
    StepExecutor,
    TaskExecutor,
    ToolExecutor,
    UnsupportedPlanningScenarioError,
)
from flowmate.schemas import ConfirmationStatus, Task, TaskStatus, ToolCallStatus
from flowmate.tools import create_default_registry


STANDARD_INPUT = "我明天早上八点半在公司开会，帮我安排好明早出门"


def test_standard_morning_commute_input_generates_task():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert isinstance(task, Task)


def test_supported_morning_commute_variants_generate_task():
    planner = RuleBasedPlanner()

    inputs = [
        "明早要去公司开会，帮我安排出门",
        "明天上班帮我安排一下通勤",
    ]

    for user_input in inputs:
        assert isinstance(planner.plan(user_input), Task)


def test_planned_task_status_is_planned():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert task.status == TaskStatus.PLANNED


def test_planned_task_has_two_steps():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert len(task.steps) == 2


def test_step_orders_are_one_and_two():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert [step.order for step in task.steps] == [1, 2]


def test_step_one_uses_weather_tool():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert task.steps[0].tool_name == "weather_tool"


def test_step_two_uses_navigation_tool():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert task.steps[1].tool_name == "navigation_tool"


def test_both_steps_have_tool_calls():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert all(step.tool_call is not None for step in task.steps)


def test_weather_arguments_are_correct():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert task.steps[0].tool_call.arguments == {
        "location": "current_city",
        "date": "tomorrow",
    }


def test_navigation_arguments_are_correct():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert task.steps[1].tool_call.arguments == {
        "origin": "home",
        "destination": "company",
        "departure_time": "tomorrow morning",
    }


def test_task_preserves_original_user_input():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert task.user_input == STANDARD_INPUT


def test_task_does_not_require_confirmation():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert task.requires_confirmation is False


def test_task_confirmation_status_is_not_required():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    assert task.confirmation_status == ConfirmationStatus.NOT_REQUIRED


def test_unsupported_scenario_raises_clear_error():
    planner = RuleBasedPlanner()

    with pytest.raises(UnsupportedPlanningScenarioError):
        planner.plan("帮我把客厅灯关掉")


def test_planner_does_not_execute_any_tool():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    for step in task.steps:
        assert step.status == ToolCallStatus.PENDING
        assert step.tool_call.status == ToolCallStatus.PENDING
        assert step.tool_call.result is None
        assert step.tool_call.error is None


def test_generated_result_validates_against_task_schema():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)

    validated = Task.model_validate(task.model_dump())

    assert isinstance(validated, Task)


def test_planner_task_executor_integration_completes_task():
    task = RuleBasedPlanner().plan(STANDARD_INPUT)
    registry = create_default_registry()
    task_executor = TaskExecutor(StepExecutor(ToolExecutor(registry)))

    executed = task_executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED
    assert all(step.status == ToolCallStatus.SUCCESS for step in executed.steps)
    assert all(step.tool_call.status == ToolCallStatus.SUCCESS for step in executed.steps)
