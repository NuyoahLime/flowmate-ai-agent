import socket

from flowmate.agent import DynamicTaskOrchestrator, ToolExecutor
from flowmate.integrations.calendar import CalendarProviderQuery, MockCalendarProvider
from flowmate.tools import CalendarEvent, CalendarTool, create_default_registry


def test_mock_provider_preserves_stage_16_events():
    events = MockCalendarProvider().list_events(
        CalendarProviderQuery(date="tomorrow")
    )

    assert [event.id for event in events] == ["event-001", "event-002"]
    assert events[0].title == "Product Weekly Meeting"
    assert events[0].start_time == "08:30"
    assert events[1].title == "Project Review"
    assert events[1].start_time == "14:00"


def test_calendar_tool_default_provider_is_mock_and_offline(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Default CalendarTool must not access the network.")

    monkeypatch.setattr(socket, "create_connection", fail_if_called)

    tool = CalendarTool()
    result = tool.run({"date": "tomorrow"})

    assert isinstance(tool.provider, MockCalendarProvider)
    assert result.event_count == 2


def test_mock_provider_results_are_copied_between_calls():
    provider = MockCalendarProvider()
    first = provider.list_events(CalendarProviderQuery(date="tomorrow"))
    second = provider.list_events(CalendarProviderQuery(date="tomorrow"))

    assert first == second
    assert first[0] is not second[0]


class GoogleShapedFakeProvider:
    def __init__(self) -> None:
        self.queries = []

    def list_events(self, query):
        self.queries.append(query)
        return [
            CalendarEvent(
                id="google-shaped-001",
                title="Client Meeting",
                start_time="08:00",
                end_time="09:00",
                location="client_site",
            )
        ]


def test_dynamic_orchestrator_is_provider_agnostic():
    provider = GoogleShapedFakeProvider()
    calendar_tool = CalendarTool(provider=provider)
    registry = create_default_registry(calendar_tool=calendar_tool)
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(registry))

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert provider.queries[0].date == "tomorrow"
    assert provider.queries[0].start_time == "06:00"
    assert provider.queries[0].end_time == "12:00"
    assert state.selected_event["id"] == "google-shaped-001"
    assert state.task.steps[1].tool_call.arguments["destination"] == "client_site"
    assert state.final_result.navigation_result["destination"] == "client_site"
