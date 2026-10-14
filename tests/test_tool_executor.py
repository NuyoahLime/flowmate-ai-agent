import pytest
from pydantic import BaseModel

from flowmate.agent import ToolExecutor
from flowmate.schemas import ToolCall, ToolCallStatus
from flowmate.tools import BaseTool, ToolRegistry, WeatherTool, create_default_registry


def test_execute_weather_tool_successfully():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="weather_tool",
        arguments={"location": "Shanghai", "date": "tomorrow"},
    )

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.result["condition"] == "rain"
    assert executed.result["temperature_c"] == 18


def test_execute_navigation_tool_successfully():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="navigation_tool",
        arguments={
            "origin": "home",
            "destination": "company",
            "departure_time": "tomorrow 07:30",
        },
    )

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.result["distance_km"] == 18.6
    assert executed.result["duration_minutes"] == 42
    assert executed.result["traffic"] == "heavy"


def test_successful_tool_call_clears_error():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="weather_tool",
        arguments={"location": "Shanghai", "date": "tomorrow"},
        error="previous error",
    )

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.error is None


def test_successful_tool_call_saves_structured_result_dict():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="weather_tool",
        arguments={"location": "Shanghai", "date": "tomorrow"},
    )

    executed = executor.execute(tool_call)

    assert executed.result == {
        "location": "Shanghai",
        "date": "tomorrow",
        "condition": "rain",
        "temperature_c": 18.0,
        "rain_probability": 0.8,
    }


def test_unknown_tool_marks_tool_call_failed():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(tool_name="missing_tool", arguments={})

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.FAILED
    assert executed.result is None
    assert executed.error


def test_missing_arguments_mark_tool_call_failed():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(tool_name="weather_tool", arguments={"date": "tomorrow"})

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.FAILED
    assert executed.result is None
    assert executed.error


def test_failed_tool_call_keeps_readable_error():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(tool_name="weather_tool", arguments={"date": "tomorrow"})

    executed = executor.execute(tool_call)

    assert "ValidationError" in executed.error
    assert "location" in executed.error


def test_original_arguments_are_preserved_after_success():
    executor = ToolExecutor(create_default_registry())
    arguments = {"location": "Shanghai", "date": "tomorrow"}
    tool_call = ToolCall(tool_name="weather_tool", arguments=arguments.copy())

    executed = executor.execute(tool_call)

    assert executed.arguments == arguments


def test_original_arguments_are_preserved_after_failure():
    executor = ToolExecutor(create_default_registry())
    arguments = {"date": "tomorrow"}
    tool_call = ToolCall(tool_name="weather_tool", arguments=arguments.copy())

    executed = executor.execute(tool_call)

    assert executed.arguments == arguments


def test_executor_can_reuse_same_registry():
    registry = create_default_registry()
    executor = ToolExecutor(registry)

    weather_call = ToolCall(
        tool_name="weather_tool",
        arguments={"location": "Shanghai", "date": "tomorrow"},
    )
    navigation_call = ToolCall(
        tool_name="navigation_tool",
        arguments={
            "origin": "home",
            "destination": "company",
            "departure_time": "tomorrow 07:30",
        },
    )

    assert executor.execute(weather_call).status == ToolCallStatus.SUCCESS
    assert executor.execute(navigation_call).status == ToolCallStatus.SUCCESS


def test_successfully_executes_calendar_tool():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="calendar_tool",
        arguments={"date": "tomorrow", "start_time": "06:00", "end_time": "12:00"},
    )

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.result["event_count"] == 1
    assert executed.result["events"][0]["id"] == "event-001"


def test_successfully_executes_notification_tool():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="notification_tool",
        arguments={
            "title": "Morning commute",
            "message": "Your route is ready.",
            "channel": "mobile",
        },
    )

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.error is None
    assert executed.result["notification_id"].startswith("mock-notification-")
    assert executed.result["channel"] == "mobile"
    assert executed.result["status"] == "mock_delivered"
    assert executed.result["title"] == "Morning commute"
    assert executed.result["message"] == "Your route is ready."


def test_notification_tool_invalid_arguments_fail_through_executor():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="notification_tool",
        arguments={"title": "Morning commute", "channel": "mobile"},
    )

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.FAILED
    assert executed.result is None
    assert executed.error


def test_successfully_executes_smart_home_tool():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="smart_home_tool",
        arguments={
            "device_id": "living-room-light",
            "device_type": "light",
            "action": "turn_off",
        },
    )

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.error is None
    assert executed.result["status"] == "mock_executed"
    assert executed.result["state"] == {"power": "off"}


def test_invalid_smart_home_arguments_fail_through_executor():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="smart_home_tool",
        arguments={
            "device_id": "bedroom-ac",
            "device_type": "air_conditioner",
            "action": "set_temperature",
        },
    )

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.FAILED
    assert executed.result is None
    assert "value" in executed.error


@pytest.mark.parametrize(
    ("arguments", "expected_state"),
    [
        ({"vehicle_id": "my-car", "action": "get_status"}, {"locked": True, "climate": "off"}),
        ({"vehicle_id": "my-car", "action": "lock"}, {"locked": True}),
        (
            {"vehicle_id": "my-car", "action": "start_climate", "temperature": 24},
            {"climate": "on", "temperature": 24},
        ),
    ],
)
def test_successfully_executes_vehicle_tool(arguments, expected_state):
    executor = ToolExecutor(create_default_registry())

    executed = executor.execute(
        ToolCall(tool_name="vehicle_tool", arguments=arguments)
    )

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.error is None
    assert executed.result["status"] == "mock_executed"
    assert executed.result["state"] == expected_state


def test_invalid_vehicle_arguments_fail_through_executor():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="vehicle_tool",
        arguments={"vehicle_id": "my-car", "action": "unlock", "temperature": 24},
    )

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.FAILED
    assert executed.result is None
    assert "temperature" in executed.error


def test_calendar_tool_invalid_arguments_fail_through_executor():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="calendar_tool",
        arguments={"start_time": "06:00", "end_time": "12:00"},
    )

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.FAILED
    assert executed.error


class FailingToolInput(BaseModel):
    value: str


class FailingToolResult(BaseModel):
    value: str


class FailingTool(BaseTool[FailingToolInput, FailingToolResult]):
    name = "failing_tool"
    description = "Test-only tool that raises from execute."
    input_schema = FailingToolInput

    def execute(self, input_data: FailingToolInput) -> FailingToolResult:
        raise RuntimeError("boom")


def test_tool_internal_exception_marks_tool_call_failed():
    registry = ToolRegistry()
    registry.register(WeatherTool())
    registry.register(FailingTool())
    executor = ToolExecutor(registry)
    tool_call = ToolCall(tool_name="failing_tool", arguments={"value": "x"})

    executed = executor.execute(tool_call)

    assert executed.status == ToolCallStatus.FAILED
    assert executed.result is None
    assert "RuntimeError" in executed.error
    assert "boom" in executed.error
