from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class WeatherProviderError(Exception):
    pass


class WeatherConfigurationError(WeatherProviderError):
    pass


class WeatherLocationNotFoundError(WeatherProviderError):
    pass


class WeatherTransportError(WeatherProviderError):
    pass


class WeatherResponseError(WeatherProviderError):
    pass


class WeatherMappingError(WeatherProviderError):
    pass


class WeatherForecastRangeError(WeatherProviderError):
    pass


class WeatherProviderQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=1)
    date: str = Field(min_length=1)


class ResolvedWeatherLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    name: str = Field(min_length=1)
    latitude: float
    longitude: float
    timezone: str = Field(min_length=1)
    country_code: str | None = None


class WeatherProvider(Protocol):
    def get_weather(self, query: WeatherProviderQuery) -> "WeatherToolResult":
        ...


from flowmate.tools.weather import WeatherToolResult
