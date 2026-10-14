from __future__ import annotations

import os
from datetime import date
from typing import Any, Mapping

from flowmate.integrations.weather.location_resolver import (
    OpenMeteoLocationResolver,
    UrllibWeatherHttpClient,
    WeatherHttpClient,
)
from flowmate.integrations.weather.provider import (
    ResolvedWeatherLocation,
    WeatherConfigurationError,
    WeatherForecastRangeError,
    WeatherMappingError,
    WeatherProviderQuery,
    WeatherResponseError,
)
from flowmate.integrations.weather.temporal_resolver import WeatherTemporalResolver
from flowmate.tools.weather import WeatherToolResult


class OpenMeteoWeatherCodeMapper:
    @staticmethod
    def condition_for(code: int) -> str:
        if code == 0:
            return "clear"
        if code in {1, 2, 3}:
            return "cloudy"
        if code in {45, 48}:
            return "fog"
        if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
            return "rain"
        if code in {71, 73, 75, 77, 85, 86}:
            return "snow"
        if code in {95, 96, 99}:
            return "thunderstorm"
        return "unknown"


class OpenMeteoWeatherProvider:
    def __init__(
        self,
        *,
        http_client: WeatherHttpClient | None = None,
        location_resolver: OpenMeteoLocationResolver | None = None,
        temporal_resolver: WeatherTemporalResolver | None = None,
        forecast_endpoint: str = "https://api.open-meteo.com/v1/forecast",
        timeout_seconds: float | None = None,
    ) -> None:
        timeout = timeout_seconds if timeout_seconds is not None else self._default_timeout()
        client = http_client or UrllibWeatherHttpClient()
        self.http_client = client
        self.location_resolver = location_resolver or OpenMeteoLocationResolver(
            http_client=client,
            timeout_seconds=timeout,
        )
        self.temporal_resolver = temporal_resolver or WeatherTemporalResolver()
        self.forecast_endpoint = forecast_endpoint
        self.timeout_seconds = timeout

    def get_weather(self, query: WeatherProviderQuery) -> WeatherToolResult:
        location = self.location_resolver.resolve(query.location)
        target_date = self.temporal_resolver.resolve_date(
            query.date,
            timezone=location.timezone,
        )
        response = self.http_client.get_json(
            self.forecast_endpoint,
            params=self._forecast_params(location, target_date),
            timeout_seconds=self.timeout_seconds,
        )
        return self._map_forecast(
            response,
            requested_date=query.date,
            target_date=target_date,
            location=location,
        )

    def _forecast_params(
        self,
        location: ResolvedWeatherLocation,
        target_date: date,
    ) -> dict[str, Any]:
        target = target_date.isoformat()
        return {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "precipitation_probability_max",
            ],
            "temperature_unit": "celsius",
            "timezone": location.timezone,
            "start_date": target,
            "end_date": target,
        }

    def _map_forecast(
        self,
        response: Mapping[str, Any],
        *,
        requested_date: str,
        target_date: date,
        location: ResolvedWeatherLocation,
    ) -> WeatherToolResult:
        daily = response.get("daily")
        if not isinstance(daily, Mapping):
            raise WeatherResponseError("Open-Meteo forecast daily data is required.")

        dates = self._list_field(daily, "time")
        weather_codes = self._list_field(daily, "weather_code")
        temperatures = self._list_field(daily, "temperature_2m_max")
        precipitation = self._list_field(daily, "precipitation_probability_max")

        target = target_date.isoformat()
        try:
            index = dates.index(target)
        except ValueError as exc:
            raise WeatherForecastRangeError(
                f"Open-Meteo forecast did not include target date: {target}"
            ) from exc

        weather_code = self._number_at(weather_codes, index, "weather_code")
        temperature = self._number_at(temperatures, index, "temperature_2m_max")
        precipitation_probability = self._number_at(
            precipitation,
            index,
            "precipitation_probability_max",
        )

        return WeatherToolResult(
            location=location.name,
            date=requested_date,
            condition=OpenMeteoWeatherCodeMapper.condition_for(int(weather_code)),
            temperature_c=float(temperature),
            rain_probability=max(0.0, min(1.0, float(precipitation_probability) / 100)),
        )

    def _list_field(self, daily: Mapping[str, Any], field_name: str) -> list[Any]:
        value = daily.get(field_name)
        if not isinstance(value, list):
            raise WeatherResponseError(f"Open-Meteo daily.{field_name} must be a list.")
        if not value:
            raise WeatherResponseError(f"Open-Meteo daily.{field_name} must not be empty.")
        return value

    def _number_at(self, values: list[Any], index: int, field_name: str) -> int | float:
        try:
            value = values[index]
        except IndexError as exc:
            raise WeatherResponseError(
                f"Open-Meteo daily.{field_name} is missing the target date value."
            ) from exc
        if not isinstance(value, int | float):
            raise WeatherMappingError(f"Open-Meteo daily.{field_name} must be numeric.")
        return value

    def _default_timeout(self) -> float:
        value = os.getenv("OPEN_METEO_TIMEOUT_SECONDS")
        if value is None or value.strip() == "":
            return 10.0
        try:
            timeout = float(value)
        except ValueError as exc:
            raise WeatherConfigurationError(
                "OPEN_METEO_TIMEOUT_SECONDS must be numeric."
            ) from exc
        if timeout <= 0:
            raise WeatherConfigurationError(
                "OPEN_METEO_TIMEOUT_SECONDS must be greater than 0."
            )
        return timeout
