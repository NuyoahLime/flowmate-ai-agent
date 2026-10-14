from typing import Any, Mapping

import pytest

from flowmate.agent import (
    LLMPlanner,
    Planner,
    PlannerOutputValidationError,
    RuleBasedPlanner,
    StepExecutor,
    TaskExecutor,
    ToolArgumentValidationError,
    ToolExecutor,
    UnsupportedPlanningScenarioError,
)
from flowmate.schemas import ConfirmationStatus, TaskStatus, ToolCallStatus
from flowmate.tools import create_default_registry
from flowmate.agent.temporal_conventions import CALENDAR_TEMPORAL_WINDOWS


USER_INPUT = "我明天早上八点半在公司开会，帮我安排好明早出门"


class FakeLLMClient:
    def __init__(self, output: Mapping[str, Any]) -> None:
        self.output = output
        self.calls: list[dict[str, str]] = []

    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        self.calls.append({"user_input": user_input, "system_prompt": system_prompt})
        return self.output


def valid_llm_output() -> dict[str, Any]:
    return {
        "unsupported": False,
        "reason": None,
        "plan": {
            "goal": "安排明早通勤，确保按时到达公司参加会议",
            "risk_level": "LOW",
            "requires_confirmation": False,
            "steps": [
                {
                    "order": 2,
                    "description": "计算到公司的通勤时间",
                    "tool_name": "navigation_tool",
                    "arguments": {
                        "origin": "home",
                        "destination": "company",
                        "departure_time": "tomorrow 08:30",
                    },
                },
                {
                    "order": 1,
                    "description": "检查明早天气",
                    "tool_name": "weather_tool",
                    "arguments": {
                        "location": "current_city",
                        "date": "tomorrow",
                    },
                },
            ],
        },
    }


def test_default_llm_planner_authorizes_notification_tool():
    planner = LLMPlanner(FakeLLMClient(valid_llm_output()))

    assert "notification_tool" in planner.allowed_tools
    assert "notification_tool" in planner.system_prompt


def test_smart_home_tool_is_planner_authorized():
    planner = LLMPlanner(FakeLLMClient(valid_llm_output()))

    assert planner.tool_registry.get("smart_home_tool").name == "smart_home_tool"
    assert planner.allowed_tools == {
        "weather_tool",
        "navigation_tool",
        "calendar_tool",
        "notification_tool",
        "smart_home_tool",
        "vehicle_tool",
    }
    assert "smart_home_tool" in planner.system_prompt


def test_vehicle_tool_is_planner_authorized():
    planner = LLMPlanner(FakeLLMClient(valid_llm_output()))

    assert planner.tool_registry.get("vehicle_tool").name == "vehicle_tool"
    assert planner.allowed_tools == {
        "weather_tool",
        "navigation_tool",
        "calendar_tool",
        "notification_tool",
        "smart_home_tool",
        "vehicle_tool",
    }
    assert "vehicle_tool" in planner.system_prompt


def smart_home_llm_output(
    *,
    device_id: str = "living-room-light",
    device_type: str = "light",
    action: str = "turn_on",
    value: int | None = None,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "device_id": device_id,
        "device_type": device_type,
        "action": action,
    }
    if value is not None:
        arguments["value"] = value
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
                    "description": "Control supported mock device.",
                    "tool_name": "smart_home_tool",
                    "arguments": arguments,
                }
            ],
        },
    }


