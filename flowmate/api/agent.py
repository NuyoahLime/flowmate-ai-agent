from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from flowmate.agent import (
    LLMClientConfigurationError,
    LLMProviderError,
    PlannerOutputValidationError,
    RiskPolicyError,
    TaskExecutionError,
    ToolArgumentValidationError,
    UnsupportedPlanningScenarioError,
)
from flowmate.agent.agent_task_service import AgentTaskResult, AgentTaskService
from flowmate.schemas import Task
from flowmate.tools import RuntimeToolConfigurationError


router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


class AgentTaskRequest(BaseModel):
    user_input: str = Field(min_length=1)


def get_agent_task_service() -> AgentTaskService:
    try:
        return AgentTaskService.from_env()
    except LLMClientConfigurationError as exc:
        raise HTTPException(status_code=503, detail=f"Planner unavailable: {exc}") from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=503, detail=f"Planner unavailable: {exc}") from exc
    except RuntimeToolConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Tool provider unavailable: {exc}",
        ) from exc


@router.post("/tasks", response_model=AgentTaskResult)
def create_agent_task(
    request: AgentTaskRequest,
    service: AgentTaskService = Depends(get_agent_task_service),
):
    try:
        return service.create_task_result(request.user_input)
    except UnsupportedPlanningScenarioError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported planning scenario: {exc}",
        ) from exc
    except LLMClientConfigurationError as exc:
        raise HTTPException(status_code=503, detail=f"Planner unavailable: {exc}") from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=f"Planner provider failed: {exc}") from exc
    except (PlannerOutputValidationError, ToolArgumentValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"Planner output invalid: {exc}") from exc
    except (RiskPolicyError, TaskExecutionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
