import pytest

from flowmate.agent import RiskPolicy, UnknownActionRiskError, UnknownToolRiskError
from flowmate.schemas import ConfirmationStatus, PlanStep, RiskLevel, Task, ToolCall


def assess(tool_names: list[str]):
    return RiskPolicy().assess(tool_names)


def _vehicle_call(action: str, temperature: int | None = None) -> ToolCall:
    arguments = {"vehicle_id": "my-car", "action": action}
    if temperature is not None:
        arguments["temperature"] = temperature
    return ToolCall(tool_name="vehicle_tool", arguments=arguments)


def test_weather_risk_is_low_without_confirmation():
    result = assess(["weather_tool"])

    assert result.risk_level == RiskLevel.LOW
    assert result.requires_confirmation is False


def test_navigation_risk_is_low_without_confirmation():
    result = assess(["navigation_tool"])

    assert result.risk_level == RiskLevel.LOW
    assert result.requires_confirmation is False


def test_calendar_risk_is_low_without_confirmation():
    result = assess(["calendar_tool"])

    assert result.risk_level == RiskLevel.LOW
    assert result.requires_confirmation is False


def test_notification_risk_is_medium_with_confirmation():
    result = assess(["notification_tool"])

    assert result.risk_level == RiskLevel.MEDIUM
    assert result.requires_confirmation is True


@pytest.mark.parametrize(
    ("device_type", "action", "value"),
    [
        ("light", "turn_on", None),
        ("light", "turn_off", None),
        ("air_conditioner", "turn_on", None),
        ("air_conditioner", "turn_off", None),
        ("air_conditioner", "set_temperature", 24),
    ],
)
def test_supported_smart_home_actions_are_medium_and_require_confirmation(
    device_type,
    action,
    value,
):
    arguments = {
        "device_id": "test-device",
        "device_type": device_type,
        "action": action,
    }
    if value is not None:
        arguments["value"] = value

    result = RiskPolicy().assess_tool_call(
        ToolCall(tool_name="smart_home_tool", arguments=arguments)
    )

    assert result.risk_level == RiskLevel.MEDIUM
    assert result.requires_confirmation is True


def test_smart_home_name_only_assessment_fails_closed_without_action_contract():
    with pytest.raises(UnknownActionRiskError):
        assess(["smart_home_tool"])


def test_vehicle_name_only_assessment_fails_closed_without_action_contract():
    with pytest.raises(UnknownActionRiskError):
        assess(["vehicle_tool"])


def test_unknown_smart_home_action_fails_closed():
    with pytest.raises(UnknownActionRiskError):
        RiskPolicy().assess_tool_call(
            ToolCall(
                tool_name="smart_home_tool",
                arguments={
                    "device_id": "front-door",
                    "device_type": "door_lock",
                    "action": "unlock",
                },
            )
        )


@pytest.mark.parametrize(
    ("action", "expected_risk", "requires_confirmation"),
    [
        ("get_status", RiskLevel.LOW, False),
        ("start_climate", RiskLevel.MEDIUM, True),
        ("stop_climate", RiskLevel.MEDIUM, True),
        ("lock", RiskLevel.HIGH, True),
        ("unlock", RiskLevel.HIGH, True),
    ],
)
def test_vehicle_action_risk_matrix(action, expected_risk, requires_confirmation):
    result = RiskPolicy().assess_tool_call(_vehicle_call(action))

    assert result.risk_level == expected_risk
    assert result.requires_confirmation is requires_confirmation


def test_unknown_vehicle_action_fails_closed():
    with pytest.raises(UnknownActionRiskError):
        RiskPolicy().assess_tool_call(_vehicle_call("start_engine"))


def test_weather_navigation_remain_low():
    result = assess(["weather_tool", "navigation_tool"])

    assert result.risk_level == RiskLevel.LOW
    assert result.requires_confirmation is False


def test_calendar_notification_uses_highest_risk():
    result = assess(["calendar_tool", "notification_tool"])

    assert result.risk_level == RiskLevel.MEDIUM
    assert result.requires_confirmation is True


def test_tool_order_does_not_affect_risk():
    first = assess(["calendar_tool", "notification_tool"])
    second = assess(["notification_tool", "calendar_tool"])

    assert first.risk_level == second.risk_level
    assert first.requires_confirmation == second.requires_confirmation


@pytest.mark.parametrize(
    "low_or_medium_tool",
    ["weather_tool", "calendar_tool", "notification_tool"],
)
def test_smart_home_combination_uses_highest_risk(low_or_medium_tool):
    task = _task_with_calls(
        [
            ToolCall(tool_name=low_or_medium_tool, arguments=_arguments_for(low_or_medium_tool)),
            ToolCall(
                tool_name="smart_home_tool",
                arguments={
                    "device_id": "living-room-light",
                    "device_type": "light",
                    "action": "turn_off",
                },
            ),
        ]
    )

    result = RiskPolicy().assess_task(task)

    assert result.risk_level == RiskLevel.MEDIUM
    assert result.requires_confirmation is True


