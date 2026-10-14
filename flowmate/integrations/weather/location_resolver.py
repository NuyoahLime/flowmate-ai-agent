from __future__ import annotations

import json
import socket
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from flowmate.integrations.weather.provider import (
    ResolvedWeatherLocation,
    WeatherLocationNotFoundError,
    WeatherMappingError,
    WeatherResponseError,
    WeatherTransportError,
)


class WeatherHttpClient(Protocol):
    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        ...


class UrllibWeatherHttpClient:
    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        request_url = f"{url}?{urlencode(params, doseq=True)}"
        try:
            with urlopen(request_url, timeout=timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise WeatherTransportError(
                f"Weather provider HTTP request failed with status {exc.code}."
            ) from exc
        except (OSError, TimeoutError, URLError, socket.timeout) as exc:
            raise WeatherTransportError("Weather provider HTTP request failed.") from exc

        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise WeatherResponseError("Weather provider returned invalid JSON.") from exc
        if not isinstance(decoded, Mapping):
            raise WeatherResponseError("Weather provider response must be a mapping.")
        return decoded


class OpenMeteoLocationResolver:
    _provider_location_aliases = {
        "\u5317\u4eac": "Beijing",
        "\u5317\u4eac\u5e02": "Beijing",
        "\u4e0a\u6d77": "Shanghai",
        "\u4e0a\u6d77\u5e02": "Shanghai",
    }

    def __init__(
        self,
        *,
        http_client: WeatherHttpClient | None = None,
        endpoint: str = "https://geocoding-api.open-meteo.com/v1/search",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.http_client = http_client or UrllibWeatherHttpClient()
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def resolve(self, location: str) -> ResolvedWeatherLocation:
        query = location.strip()
        if not query:
            raise WeatherMappingError("Weather location must not be blank.")

        provider_query = self._provider_location_aliases.get(query, query)
        response = self.http_client.get_json(
            self.endpoint,
            params={
                "name": provider_query,
                "count": 1,
                "language": "en",
                "format": "json",
            },
            timeout_seconds=self.timeout_seconds,
        )
        results = response.get("results")
        if results is None:
            raise WeatherLocationNotFoundError(f"Weather location not found: {query}")
        if not isinstance(results, list):
            raise WeatherResponseError("Open-Meteo geocoding results must be a list.")
        if not results:
            raise WeatherLocationNotFoundError(f"Weather location not found: {query}")

        first = results[0]
        if not isinstance(first, Mapping):
            raise WeatherResponseError("Open-Meteo geocoding result must be a mapping.")
        return self._map_location(query, first)

    def _map_location(
        self,
        query: str,
        raw_location: Mapping[str, Any],
    ) -> ResolvedWeatherLocation:
        name = raw_location.get("name")
        latitude = raw_location.get("latitude")
        longitude = raw_location.get("longitude")
        timezone = raw_location.get("timezone")
        country_code = raw_location.get("country_code")

        if not isinstance(name, str) or not name:
            raise WeatherResponseError("Open-Meteo location name is required.")
        if not isinstance(latitude, int | float):
            raise WeatherResponseError("Open-Meteo latitude must be numeric.")
        if not isinstance(longitude, int | float):
            raise WeatherResponseError("Open-Meteo longitude must be numeric.")
        if not isinstance(timezone, str) or not timezone:
            raise WeatherResponseError("Open-Meteo timezone is required.")
        if country_code is not None and not isinstance(country_code, str):
            raise WeatherResponseError("Open-Meteo country_code must be a string.")

        return ResolvedWeatherLocation(
            query=query,
            name=name,
            latitude=float(latitude),
            longitude=float(longitude),
            timezone=timezone,
            country_code=country_code,
        )
