import socket

import pytest
from pydantic import ValidationError

from flowmate.tools import VehicleAction, VehicleTool, VehicleToolInput, VehicleToolResult


GET_STATUS = {"vehicle_id": "my-car", "action": "get_status"}
LOCK = {"vehicle_id": "my-car", "action": "lock"}
UNLOCK = {"vehicle_id": "my-car", "action": "unlock"}
START_CLIMATE = {"vehicle_id": "my-car", "action": "start_climate"}
START_CLIMATE_24 = {**START_CLIMATE, "temperature": 24}
STOP_CLIMATE = {"vehicle_id": "my-car", "action": "stop_climate"}


def test_vehicle_tool_name_and_safety_accurate_description():
    tool = VehicleTool()

    assert tool.name == "vehicle_tool"
    assert tool.description
    assert "Mock vehicle status and limited vehicle-control" in tool.description
    assert "No real vehicle is controlled" in tool.description
    assert "vehicle movement are unsupported" in tool.description


@pytest.mark.parametrize("missing_field", ["vehicle_id", "action"])
def test_required_input_fields(missing_field):
    arguments = LOCK.copy()
    arguments.pop(missing_field)

    with pytest.raises(ValidationError):
        VehicleToolInput(**arguments)


def test_temperature_is_optional_and_defaults_to_none():
    input_data = VehicleToolInput(**START_CLIMATE)

    assert input_data.temperature is None


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        VehicleToolInput(**LOCK, vin="mock-vin")


def test_whitespace_only_vehicle_id_is_invalid():
    with pytest.raises(ValidationError):
        VehicleToolInput(**{**LOCK, "vehicle_id": "   "})


def test_vehicle_id_is_trimmed_as_mock_logical_identifier():
    input_data = VehicleToolInput(**{**LOCK, "vehicle_id": " my-car "})

    assert input_data.vehicle_id == "my-car"


def test_unknown_action_is_invalid():
    with pytest.raises(ValidationError):
        VehicleToolInput(vehicle_id="my-car", action="start_engine")


@pytest.mark.parametrize(
    "arguments",
    [GET_STATUS, LOCK, UNLOCK, START_CLIMATE, START_CLIMATE_24, STOP_CLIMATE],
)
def test_supported_action_contracts_are_valid(arguments):
    input_data = VehicleToolInput(**arguments)

    assert input_data.action in VehicleAction


@pytest.mark.parametrize(
    "action",
    ["get_status", "lock", "unlock", "stop_climate"],
)
def test_non_start_climate_actions_reject_temperature(action):
    with pytest.raises(ValidationError):
        VehicleToolInput(vehicle_id="my-car", action=action, temperature=24)


@pytest.mark.parametrize("temperature", [16, 30])
def test_climate_temperature_boundaries_are_valid(temperature):
    input_data = VehicleToolInput(
        vehicle_id="my-car",
        action="start_climate",
        temperature=temperature,
    )

    assert input_data.temperature == temperature


@pytest.mark.parametrize("temperature", [15.9, 30.1])
def test_climate_temperature_outside_range_is_invalid(temperature):
    with pytest.raises(ValidationError):
        VehicleToolInput(
            vehicle_id="my-car",
            action="start_climate",
            temperature=temperature,
        )


@pytest.mark.parametrize("temperature", [True, False])
def test_boolean_temperature_is_invalid(temperature):
    with pytest.raises(ValidationError):
        VehicleToolInput(
            vehicle_id="my-car",
            action="start_climate",
            temperature=temperature,
        )


@pytest.mark.parametrize(
    ("arguments", "expected_state"),
    [
        (GET_STATUS, {"locked": True, "climate": "off"}),
        (LOCK, {"locked": True}),
        (UNLOCK, {"locked": False}),
        (START_CLIMATE, {"climate": "on"}),
        (START_CLIMATE_24, {"climate": "on", "temperature": 24}),
        (STOP_CLIMATE, {"climate": "off"}),
    ],
)
def test_execution_returns_expected_structured_mock_result(arguments, expected_state):
    result = VehicleTool().run(arguments)

    assert isinstance(result, VehicleToolResult)
    assert result.vehicle_id == "my-car"
    assert result.action == arguments["action"]
    assert result.status == "mock_executed"
    assert result.state == expected_state


def test_same_input_produces_same_output():
    tool = VehicleTool()

    assert tool.run(START_CLIMATE_24) == tool.run(START_CLIMATE_24)


def test_execution_does_not_open_network_connection(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("VehicleTool must not open network connections.")

    monkeypatch.setattr(socket, "create_connection", fail_if_called)

    result = VehicleTool().run(LOCK)

    assert result.status == "mock_executed"


def test_contract_has_no_vehicle_movement_or_autonomous_driving_capability():
    supported_actions = {action.value for action in VehicleAction}
    forbidden_actions = {
        "remote_drive",
        "move_vehicle",
        "summon",
        "autonomous_drive",
        "park_vehicle",
    }

    assert supported_actions.isdisjoint(forbidden_actions)
    assert VehicleTool().run(GET_STATUS).state.keys() == {"locked", "climate"}
