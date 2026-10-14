from flowmate.agent import DynamicTaskOrchestrator, ToolExecutor
from flowmate.integrations.navigation import NavigationProviderQuery
from flowmate.schemas import DynamicPlanningPhase
from flowmate.tools import CalendarTool, NavigationTool, ToolRegistry, WeatherTool
from flowmate.tools.navigation import NavigationToolResult


class RealShapedNavigationProvider:
    def get_route(self, query: NavigationProviderQuery) -> NavigationToolResult:
        return NavigationToolResult(
            origin=query.origin,
            destination=query.destination,
            distance_km=9.4,
            duration_minutes=23,
            traffic="unknown",
        )


def test_dynamic_navigation_accepts_real_shaped_provider_and_preserves_grounding():
    registry = ToolRegistry()
    registry.register(WeatherTool())
    registry.register(NavigationTool(provider=RealShapedNavigationProvider()))
    registry.register(CalendarTool())
    orchestrator = DynamicTaskOrchestrator(ToolExecutor(registry))

    state = orchestrator.execute("help me plan tomorrow morning departure")

    assert state.phase == DynamicPlanningPhase.COMPLETED
    assert state.selected_event["location"] == "company"
    assert state.final_result.navigation_result == {
        "origin": "home",
        "destination": "company",
        "distance_km": 9.4,
        "duration_minutes": 23,
        "traffic": "unknown",
    }