def vehicle_llm_output(
    *,
    action: str = "get_status",
    temperature: int | None = None,
    risk_level: str = "LOW",
    requires_confirmation: bool = False,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {"vehicle_id": "my-car", "action": action}
    if temperature is not None:
        arguments["temperature"] = temperature
    return {
        "unsupported": False,
        "reason": None,
        "plan": {
            "goal": "Perform an explicit immediate mock vehicle action.",
            "risk_level": risk_level,
            "requires_confirmation": requires_confirmation,
            "steps": [
                {
                    "order": 1,
                    "description": "Use supported mock vehicle capability.",
                    "tool_name": "vehicle_tool",
                    "arguments": arguments,
                }
            ],
        },
    }


@pytest.mark.parametrize(
    ("action", "temperature", "expected_risk", "requires_confirmation"),
    [
        ("get_status", None, "LOW", False),
        ("start_climate", None, "MEDIUM", True),
        ("start_climate", 24, "MEDIUM", True),
        ("stop_climate", None, "MEDIUM", True),
        ("lock", None, "HIGH", True),
        ("unlock", None, "HIGH", True),
    ],
)
def test_supported_vehicle_plan_is_valid(
    action,
    temperature,
    expected_risk,
    requires_confirmation,
):
    task = create_planner(
        vehicle_llm_output(action=action, temperature=temperature)
    ).plan("explicit immediate vehicle request")

    assert [step.tool_name for step in task.steps] == ["vehicle_tool"]
    assert task.steps[0].tool_call.arguments["action"] == action
    if temperature is not None:
        assert task.steps[0].tool_call.arguments["temperature"] == temperature
    assert task.risk_level == expected_risk
    assert task.requires_confirmation is requires_confirmation


def test_vehicle_tool_spec_comes_from_registry_schema():
    prompt = LLMPlanner(FakeLLMClient(valid_llm_output())).system_prompt

    assert "vehicle_tool" in prompt
    assert "- vehicle_id" in prompt
    assert "- action" in prompt
    assert "- temperature" in prompt


def test_vehicle_prompt_defines_capability_and_movement_boundary():
    prompt = LLMPlanner(FakeLLMClient(valid_llm_output())).system_prompt

    assert "explicit, immediate mock vehicle actions only" in prompt
    assert "get_status" in prompt
    assert "start_climate" in prompt
    assert "report fuel, battery or charge level" in prompt
    assert "Vehicle movement, remote driving, autonomous driving" in prompt
    assert "Scheduled, delayed, conditional" in prompt
    assert "Keep navigation and vehicle control separate" in prompt


def test_llm_low_metadata_cannot_downgrade_vehicle_unlock():
    task = create_planner(
        vehicle_llm_output(
            action="unlock",
            risk_level="LOW",
            requires_confirmation=False,
        )
    ).plan("把我的车解锁")

    assert task.risk_level == "HIGH"
    assert task.requires_confirmation is True
    assert task.confirmation_status == "PENDING"


def test_llm_high_metadata_cannot_raise_vehicle_get_status():
    task = create_planner(
        vehicle_llm_output(
            action="get_status",
            risk_level="HIGH",
            requires_confirmation=True,
        )
    ).plan("看看我的车现在是什么状态")

    assert task.risk_level == "LOW"
    assert task.requires_confirmation is False
    assert task.confirmation_status == "NOT_REQUIRED"


def test_unknown_vehicle_action_arguments_are_rejected():
    with pytest.raises(ToolArgumentValidationError):
        create_planner(vehicle_llm_output(action="start_engine")).plan("启动发动机")


@pytest.mark.parametrize(
    "user_input",
    [
        "把车开到楼下",
        "让车自己开到公司",
        "召唤车辆过来",
        "打开后备箱",
        "鸣笛两声",
        "明早七点打开车内空调",
        "如果明天下雨就提前打开车内空调",
    ],
)
def test_unsupported_vehicle_boundary_does_not_create_task(user_input):
    output = {
        "unsupported": True,
        "reason": "The requested vehicle capability is unsupported.",
        "plan": None,
    }

    with pytest.raises(UnsupportedPlanningScenarioError):
        create_planner(output).plan(user_input)


@pytest.mark.parametrize(
    "user_input",
    [
        "帮我规划去公司的路线",
        "我自己开车去公司，帮我规划路线",
    ],
)
def test_navigation_only_request_does_not_select_vehicle_tool(user_input):
    output = {
        "unsupported": False,
        "reason": None,
        "plan": {
            "goal": "Plan route to company.",
            "risk_level": "LOW",
            "requires_confirmation": False,
            "steps": [
                {
                    "order": 1,
                    "description": "Plan route.",
                    "tool_name": "navigation_tool",
                    "arguments": {
                        "origin": "home",
                        "destination": "company",
                        "departure_time": "tomorrow morning",
                    },
                }
            ],
        },
    }

    task = create_planner(output).plan(user_input)

    assert [step.tool_name for step in task.steps] == ["navigation_tool"]


@pytest.mark.parametrize(
    ("device_id", "device_type", "action", "value"),
    [
        ("living-room-light", "light", "turn_on", None),
        ("living-room-light", "light", "turn_off", None),
        ("bedroom-ac", "air_conditioner", "turn_on", None),
        ("bedroom-ac", "air_conditioner", "turn_off", None),
        ("bedroom-ac", "air_conditioner", "set_temperature", 24),
    ],
)
def test_supported_smart_home_plan_is_valid(
    device_id,
    device_type,
    action,
    value,
):
    task = create_planner(
        smart_home_llm_output(
            device_id=device_id,
            device_type=device_type,
            action=action,
            value=value,
        )
    ).plan("explicit immediate smart-home request")

    assert [step.tool_name for step in task.steps] == ["smart_home_tool"]
    assert task.steps[0].tool_call.arguments["device_id"] == device_id
    assert task.steps[0].tool_call.arguments["action"] == action
    if value is not None:
        assert task.steps[0].tool_call.arguments["value"] == value
    assert task.risk_level == "MEDIUM"
    assert task.requires_confirmation is True
    assert task.confirmation_status == "PENDING"


def test_smart_home_tool_spec_comes_from_registry_schema():
    planner = LLMPlanner(FakeLLMClient(valid_llm_output()))

    prompt = planner.system_prompt
    assert "smart_home_tool" in prompt
    assert "- device_id" in prompt
    assert "- device_type" in prompt
    assert "- action" in prompt
    assert "- value" in prompt


def test_smart_home_prompt_defines_immediate_only_boundary_and_device_mappings():
    prompt = LLMPlanner(FakeLLMClient(valid_llm_output())).system_prompt

    assert "explicit, immediate mock control only" in prompt
    assert "living room light => living-room-light" in prompt
    assert "bedroom air conditioner => bedroom-ac" in prompt
    assert "Do not guess a default room or device" in prompt
    assert "Scheduled, delayed, conditional, scene-based" in prompt
    assert "do not claim or verify that a real physical device changed state" in prompt


def test_llm_low_risk_metadata_cannot_downgrade_smart_home_task():
    task = create_planner(smart_home_llm_output()).plan("把客厅灯打开")

    assert task.risk_level == "MEDIUM"
    assert task.requires_confirmation is True
    assert task.confirmation_status == "PENDING"


def test_unknown_smart_home_device_arguments_are_rejected():
    output = smart_home_llm_output(
        device_id="living-room-curtain",
        device_type="curtain",
        action="turn_off",
    )

    with pytest.raises(ToolArgumentValidationError):
        create_planner(output).plan("把窗帘关上")


@pytest.mark.parametrize(
    "user_input",
    [
        "晚上十点把客厅灯关掉",
        "如果房间超过30度就开空调",
        "开启学习模式",
        "确认我家客厅灯现在真的已经关了",
    ],
)
def test_unsupported_smart_home_boundary_does_not_create_task(user_input):
    output = {
        "unsupported": True,
        "reason": "The requested smart-home capability is unsupported.",
        "plan": None,
    }

    with pytest.raises(UnsupportedPlanningScenarioError):
        create_planner(output).plan(user_input)


@pytest.mark.parametrize(
    "output_factory, expected_tool",
    [
        (lambda: weather_high_risk_llm_output(), "weather_tool"),
        (lambda: valid_calendar_llm_output(), "calendar_tool"),
        (lambda: notification_llm_output(), "notification_tool"),
    ],
)
def test_non_smart_home_plans_do_not_over_select_smart_home(
    output_factory,
    expected_tool,
):
    task = create_planner(output_factory()).plan("unrelated explicit request")

    assert [step.tool_name for step in task.steps] == [expected_tool]
    assert "smart_home_tool" not in [step.tool_name for step in task.steps]


def test_notification_prompt_describes_immediate_only_boundary():
    planner = LLMPlanner(FakeLLMClient(valid_llm_output()))

    assert "immediate mock mobile notifications" in planner.system_prompt
    assert "Scheduled, delayed, conditional" in planner.system_prompt
    assert "Do not add notification_tool unless" in planner.system_prompt


def test_notification_plan_uses_risk_policy_over_llm_low_metadata():
    task = LLMPlanner(FakeLLMClient(notification_llm_output())).plan(
        "send me a notification now"
    )

    assert task.steps[0].tool_name == "notification_tool"
    assert task.risk_level == "MEDIUM"
    assert task.requires_confirmation is True
    assert task.confirmation_status == "PENDING"


def test_weather_plan_uses_risk_policy_over_llm_high_metadata():
    task = LLMPlanner(FakeLLMClient(weather_high_risk_llm_output())).plan(
        "will it rain tomorrow?"
    )

    assert task.steps[0].tool_name == "weather_tool"
    assert task.risk_level == "LOW"
    assert task.requires_confirmation is False
    assert task.confirmation_status == "NOT_REQUIRED"


def test_notification_calendar_plan_uses_highest_risk_policy():
    output = notification_llm_output()
    output["plan"]["steps"].append(
        {
            "order": 2,
            "description": "Check calendar.",
            "tool_name": "calendar_tool",
            "arguments": {"date": "tomorrow"},
        }
    )

    task = LLMPlanner(FakeLLMClient(output)).plan("notify me and check calendar")

    assert [step.tool_name for step in task.steps] == [
        "notification_tool",
        "calendar_tool",
    ]
    assert task.risk_level == "MEDIUM"
    assert task.requires_confirmation is True


def valid_calendar_llm_output() -> dict[str, Any]:
    return {
        "unsupported": False,
        "reason": None,
        "plan": {
            "goal": "查询明天上午的日程安排",
            "risk_level": "LOW",
            "requires_confirmation": False,
            "steps": [
                {
                    "order": 1,
                    "description": "查询明天上午的日程",
                    "tool_name": "calendar_tool",
                    "arguments": {
                        "date": "tomorrow",
                        "start_time": "06:00",
                        "end_time": "12:00",
                    },
                }
            ],
        },
    }


def notification_llm_output(
    *,
    risk_level: str = "LOW",
    requires_confirmation: bool = False,
) -> dict[str, Any]:
    return {
        "unsupported": False,
        "reason": None,
        "plan": {
            "goal": "Send an immediate mock mobile notification.",
            "risk_level": risk_level,
            "requires_confirmation": requires_confirmation,
            "steps": [
                {
                    "order": 1,
                    "description": "Send immediate notification.",
                    "tool_name": "notification_tool",
                    "arguments": {
                        "title": "Morning commute",
                        "message": "Your route is ready.",
                        "channel": "mobile",
                    },
                }
            ],
        },
    }


def weather_high_risk_llm_output() -> dict[str, Any]:
    return {
        "unsupported": False,
        "reason": None,
        "plan": {
            "goal": "Check weather.",
            "risk_level": "HIGH",
            "requires_confirmation": True,
            "steps": [
                {
                    "order": 1,
                    "description": "Check weather.",
                    "tool_name": "weather_tool",
                    "arguments": {
                        "location": "current_city",
                        "date": "tomorrow",
                    },
                }
            ],
        },
    }


def calendar_output_with_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    output = valid_calendar_llm_output()
    output["plan"]["steps"][0]["arguments"] = arguments
    return output


def create_planner(output: Mapping[str, Any]) -> LLMPlanner:
    return LLMPlanner(FakeLLMClient(output))


def test_valid_morning_commute_output_generates_task():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)

    assert task.goal == "安排明早通勤，确保按时到达公司参加会议"


