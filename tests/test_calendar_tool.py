import pytest
from pydantic import ValidationError

from flowmate.tools import CalendarTool, CalendarToolInput, CalendarToolResult


def test_calendar_tool_name_and_description():
    tool = CalendarTool()

    assert tool.name == "calendar_tool"
    assert tool.description


def test_calendar_input_requires_date():
    with pytest.raises(ValidationError):
        CalendarToolInput()


def test_calendar_input_allows_optional_time_window():
    input_data = CalendarToolInput(
        date="tomorrow",
        start_time="06:00",
        end_time="12:00",
    )

    assert input_data.start_time == "06:00"
    assert input_data.end_time == "12:00"


def test_calendar_input_forbids_extra_fields():
    with pytest.raises(ValidationError):
        CalendarToolInput(date="tomorrow", timezone="Asia/Shanghai")


def test_query_tomorrow_returns_deterministic_events():
    result = CalendarTool().run({"date": "tomorrow"})

    assert [event.id for event in result.events] == ["event-001", "event-002"]


def test_calendar_event_fields_are_complete():
    event = CalendarTool().run({"date": "tomorrow"}).events[0]

    assert event.id == "event-001"
    assert event.title == "Product Weekly Meeting"
    assert event.start_time == "08:30"
    assert event.end_time == "09:30"
    assert event.location == "company"


def test_full_day_query_returns_all_events():
    result = CalendarTool().run({"date": "tomorrow"})

    assert result.event_count == 2
    assert len(result.events) == 2


def test_morning_window_returns_only_morning_event():
    result = CalendarTool().run(
        {"date": "tomorrow", "start_time": "06:00", "end_time": "12:00"}
    )

    assert result.event_count == 1
    assert result.events[0].id == "event-001"


def test_afternoon_window_returns_only_afternoon_event():
    result = CalendarTool().run(
        {"date": "tomorrow", "start_time": "12:00", "end_time": "18:00"}
    )

    assert result.event_count == 1
    assert result.events[0].id == "event-002"


def test_no_matching_window_returns_empty_events():
    result = CalendarTool().run(
        {"date": "tomorrow", "start_time": "18:00", "end_time": "20:00"}
    )

    assert result.event_count == 0
    assert result.events == []


def test_event_count_must_match_events_length():
    with pytest.raises(ValidationError):
        CalendarToolResult(date="tomorrow", events=[], event_count=1)


def test_same_input_returns_same_output_multiple_times():
    tool = CalendarTool()
    arguments = {"date": "tomorrow", "start_time": "06:00", "end_time": "12:00"}

    assert tool.run(arguments) == tool.run(arguments)


def test_run_uses_input_schema_validation():
    with pytest.raises(ValidationError):
        CalendarTool().run({"start_time": "06:00", "end_time": "12:00"})
