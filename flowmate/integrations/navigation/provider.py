from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from flowmate.tools.navigation import NavigationToolResult


class NavigationProviderError(Exception):
    pass


class NavigationConfigurationError(NavigationProviderError):
    pass


class NavigationLocationNotFoundError(NavigationProviderError):
    pass


class NavigationTransportError(NavigationProviderError):
    pass


class NavigationResponseError(NavigationProviderError):
    pass


class NavigationMappingError(NavigationProviderError):
    pass


class NavigationRouteNotFoundError(NavigationProviderError):
    pass


class NavigationProviderQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    departure_time: str = Field(min_length=1)


class ResolvedNavigationLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    longitude: float
    latitude: float
    adcode: str | None = None
    city: str | None = None
    citycode: str | None = None
    province: str | None = None
    source: str = Field(min_length=1, default="geocode")

    def amap_location(self) -> str:
        return f"{self.longitude},{self.latitude}"

    @property
    def region_name(self) -> str | None:
        return self.city or self.province


class NavigationProvider(Protocol):
    def get_route(self, query: NavigationProviderQuery) -> "NavigationToolResult":
        ...
