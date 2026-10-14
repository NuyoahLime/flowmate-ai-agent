import pytest

from flowmate.agent import ToolExecutor
from flowmate.schemas import ToolCall, ToolCallStatus
from flowmate.tools import create_default_registry


@pytest.mark.parametrize(
    ("arguments", "expected_state"),
    [
        (
            {"vehicle_id": "my-car", "action": "get_status"},
            {"locked": True, "climate": "off"},
        ),
        (
            {"vehicle_id": "my-car", "action": "lock"},
            {"locked": True},
        ),
        (
            {
                "vehicle_id": "my-car",
                "action": "start_climate",
                "temperature": 24,
            },
            {"climate": "on", "temperature": 24},
        ),
    ],
)
def test_registry_to_executor_vehicle_infrastructure(arguments, expected_state):
    executor = ToolExecutor(create_default_registry())

    executed = executor.execute(
        ToolCall(tool_name="vehicle_tool", arguments=arguments)
    )

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.error is None
    assert executed.result["status"] == "mock_executed"
    assert executed.result["state"] == expected_state