def test_llm_planner_task_status_is_planned():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)

    assert task.status == TaskStatus.PLANNED


def test_llm_planner_generates_task_id():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)

    assert task.id.startswith("task-")


def test_llm_planner_generates_plan_step_ids():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)

    assert all(step.id.startswith("step-") for step in task.steps)


def test_llm_planner_tool_call_status_defaults_to_pending():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)

    assert all(step.tool_call.status == ToolCallStatus.PENDING for step in task.steps)


def test_confirmation_status_comes_from_task_invariant():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)

    assert task.requires_confirmation is False
    assert task.confirmation_status == ConfirmationStatus.NOT_REQUIRED


def test_weather_and_navigation_steps_are_converted_in_order():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)

    assert [step.order for step in task.steps] == [1, 2]
    assert task.steps[0].tool_name == "weather_tool"
    assert task.steps[1].tool_name == "navigation_tool"


def test_weather_arguments_are_converted():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)

    assert task.steps[0].tool_call.arguments == {
        "location": "current_city",
        "date": "tomorrow",
    }


def test_navigation_arguments_are_converted():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)

    assert task.steps[1].tool_call.arguments == {
        "origin": "home",
        "destination": "company",
        "departure_time": "tomorrow 08:30",
    }


def test_invalid_tool_is_rejected():
    output = valid_llm_output()
    output["plan"]["steps"][0]["tool_name"] = "unsupported_tool"

    with pytest.raises(PlannerOutputValidationError):
        create_planner(output).plan(USER_INPUT)


