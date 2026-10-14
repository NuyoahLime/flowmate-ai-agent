import pytest

from flowmate.agent import (
    StepExecutor,
    TaskConfirmationError,
    TaskConfirmationService,
    TaskExecutionError,
    TaskExecutor,
    ToolExecutor,
)
from flowmate.schemas import (
    ConfirmationStatus,
    PlanStep,
    RiskLevel,
    Task,
    TaskStatus,
    ToolCall,
    ToolCallStatus,
)
from flowmate.tools import create_default_registry


USER_INPUT = "明天早上八点半在公司开会，帮我安排好明早出门"


def create_confirmation_service() -> TaskConfirmationService:
    return TaskConfirmationService()


def create_task_executor() -> TaskExecutor:
    tool_executor = ToolExecutor(create_default_registry())
    return TaskExecutor(StepExecutor(tool_executor))


def create_confirmable_task(
    status: TaskStatus = TaskStatus.PLANNED,
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING,
) -> Task:
    return Task(
        id="task-confirmation",
        user_input=USER_INPUT,
        goal="启动需要用户确认的跨端任务",
        status=status,
        risk_level=RiskLevel.MEDIUM,
        requires_confirmation=True,
        confirmation_status=confirmation_status,
        steps=[
            PlanStep(
                id="step-weather",
                order=1,
                description="检查明早天气",
                tool_name="weather_tool",
                tool_call=ToolCall(
                    tool_name="weather_tool",
                    arguments={"location": "Shanghai", "date": "tomorrow"},
                ),
            ),
            PlanStep(
                id="step-navigation",
                order=2,
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
            ),
        ],
    )


def test_planned_task_requiring_confirmation_can_enter_waiting_confirmation():
    service = create_confirmation_service()
    task = create_confirmable_task()

    updated = service.request_confirmation(task)

    assert updated.status == TaskStatus.WAITING_CONFIRMATION


def test_request_confirmation_sets_pending_status():
    service = create_confirmation_service()
    task = create_confirmable_task()

    updated = service.request_confirmation(task)

    assert updated.confirmation_status == ConfirmationStatus.PENDING


def test_confirm_sets_confirmation_status_confirmed():
    service = create_confirmation_service()
    task = create_confirmable_task()
    service.request_confirmation(task)

    updated = service.confirm(task)

    assert updated.confirmation_status == ConfirmationStatus.CONFIRMED


def test_confirm_returns_task_to_planned():
    service = create_confirmation_service()
    task = create_confirmable_task()
    service.request_confirmation(task)

    updated = service.confirm(task)

    assert updated.status == TaskStatus.PLANNED


def test_confirmed_task_can_be_executed_by_task_executor():
    service = create_confirmation_service()
    task_executor = create_task_executor()
    task = create_confirmable_task()
    service.request_confirmation(task)
    service.confirm(task)

    executed = task_executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED


def test_pending_confirmation_task_cannot_execute():
    service = create_confirmation_service()
    task_executor = create_task_executor()
    task = create_confirmable_task()
    service.request_confirmation(task)

    with pytest.raises(TaskExecutionError):
        task_executor.execute(task)

    assert task.status == TaskStatus.WAITING_CONFIRMATION


def test_reject_sets_confirmation_status_rejected():
    service = create_confirmation_service()
    task = create_confirmable_task()
    service.request_confirmation(task)

    updated = service.reject(task)

    assert updated.confirmation_status == ConfirmationStatus.REJECTED


def test_reject_sets_task_status_cancelled():
    service = create_confirmation_service()
    task = create_confirmable_task()
    service.request_confirmation(task)

    updated = service.reject(task)

    assert updated.status == TaskStatus.CANCELLED


def test_rejected_task_does_not_execute_any_step():
    service = create_confirmation_service()
    task_executor = create_task_executor()
    task = create_confirmable_task()
    service.request_confirmation(task)
    service.reject(task)

    with pytest.raises(TaskExecutionError):
        task_executor.execute(task)

    assert all(step.status == ToolCallStatus.PENDING for step in task.steps)


def test_task_not_requiring_confirmation_cannot_enter_waiting_confirmation():
    service = create_confirmation_service()
    task = Task(
        id="task-no-confirmation",
        user_input="我晚上七点到家，提前把家里准备好。",
        goal="提前准备家庭环境",
        status=TaskStatus.PLANNED,
        requires_confirmation=False,
        confirmation_status=ConfirmationStatus.NOT_REQUIRED,
        steps=[],
    )

    with pytest.raises(TaskConfirmationError):
        service.request_confirmation(task)

    assert task.status == TaskStatus.PLANNED
    assert task.confirmation_status == ConfirmationStatus.NOT_REQUIRED


def test_completed_task_cannot_request_confirmation_again():
    service = create_confirmation_service()
    task = create_confirmable_task(status=TaskStatus.COMPLETED)

    with pytest.raises(TaskConfirmationError):
        service.request_confirmation(task)

    assert task.status == TaskStatus.COMPLETED


def test_non_waiting_confirmation_task_cannot_be_directly_confirmed():
    service = create_confirmation_service()
    task = create_confirmable_task(status=TaskStatus.PLANNED)

    with pytest.raises(TaskConfirmationError):
        service.confirm(task)

    assert task.status == TaskStatus.PLANNED


def test_confirm_keeps_requires_confirmation_true():
    service = create_confirmation_service()
    task = create_confirmable_task()
    service.request_confirmation(task)

    updated = service.confirm(task)

    assert updated.requires_confirmation is True
