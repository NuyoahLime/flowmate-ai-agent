from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from flowmate.schemas.enums import TriggerStatus, TriggerType


class TriggerDefinition(BaseModel):
    id: str
    trigger_type: TriggerType = TriggerType.CALENDAR_EVENT_LEAD_TIME
    status: TriggerStatus = TriggerStatus.ACTIVE
    source_event_id: str = Field(min_length=1)
    source_event_start: datetime
    source_event_location: str = Field(min_length=1)
    source_event_summary: Optional[str] = None
    lead_time_minutes: int = Field(gt=0)
    created_at: datetime
    last_evaluated_at: Optional[datetime] = None
    fired_at: Optional[datetime] = None
    generated_task_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_trigger_datetimes(self) -> "TriggerDefinition":
        for value in (
            self.source_event_start,
            self.created_at,
            self.last_evaluated_at,
            self.fired_at,
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError("Trigger datetimes must be timezone-aware.")
        return self

    @property
    def trigger_at(self) -> datetime:
        return self.source_event_start - timedelta(minutes=self.lead_time_minutes)
