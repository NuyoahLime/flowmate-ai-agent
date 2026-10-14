from typing import Any, Mapping

import pytest

from flowmate.agent import (
    LLMPlanner,
    StepExecutor,
    TaskConfirmationService,
    TaskExecutionError,
    TaskExecutor,
    ToolExecutor,
)
from flowmate.schemas import ConfirmationStatus, TaskStatus
from flowmate.tools import (
    CalendarTool,
    NavigationTool,
    NotificationTool,
    ToolRegistry,
    WeatherTool,
)


class FakeLLMClient:
    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        return {
            "unsupported": False,
            "reason": None,
            "plan": {
                "goal": "Send immediate notification.",
                "risk_level": "LOW",
                "requires_confirmation": False,
                "steps": [
                    {
                        "order": 1,
                        "description": "Send notification.",
                        "tool_name": "notification_tool",
                        "arguments": {
                            "title": "Morning commute",
                            "message": "Your route is ready.",
                            "channel": "mobile",
                        },
                    }
                ],
            },
        }


class CountingNotificationTool(NotificationTool):
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, input_data):
        self.execution_count += 1
        return super().execute(input_data)


def create_registry(notification_tool: CountingNotificationTool) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(WeatherTool())
    registry.register(NavigationTool())
    registry.register(CalendarTool())
    registry.register(notification_tool)
    return registry


def create_notification_task(notification_tool: CountingNotificationTool):
    registry = create_registry(notification_tool)
    planner = LLMPlanner(FakeLLMClient(), tool_registry=registry)
    return planner.plan("send me a notification now")


def create_task_executor(notification_tool: CountingNotificationTool) -> TaskExecutor:
    registry = create_registry(notification_tool)
    return TaskExecutor(StepExecutor(ToolExecutor(registry)))


def test_pending_notification_task_is_blocked_before_confirmation():
    notification_tool = CountingNotificationTool()
    task = create_notification_task(notification_tool)
    executor = create_task_executor(notification_tool)

    assert task.risk_level == "MEDIUM"
    assert task.requires_confirmation is True
    assert task.confirmation_status == ConfirmationStatus.PENDING

    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert notification_tool.execution_count == 0


def test_confirmed_notification_task_executes_once():
    notification_tool = CountingNotificationTool()
    task = create_notification_task(notification_tool)
    service = TaskConfirmationService()
    executor = create_task_executor(notification_tool)

    service.request_confirmation(task)
    assert task.status == TaskStatus.WAITING_CONFIRMATION
    service.confirm(task)
    assert task.status == TaskStatus.PLANNED
    assert task.confirmation_status == ConfirmationStatus.CONFIRMED

    executed = executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED
    assert notification_tool.execution_count == 1
    assert executed.steps[0].tool_call.result["status"] == "mock_delivered"


def test_rejected_notification_task_never_executes():
    notification_tool = CountingNotificationTool()
    task = create_notification_task(notification_tool)
    service = TaskConfirmationService()
    executor = create_task_executor(notification_tool)

    service.request_confirmation(task)
    service.reject(task)

    assert task.status == TaskStatus.CANCELLED
    assert task.confirmation_status == ConfirmationStatus.REJECTED
    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert notification_tool.execution_count == 0
