from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalendarProviderError(Exception):
    pass


class CalendarProviderQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str = Field(min_length=1)
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class ResolvedCalendarWindow(BaseModel):
    start: datetime
    end: datetime
    timezone: str

    @model_validator(mode="after")
    def validate_window(self) -> "ResolvedCalendarWindow":
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Calendar window datetimes must be timezone-aware.")
        if self.end <= self.start:
            raise ValueError("Calendar window end must be after start.")
        return self


class CalendarProvider(Protocol):
    def list_events(self, query: CalendarProviderQuery) -> list["CalendarEvent"]:
        ...
