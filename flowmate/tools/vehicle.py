from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from flowmate.tools.base import BaseTool


class VehicleAction(str, Enum):
    GET_STATUS = "get_status"
    LOCK = "lock"
    UNLOCK = "unlock"
    START_CLIMATE = "start_climate"
    STOP_CLIMATE = "stop_climate"


class VehicleToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_id: str = Field(min_length=1)
    action: VehicleAction
    temperature: int | float | None = None

    @field_validator("vehicle_id")
    @classmethod
    def validate_vehicle_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("vehicle_id must not be blank.")
        return normalized

    @field_validator("temperature", mode="before")
    @classmethod
    def reject_boolean_temperature(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("temperature must be numeric, not a boolean.")
        return value

    @model_validator(mode="after")
    def validate_action_arguments(self) -> "VehicleToolInput":
        if self.action != VehicleAction.START_CLIMATE:
            if self.temperature is not None:
                raise ValueError(f"{self.action.value} requires temperature=None.")
            return self

        if self.temperature is not None and not 16 <= self.temperature <= 30:
            raise ValueError("temperature must be between 16 and 30 degrees Celsius.")
        return self


class VehicleToolResult(BaseModel):
    vehicle_id: str
    action: VehicleAction
    status: Literal["mock_executed"]
    state: dict[str, Any]


class VehicleTool(BaseTool[VehicleToolInput, VehicleToolResult]):
    name = "vehicle_tool"
    description = (
        "Mock vehicle status and limited vehicle-control capability. No real "
        "vehicle is controlled. Autonomous driving, remote driving, and vehicle "
        "movement are unsupported."
    )
    input_schema = VehicleToolInput

    def execute(self, input_data: VehicleToolInput) -> VehicleToolResult:
        if input_data.action == VehicleAction.GET_STATUS:
            state: dict[str, Any] = {"locked": True, "climate": "off"}
        elif input_data.action == VehicleAction.LOCK:
            state = {"locked": True}
        elif input_data.action == VehicleAction.UNLOCK:
            state = {"locked": False}
        elif input_data.action == VehicleAction.START_CLIMATE:
            state = {"climate": "on"}
            if input_data.temperature is not None:
                state["temperature"] = input_data.temperature
        else:
            state = {"climate": "off"}

        return VehicleToolResult(
            vehicle_id=input_data.vehicle_id,
            action=input_data.action,
            status="mock_executed",
            state=state,
        )
