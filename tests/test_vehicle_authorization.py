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
    VehicleTool,
    WeatherTool,
)


class FakeVehicleLLMClient:
    def __init__(self, arguments: dict[str, Any]) -> None:
        self.arguments = arguments

    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        return {
            "unsupported": False,
            "reason": None,
            "plan": {
                "goal": "Perform explicit immediate mock vehicle action.",
                "risk_level": "LOW",
                "requires_confirmation": False,
                "steps": [
                    {
                        "order": 1,
                        "description": "Use supported mock vehicle capability.",
                        "tool_name": "vehicle_tool",
                        "arguments": self.arguments,
                    }
                ],
            },
        }


class CountingVehicleTool(VehicleTool):
    def __init__(self) -> None:
        self.execution_count = 0

    def execute(self, input_data):
        self.execution_count += 1
        return super().execute(input_data)


def create_authorization_stack(arguments: dict[str, Any]):
    vehicle_tool = CountingVehicleTool()
    registry = ToolRegistry()
    registry.register(WeatherTool())
    registry.register(NavigationTool())
    registry.register(CalendarTool())
    registry.register(NotificationTool())
    registry.register(SmartHomeTool())
    registry.register(vehicle_tool)

    task = LLMPlanner(
        FakeVehicleLLMClient(arguments),
        tool_registry=registry,
    ).plan("explicit immediate vehicle request")
    executor = TaskExecutor(StepExecutor(ToolExecutor(registry)))
    return task, executor, vehicle_tool


def vehicle_arguments(action: str, temperature: int | None = None) -> dict[str, Any]:
    arguments: dict[str, Any] = {"vehicle_id": "my-car", "action": action}
    if temperature is not None:
        arguments["temperature"] = temperature
    return arguments


def confirm_and_execute(task, executor):
    confirmation = TaskConfirmationService()
    confirmation.request_confirmation(task)
    confirmation.confirm(task)
    return executor.execute(task)


def test_get_status_is_low_risk_and_executes_without_confirmation():
    task, executor, vehicle_tool = create_authorization_stack(
        vehicle_arguments("get_status")
    )

    assert task.risk_level == "LOW"
    assert task.requires_confirmation is False
    assert task.confirmation_status == ConfirmationStatus.NOT_REQUIRED

    executed = executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED
    assert executed.steps[0].tool_call.result["state"] == {
        "locked": True,
        "climate": "off",
    }
    assert vehicle_tool.execution_count == 1


def test_start_climate_pending_is_blocked_with_zero_execution():
    task, executor, vehicle_tool = create_authorization_stack(
        vehicle_arguments("start_climate", temperature=24)
    )

    assert task.risk_level == "MEDIUM"
    assert task.requires_confirmation is True
    assert task.confirmation_status == ConfirmationStatus.PENDING
    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert vehicle_tool.execution_count == 0


def test_start_climate_confirm_executes_once_with_temperature():
    task, executor, vehicle_tool = create_authorization_stack(
        vehicle_arguments("start_climate", temperature=24)
    )

    executed = confirm_and_execute(task, executor)

    assert executed.status == TaskStatus.COMPLETED
    assert executed.steps[0].tool_call.result["status"] == "mock_executed"
    assert executed.steps[0].tool_call.result["state"] == {
        "climate": "on",
        "temperature": 24,
    }
    assert vehicle_tool.execution_count == 1


def test_unlock_pending_is_blocked_with_zero_execution():
    task, executor, vehicle_tool = create_authorization_stack(
        vehicle_arguments("unlock")
    )

    assert task.risk_level == "HIGH"
    assert task.requires_confirmation is True
    assert task.confirmation_status == ConfirmationStatus.PENDING
    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert vehicle_tool.execution_count == 0


def test_unlock_confirm_executes_once_and_cannot_repeat():
    task, executor, vehicle_tool = create_authorization_stack(
        vehicle_arguments("unlock")
    )

    executed = confirm_and_execute(task, executor)

    assert executed.status == TaskStatus.COMPLETED
    assert executed.steps[0].tool_call.result["status"] == "mock_executed"
    assert executed.steps[0].tool_call.result["state"] == {"locked": False}
    assert vehicle_tool.execution_count == 1

    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert vehicle_tool.execution_count == 1


def test_unlock_reject_is_contained_with_zero_execution():
    task, executor, vehicle_tool = create_authorization_stack(
        vehicle_arguments("unlock")
    )
    confirmation = TaskConfirmationService()

    confirmation.request_confirmation(task)
    confirmation.reject(task)

    assert task.status == TaskStatus.CANCELLED
    assert task.confirmation_status == ConfirmationStatus.REJECTED
    with pytest.raises(TaskExecutionError):
        executor.execute(task)

    assert vehicle_tool.execution_count == 0


def test_lock_is_high_risk_blocked_then_confirmed_once():
    task, executor, vehicle_tool = create_authorization_stack(vehicle_arguments("lock"))

    assert task.risk_level == "HIGH"
    assert task.requires_confirmation is True
    with pytest.raises(TaskExecutionError):
        executor.execute(task)
    assert vehicle_tool.execution_count == 0

    executed = confirm_and_execute(task, executor)

    assert executed.status == TaskStatus.COMPLETED
    assert executed.steps[0].tool_call.result["state"] == {"locked": True}
    assert vehicle_tool.execution_count == 1
