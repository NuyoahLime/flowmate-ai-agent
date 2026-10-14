from flowmate.integrations.navigation import (
    MockNavigationProvider,
    NavigationProviderQuery,
)
from flowmate.tools.navigation import NavigationTool, NavigationToolResult


class FakeRealNavigationProvider:
    def get_route(self, query: NavigationProviderQuery) -> NavigationToolResult:
        return NavigationToolResult(
            origin=query.origin,
            destination=query.destination,
            distance_km=12.3,
            duration_minutes=28,
            traffic="unknown",
        )


def test_mock_navigation_provider_preserves_existing_output():
    provider = MockNavigationProvider()

    result = provider.get_route(
        NavigationProviderQuery(
            origin="home",
            destination="company",
            departure_time="tomorrow 07:30",
        )
    )

    assert result == NavigationToolResult(
        origin="home",
        destination="company",
        distance_km=18.6,
        duration_minutes=42,
        traffic="heavy",
    )


def test_navigation_tool_defaults_to_mock_provider():
    tool = NavigationTool()

    result = tool.run(
        {
            "origin": "home",
            "destination": "company",
            "departure_time": "tomorrow 07:30",
        }
    )

    assert result.distance_km == 18.6
    assert result.duration_minutes == 42
    assert result.traffic == "heavy"


def test_navigation_tool_accepts_real_shaped_provider_without_schema_branching():
    tool = NavigationTool(provider=FakeRealNavigationProvider())

    result = tool.run(
        {
            "origin": "上海虹桥站",
            "destination": "人民广场",
            "departure_time": "now",
        }
    )

    assert isinstance(result, NavigationToolResult)
    assert result.origin == "上海虹桥站"
    assert result.destination == "人民广场"
    assert result.distance_km == 12.3