def test_calendar_tool_is_in_default_llm_planner_authorization():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    assert "calendar_tool" in client.calls[0]["system_prompt"]
    assert "calendar_tool" in planner.allowed_tools


def test_calendar_tool_spec_exposes_required_and_optional_arguments():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    prompt = client.calls[0]["system_prompt"]
    assert "calendar_tool" in prompt
    assert "- date" in prompt
    assert "Optional arguments:" in prompt
    assert "- start_time" in prompt
    assert "- end_time" in prompt


def test_duplicate_step_order_is_rejected():
    output = valid_llm_output()
    output["plan"]["steps"][0]["order"] = 1

    with pytest.raises(PlannerOutputValidationError):
        create_planner(output).plan(USER_INPUT)


def test_missing_schema_field_is_rejected():
    output = valid_llm_output()
    del output["plan"]["goal"]

    with pytest.raises(PlannerOutputValidationError):
        create_planner(output).plan(USER_INPUT)


def test_missing_required_tool_argument_is_rejected():
    output = valid_llm_output()
    del output["plan"]["steps"][0]["arguments"]["departure_time"]

    with pytest.raises(ToolArgumentValidationError):
        create_planner(output).plan(USER_INPUT)


def test_calendar_only_plan_generates_task():
    task = create_planner(valid_calendar_llm_output()).plan("calendar read request")

    assert task.steps[0].tool_name == "calendar_tool"
    assert task.steps[0].tool_call.arguments == {
        "date": "tomorrow",
        "start_time": "06:00",
        "end_time": "12:00",
    }


