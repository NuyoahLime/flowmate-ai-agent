from flowmate.agent import ToolExecutor
from flowmate.schemas import ToolCall, ToolCallStatus
from flowmate.tools import create_default_registry


def test_registry_to_executor_turns_off_mock_living_room_light():
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
    assert executed.result == {
        "device_id": "living-room-light",
        "device_type": "light",
        "action": "turn_off",
        "status": "mock_executed",
        "state": {"power": "off"},
    }


def test_registry_to_executor_sets_mock_bedroom_ac_temperature():
    executor = ToolExecutor(create_default_registry())
    tool_call = ToolCall(
        tool_name="smart_home_tool",
        arguments={
            "device_id": "bedroom-ac",
            "device_type": "air_conditioner",
            "action": "set_temperature",
            "value": 24,
        },
    )

    first = executor.execute(tool_call)
    second = executor.execute(
        ToolCall(tool_name="smart_home_tool", arguments=tool_call.arguments.copy())
    )

    assert first.status == ToolCallStatus.SUCCESS
    assert first.result == second.result
    assert first.result["state"] == {"temperature": 24}
