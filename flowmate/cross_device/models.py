from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DeviceType(str, Enum):
    PHONE = "PHONE"
    CAR = "CAR"


class DeviceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class DeviceCapability(str, Enum):
    CALENDAR = "CALENDAR"
    WEATHER = "WEATHER"
    NAVIGATION = "NAVIGATION"
    NAVIGATION_VIEW = "NAVIGATION_VIEW"
    NOTIFICATION = "NOTIFICATION"
    VEHICLE_STATUS = "VEHICLE_STATUS"


class HandoffStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    created_at: datetime


class Device(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    device_type: DeviceType
    display_name: str = Field(min_length=1)
    status: DeviceStatus
    last_seen_at: datetime | None = None
    created_at: datetime
    capabilities: list[DeviceCapability] = Field(default_factory=list)


class TaskDeviceState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    owner_user_id: str = Field(min_length=1)
    origin_device_id: str = Field(min_length=1)
    current_device_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    updated_at: datetime


class HandoffContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    meeting_summary: str | None = None
    meeting_start: str | None = None
    destination: str | None = None
    navigation_summary: str | None = None
    risk_level: str
    confirmation_status: str


class Handoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    source_device_id: str = Field(min_length=1)
    target_device_id: str = Field(min_length=1)
    required_capability: DeviceCapability
    status: HandoffStatus
    context: HandoffContext
    created_at: datetime
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    cancelled_at: datetime | None = None
    task_version: int = Field(ge=1)


class RoutingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    recommended_device: str
    reason: str
    capability: DeviceCapability
    available: bool