def test_calendar_plan_missing_date_is_rejected():
    output = valid_calendar_llm_output()
    del output["plan"]["steps"][0]["arguments"]["date"]

    with pytest.raises(ToolArgumentValidationError):
        create_planner(output).plan("calendar read request")


def test_calendar_plan_with_extra_argument_is_rejected():
    output = valid_calendar_llm_output()
    output["plan"]["steps"][0]["arguments"]["timezone"] = "Asia/Shanghai"

    with pytest.raises(ToolArgumentValidationError):
        create_planner(output).plan("calendar read request")


def test_calendar_read_is_low_risk_without_confirmation():
    task = create_planner(valid_calendar_llm_output()).plan("calendar read request")

    assert task.risk_level.name == "LOW"
    assert task.requires_confirmation is False


def test_calendar_morning_plan_preserves_temporal_window():
    task = create_planner(
        calendar_output_with_arguments(
            {"date": "tomorrow", "start_time": "06:00", "end_time": "12:00"}
        )
    ).plan("calendar morning request")

    assert task.steps[0].tool_call.arguments["start_time"] == "06:00"
    assert task.steps[0].tool_call.arguments["end_time"] == "12:00"


def test_calendar_afternoon_plan_preserves_temporal_window():
    task = create_planner(
        calendar_output_with_arguments(
            {"date": "tomorrow", "start_time": "12:00", "end_time": "18:00"}
        )
    ).plan("calendar afternoon request")

    assert task.steps[0].tool_call.arguments["start_time"] == "12:00"
    assert task.steps[0].tool_call.arguments["end_time"] == "18:00"


def test_calendar_whole_day_plan_can_omit_temporal_window():
    task = create_planner(calendar_output_with_arguments({"date": "tomorrow"})).plan(
        "calendar whole day request"
    )

    assert task.steps[0].tool_call.arguments == {"date": "tomorrow"}


def test_unsupported_output_does_not_create_task():
    output = {
        "unsupported": True,
        "reason": "The requested device is not supported.",
        "plan": None,
    }

    with pytest.raises(UnsupportedPlanningScenarioError):
        create_planner(output).plan("帮我把窗帘关上")


def test_calendar_write_unsupported_output_is_handled():
    output = {
        "unsupported": True,
        "reason": "calendar_tool is read-only and cannot create calendar events.",
        "plan": None,
    }

    with pytest.raises(UnsupportedPlanningScenarioError):
        create_planner(output).plan("calendar write request")


def test_dynamic_dependency_unsupported_output_is_handled():
    output = {
        "unsupported": True,
        "reason": (
            "Current planner does not support plans whose later tool arguments "
            "depend on runtime results from an earlier tool."
        ),
        "plan": None,
    }

    with pytest.raises(UnsupportedPlanningScenarioError):
        create_planner(output).plan("calendar then navigation request")


def test_llm_planner_does_not_execute_any_tool():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)

    for step in task.steps:
        assert step.status == ToolCallStatus.PENDING
        assert step.tool_call.result is None
        assert step.tool_call.error is None


def test_rule_based_and_llm_planners_follow_planner_contract():
    assert isinstance(RuleBasedPlanner(), Planner)
    assert isinstance(create_planner(valid_llm_output()), Planner)


