from typing import Any

from pydantic import BaseModel, Field, model_validator

from flowmate.schemas.enums import ConfirmationStatus, RiskLevel, TaskStatus
from flowmate.schemas.plan_step import PlanStep


class Task(BaseModel):
    id: str
    user_input: str
    goal: str
    status: TaskStatus = TaskStatus.CREATED
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    confirmation_status: ConfirmationStatus = ConfirmationStatus.NOT_REQUIRED
    steps: list[PlanStep] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_confirmation_status(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        requires_confirmation = data.get("requires_confirmation", False)
        confirmation_status = data.get(
            "confirmation_status",
            ConfirmationStatus.NOT_REQUIRED,
        )

        if isinstance(confirmation_status, ConfirmationStatus):
            confirmation_status_value = confirmation_status.value
        else:
            confirmation_status_value = confirmation_status

        if not requires_confirmation:
            data["confirmation_status"] = ConfirmationStatus.NOT_REQUIRED
        elif confirmation_status_value == ConfirmationStatus.NOT_REQUIRED.value:
            data["confirmation_status"] = ConfirmationStatus.PENDING

        return data
