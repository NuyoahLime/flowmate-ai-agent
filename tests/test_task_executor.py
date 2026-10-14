import pytest

from flowmate.agent import StepExecutor, TaskExecutionError, TaskExecutor, ToolExecutor
from flowmate.schemas import PlanStep, Task, TaskStatus, ToolCall, ToolCallStatus
from flowmate.tools import create_default_registry


USER_INPUT = "明天早上八点半在公司开会，帮我安排好明早出门"
GOAL = "安排明早出门，确保按时到达公司参加八点半会议"


def create_task_executor() -> TaskExecutor:
    tool_executor = ToolExecutor(create_default_registry())
    return TaskExecutor(StepExecutor(tool_executor))


def create_weather_step(
    order: int = 1,
    arguments: dict | None = None,
) -> PlanStep:
    return PlanStep(
        id="step-weather",
        order=order,
        description="检查明早天气",
        tool_name="weather_tool",
        tool_call=ToolCall(
            tool_name="weather_tool",
            arguments=arguments or {"location": "Shanghai", "date": "tomorrow"},
        ),
    )


def create_navigation_step(order: int = 2) -> PlanStep:
    return PlanStep(
        id="step-navigation",
        order=order,
        description="计算到公司的通勤时间",
        tool_name="navigation_tool",
        tool_call=ToolCall(
            tool_name="navigation_tool",
            arguments={
                "origin": "home",
                "destination": "company",
                "departure_time": "tomorrow 07:30",
            },
        ),
    )


def create_planned_task(
    steps: list[PlanStep] | None = None,
    status: TaskStatus = TaskStatus.PLANNED,
    requires_confirmation: bool = False,
) -> Task:
    return Task(
        id="task-morning-commute",
        user_input=USER_INPUT,
        goal=GOAL,
        status=status,
        risk_level="MEDIUM",
        requires_confirmation=requires_confirmation,
        steps=steps if steps is not None else [create_weather_step(), create_navigation_step()],
    )


def test_two_successful_steps_complete_task():
    executor = create_task_executor()
    task = create_planned_task()

    executed = executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED


def test_task_final_status_is_completed_after_success():
    executor = create_task_executor()
    task = create_planned_task()

    executed = executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED


def test_steps_execute_by_order_not_list_order():
    executor = create_task_executor()
    navigation_step = create_navigation_step(order=2)
    failing_weather_step = create_weather_step(order=1, arguments={"date": "tomorrow"})
    task = create_planned_task(steps=[navigation_step, failing_weather_step])

    executed = executor.execute(task)

    assert executed.status == TaskStatus.FAILED
    assert failing_weather_step.status == ToolCallStatus.FAILED
    assert navigation_step.status == ToolCallStatus.PENDING
    assert navigation_step.tool_call.status == ToolCallStatus.PENDING


def test_first_step_failure_marks_task_failed():
    executor = create_task_executor()
    task = create_planned_task(
        steps=[
            create_weather_step(order=1, arguments={"date": "tomorrow"}),
            create_navigation_step(order=2),
        ]
    )

    executed = executor.execute(task)

    assert executed.status == TaskStatus.FAILED


def test_step_failure_stops_later_steps():
    executor = create_task_executor()
    failing_step = create_weather_step(order=1, arguments={"date": "tomorrow"})
    later_step = create_navigation_step(order=2)
    task = create_planned_task(steps=[failing_step, later_step])

    executor.execute(task)

    assert failing_step.status == ToolCallStatus.FAILED
    assert later_step.status == ToolCallStatus.PENDING
    assert later_step.tool_call.status == ToolCallStatus.PENDING


def test_empty_steps_task_does_not_complete():
    executor = create_task_executor()
    task = create_planned_task(steps=[])

    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert task.status == TaskStatus.PLANNED


def test_created_task_cannot_execute_directly():
    executor = create_task_executor()
    task = create_planned_task(status=TaskStatus.CREATED)

    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert task.status == TaskStatus.CREATED


def test_completed_task_cannot_execute_again():
    executor = create_task_executor()
    task = create_planned_task(status=TaskStatus.COMPLETED)

    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert task.status == TaskStatus.COMPLETED


def test_task_requiring_confirmation_does_not_execute():
    executor = create_task_executor()
    task = create_planned_task(requires_confirmation=True)

    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert task.status == TaskStatus.PLANNED
    assert task.requires_confirmation is True
    assert task.steps[0].status == ToolCallStatus.PENDING


def test_waiting_confirmation_task_does_not_execute():
    executor = create_task_executor()
    task = create_planned_task(status=TaskStatus.WAITING_CONFIRMATION)

    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert task.status == TaskStatus.WAITING_CONFIRMATION
    assert task.steps[0].status == ToolCallStatus.PENDING


def test_successful_task_updates_all_step_and_tool_call_statuses():
    executor = create_task_executor()
    task = create_planned_task()

    executed = executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED
    assert all(step.status == ToolCallStatus.SUCCESS for step in executed.steps)
    assert all(step.tool_call.status == ToolCallStatus.SUCCESS for step in executed.steps)


def test_task_identity_fields_are_preserved():
    executor = create_task_executor()
    task = create_planned_task()

    executed = executor.execute(task)

    assert executed.id == "task-morning-commute"
    assert executed.user_input == USER_INPUT
    assert executed.goal == GOAL
