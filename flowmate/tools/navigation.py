from pydantic import BaseModel, ConfigDict, Field

from flowmate.tools.base import BaseTool


class NavigationToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    departure_time: str = Field(min_length=1)


class NavigationToolResult(BaseModel):
    origin: str
    destination: str
    distance_km: float = Field(ge=0)
    duration_minutes: int = Field(ge=0)
    traffic: str


class NavigationTool(BaseTool[NavigationToolInput, NavigationToolResult]):
    name = "navigation_tool"
    description = (
        "Calculate routes, distance, estimated travel time, and navigation planning "
        "information. It cannot drive a vehicle, move, start, lock, or otherwise "
        "control vehicles."
    )
    input_schema = NavigationToolInput

    def __init__(self, provider: "NavigationProvider | None" = None) -> None:
        if provider is None:
            from flowmate.integrations.navigation.mock_provider import (
                MockNavigationProvider,
            )

            provider = MockNavigationProvider()
        self.provider = provider

    def execute(self, input_data: NavigationToolInput) -> NavigationToolResult:
        from flowmate.integrations.navigation.provider import NavigationProviderQuery

        provider = getattr(self, "provider", None)
        if provider is None:
            from flowmate.integrations.navigation.mock_provider import (
                MockNavigationProvider,
            )

            provider = MockNavigationProvider()
            self.provider = provider

        return provider.get_route(
            NavigationProviderQuery(
                origin=input_data.origin,
                destination=input_data.destination,
                departure_time=input_data.departure_time,
            )
        )


from flowmate.integrations.navigation.provider import NavigationProvider
