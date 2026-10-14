import socket

import pytest
from pydantic import ValidationError

from flowmate.tools import (
    SmartHomeAction,
    SmartHomeDeviceType,
    SmartHomeTool,
    SmartHomeToolInput,
    SmartHomeToolResult,
)


LIGHT_ON = {
    "device_id": "living-room-light",
    "device_type": "light",
    "action": "turn_on",
}
LIGHT_OFF = {**LIGHT_ON, "action": "turn_off"}
AC_ON = {
    "device_id": "bedroom-ac",
    "device_type": "air_conditioner",
    "action": "turn_on",
}
AC_OFF = {**AC_ON, "action": "turn_off"}
AC_TEMPERATURE = {**AC_ON, "action": "set_temperature", "value": 24}


def test_smart_home_tool_name_and_description_are_capability_accurate():
    tool = SmartHomeTool()

    assert tool.name == "smart_home_tool"
    assert tool.description
    assert "Mock" in tool.description
    assert "No real physical device is controlled" in tool.description


@pytest.mark.parametrize("missing_field", ["device_id", "device_type", "action"])
def test_required_input_fields(missing_field):
    arguments = LIGHT_ON.copy()
    arguments.pop(missing_field)

    with pytest.raises(ValidationError):
        SmartHomeToolInput(**arguments)


def test_value_is_optional_and_defaults_to_none():
    input_data = SmartHomeToolInput(**LIGHT_ON)

    assert input_data.value is None


def test_extra_field_is_rejected():
    with pytest.raises(ValidationError):
        SmartHomeToolInput(**LIGHT_ON, room="living-room")


def test_whitespace_only_device_id_is_rejected():
    with pytest.raises(ValidationError):
        SmartHomeToolInput(**{**LIGHT_ON, "device_id": "   "})


def test_device_id_is_trimmed_to_a_mock_logical_identifier():
    input_data = SmartHomeToolInput(**{**LIGHT_ON, "device_id": " living-room-light "})

    assert input_data.device_id == "living-room-light"


@pytest.mark.parametrize("arguments", [LIGHT_ON, LIGHT_OFF, AC_ON, AC_OFF, AC_TEMPERATURE])
def test_supported_device_action_combinations_are_valid(arguments):
    input_data = SmartHomeToolInput(**arguments)

    assert input_data.device_type in SmartHomeDeviceType
    assert input_data.action in SmartHomeAction


def test_light_set_temperature_is_invalid():
    with pytest.raises(ValidationError):
        SmartHomeToolInput(
            device_id="living-room-light",
            device_type="light",
            action="set_temperature",
            value=24,
        )


def test_set_temperature_without_value_is_invalid():
    with pytest.raises(ValidationError):
        SmartHomeToolInput(
            device_id="bedroom-ac",
            device_type="air_conditioner",
            action="set_temperature",
        )


@pytest.mark.parametrize("action", ["turn_on", "turn_off"])
def test_power_action_with_value_is_invalid(action):
    with pytest.raises(ValidationError):
        SmartHomeToolInput(**{**AC_ON, "action": action, "value": 24})


@pytest.mark.parametrize("temperature", [16, 30])
def test_temperature_boundary_is_valid(temperature):
    input_data = SmartHomeToolInput(**{**AC_TEMPERATURE, "value": temperature})

    assert input_data.value == temperature


@pytest.mark.parametrize("temperature", [15.9, 30.1])
def test_temperature_outside_supported_range_is_invalid(temperature):
    with pytest.raises(ValidationError):
        SmartHomeToolInput(**{**AC_TEMPERATURE, "value": temperature})


def test_boolean_temperature_is_invalid():
    with pytest.raises(ValidationError):
        SmartHomeToolInput(**{**AC_TEMPERATURE, "value": True})


def test_unknown_device_type_is_invalid():
    with pytest.raises(ValidationError):
        SmartHomeToolInput(**{**LIGHT_ON, "device_type": "television"})


def test_unknown_action_is_invalid():
    with pytest.raises(ValidationError):
        SmartHomeToolInput(**{**LIGHT_ON, "action": "toggle"})


@pytest.mark.parametrize(
    ("arguments", "expected_state"),
    [
        (LIGHT_ON, {"power": "on"}),
        (LIGHT_OFF, {"power": "off"}),
        (AC_ON, {"power": "on"}),
        (AC_OFF, {"power": "off"}),
        (AC_TEMPERATURE, {"temperature": 24}),
    ],
)
def test_execution_returns_expected_structured_mock_result(arguments, expected_state):
    result = SmartHomeTool().run(arguments)

    assert isinstance(result, SmartHomeToolResult)
    assert result.device_id == arguments["device_id"]
    assert result.device_type == arguments["device_type"]
    assert result.action == arguments["action"]
    assert result.status == "mock_executed"
    assert result.state == expected_state


def test_repeated_same_input_returns_same_result():
    tool = SmartHomeTool()

    assert tool.run(AC_TEMPERATURE) == tool.run(AC_TEMPERATURE)


def test_execution_does_not_open_a_network_connection(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("SmartHomeTool must not open network connections.")

    monkeypatch.setattr(socket, "create_connection", fail_if_called)

    result = SmartHomeTool().run(LIGHT_OFF)

    assert result.status == "mock_executed"
