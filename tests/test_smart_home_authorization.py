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
    SmartHomeTool,
    ToolRegistry,
    WeatherTool,
)


class FakeSmartHomeLLMClient:
    def __init__(self, arguments: dict[str, Any]) -> None:
        self.arguments = arguments

    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        return {
            "unsupported": False,
            "reason": None,
            "plan": {
                "goal": "Perform explicit immediate mock smart-home control.",
                "risk_level": "LOW",
                "requires_confirmation": False,
                "steps": [
                    {
                        "order": 1,
                        "description": "Control supported mock smart-home device.",
                        "tool_name": "smart_home_tool",
                        "arguments": self.arguments,
                    }
                ],
            },
        }


class CountingSmartHomeTool(SmartHomeTool):
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, input_data):
        self.execution_count += 1
        return super().execute(input_data)


def create_authorization_stack(arguments: dict[str, Any]):
    smart_home_tool = CountingSmartHomeTool()
    registry = ToolRegistry()
    registry.register(WeatherTool())
    registry.register(NavigationTool())
    registry.register(CalendarTool())
    registry.register(NotificationTool())
    registry.register(smart_home_tool)

    planner = LLMPlanner(
        FakeSmartHomeLLMClient(arguments),
        tool_registry=registry,
    )
    task = planner.plan("explicit immediate smart-home request")
    executor = TaskExecutor(StepExecutor(ToolExecutor(registry)))
    return task, executor, smart_home_tool


def light_arguments(action: str = "turn_off") -> dict[str, Any]:
    return {
        "device_id": "living-room-light",
        "device_type": "light",
        "action": action,
    }


def test_pending_smart_home_task_is_blocked_with_zero_execution():
    task, executor, smart_home_tool = create_authorization_stack(light_arguments())

    assert task.status == TaskStatus.PLANNED
    assert task.risk_level == "MEDIUM"
    assert task.requires_confirmation is True
    assert task.confirmation_status == ConfirmationStatus.PENDING

    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert smart_home_tool.execution_count == 0


def test_confirmed_smart_home_task_executes_exactly_once():
    task, executor, smart_home_tool = create_authorization_stack(
        light_arguments("turn_on")
    )
    confirmation = TaskConfirmationService()

    confirmation.request_confirmation(task)
    confirmation.confirm(task)
    executed = executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED
    assert executed.steps[0].tool_call.result["status"] == "mock_executed"
    assert executed.steps[0].tool_call.result["state"] == {"power": "on"}
    assert smart_home_tool.execution_count == 1

    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert smart_home_tool.execution_count == 1


def test_rejected_smart_home_task_is_cancelled_with_zero_execution():
    task, executor, smart_home_tool = create_authorization_stack(light_arguments())
    confirmation = TaskConfirmationService()

    confirmation.request_confirmation(task)
    confirmation.reject(task)

    assert task.status == TaskStatus.CANCELLED
    assert task.confirmation_status == ConfirmationStatus.REJECTED
    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert smart_home_tool.execution_count == 0


def test_confirmed_ac_temperature_executes_once_with_requested_value():
    task, executor, smart_home_tool = create_authorization_stack(
        {
            "device_id": "bedroom-ac",
            "device_type": "air_conditioner",
            "action": "set_temperature",
            "value": 24,
        }
    )
    confirmation = TaskConfirmationService()

    confirmation.request_confirmation(task)
    confirmation.confirm(task)
    executed = executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED
    assert executed.steps[0].tool_call.arguments["value"] == 24
    assert executed.steps[0].tool_call.result["state"] == {"temperature": 24}
    assert executed.steps[0].tool_call.result["status"] == "mock_executed"
    assert smart_home_tool.execution_count == 1
