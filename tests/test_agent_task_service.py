from pathlib import Path
from typing import Any, Mapping

import pytest

from flowmate.agent import (
    AgentTaskService,
    LLMPlanner,
    PlannerOutputValidationError,
    UnsupportedPlanningScenarioError,
)
from flowmate.persistence import TaskPersistenceService
from flowmate.schemas import TaskStatus, ToolCallStatus


class FakeLLMClient:
    def __init__(self, outputs: Mapping[str, Mapping[str, Any]]) -> None:
        self.outputs = outputs
        self.calls: list[str] = []

    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        self.calls.append(user_input)
        return self.outputs[user_input]


def supported_plan(tool_name: str, arguments: dict[str, Any], goal: str) -> dict:
    return {
        "unsupported": False,
        "reason": None,
        "plan": {
            "goal": goal,
            "risk_level": "LOW",
            "requires_confirmation": False,
            "steps": [
                {
                    "order": 1,
                    "description": goal,
                    "tool_name": tool_name,
                    "arguments": arguments,
                }
            ],
        },
    }


def service_for(tmp_path: Path, outputs: Mapping[str, Mapping[str, Any]]):
    client = FakeLLMClient(outputs)
    service = AgentTaskService(
        LLMPlanner(client),
        persistence=TaskPersistenceService(db_path=tmp_path / "agent.db"),
    )
    return service, client


def test_free_text_reaches_llm_planner_and_executes_dynamic_arguments(tmp_path):
    user_input = "我明天9点从心理所出发去人民广场"
    service, client = service_for(
        tmp_path,
        {
            user_input: supported_plan(
                "navigation_tool",
                {
                    "origin": "心理所",
                    "destination": "人民广场",
                    "departure_time": "tomorrow 09:00",
                },
                "规划心理所到人民广场的路线",
            )
        },
    )

    task = service.create_task(user_input)

    assert client.calls == [user_input]
    assert task.user_input == user_input
    assert task.status == TaskStatus.COMPLETED
    assert task.steps[0].tool_call.arguments == {
        "origin": "心理所",
        "destination": "人民广场",
        "departure_time": "tomorrow 09:00",
    }
    assert task.steps[0].tool_call.status == ToolCallStatus.SUCCESS


def test_different_inputs_generate_different_tasks(tmp_path):
    first = "我明天9点从心理所出发去人民广场"
    second = "我明天下午6点从学校出发去公司"
    service, _ = service_for(
        tmp_path,
        {
            first: supported_plan(
                "navigation_tool",
                {
                    "origin": "心理所",
                    "destination": "人民广场",
                    "departure_time": "tomorrow 09:00",
                },
                "规划上午路线",
            ),
            second: supported_plan(
                "navigation_tool",
                {
                    "origin": "学校",
                    "destination": "company",
                    "departure_time": "tomorrow 18:00",
                },
                "规划下午路线",
            ),
        },
    )

    task_a = service.create_task(first)
    task_b = service.create_task(second)

    assert task_a.id != task_b.id
    assert task_a.goal != task_b.goal
    assert task_a.steps[0].tool_call.arguments != task_b.steps[0].tool_call.arguments


def test_explicit_time_cannot_be_degraded_to_daypart(tmp_path):
    user_input = "我明天9点从心理所出发去人民广场"
    service, _ = service_for(
        tmp_path,
        {
            user_input: supported_plan(
                "navigation_tool",
                {
                    "origin": "心理所",
                    "destination": "人民广场",
                    "departure_time": "tomorrow morning",
                },
                "规划路线",
            )
        },
    )

    with pytest.raises(PlannerOutputValidationError, match="departure time"):
        service.create_task(user_input)


def test_explicit_origin_cannot_be_replaced_by_home(tmp_path):
    user_input = "我明天9点从心理所出发去人民广场"
    service, _ = service_for(
        tmp_path,
        {
            user_input: supported_plan(
                "navigation_tool",
                {
                    "origin": "home",
                    "destination": "人民广场",
                    "departure_time": "tomorrow 09:00",
                },
                "规划路线",
            )
        },
    )

    with pytest.raises(PlannerOutputValidationError, match="origin"):
        service.create_task(user_input)


def test_explicit_home_and_company_can_use_canonical_aliases(tmp_path):
    user_input = "我明天8点从家出发去公司"
    service, _ = service_for(
        tmp_path,
        {
            user_input: supported_plan(
                "navigation_tool",
                {
                    "origin": "home",
                    "destination": "company",
                    "departure_time": "tomorrow 08:00",
                },
                "规划上班路线",
            )
        },
    )

    task = service.create_task(user_input)

    assert task.status == TaskStatus.COMPLETED
    assert task.steps[0].tool_call.arguments["origin"] == "home"


def test_missing_destination_cannot_be_invented(tmp_path):
    user_input = "我明天9点从心理所出发"
    service, _ = service_for(
        tmp_path,
        {
            user_input: supported_plan(
                "navigation_tool",
                {
                    "origin": "心理所",
                    "destination": "人民广场",
                    "departure_time": "tomorrow 09:00",
                },
                "规划路线",
            )
        },
    )

    with pytest.raises(PlannerOutputValidationError, match="destination is missing"):
        service.create_task(user_input)


def test_high_risk_vehicle_task_waits_for_confirmation(tmp_path):
    user_input = "解锁我的车"
    service, _ = service_for(
        tmp_path,
        {
            user_input: supported_plan(
                "vehicle_tool",
                {"vehicle_id": "my-car", "action": "unlock"},
                "解锁车辆",
            )
        },
    )

    task = service.create_task(user_input)

    assert task.risk_level == "HIGH"
    assert task.status == TaskStatus.WAITING_CONFIRMATION
    assert task.confirmation_status == "PENDING"
    assert task.steps[0].tool_call.status == ToolCallStatus.PENDING
    assert task.steps[0].tool_call.result is None


def test_unsupported_request_creates_no_task(tmp_path):
    user_input = "帮我写一封邮件给老板"
    service, _ = service_for(
        tmp_path,
        {
            user_input: {
                "unsupported": True,
                "reason": "No email tool is available.",
                "plan": None,
            }
        },
    )

    with pytest.raises(UnsupportedPlanningScenarioError):
        service.create_task(user_input)
    assert service.persistence.list_history() == []


def test_weather_only_request_uses_only_weather_tool(tmp_path):
    user_input = "帮我看看明天天气"
    service, _ = service_for(
        tmp_path,
        {
            user_input: supported_plan(
                "weather_tool",
                {"location": "current_city", "date": "tomorrow"},
                "查询明天天气",
            )
        },
    )

    task = service.create_task(user_input)

    assert [step.tool_name for step in task.steps] == ["weather_tool"]
    assert task.status == TaskStatus.COMPLETED
