from typing import Any, Optional

from pydantic import BaseModel, Field

from flowmate.schemas.enums import (
    DynamicPlanningFailureType,
    DynamicPlanningPhase,
)
from flowmate.schemas.task import Task


class ToolObservation(BaseModel):
    tool_name: str
    step_id: Optional[str] = None
    result: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class DynamicSideEffectProposal(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = None


class DynamicTaskResult(BaseModel):
    status: DynamicPlanningPhase
    selected_event: Optional[dict[str, Any]] = None
    observations: list[ToolObservation] = Field(default_factory=list)
    continuation_observations: list[ToolObservation] = Field(default_factory=list)
    weather_result: Optional[dict[str, Any]] = None
    navigation_result: Optional[dict[str, Any]] = None
    notification_task: Optional[Task] = None
    notification_result: Optional[dict[str, Any]] = None
    side_effect_status: Optional[str] = None
    failure_type: Optional[DynamicPlanningFailureType] = None
    error: Optional[str] = None


class DynamicPlanningState(BaseModel):
    user_input: str
    phase: DynamicPlanningPhase = DynamicPlanningPhase.INITIAL_PLANNING
    task: Optional[Task] = None
    observations: list[ToolObservation] = Field(default_factory=list)
    iteration_count: int = Field(default=0, ge=0)
    max_iterations: int = Field(default=2, ge=1)
    selected_event: Optional[dict[str, Any]] = None
    continuation_observations: list[ToolObservation] = Field(default_factory=list)
    side_effect_proposal: Optional[DynamicSideEffectProposal] = None
    notification_task: Optional[Task] = None
    notification_result: Optional[dict[str, Any]] = None
    side_effect_status: Optional[str] = None
    final_result: Optional[DynamicTaskResult] = None
    failure_type: Optional[DynamicPlanningFailureType] = None
    error: Optional[str] = None
