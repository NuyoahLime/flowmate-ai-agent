from typing import Any, Mapping

from fastapi.testclient import TestClient

from flowmate.agent import AgentTaskService, LLMPlanner, LLMProviderError
from flowmate.api.agent import get_agent_task_service
from flowmate.persistence import TaskPersistenceService
from main import app


ROUTE_INPUT = (
    "\u6211\u660e\u5929 9 \u70b9\u4ece\u5fc3\u7406\u6240"
    "\u51fa\u53d1\u53bb\u4eba\u6c11\u5e7f\u573a"
)
ORIGIN = "\u5fc3\u7406\u6240"
DESTINATION = "\u4eba\u6c11\u5e7f\u573a"
UNSUPPORTED_EMAIL_INPUT = "\u5e2e\u6211\u5199\u4e00\u5c01\u90ae\u4ef6\u7ed9\u8001\u677f"
WEATHER_INPUT = "\u5e2e\u6211\u770b\u770b\u660e\u5929\u5929\u6c14"
DYNAMIC_COMMUTE_REMINDER_INPUT = (
    "\u660e\u65e9 8:30 \u516c\u53f8\u5f00\u4f1a\uff0c"
    "\u5e2e\u6211\u5b89\u6392\u597d\u51fa\u95e8\u5e76\u63d0\u9192\u6211\u3002"
)


class FakeLLMClient:
    def __init__(self, output: Mapping[str, Any]) -> None:
        self.output = output
        self.user_inputs: list[str] = []

    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        self.user_inputs.append(user_input)
        return self.output


class FailingLLMClient:
    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        raise LLMProviderError("Provider request failed")


def planner_output(tool_name: str, arguments: dict[str, Any]) -> dict:
    return {
        "unsupported": False,
        "reason": None,
        "plan": {
            "goal": "Handle the free-text request.",
            "risk_level": "LOW",
            "requires_confirmation": False,
            "steps": [
                {
                    "order": 1,
                    "description": "Use the required tool.",
                    "tool_name": tool_name,
                    "arguments": arguments,
                }
            ],
        },
    }


def test_agent_api_accepts_only_user_input_and_returns_task(tmp_path):
    fake = FakeLLMClient(
        planner_output(
            "navigation_tool",
            {
                "origin": ORIGIN,
                "destination": DESTINATION,
                "departure_time": "tomorrow 09:00",
            },
        )
    )
    service = AgentTaskService(
        LLMPlanner(fake),
        persistence=TaskPersistenceService(db_path=tmp_path / "api.db"),
    )
    app.dependency_overrides[get_agent_task_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/agent/tasks",
            json={"user_input": ROUTE_INPUT},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake.user_inputs == [ROUTE_INPUT]
    body = response.json()
    task = body["task"]
    assert task["user_input"] == ROUTE_INPUT
    assert task["status"] == "COMPLETED"
    assert task["steps"][0]["tool_call"]["arguments"]["origin"] == ORIGIN
    assert body["notification_task"] is None
    assert body["dynamic_state"] is None


def test_agent_api_routes_dynamic_commute_with_reminder_to_dynamic_chain(tmp_path):
    service = AgentTaskService(
        LLMPlanner(FakeLLMClient({})),
        persistence=TaskPersistenceService(db_path=tmp_path / "dynamic-agent.db"),
    )
    app.dependency_overrides[get_agent_task_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/agent/tasks",
            json={"user_input": DYNAMIC_COMMUTE_REMINDER_INPUT},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["task"]["status"] == "COMPLETED"
    assert [step["tool_name"] for step in body["task"]["steps"]] == [
        "calendar_tool",
        "navigation_tool",
    ]
    assert body["notification_task"]["status"] == "WAITING_CONFIRMATION"
    assert body["notification_task"]["confirmation_status"] == "PENDING"
    assert body["notification_task"]["steps"][0]["tool_name"] == "notification_tool"
    assert body["dynamic_state"]["selected_event"]["start_time"] == "08:30"


def test_agent_api_reports_unsupported_without_task(tmp_path):
    fake = FakeLLMClient(
        {"unsupported": True, "reason": "No email tool is available.", "plan": None}
    )
    persistence = TaskPersistenceService(db_path=tmp_path / "unsupported.db")
    service = AgentTaskService(LLMPlanner(fake), persistence=persistence)
    app.dependency_overrides[get_agent_task_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/agent/tasks",
            json={"user_input": UNSUPPORTED_EMAIL_INPUT},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "Unsupported planning scenario" in response.json()["detail"]
    assert persistence.list_history() == []


def test_agent_api_reports_invalid_planner_output(tmp_path):
    fake = FakeLLMClient(
        planner_output(
            "navigation_tool",
            {
                "origin": "home",
                "destination": DESTINATION,
                "departure_time": "tomorrow morning",
            },
        )
    )
    service = AgentTaskService(
        LLMPlanner(fake),
        persistence=TaskPersistenceService(db_path=tmp_path / "invalid.db"),
    )
    app.dependency_overrides[get_agent_task_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/agent/tasks",
            json={"user_input": ROUTE_INPUT},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "Planner output invalid" in response.json()["detail"]


def test_agent_api_reports_missing_llm_configuration(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    response = TestClient(app).post(
        "/api/v1/agent/tasks",
        json={"user_input": WEATHER_INPUT},
    )

    assert response.status_code == 503
    assert "Planner unavailable" in response.json()["detail"]


def test_agent_api_reports_provider_failure(tmp_path):
    service = AgentTaskService(
        LLMPlanner(FailingLLMClient()),
        persistence=TaskPersistenceService(db_path=tmp_path / "provider-failure.db"),
    )
    app.dependency_overrides[get_agent_task_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/agent/tasks",
            json={"user_input": "Check tomorrow's weather"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert "Planner provider failed" in response.json()["detail"]
