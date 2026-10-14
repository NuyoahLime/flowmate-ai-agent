from flowmate.integrations.navigation.provider import NavigationProviderQuery
from flowmate.tools.navigation import NavigationToolResult


class MockNavigationProvider:
    def get_route(self, query: NavigationProviderQuery) -> NavigationToolResult:
        return NavigationToolResult(
            origin=query.origin,
            destination=query.destination,
            distance_km=18.6,
            duration_minutes=42,
            traffic="heavy",
        )