def test_tool_call_order_does_not_affect_task_risk():
    weather = ToolCall(
        tool_name="weather_tool",
        arguments={"location": "current_city", "date": "tomorrow"},
    )
    smart_home = ToolCall(
        tool_name="smart_home_tool",
        arguments={
            "device_id": "bedroom-ac",
            "device_type": "air_conditioner",
            "action": "set_temperature",
            "value": 24,
        },
    )

    first = RiskPolicy().assess_task(_task_with_calls([weather, smart_home]))
    second = RiskPolicy().assess_task(_task_with_calls([smart_home, weather]))

    assert first.risk_level == second.risk_level == RiskLevel.MEDIUM
    assert first.requires_confirmation == second.requires_confirmation is True


@pytest.mark.parametrize(
    ("tool_calls", "expected_risk", "requires_confirmation"),
    [
        (
            [
                ToolCall(tool_name="calendar_tool", arguments={"date": "tomorrow"}),
                _vehicle_call("get_status"),
            ],
            RiskLevel.LOW,
            False,
        ),
        (
            [
                ToolCall(
                    tool_name="weather_tool",
                    arguments={"location": "current_city", "date": "tomorrow"},
                ),
                _vehicle_call("start_climate", temperature=24),
            ],
            RiskLevel.MEDIUM,
            True,
        ),
        (
            [
                ToolCall(
                    tool_name="notification_tool",
                    arguments={
                        "title": "Vehicle",
                        "message": "Status changed.",
                        "channel": "mobile",
                    },
                ),
                _vehicle_call("unlock"),
            ],
            RiskLevel.HIGH,
            True,
        ),
        (
            [
                ToolCall(
                    tool_name="smart_home_tool",
                    arguments={
                        "device_id": "living-room-light",
                        "device_type": "light",
                        "action": "turn_off",
                    },
                ),
                _vehicle_call("lock"),
            ],
            RiskLevel.HIGH,
            True,
        ),
    ],
)
def test_vehicle_combinations_use_highest_action_risk(
    tool_calls,
    expected_risk,
    requires_confirmation,
):
    result = RiskPolicy().assess_task(_task_with_calls(tool_calls))

    assert result.risk_level == expected_risk
    assert result.requires_confirmation is requires_confirmation


def test_vehicle_tool_call_order_does_not_affect_highest_risk():
    status = _vehicle_call("get_status")
    unlock = _vehicle_call("unlock")

    first = RiskPolicy().assess_task(_task_with_calls([status, unlock]))
    second = RiskPolicy().assess_task(_task_with_calls([unlock, status]))

    assert first.risk_level == second.risk_level == RiskLevel.HIGH
    assert first.requires_confirmation == second.requires_confirmation is True


def test_unknown_tool_risk_fails_closed():
    with pytest.raises(UnknownToolRiskError):
        assess(["unknown_tool"])


def test_apply_to_task_sets_confirmation_invariant():
    task = Task(
        id="task-1",
        user_input="notify me",
        goal="send notification",
        risk_level=RiskLevel.LOW,
        requires_confirmation=False,
        steps=[
            PlanStep(
                id="step-1",
                order=1,
                description="notify",
                tool_name="notification_tool",
                tool_call=ToolCall(
                    tool_name="notification_tool",
                    arguments={
                        "title": "Morning commute",
                        "message": "Your route is ready.",
                        "channel": "mobile",
                    },
                ),
            )
        ],
    )

    RiskPolicy().apply_to_task(task)

    assert task.risk_level == RiskLevel.MEDIUM
    assert task.requires_confirmation is True
    assert task.confirmation_status == ConfirmationStatus.PENDING


def _arguments_for(tool_name: str) -> dict:
    if tool_name == "weather_tool":
        return {"location": "current_city", "date": "tomorrow"}
    if tool_name == "calendar_tool":
        return {"date": "tomorrow"}
    if tool_name == "notification_tool":
        return {"title": "Done", "message": "Task complete.", "channel": "mobile"}
    raise AssertionError(f"Unsupported test tool: {tool_name}")


def _task_with_calls(tool_calls: list[ToolCall]) -> Task:
    return Task(
        id="task-risk-test",
        user_input="risk test",
        goal="assess tool calls",
        risk_level=RiskLevel.LOW,
        requires_confirmation=False,
        steps=[
            PlanStep(
                id=f"step-{index}",
                order=index,
                description="Assess call.",
                tool_name=tool_call.tool_name,
                tool_call=tool_call,
            )
            for index, tool_call in enumerate(tool_calls, start=1)
        ],
    )

