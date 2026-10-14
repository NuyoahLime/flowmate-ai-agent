from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from flowmate.tools.base import BaseTool


class SmartHomeDeviceType(str, Enum):
    LIGHT = "light"
    AIR_CONDITIONER = "air_conditioner"


class SmartHomeAction(str, Enum):
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    SET_TEMPERATURE = "set_temperature"


class SmartHomeToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1)
    device_type: SmartHomeDeviceType
    action: SmartHomeAction
    value: int | float | None = None

    @field_validator("device_id")
    @classmethod
    def validate_device_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("device_id must not be blank.")
        return normalized

    @field_validator("value", mode="before")
    @classmethod
    def reject_boolean_value(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("value must be a numeric temperature, not a boolean.")
        return value

    @model_validator(mode="after")
    def validate_action_contract(self) -> "SmartHomeToolInput":
        if self.action in {SmartHomeAction.TURN_ON, SmartHomeAction.TURN_OFF}:
            if self.value is not None:
                raise ValueError(f"{self.action.value} requires value=None.")
            return self

        if self.device_type != SmartHomeDeviceType.AIR_CONDITIONER:
            raise ValueError("set_temperature is only valid for air_conditioner.")
        if self.value is None:
            raise ValueError("set_temperature requires an explicit value.")
        if not 16 <= self.value <= 30:
            raise ValueError("temperature must be between 16 and 30 degrees Celsius.")
        return self


class SmartHomeToolResult(BaseModel):
    device_id: str
    device_type: SmartHomeDeviceType
    action: SmartHomeAction
    status: Literal["mock_executed"]
    state: dict[str, Any]


class SmartHomeTool(BaseTool[SmartHomeToolInput, SmartHomeToolResult]):
    name = "smart_home_tool"
    description = (
        "Mock smart-home device control for supported light and air-conditioner "
        "actions. No real physical device is controlled."
    )
    input_schema = SmartHomeToolInput

    def execute(self, input_data: SmartHomeToolInput) -> SmartHomeToolResult:
        if input_data.action == SmartHomeAction.SET_TEMPERATURE:
            state: dict[str, Any] = {"temperature": input_data.value}
        else:
            state = {
                "power": (
                    "on" if input_data.action == SmartHomeAction.TURN_ON else "off"
                )
            }

        return SmartHomeToolResult(
            device_id=input_data.device_id,
            device_type=input_data.device_type,
            action=input_data.action,
            status="mock_executed",
            state=state,
        )
