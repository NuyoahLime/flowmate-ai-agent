from typing import Any

import pytest
from pydantic import BaseModel

from flowmate.agent import ToolArgumentValidationError, ToolArgumentValidator
from flowmate.tools import BaseTool, create_default_registry
from flowmate.tools.calendar import CalendarToolInput
from flowmate.tools.navigation import NavigationToolInput
from flowmate.tools.notification import NotificationToolInput
from flowmate.tools.smart_home import SmartHomeToolInput
from flowmate.tools.vehicle import VehicleToolInput
from flowmate.tools.registry import ToolRegistry
from flowmate.tools.weather import WeatherToolInput


def test_weather_arguments_pass_validator():
    validator = ToolArgumentValidator(create_default_registry())

    validated = validator.validate(
        "weather_tool",
        {"location": "current_city", "date": "tomorrow"},
    )

    assert isinstance(validated, WeatherToolInput)


def test_navigation_arguments_pass_validator():
    validator = ToolArgumentValidator(create_default_registry())

    validated = validator.validate(
        "navigation_tool",
        {
            "origin": "home",
            "destination": "company",
            "departure_time": "tomorrow morning",
        },
    )

    assert isinstance(validated, NavigationToolInput)


def test_calendar_date_only_arguments_pass_validator():
    validator = ToolArgumentValidator(create_default_registry())

    validated = validator.validate("calendar_tool", {"date": "tomorrow"})

    assert isinstance(validated, CalendarToolInput)


def test_calendar_time_window_arguments_pass_validator():
    validator = ToolArgumentValidator(create_default_registry())

    validated = validator.validate(
        "calendar_tool",
        {"date": "tomorrow", "start_time": "06:00", "end_time": "12:00"},
    )

    assert validated.start_time == "06:00"
    assert validated.end_time == "12:00"


def test_notification_arguments_pass_validator():
    validator = ToolArgumentValidator(create_default_registry())

    validated = validator.validate(
        "notification_tool",
        {
            "title": "Morning commute",
            "message": "Your route is ready.",
            "channel": "mobile",
        },
    )

    assert isinstance(validated, NotificationToolInput)


@pytest.mark.parametrize(
    "arguments",
    [
        {
            "device_id": "living-room-light",
            "device_type": "light",
            "action": "turn_off",
        },
        {
            "device_id": "bedroom-ac",
            "device_type": "air_conditioner",
            "action": "set_temperature",
            "value": 24,
        },
    ],
)
def test_smart_home_arguments_pass_validator(arguments):
    validator = ToolArgumentValidator(create_default_registry())

    validated = validator.validate("smart_home_tool", arguments)

    assert isinstance(validated, SmartHomeToolInput)


@pytest.mark.parametrize(
    "arguments",
    [
        {
            "device_id": "living-room-light",
            "device_type": "light",
            "action": "set_temperature",
            "value": 24,
        },
        {
            "device_id": "bedroom-ac",
            "device_type": "air_conditioner",
            "action": "set_temperature",
        },
        {
            "device_id": "bedroom-ac",
            "device_type": "air_conditioner",
            "action": "turn_on",
            "value": 24,
        },
        {
            "device_id": "living-room-light",
            "device_type": "light",
            "action": "turn_off",
            "room": "living-room",
        },
    ],
)
def test_invalid_smart_home_arguments_fail_validation(arguments):
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate("smart_home_tool", arguments)


@pytest.mark.parametrize(
    "arguments",
    [
        {"vehicle_id": "my-car", "action": "lock"},
        {"vehicle_id": "my-car", "action": "start_climate", "temperature": 24},
    ],
)
def test_vehicle_arguments_pass_validator(arguments):
    validator = ToolArgumentValidator(create_default_registry())

    validated = validator.validate("vehicle_tool", arguments)

    assert isinstance(validated, VehicleToolInput)


@pytest.mark.parametrize(
    "arguments",
    [
        {"vehicle_id": "my-car", "action": "unlock", "temperature": 24},
        {"vehicle_id": "my-car", "action": "lock", "temperature": 24},
        {"vehicle_id": "my-car", "action": "stop_climate", "temperature": 24},
        {"vehicle_id": "my-car", "action": "start_climate", "temperature": 35},
        {"vehicle_id": "my-car", "action": "start_engine"},
        {"vehicle_id": "my-car", "action": "lock", "vin": "mock-vin"},
    ],
)
def test_invalid_vehicle_arguments_fail_validation(arguments):
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate("vehicle_tool", arguments)


def test_notification_missing_title_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate(
            "notification_tool",
            {"message": "Your route is ready.", "channel": "mobile"},
        )


def test_notification_missing_message_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate(
            "notification_tool",
            {"title": "Morning commute", "channel": "mobile"},
        )


def test_notification_missing_channel_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate(
            "notification_tool",
            {"title": "Morning commute", "message": "Your route is ready."},
        )


def test_notification_extra_field_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate(
            "notification_tool",
            {
                "title": "Morning commute",
                "message": "Your route is ready.",
                "channel": "mobile",
                "priority": "high",
            },
        )


def test_notification_unknown_channel_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate(
            "notification_tool",
            {
                "title": "Morning commute",
                "message": "Your route is ready.",
                "channel": "email",
            },
        )


def test_calendar_missing_date_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate(
            "calendar_tool",
            {"start_time": "06:00", "end_time": "12:00"},
        )


def test_calendar_extra_field_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate(
            "calendar_tool",
            {"date": "tomorrow", "timezone": "Asia/Shanghai"},
        )


def test_navigation_missing_departure_time_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate(
            "navigation_tool",
            {"origin": "home", "destination": "company"},
        )


def test_navigation_missing_origin_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate(
            "navigation_tool",
            {"destination": "company", "departure_time": "tomorrow morning"},
        )


def test_navigation_missing_destination_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate(
            "navigation_tool",
            {"origin": "home", "departure_time": "tomorrow morning"},
        )


def test_unknown_tool_fails_validation():
    validator = ToolArgumentValidator(create_default_registry())

    with pytest.raises(ToolArgumentValidationError):
        validator.validate("missing_tool", {})


def test_validator_does_not_call_tool_run_or_execute():
    class FakeInput(BaseModel):
        value: str

    class FakeResult(BaseModel):
        ok: bool

    class FakeTool(BaseTool[FakeInput, FakeResult]):
        name = "fake_tool"
        description = "Fake tool for validator tests."
        input_schema = FakeInput

        def __init__(self) -> None:
            self.run_called = False
            self.execute_called = False

        def run(self, arguments: dict[str, Any]) -> FakeResult:
            self.run_called = True
            return super().run(arguments)

        def execute(self, input_data: FakeInput) -> FakeResult:
            self.execute_called = True
            return FakeResult(ok=True)

    tool = FakeTool()
    registry = ToolRegistry()
    registry.register(tool)

    ToolArgumentValidator(registry).validate("fake_tool", {"value": "ok"})

    assert tool.run_called is False
    assert tool.execute_called is False