def test_llm_client_receives_user_input_and_prompt():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    assert client.calls[0]["user_input"] == USER_INPUT
    assert "weather_tool" in client.calls[0]["system_prompt"]
    assert "navigation_tool" in client.calls[0]["system_prompt"]


def test_planner_prompt_contains_capability_boundary():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    prompt = client.calls[0]["system_prompt"]
    assert "cannot drive a vehicle" in prompt
    assert "A tool being related to the topic is not sufficient" in prompt
    assert "Requests to move a vehicle" in prompt
    assert "Identify the user's actual requested outcome" in prompt
    assert "information/planning or real-world physical control" in prompt


def test_planner_prompt_contains_minimal_tool_principle():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    prompt = client.calls[0]["system_prompt"]
    assert "smallest sufficient set of tools" in prompt
    assert "optional contextual tools" in prompt


def test_planner_prompt_requires_explicit_constraint_preservation():
    prompt = LLMPlanner(FakeLLMClient(valid_llm_output())).system_prompt

    assert "Preserve every explicit user-provided constraint" in prompt
    assert "explicit origin such as 心理所 or 学校" in prompt
    assert "Never degrade a specific clock time" in prompt
    assert '"departure_time": "tomorrow 08:30"' in prompt


def test_planner_prompt_supports_user_driving_with_assistant_planning():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    prompt = client.calls[0]["system_prompt"]
    assert "they will perform the physical action themselves" in prompt
    assert "assistant only for information or planning" in prompt
    assert "driving" in prompt


def test_planner_prompt_keeps_agent_vehicle_control_unsupported():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    prompt = client.calls[0]["system_prompt"]
    assert "asks the assistant to drive" in prompt
    assert "unsupported physical" in prompt
    assert "Do not map it to navigation_tool" in prompt


def test_planner_prompt_contains_calendar_read_and_write_boundary():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    prompt = client.calls[0]["system_prompt"]
    assert "Calendar read requests are supported" in prompt
    assert "Calendar write requests are unsupported" in prompt
    assert "create, update, delete" in prompt


def test_planner_prompt_contains_dynamic_dependency_boundary():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    prompt = client.calls[0]["system_prompt"]
    assert "later tool arguments depend on runtime results" in prompt
    assert "unsupported instead of guessing meeting time" in prompt


def test_planner_prompt_contains_calendar_temporal_conventions():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    prompt = client.calls[0]["system_prompt"]
    assert "Calendar temporal conventions:" in prompt
    assert "start_time=06:00, end_time=12:00" in prompt
    assert "start_time=12:00, end_time=18:00" in prompt
    assert "start_time=18:00, end_time=23:59" in prompt
    assert "omit start_time and end_time" in prompt
    assert "Optional schema fields" in prompt
    assert "still be populated" in prompt


def test_calendar_temporal_conventions_define_canonical_windows():
    assert CALENDAR_TEMPORAL_WINDOWS["morning"].start_time == "06:00"
    assert CALENDAR_TEMPORAL_WINDOWS["morning"].end_time == "12:00"
    assert CALENDAR_TEMPORAL_WINDOWS["afternoon"].start_time == "12:00"
    assert CALENDAR_TEMPORAL_WINDOWS["afternoon"].end_time == "18:00"
    assert CALENDAR_TEMPORAL_WINDOWS["evening"].start_time == "18:00"
    assert CALENDAR_TEMPORAL_WINDOWS["evening"].end_time == "23:59"
    assert CALENDAR_TEMPORAL_WINDOWS["whole_day"].start_time is None
    assert CALENDAR_TEMPORAL_WINDOWS["whole_day"].end_time is None


def test_planner_prompt_exposes_required_arguments_from_tool_schema():
    client = FakeLLMClient(valid_llm_output())
    planner = LLMPlanner(client)

    planner.plan(USER_INPUT)

    prompt = client.calls[0]["system_prompt"]
    assert "Required arguments:" in prompt
    assert "- departure_time" in prompt
    assert "provide every required argument defined by that tool's schema" in prompt


def test_llm_planner_task_executor_integration_completes_task():
    task = create_planner(valid_llm_output()).plan(USER_INPUT)
    registry = create_default_registry()
    task_executor = TaskExecutor(StepExecutor(ToolExecutor(registry)))

    executed = task_executor.execute(task)

    assert executed.status == TaskStatus.COMPLETED
    assert all(step.status == ToolCallStatus.SUCCESS for step in executed.steps)
    assert all(step.tool_call.status == ToolCallStatus.SUCCESS for step in executed.steps)
