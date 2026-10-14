from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from flowmate.agent import ToolExecutor
from flowmate.integrations.calendar import (
    CalendarProviderQuery,
    CalendarTemporalResolver,
    GoogleCalendarMappingError,
    GoogleCalendarProvider,
    GoogleCalendarResponseError,
    GoogleCalendarTransportError,
)
from flowmate.schemas import ToolCall, ToolCallStatus
from flowmate.tools import CalendarTool, ToolRegistry


FIXED_NOW = datetime(2026, 8, 9, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


def timed_event(**overrides):
    event = {
        "id": "google-event-001",
        "summary": "Product Meeting",
        "start": {"dateTime": "2026-08-10T00:30:00Z"},
        "end": {"dateTime": "2026-08-10T01:30:00Z"},
        "location": "company",
        "description": "Private meeting details",
    }
    event.update(overrides)
    return event


class FakeRequest:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def execute(self):
        if self.error is not None:
            raise self.error
        return self.response


class FakeEventsResource:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def list(self, **parameters):
        self.calls.append(parameters)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            return FakeRequest(error=response)
        return FakeRequest(response=response)


class FakeGoogleService:
    def __init__(self, responses):
        self.resource = FakeEventsResource(responses)

    def events(self):
        return self.resource


def create_provider(responses, calendar_id="primary", timezone="Asia/Shanghai"):
    service = FakeGoogleService(responses)
    resolver = CalendarTemporalResolver(timezone=timezone, clock=lambda: FIXED_NOW)
    provider = GoogleCalendarProvider(
        service=service,
        calendar_id=calendar_id,
        timezone=timezone,
        resolver=resolver,
    )
    return provider, service


def test_query_maps_google_events_list_parameters():
    provider, service = create_provider([{"items": [timed_event()]}])

    events = provider.list_events(
        CalendarProviderQuery(
            date="tomorrow",
            start_time="06:00",
            end_time="12:00",
        )
    )

    call = service.resource.calls[0]
    assert call == {
        "calendarId": "primary",
        "timeMin": "2026-08-10T06:00:00+08:00",
        "timeMax": "2026-08-10T12:00:00+08:00",
        "singleEvents": True,
        "orderBy": "startTime",
        "showDeleted": False,
        "timeZone": "Asia/Shanghai",
    }
    assert events[0].start_time == "08:30"
    assert events[0].end_time == "09:30"


def test_custom_calendar_id_and_explicit_timezone_are_used():
    provider, service = create_provider(
        [{"items": []}],
        calendar_id="team-calendar",
        timezone="Asia/Shanghai",
    )

    provider.list_events(CalendarProviderQuery(date="tomorrow"))

    assert service.resource.calls[0]["calendarId"] == "team-calendar"
    assert service.resource.calls[0]["timeZone"] == "Asia/Shanghai"


def test_pagination_reads_every_page_in_order():
    provider, service = create_provider(
        [
            {"items": [timed_event(id="page-1")], "nextPageToken": "next-page"},
            {"items": [timed_event(id="page-2")]},
        ]
    )

    events = provider.list_events(CalendarProviderQuery(date="tomorrow"))

    assert [event.id for event in events] == ["page-1", "page-2"]
    assert "pageToken" not in service.resource.calls[0]
    assert service.resource.calls[1]["pageToken"] == "next-page"


def test_recurring_instance_compatible_response_maps_as_timed_event():
    recurring = timed_event(
        id="recurring-instance",
        recurringEventId="series-001",
        originalStartTime={"dateTime": "2026-08-10T00:30:00Z"},
    )
    provider, _ = create_provider([{"items": [recurring]}])

    events = provider.list_events(CalendarProviderQuery(date="tomorrow"))

    assert events[0].id == "recurring-instance"


def test_missing_summary_location_and_description_use_safe_mapping():
    raw_event = timed_event()
    raw_event.pop("summary")
    raw_event.pop("location")
    raw_event.pop("description")
    provider, _ = create_provider([{"items": [raw_event]}])

    event = provider.list_events(CalendarProviderQuery(date="tomorrow"))[0]

    assert event.title == "(untitled)"
    assert event.location is None
    assert event.description is None


def test_all_day_event_is_skipped_without_fabricated_times():
    all_day = {
        "id": "all-day-001",
        "summary": "Holiday",
        "start": {"date": "2026-08-10"},
        "end": {"date": "2026-08-11"},
    }
    provider, _ = create_provider([{"items": [all_day, timed_event()]}])

    events = provider.list_events(CalendarProviderQuery(date="tomorrow"))

    assert [event.id for event in events] == ["google-event-001"]


def test_empty_event_list_is_valid():
    provider, _ = create_provider([{"items": []}])

    assert provider.list_events(CalendarProviderQuery(date="tomorrow")) == []


@pytest.mark.parametrize(
    "response",
    [None, {"items": "not-a-list"}, {"items": [], "nextPageToken": ""}],
)
def test_malformed_response_raises_response_error(response):
    provider, _ = create_provider([response])

    with pytest.raises(GoogleCalendarResponseError):
        provider.list_events(CalendarProviderQuery(date="tomorrow"))


@pytest.mark.parametrize(
    "raw_event",
    [
        "not-a-mapping",
        {"id": "missing-times"},
        {
            "id": "naive-time",
            "start": {"dateTime": "2026-08-10T08:30:00"},
            "end": {"dateTime": "2026-08-10T09:30:00"},
        },
        {
            "id": "bad-time",
            "start": {"dateTime": "bad"},
            "end": {"dateTime": "2026-08-10T09:30:00+08:00"},
        },
    ],
)
def test_malformed_event_raises_mapping_error(raw_event):
    provider, _ = create_provider([{"items": [raw_event]}])

    with pytest.raises(GoogleCalendarMappingError):
        provider.list_events(CalendarProviderQuery(date="tomorrow"))


def test_transport_error_is_wrapped_without_raw_payload_logging(caplog):
    provider, _ = create_provider([RuntimeError("private payload must not log")])

    with pytest.raises(GoogleCalendarTransportError):
        provider.list_events(CalendarProviderQuery(date="tomorrow"))

    assert "private payload must not log" not in caplog.text


def test_calendar_tool_preserves_start_time_filtering_for_provider_results():
    early = timed_event(
        id="early",
        start={"dateTime": "2026-08-09T21:00:00Z"},
        end={"dateTime": "2026-08-09T22:00:00Z"},
    )
    provider, _ = create_provider([{"items": [early, timed_event()]}])
    tool = CalendarTool(provider=provider)

    result = tool.run(
        {"date": "tomorrow", "start_time": "06:00", "end_time": "12:00"}
    )

    assert [event.id for event in result.events] == ["google-event-001"]
    assert result.event_count == 1


def test_provider_failure_flows_through_generic_tool_executor():
    provider, _ = create_provider([RuntimeError("calendar unavailable")])
    registry = ToolRegistry()
    registry.register(CalendarTool(provider=provider))
    executor = ToolExecutor(registry)

    executed = executor.execute(
        ToolCall(tool_name="calendar_tool", arguments={"date": "tomorrow"})
    )

    assert executed.status == ToolCallStatus.FAILED
    assert executed.result is None
    assert "GoogleCalendarTransportError" in executed.error
