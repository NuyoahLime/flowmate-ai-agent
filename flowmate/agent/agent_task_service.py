from __future__ import annotations

from pydantic import BaseModel

from flowmate.agent.dynamic_task_orchestrator import DynamicTaskOrchestrator
from flowmate.agent.llm_client import LLMClientConfig
from flowmate.agent.llm_planner import LLMPlanner
from flowmate.agent.openai_llm_client import OpenAILLMClient
from flowmate.agent.planner import Planner
from flowmate.agent.retrying_llm_client import RetryingLLMClient
from flowmate.agent.risk_policy import RiskPolicy
from flowmate.agent.step_executor import StepExecutor
from flowmate.agent.task_confirmation import TaskConfirmationService
from flowmate.agent.task_executor import TaskExecutor
from flowmate.agent.tool_executor import ToolExecutor
from flowmate.persistence import TaskPersistenceService
from flowmate.schemas import Task
from flowmate.tools import (
    ToolRegistry,
    create_default_registry,
    create_runtime_registry_from_env,
)


class AgentTaskResult(BaseModel):
    task: Task | None = None
    notification_task: Task | None = None
    dynamic_state: dict | None = None


class AgentTaskService:
    def __init__(
        self,
        planner: Planner,
        *,
        tool_registry: ToolRegistry | None = None,
        persistence: TaskPersistenceService | None = None,
        risk_policy: RiskPolicy | None = None,
        confirmation_service: TaskConfirmationService | None = None,
        task_executor: TaskExecutor | None = None,
    ) -> None:
        self.planner = planner
        self.tool_registry = tool_registry or create_default_registry()
        self.persistence = persistence or TaskPersistenceService()
        self.risk_policy = risk_policy or RiskPolicy()
        self.confirmation_service = confirmation_service or TaskConfirmationService()
        self.task_executor = task_executor or TaskExecutor(
            StepExecutor(ToolExecutor(self.tool_registry))
        )

    @classmethod
    def from_env(cls) -> "AgentTaskService":
        registry = create_runtime_registry_from_env()
        provider_client = OpenAILLMClient(LLMClientConfig.from_env())
        planner = LLMPlanner(
            RetryingLLMClient(provider_client, max_attempts=2),
            tool_registry=registry,
        )
        return cls(planner, tool_registry=registry)

    def create_task(self, user_input: str) -> Task:
        return self.create_task_result(user_input).task

    def create_task_result(self, user_input: str) -> AgentTaskResult:
        dynamic_result = self._try_dynamic_task(user_input)
        if dynamic_result is not None:
            return dynamic_result

        task = self.planner.plan(user_input)
        self.risk_policy.apply_to_task(task)

        if task.requires_confirmation:
            self.confirmation_service.request_confirmation(task)
        else:
            self.task_executor.execute(task)

        self.persistence.persist(task)
        return AgentTaskResult(task=task)

    def _try_dynamic_task(self, user_input: str) -> AgentTaskResult | None:
        if not self._should_use_dynamic_orchestrator(user_input):
            return None

        orchestrator = DynamicTaskOrchestrator(
            ToolExecutor(self.tool_registry),
            max_iterations=2,
        )
        state = orchestrator.execute(user_input)
        if state.task is None:
            return None

        self.persistence.persist(state.task)
        if state.notification_task is not None:
            self.persistence.persist(state.notification_task)

        return AgentTaskResult(
            task=state.task,
            notification_task=state.notification_task,
            dynamic_state={
                "phase": state.phase.value,
                "selected_event": state.selected_event,
                "observations": [
                    observation.model_dump(mode="json")
                    for observation in state.observations
                ],
                "continuation_observations": [
                    observation.model_dump(mode="json")
                    for observation in state.continuation_observations
                ],
                "side_effect_status": state.side_effect_status,
                "failure_type": state.failure_type.value if state.failure_type else None,
                "error": state.error,
            },
        )

    def _should_use_dynamic_orchestrator(self, user_input: str) -> bool:
        text = user_input.lower()
        has_morning = any(
            marker in text
            for marker in (
                "\u660e\u65e9",
                "\u660e\u5929\u65e9\u4e0a",
                "\u660e\u5929\u4e0a\u5348",
                "tomorrow morning",
                "morning",
            )
        )
        has_departure_or_commute = any(
            marker in text
            for marker in (
                "\u51fa\u95e8",
                "\u901a\u52e4",
                "\u8def\u7ebf",
                "\u51e0\u70b9\u8d77\u5e8a",
                "\u51e0\u70b9\u8d77",
                "departure",
                "commute",
                "route",
            )
        )
        has_calendar_anchor = any(
            marker in text
            for marker in (
                "\u5f00\u4f1a",
                "\u4f1a\u8bae",
                "\u65e5\u7a0b",
                "\u516c\u53f8",
                "meeting",
                "schedule",
                "company",
            )
        )
        return has_morning and has_departure_or_commute and has_calendar_anchor
