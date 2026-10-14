import pytest
from pydantic import ValidationError

from flowmate.tools import (
    NotificationChannel,
    NotificationTool,
    NotificationToolInput,
    NotificationToolResult,
)


VALID_ARGUMENTS = {
    "title": "Morning commute",
    "message": "Your route is ready.",
    "channel": "mobile",
}


def test_notification_tool_name_and_description():
    tool = NotificationTool()

    assert tool.name == "notification_tool"
    assert tool.description
    assert "Mock" in tool.description


def test_notification_input_requires_title():
    with pytest.raises(ValidationError):
        NotificationToolInput(message="Your route is ready.", channel="mobile")


def test_notification_input_requires_message():
    with pytest.raises(ValidationError):
        NotificationToolInput(title="Morning commute", channel="mobile")


def test_notification_input_requires_channel():
    with pytest.raises(ValidationError):
        NotificationToolInput(title="Morning commute", message="Your route is ready.")


def test_mobile_channel_is_valid():
    input_data = NotificationToolInput(**VALID_ARGUMENTS)

    assert input_data.channel == NotificationChannel.MOBILE


def test_unknown_channel_is_invalid():
    with pytest.raises(ValidationError):
        NotificationToolInput(
            title="Morning commute",
            message="Your route is ready.",
            channel="email",
        )


def test_extra_field_is_forbidden():
    with pytest.raises(ValidationError):
        NotificationToolInput(**VALID_ARGUMENTS, priority="high")


def test_empty_title_is_invalid():
    with pytest.raises(ValidationError):
        NotificationToolInput(title="", message="Your route is ready.", channel="mobile")


def test_whitespace_only_title_is_invalid():
    with pytest.raises(ValidationError):
        NotificationToolInput(title="   ", message="Your route is ready.", channel="mobile")


def test_empty_message_is_invalid():
    with pytest.raises(ValidationError):
        NotificationToolInput(title="Morning commute", message="", channel="mobile")


def test_whitespace_only_message_is_invalid():
    with pytest.raises(ValidationError):
        NotificationToolInput(title="Morning commute", message="   ", channel="mobile")


def test_valid_input_returns_mock_result():
    result = NotificationTool().run(VALID_ARGUMENTS)

    assert isinstance(result, NotificationToolResult)
    assert result.channel == NotificationChannel.MOBILE
    assert result.status == "mock_delivered"
    assert result.title == "Morning commute"
    assert result.message == "Your route is ready."


def test_same_input_returns_same_result_multiple_times():
    tool = NotificationTool()

    assert tool.run(VALID_ARGUMENTS) == tool.run(VALID_ARGUMENTS)


def test_notification_id_is_deterministic_and_mock_scoped():
    result = NotificationTool().run(VALID_ARGUMENTS)

    assert result.notification_id.startswith("mock-notification-")


def test_run_uses_input_schema_validation():
    with pytest.raises(ValidationError):
        NotificationTool().run({"title": "Morning commute", "channel": "mobile"})
