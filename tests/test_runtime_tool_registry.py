from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient

from flowmate.agent import (
    AgentTaskService,
    LLMPlanner,
    UnsupportedPlanningScenarioError,
)
from flowmate.integrations.calendar import MockCalendarProvider
from flowmate.integrations.navigation import (
    AmapNavigationProvider,
    MockNavigationProvider,
)
from flowmate.integrations.notification import MockNotificationProvider
from flowmate.integrations.weather import (
    MockWeatherProvider,
    OpenMeteoWeatherProvider,
    WeatherProviderQuery,
    WeatherTransportError,
)
from flowmate.persistence import TaskPersistenceService
from flowmate.schemas import TaskStatus, ToolCallStatus
from flowmate.tools import (
    RuntimeToolConfigurationError,
    RuntimeToolMode,
    SmartHomeTool,
    VehicleTool,
    WeatherTool,
    create_default_registry,
    create_runtime_registry_from_env,
    runtime_provider_status,
    runtime_tool_mode_from_env,
)
from main import app


class FakeLLMClient:
    def __init__(self, output: Mapping[str, Any]) -> None:
        self.output = output

    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        return self.output


class FailingWeatherProvider:
    def __init__(self) -> None:
        self.calls: list[WeatherProviderQuery] = []

    def get_weather(self, query: WeatherProviderQuery):
        self.calls.append(query)
        raise WeatherTransportError("injected weather timeout")


