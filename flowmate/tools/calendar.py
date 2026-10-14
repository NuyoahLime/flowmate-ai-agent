from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flowmate.tools.base import BaseTool

if TYPE_CHECKING:
    from flowmate.integrations.calendar import CalendarProvider


class CalendarEvent(BaseModel):
    id: str
    title: str
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    location: Optional[str] = None
    description: Optional[str] = None


class CalendarToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str = Field(min_length=1)
    start_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class CalendarToolResult(BaseModel):
    date: str
    events: list[CalendarEvent]
    event_count: int

    @model_validator(mode="after")
    def validate_event_count(self) -> "CalendarToolResult":
        if self.event_count != len(self.events):
            raise ValueError("event_count must equal len(events).")
        return self


class CalendarTool(BaseTool[CalendarToolInput, CalendarToolResult]):
    name = "calendar_tool"
    description = (
        "Read-only mock calendar query for events on a date or inside a time window. "
        "Cannot create, update, delete, accept, reject, or cancel calendar events."
    )
    input_schema = CalendarToolInput

    def __init__(self, provider: CalendarProvider | None = None) -> None:
        if provider is None:
            from flowmate.integrations.calendar.mock_provider import MockCalendarProvider

            provider = MockCalendarProvider()
        self.provider = provider

    def execute(self, input_data: CalendarToolInput) -> CalendarToolResult:
        from flowmate.integrations.calendar.provider import CalendarProviderQuery

        provider = getattr(self, "provider", None)
        if provider is None:
            from flowmate.integrations.calendar.mock_provider import MockCalendarProvider

            provider = MockCalendarProvider()
            self.provider = provider

        events = provider.list_events(
            CalendarProviderQuery(
                date=input_data.date,
                start_time=input_data.start_time,
                end_time=input_data.end_time,
            )
        )
        filtered_events = [
            event
            for event in events
            if self._is_in_time_window(
                event,
                start_time=input_data.start_time,
                end_time=input_data.end_time,
            )
        ]
        return CalendarToolResult(
            date=input_data.date,
            events=filtered_events,
            event_count=len(filtered_events),
        )

    def _is_in_time_window(
        self,
        event: CalendarEvent,
        *,
        start_time: str | None,
        end_time: str | None,
    ) -> bool:
        if start_time is not None and event.start_time < start_time:
            return False
        if end_time is not None and event.start_time >= end_time:
            return False
        return True
