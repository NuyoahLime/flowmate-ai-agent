from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from flowmate.schemas.enums import RiskLevel


class PlannedStep(BaseModel):
    order: int = Field(gt=0)
    description: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class PlannedTask(BaseModel):
    goal: str
    risk_level: RiskLevel
    requires_confirmation: bool
    steps: list[PlannedStep]

    @model_validator(mode="after")
    def validate_unique_step_orders(self) -> "PlannedTask":
        orders = [step.order for step in self.steps]
        if len(orders) != len(set(orders)):
            raise ValueError("PlannedStep order values must be unique.")

        return self


class LLMPlanResponse(BaseModel):
    unsupported: bool
    reason: Optional[str] = None
    plan: Optional[PlannedTask] = None

    @model_validator(mode="after")
    def validate_supported_plan_shape(self) -> "LLMPlanResponse":
        if self.unsupported:
            if not self.reason:
                raise ValueError("Unsupported LLM plan responses must include reason.")
            if self.plan is not None:
                raise ValueError("Unsupported LLM plan responses must not include plan.")
        else:
            if self.plan is None:
                raise ValueError("Supported LLM plan responses must include plan.")

        return self
