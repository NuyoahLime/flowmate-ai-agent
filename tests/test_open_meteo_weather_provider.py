from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from flowmate.integrations.weather import (
    OpenMeteoLocationResolver,
    OpenMeteoWeatherCodeMapper,
    OpenMeteoWeatherProvider,
    WeatherConfigurationError,
    WeatherForecastRangeError,
    WeatherMappingError,
    WeatherProviderQuery,
    WeatherResponseError,
    WeatherTemporalResolver,
    WeatherTransportError,
)


class FakeHttpClient:
    def __init__(self, responses=None, exc: Exception | None = None):
        self.responses = list(responses or [])
        self.exc = exc
        self.calls = []

    def get_json(self, url, *, params, timeout_seconds):
        self.calls.append((url, params, timeout_seconds))
        if self.exc is not None:
            raise self.exc
        return self.responses.pop(0)


def create_provider(client: FakeHttpClient) -> OpenMeteoWeatherProvider:
    return OpenMeteoWeatherProvider(
        http_client=client,
        location_resolver=OpenMeteoLocationResolver(
            http_client=client,
            timeout_seconds=2,
        ),
        temporal_resolver=WeatherTemporalResolver(
            clock=datetime(2026, 8, 10, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        ),
        timeout_seconds=2,
    )


def test_open_meteo_provider_maps_minimal_forecast_to_weather_result():
    client = FakeHttpClient(
        responses=[
            {
                "results": [
                    {
                        "name": "Shanghai",
                        "latitude": 31.22222,
                        "longitude": 121.45806,
                        "timezone": "Asia/Shanghai",
                        "country_code": "CN",
                    }
                ]
            },
            {
                "daily": {
                    "time": ["2026-08-11"],
                    "weather_code": [61],
                    "temperature_2m_max": [27.4],
                    "precipitation_probability_max": [80],
                }
            },
        ]
    )
    provider = create_provider(client)

    result = provider.get_weather(
        WeatherProviderQuery(location="Shanghai", date="tomorrow")
    )

    assert result.location == "Shanghai"
    assert result.date == "tomorrow"
    assert result.condition == "rain"
    assert result.temperature_c == 27.4
    assert result.rain_probability == 0.8

    forecast_params = client.calls[1][1]
    assert forecast_params == {
        "latitude": 31.22222,
        "longitude": 121.45806,
        "daily": [
            "weather_code",
            "temperature_2m_max",
            "precipitation_probability_max",
        ],
        "temperature_unit": "celsius",
        "timezone": "Asia/Shanghai",
        "start_date": "2026-08-11",
        "end_date": "2026-08-11",
    }


def test_open_meteo_provider_does_not_require_api_key(monkeypatch):
    monkeypatch.delenv("WEATHER_API_KEY", raising=False)
    client = FakeHttpClient(
        responses=[
            {
                "results": [
                    {
                        "name": "Shanghai",
                        "latitude": 31.2,
                        "longitude": 121.4,
                        "timezone": "Asia/Shanghai",
                    }
                ]
            },
            {
                "daily": {
                    "time": ["2026-08-11"],
                    "weather_code": [0],
                    "temperature_2m_max": [29],
                    "precipitation_probability_max": [0],
                }
            },
        ]
    )

    result = create_provider(client).get_weather(
        WeatherProviderQuery(location="Shanghai", date="tomorrow")
    )

    assert result.condition == "clear"


def test_open_meteo_provider_missing_daily_raises_response_error():
    client = FakeHttpClient(
        responses=[
            {
                "results": [
                    {
                        "name": "Shanghai",
                        "latitude": 31.2,
                        "longitude": 121.4,
                        "timezone": "Asia/Shanghai",
                    }
                ]
            },
            {},
        ]
    )

    with pytest.raises(WeatherResponseError):
        create_provider(client).get_weather(
            WeatherProviderQuery(location="Shanghai", date="tomorrow")
        )


def test_open_meteo_provider_missing_target_date_raises_range_error():
    client = FakeHttpClient(
        responses=[
            {
                "results": [
                    {
                        "name": "Shanghai",
                        "latitude": 31.2,
                        "longitude": 121.4,
                        "timezone": "Asia/Shanghai",
                    }
                ]
            },
            {
                "daily": {
                    "time": ["2026-08-12"],
                    "weather_code": [0],
                    "temperature_2m_max": [29],
                    "precipitation_probability_max": [0],
                }
            },
        ]
    )

    with pytest.raises(WeatherForecastRangeError):
        create_provider(client).get_weather(
            WeatherProviderQuery(location="Shanghai", date="tomorrow")
        )


def test_open_meteo_provider_malformed_numeric_value_raises_mapping_error():
    client = FakeHttpClient(
        responses=[
            {
                "results": [
                    {
                        "name": "Shanghai",
                        "latitude": 31.2,
                        "longitude": 121.4,
                        "timezone": "Asia/Shanghai",
                    }
                ]
            },
            {
                "daily": {
                    "time": ["2026-08-11"],
                    "weather_code": ["rain"],
                    "temperature_2m_max": [29],
                    "precipitation_probability_max": [0],
                }
            },
        ]
    )

    with pytest.raises(WeatherMappingError):
        create_provider(client).get_weather(
            WeatherProviderQuery(location="Shanghai", date="tomorrow")
        )


def test_open_meteo_provider_transport_error_propagates():
    client = FakeHttpClient(exc=WeatherTransportError("timeout"))

    with pytest.raises(WeatherTransportError):
        create_provider(client).get_weather(
            WeatherProviderQuery(location="Shanghai", date="tomorrow")
        )


def test_open_meteo_timeout_env_validation(monkeypatch):
    monkeypatch.setenv("OPEN_METEO_TIMEOUT_SECONDS", "0")

    with pytest.raises(WeatherConfigurationError):
        OpenMeteoWeatherProvider()


@pytest.mark.parametrize(
    ("code", "condition"),
    [
        (0, "clear"),
        (2, "cloudy"),
        (45, "fog"),
        (51, "rain"),
        (71, "snow"),
        (95, "thunderstorm"),
        (999, "unknown"),
    ],
)
def test_weather_code_mapping_is_deterministic(code, condition):
    assert OpenMeteoWeatherCodeMapper.condition_for(code) == condition
