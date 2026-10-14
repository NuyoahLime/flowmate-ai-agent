import pytest

from flowmate.integrations.weather import (
    OpenMeteoLocationResolver,
    WeatherLocationNotFoundError,
    WeatherResponseError,
    WeatherTransportError,
)


class FakeHttpClient:
    def __init__(self, response=None, exc: Exception | None = None):
        self.response = response
        self.exc = exc
        self.calls = []

    def get_json(self, url, *, params, timeout_seconds):
        self.calls.append((url, params, timeout_seconds))
        if self.exc is not None:
            raise self.exc
        return self.response


def test_location_resolver_maps_chinese_city_query():
    client = FakeHttpClient(
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
        }
    )
    resolver = OpenMeteoLocationResolver(http_client=client, timeout_seconds=3.5)

    result = resolver.resolve("上海")

    assert result.query == "上海"
    assert result.name == "Shanghai"
    assert result.latitude == 31.22222
    assert result.longitude == 121.45806
    assert result.timezone == "Asia/Shanghai"
    assert result.country_code == "CN"
    assert client.calls[0][1] == {
        "name": "Shanghai",
        "count": 1,
        "language": "en",
        "format": "json",
    }
    assert client.calls[0][2] == 3.5


def test_location_resolver_maps_english_city_query_and_uses_first_match():
    resolver = OpenMeteoLocationResolver(
        http_client=FakeHttpClient(
            {
                "results": [
                    {
                        "name": "Paris",
                        "latitude": 48.85341,
                        "longitude": 2.3488,
                        "timezone": "Europe/Paris",
                    },
                    {
                        "name": "Paris",
                        "latitude": 33.66094,
                        "longitude": -95.55551,
                        "timezone": "America/Chicago",
                    },
                ]
            }
        )
    )

    result = resolver.resolve("Paris")

    assert result.name == "Paris"
    assert result.latitude == 48.85341
    assert result.timezone == "Europe/Paris"


def test_location_resolver_empty_results_raise_not_found():
    resolver = OpenMeteoLocationResolver(http_client=FakeHttpClient({"results": []}))

    with pytest.raises(WeatherLocationNotFoundError):
        resolver.resolve("Missing City")


def test_location_resolver_missing_results_raise_not_found():
    resolver = OpenMeteoLocationResolver(http_client=FakeHttpClient({}))

    with pytest.raises(WeatherLocationNotFoundError):
        resolver.resolve("Missing City")


def test_location_resolver_malformed_result_raises_response_error():
    resolver = OpenMeteoLocationResolver(
        http_client=FakeHttpClient({"results": [{"name": "Broken"}]})
    )

    with pytest.raises(WeatherResponseError):
        resolver.resolve("Broken")


def test_location_resolver_http_failure_propagates_transport_error():
    resolver = OpenMeteoLocationResolver(
        http_client=FakeHttpClient(exc=WeatherTransportError("timeout"))
    )

    with pytest.raises(WeatherTransportError):
        resolver.resolve("Shanghai")
