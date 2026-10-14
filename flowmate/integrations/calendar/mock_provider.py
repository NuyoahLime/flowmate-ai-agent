from collections.abc import Mapping

from flowmate.integrations.calendar.provider import CalendarProviderQuery
from flowmate.tools.calendar import CalendarEvent


DEFAULT_MOCK_CALENDAR_EVENTS = {
    "tomorrow": [
        CalendarEvent(
            id="event-001",
            title="Product Weekly Meeting",
            start_time="08:30",
            end_time="09:30",
            location="company",
        ),
        CalendarEvent(
            id="event-002",
            title="Project Review",
            start_time="14:00",
            end_time="15:00",
            location="company",
        ),
    ]
}


class MockCalendarProvider:
    def __init__(
        self,
        events_by_date: Mapping[str, list[CalendarEvent]] | None = None,
    ) -> None:
        self.events_by_date = events_by_date or DEFAULT_MOCK_CALENDAR_EVENTS

    def list_events(self, query: CalendarProviderQuery) -> list[CalendarEvent]:
        return [event.model_copy(deep=True) for event in self.events_by_date.get(query.date, [])]
