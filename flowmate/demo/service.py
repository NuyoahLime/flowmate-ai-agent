from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from flowmate.agent import (
    DynamicTaskOrchestrator,
    RiskPolicy,
    StepExecutor,
    TaskConfirmationService,
    TaskExecutor,
    ToolExecutor,
)
from flowmate.integrations.calendar.mock_provider import MockCalendarProvider
from flowmate.persistence import TaskPersistenceService
from flowmate.schemas import (
    ConfirmationStatus,
    DynamicPlanningState,
    PlanStep,
    RiskLevel,
    Task,
    TaskStatus,
    ToolCall,
)
from flowmate.tools import (
    CalendarTool,
    NavigationTool,
    NotificationTool,
    SmartHomeTool,
    ToolRegistry,
    VehicleTool,
    WeatherTool,
)
from flowmate.tools.calendar import CalendarEvent


class DemoTaskRequest(BaseModel):
    scenario: str = Field(default="morning_commute")
    user_input: str = Field(min_length=1)


class DemoTaskResponse(BaseModel):
    scenario: str
    task: dict | None = None
    notification_task: dict | None = None
    dynamic_state: dict | None = None


class DemoTaskService:
    def __init__(
        self,
        persistence: TaskPersistenceService | None = None,
    ) -> None:
        self.persistence = persistence or TaskPersistenceService()
        self.risk_policy = RiskPolicy()
        self.confirmation_service = TaskConfirmationService()

    def create_demo_task(self, request: DemoTaskRequest) -> DemoTaskResponse:
        if request.scenario == "morning_commute":
            return self._run_morning_commute(request.user_input)
        if request.scenario == "smart_home_safety":
            task = self._build_smart_home_task(request.user_input)
            self.persistence.persist(task)
            return DemoTaskResponse(scenario=request.scenario, task=task.model_dump(mode="json"))
        if request.scenario == "vehicle_safety":
            task = self._build_vehicle_task(request.user_input)
            self.persistence.persist(task)
            return DemoTaskResponse(scenario=request.scenario, task=task.model_dump(mode="json"))
        raise ValueError(f"Unsupported demo scenario: {request.scenario}")

    def _run_morning_commute(self, user_input: str) -> DemoTaskResponse:
        orchestrator = DynamicTaskOrchestrator(
            ToolExecutor(self._demo_registry()),
            max_iterations=2,
        )
        state = orchestrator.execute(
            "tomorrow morning meeting departure route weather notify me when ready"
        )
        if state.task is not None:
            state.task.user_input = user_input
            self.persistence.persist(state.task)
        if state.notification_task is not None:
            state.notification_task.user_input = user_input
            self.persistence.persist(state.notification_task)
        return DemoTaskResponse(
            scenario="morning_commute",
            task=state.task.model_dump(mode="json") if state.task else None,
            notification_task=(
                state.notification_task.model_dump(mode="json")
                if state.notification_task
                else None
            ),
            dynamic_state=self._safe_dynamic_state(state),
        )

    def _build_smart_home_task(self, user_input: str) -> Task:
        task = Task(
            id="demo-task-smart-home-safety",
            user_input=user_input,
            goal="Turn off a mock living room light after confirmation.",
            status=TaskStatus.PLANNED,
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            steps=[
                PlanStep(
                    id="demo-step-smart-home",
                    order=1,
                    description="Turn off mock living room light.",
                    tool_name="smart_home_tool",
                    tool_call=ToolCall(
                        tool_name="smart_home_tool",
                        arguments={
                            "device_id": "living-room-light",
                            "device_type": "light",
                            "action": "turn_off",
                        },
                    ),
                )
            ],
        )
        self.risk_policy.apply_to_task(task)
        self.confirmation_service.request_confirmation(task)
        return task

    def _build_vehicle_task(self, user_input: str) -> Task:
        task = Task(
            id="demo-task-vehicle-safety",
            user_input=user_input,
            goal="Unlock a mock vehicle after high-risk confirmation.",
            status=TaskStatus.PLANNED,
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            steps=[
                PlanStep(
                    id="demo-step-vehicle",
                    order=1,
                    description="Unlock mock vehicle.",
                    tool_name="vehicle_tool",
                    tool_call=ToolCall(
                        tool_name="vehicle_tool",
                        arguments={
                            "vehicle_id": "my-car",
                            "action": "unlock",
                        },
                    ),
                )
            ],
        )
        self.risk_policy.apply_to_task(task)
        self.confirmation_service.request_confirmation(task)
        return task

    def create_executor(self) -> TaskExecutor:
        return TaskExecutor(StepExecutor(ToolExecutor(self._demo_registry())))

    def _demo_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(
            CalendarTool(
                provider=MockCalendarProvider(
                    events_by_date={
                        "tomorrow": [
                            CalendarEvent(
                                id="demo-event-morning-meeting",
                                title="Morning Meeting",
                                start_time="08:30",
                                end_time="09:30",
                                location="人民广场",
                            )
                        ]
                    }
                )
            )
        )
        registry.register(WeatherTool())
        registry.register(NavigationTool())
        registry.register(NotificationTool())
        registry.register(SmartHomeTool())
        registry.register(VehicleTool())
        return registry

    def _safe_dynamic_state(self, state: DynamicPlanningState) -> dict:
        return {
            "phase": state.phase.value,
            "selected_event": state.selected_event,
            "observations": [item.model_dump(mode="json") for item in state.observations],
            "continuation_observations": [
                item.model_dump(mode="json") for item in state.continuation_observations
            ],
            "side_effect_status": state.side_effect_status,
            "failure_type": state.failure_type.value if state.failure_type else None,
            "error": state.error,
        }


def demo_mode_enabled() -> bool:
    import os

    return os.getenv("FLOWMATE_DEMO_MODE", "false").lower() == "true"