def supported_plan(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "unsupported": False,
        "reason": None,
        "plan": {
            "goal": "Handle the request.",
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


def test_runtime_registry_defaults_to_all_mock(monkeypatch):
    monkeypatch.delenv("FLOWMATE_TOOL_MODE", raising=False)

    registry = create_runtime_registry_from_env()

    assert runtime_tool_mode_from_env() == RuntimeToolMode.MOCK
    assert isinstance(registry.get("weather_tool").provider, MockWeatherProvider)
    assert isinstance(registry.get("navigation_tool").provider, MockNavigationProvider)
    assert isinstance(registry.get("calendar_tool").provider, MockCalendarProvider)
    assert isinstance(registry.get("notification_tool").provider, MockNotificationProvider)
    assert isinstance(registry.get("smart_home_tool"), SmartHomeTool)
    assert isinstance(registry.get("vehicle_tool"), VehicleTool)
    assert set(runtime_provider_status().values()) == {"Mock"}


def test_real_information_mode_selects_only_real_read_providers(monkeypatch):
    monkeypatch.setenv("FLOWMATE_TOOL_MODE", "real_information")
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", "test-only-key")

    registry = create_runtime_registry_from_env()

    assert isinstance(registry.get("weather_tool").provider, OpenMeteoWeatherProvider)
    assert isinstance(registry.get("navigation_tool").provider, AmapNavigationProvider)
    assert isinstance(registry.get("calendar_tool").provider, MockCalendarProvider)
    assert isinstance(registry.get("notification_tool").provider, MockNotificationProvider)
    assert isinstance(registry.get("smart_home_tool"), SmartHomeTool)
    assert isinstance(registry.get("vehicle_tool"), VehicleTool)
    assert runtime_provider_status() == {
        "calendar": "Mock",
        "weather": "Open-Meteo Real Active",
        "navigation": "Amap Real Active",
        "notification": "Mock",
        "smart_home": "Mock",
        "vehicle": "Mock",
    }


def test_tool_contract_is_identical_between_mock_and_real_modes(monkeypatch):
    mock_registry = create_default_registry()
    monkeypatch.setenv("FLOWMATE_TOOL_MODE", "real_information")
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", "test-only-key")
    real_registry = create_runtime_registry_from_env()

    for tool_name in ("weather_tool", "navigation_tool"):
        mock_tool = mock_registry.get(tool_name)
        real_tool = real_registry.get(tool_name)
        assert type(real_tool) is type(mock_tool)
        assert real_tool.name == mock_tool.name
        assert real_tool.description == mock_tool.description
        assert real_tool.input_schema is mock_tool.input_schema


def test_real_information_mode_requires_amap_key(monkeypatch):
    monkeypatch.setenv("FLOWMATE_TOOL_MODE", "real_information")
    monkeypatch.delenv("AMAP_WEB_SERVICE_KEY", raising=False)

    with pytest.raises(RuntimeToolConfigurationError, match="AMAP_WEB_SERVICE_KEY"):
        create_runtime_registry_from_env()
    with pytest.raises(RuntimeToolConfigurationError, match="AMAP_WEB_SERVICE_KEY"):
        runtime_provider_status()


def test_invalid_runtime_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("FLOWMATE_TOOL_MODE", "automatic")

    with pytest.raises(RuntimeToolConfigurationError, match="FLOWMATE_TOOL_MODE"):
        create_runtime_registry_from_env()


def test_provider_failure_is_failed_once_and_persisted(tmp_path):
    provider = FailingWeatherProvider()
    registry = create_default_registry(weather_tool=WeatherTool(provider=provider))
    persistence = TaskPersistenceService(db_path=tmp_path / "provider-failure.db")
    service = AgentTaskService(
        LLMPlanner(
            FakeLLMClient(
                supported_plan(
                    "weather_tool",
                    {"location": "Beijing", "date": "tomorrow"},
                )
            ),
            tool_registry=registry,
        ),
        tool_registry=registry,
        persistence=persistence,
    )

    task = service.create_task("Check tomorrow's weather in Beijing")

    assert len(provider.calls) == 1
    assert task.status == TaskStatus.FAILED
    assert task.steps[0].status == ToolCallStatus.FAILED
    assert task.steps[0].tool_call.status == ToolCallStatus.FAILED
    assert task.steps[0].tool_call.result is None
    assert task.steps[0].tool_call.error == (
        "WeatherTransportError: injected weather timeout"
    )
    loaded = persistence.load(task.id)
    assert loaded == task


def test_real_information_mode_keeps_vehicle_high_risk_and_pending(monkeypatch, tmp_path):
    monkeypatch.setenv("FLOWMATE_TOOL_MODE", "real_information")
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", "test-only-key")
    registry = create_runtime_registry_from_env()
    service = AgentTaskService(
        LLMPlanner(
            FakeLLMClient(
                supported_plan(
                    "vehicle_tool",
                    {"vehicle_id": "my-car", "action": "unlock"},
                )
            ),
            tool_registry=registry,
        ),
        tool_registry=registry,
        persistence=TaskPersistenceService(db_path=tmp_path / "vehicle.db"),
    )

    task = service.create_task("Unlock my car")

    assert task.status == TaskStatus.WAITING_CONFIRMATION
    assert task.risk_level == "HIGH"
    assert task.confirmation_status == "PENDING"
    assert task.steps[0].tool_call.status == ToolCallStatus.PENDING
    assert task.steps[0].tool_call.result is None


def test_real_information_mode_does_not_expand_unsupported_capabilities(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("FLOWMATE_TOOL_MODE", "real_information")
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", "test-only-key")
    registry = create_runtime_registry_from_env()
    persistence = TaskPersistenceService(db_path=tmp_path / "unsupported.db")
    service = AgentTaskService(
        LLMPlanner(
            FakeLLMClient(
                {
                    "unsupported": True,
                    "reason": "No email tool is available.",
                    "plan": None,
                }
            ),
            tool_registry=registry,
        ),
        tool_registry=registry,
        persistence=persistence,
    )

    with pytest.raises(UnsupportedPlanningScenarioError):
        service.create_task("Write an email to my manager")

    assert persistence.list_history() == []


def test_system_status_reports_default_and_real_modes(monkeypatch, tmp_path):
    monkeypatch.setenv("FLOWMATE_DB_PATH", str(tmp_path / "status.db"))
    monkeypatch.delenv("FLOWMATE_TOOL_MODE", raising=False)
    client = TestClient(app)

    mock_response = client.get("/api/v1/system/status")
    assert mock_response.status_code == 200
    assert mock_response.json()["tool_mode"] == "mock"
    assert mock_response.json()["providers"]["weather"] == "Mock"

    monkeypatch.setenv("FLOWMATE_TOOL_MODE", "real_information")
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", "test-only-key")
    real_response = client.get("/api/v1/system/status")
    assert real_response.status_code == 200
    assert real_response.json()["tool_mode"] == "real_information"
    assert real_response.json()["providers"]["weather"] == "Open-Meteo Real Active"
    assert real_response.json()["providers"]["navigation"] == "Amap Real Active"


def test_system_and_agent_api_report_missing_real_provider_config(monkeypatch, tmp_path):
    monkeypatch.setenv("FLOWMATE_DB_PATH", str(tmp_path / "missing-key.db"))
    monkeypatch.setenv("FLOWMATE_TOOL_MODE", "real_information")
    monkeypatch.delenv("AMAP_WEB_SERVICE_KEY", raising=False)
    client = TestClient(app)

    status_response = client.get("/api/v1/system/status")
    task_response = client.post(
        "/api/v1/agent/tasks",
        json={"user_input": "Check tomorrow's weather in Beijing"},
    )

    assert status_response.status_code == 503
    assert "Tool provider unavailable" in status_response.json()["detail"]
    assert task_response.status_code == 503
    assert "Tool provider unavailable" in task_response.json()["detail"]
