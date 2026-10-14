import pytest
from pydantic import ValidationError

from flowmate.schemas import (
    ConfirmationStatus,
    PlanStep,
    RiskLevel,
    Task,
    TaskStatus,
    ToolCall,
    ToolCallStatus,
)


def test_can_create_task():
    task = Task(
        id="task-001",
        user_input="明天早上八点半在公司开会，帮我安排好明早出门",
        goal="安排明早出门",
    )

    assert task.status == TaskStatus.CREATED
    assert task.risk_level == RiskLevel.LOW
    assert task.requires_confirmation is False
    assert task.confirmation_status == ConfirmationStatus.NOT_REQUIRED
    assert task.steps == []


def test_can_create_task_with_multiple_plan_steps():
    task = Task(
        id="task-002",
        user_input="明天早上八点半在公司开会，帮我安排好明早出门",
        goal="安排明早出门",
        status=TaskStatus.PLANNED,
        risk_level=RiskLevel.MEDIUM,
        requires_confirmation=True,
        steps=[
            PlanStep(
                id="step-001",
                order=1,
                description="检查明早天气",
                tool_name="weather_tool",
                tool_call=ToolCall(
                    tool_name="weather_tool",
                    arguments={"date": "tomorrow_morning", "location": "current_city"},
                ),
            ),
            PlanStep(
                id="step-002",
                order=2,
                description="估算去公司的通勤时间",
                tool_name="navigation_tool",
                tool_call=ToolCall(
                    tool_name="navigation_tool",
                    arguments={"destination": "company", "arrival_time": "08:30"},
                ),
            ),
        ],
    )

    assert len(task.steps) == 2
    assert task.steps[0].tool_name == "weather_tool"
    assert task.steps[1].tool_name == "navigation_tool"


def test_risk_level_enum_is_valid():
    task = Task(
        id="task-003",
        user_input="今晚孩子回家后，把家里调整成适合学习的状态。",
        goal="调整家庭学习环境",
        risk_level=RiskLevel.HIGH,
        requires_confirmation=True,
    )

    assert task.risk_level == RiskLevel.HIGH


def test_invalid_status_fails_validation():
    with pytest.raises(ValidationError):
        Task(
            id="task-004",
            user_input="我晚上七点到家，提前把家里准备好。",
            goal="提前准备家庭环境",
            status="INVALID_STATUS",
        )


def test_tool_call_can_store_arguments():
    tool_call = ToolCall(
        tool_name="calendar_tool",
        arguments={"event": "company_meeting", "time": "08:30"},
    )

    assert tool_call.arguments["event"] == "company_meeting"
    assert tool_call.arguments["time"] == "08:30"


def test_failed_tool_call_can_store_error():
    tool_call = ToolCall(
        tool_name="navigation_tool",
        arguments={"destination": "company"},
        status=ToolCallStatus.FAILED,
        error="Unable to calculate route.",
    )

    assert tool_call.status == ToolCallStatus.FAILED
    assert tool_call.error == "Unable to calculate route."


def test_task_without_confirmation_defaults_to_not_required():
    task = Task(
        id="task-no-confirmation",
        user_input="我晚上七点到家，提前把家里准备好。",
        goal="提前准备家庭环境",
        requires_confirmation=False,
    )

    assert task.confirmation_status == ConfirmationStatus.NOT_REQUIRED


def test_task_requiring_confirmation_defaults_to_pending():
    task = Task(
        id="task-requires-confirmation",
        user_input="今晚孩子回家后，把家里调整成适合学习的状态。",
        goal="调整家庭学习环境",
        requires_confirmation=True,
    )

    assert task.confirmation_status == ConfirmationStatus.PENDING


def test_task_requiring_confirmation_does_not_need_manual_pending_status():
    task = Task(
        id="task-auto-pending",
        user_input="明天早上八点半在公司开会，帮我安排好明早出门",
        goal="安排明早出门",
        status=TaskStatus.PLANNED,
        risk_level=RiskLevel.MEDIUM,
        requires_confirmation=True,
    )

    assert task.requires_confirmation is True
    assert task.confirmation_status == ConfirmationStatus.PENDING


def test_task_normalizes_conflicting_not_required_status_when_confirmation_is_required():
    task = Task(
        id="task-conflict",
        user_input="明天早上八点半在公司开会，帮我安排好明早出门",
        goal="安排明早出门",
        requires_confirmation=True,
        confirmation_status=ConfirmationStatus.NOT_REQUIRED,
    )

    assert task.confirmation_status == ConfirmationStatus.PENDING


def test_task_normalizes_confirmation_status_when_confirmation_is_not_required():
    task = Task(
        id="task-no-confirmation-conflict",
        user_input="我晚上七点到家，提前把家里准备好。",
        goal="提前准备家庭环境",
        requires_confirmation=False,
        confirmation_status=ConfirmationStatus.PENDING,
    )

    assert task.confirmation_status == ConfirmationStatus.NOT_REQUIRED
