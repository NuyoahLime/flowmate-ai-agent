import pytest

from flowmate.integrations.navigation import (
    AmapNavigationProvider,
    NavigationConfigurationError,
    NavigationMappingError,
    NavigationProviderQuery,
    NavigationResponseError,
    NavigationRouteNotFoundError,
    NavigationTransportError,
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


def geocode_response(name: str, location: str) -> dict:
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "count": "1",
        "geocodes": [
            {
                "formatted_address": name,
                "location": location,
            }
        ],
    }


def route_response(*, distance: str = "18600", duration: str = "2501") -> dict:
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "route": {
            "paths": [
                {
                    "distance": distance,
                    "cost": {"duration": duration, "traffic_lights": "12"},
                    "restriction": "0",
                    "steps": [{"instruction": "hidden from domain"}],
                },
                {"distance": "99999", "duration": "99999"},
            ]
        },
    }


def create_provider(client: FakeHttpClient) -> AmapNavigationProvider:
    return AmapNavigationProvider(
        api_key="test-secret-key",
        http_client=client,
        timeout_seconds=2,
    )


def test_amap_navigation_provider_maps_first_recommended_path():
    client = FakeHttpClient(
        responses=[
            geocode_response("上海市闵行区上海虹桥站", "121.327907,31.200316"),
            geocode_response("上海市黄浦区人民广场", "121.475190,31.228833"),
            route_response(),
        ]
    )

    result = create_provider(client).get_route(
        NavigationProviderQuery(
            origin="上海虹桥站",
            destination="人民广场",
            departure_time="now",
        )
    )

    assert result.origin == "上海虹桥站"
    assert result.destination == "人民广场"
    assert result.distance_km == 18.6
    assert result.duration_minutes == 42
    assert result.traffic == "unknown"
    assert result.model_dump() == {
        "origin": "上海虹桥站",
        "destination": "人民广场",
        "distance_km": 18.6,
        "duration_minutes": 42,
        "traffic": "unknown",
    }

    route_params = client.calls[2][1]
    assert route_params == {
        "key": "test-secret-key",
        "origin": "121.327907,31.200316",
        "destination": "121.47519,31.228833",
        "show_fields": "cost",
    }


def test_amap_navigation_provider_preserves_explicit_cross_city_destination():
    client = FakeHttpClient(
        responses=[
            geocode_response("上海市闵行区上海虹桥站", "121.327907,31.200316"),
            geocode_response("北京市东城区天安门", "116.397463,39.909187"),
            route_response(distance="1060000", duration="63120"),
        ]
    )

    result = create_provider(client).get_route(
        NavigationProviderQuery(
            origin="上海虹桥站",
            destination="北京天安门",
            departure_time="now",
        )
    )

    assert result.destination == "北京天安门"
    assert result.distance_km == 1060.0
    assert result.duration_minutes == 1052


def test_amap_navigation_provider_requires_key(monkeypatch):
    monkeypatch.delenv("AMAP_WEB_SERVICE_KEY", raising=False)

    with pytest.raises(NavigationConfigurationError):
        AmapNavigationProvider()


def test_amap_navigation_provider_reads_key_from_env(monkeypatch):
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", "test-secret-key")
    client = FakeHttpClient(
        responses=[
            geocode_response("上海市闵行区上海虹桥站", "121.327907,31.200316"),
            geocode_response("上海市黄浦区人民广场", "121.475190,31.228833"),
            route_response(),
        ]
    )

    result = AmapNavigationProvider(http_client=client, timeout_seconds=2).get_route(
        NavigationProviderQuery(
            origin="上海虹桥站",
            destination="人民广场",
            departure_time="now",
        )
    )

    assert result.distance_km == 18.6


def test_amap_navigation_provider_timeout_env_validation(monkeypatch):
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", "test-secret-key")
    monkeypatch.setenv("AMAP_TIMEOUT_SECONDS", "0")

    with pytest.raises(NavigationConfigurationError):
        AmapNavigationProvider()


def test_amap_navigation_provider_empty_paths_raise_route_not_found():
    client = FakeHttpClient(
        responses=[
            geocode_response("上海市闵行区上海虹桥站", "121.327907,31.200316"),
            geocode_response("上海市黄浦区人民广场", "121.475190,31.228833"),
            {
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "route": {"paths": []},
            },
        ]
    )

    with pytest.raises(NavigationRouteNotFoundError):
        create_provider(client).get_route(
            NavigationProviderQuery(
                origin="上海虹桥站",
                destination="人民广场",
                departure_time="now",
            )
        )


def test_amap_navigation_provider_malformed_path_raises_response_error():
    client = FakeHttpClient(
        responses=[
            geocode_response("上海市闵行区上海虹桥站", "121.327907,31.200316"),
            geocode_response("上海市黄浦区人民广场", "121.475190,31.228833"),
            {
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "route": {"paths": [{"duration": "1200"}]},
            },
        ]
    )

    with pytest.raises(NavigationResponseError):
        create_provider(client).get_route(
            NavigationProviderQuery(
                origin="上海虹桥站",
                destination="人民广场",
                departure_time="now",
            )
        )


def test_amap_navigation_provider_non_numeric_path_raises_mapping_error():
    client = FakeHttpClient(
        responses=[
            geocode_response("上海市闵行区上海虹桥站", "121.327907,31.200316"),
            geocode_response("上海市黄浦区人民广场", "121.475190,31.228833"),
            route_response(distance="not-a-number"),
        ]
    )

    with pytest.raises(NavigationMappingError):
        create_provider(client).get_route(
            NavigationProviderQuery(
                origin="上海虹桥站",
                destination="人民广场",
                departure_time="now",
            )
        )


def test_amap_navigation_provider_business_error_does_not_leak_key():
    client = FakeHttpClient(
        responses=[
            geocode_response("上海市闵行区上海虹桥站", "121.327907,31.200316"),
            geocode_response("上海市黄浦区人民广场", "121.475190,31.228833"),
            {
                "status": "0",
                "info": "INVALID_USER_KEY",
                "infocode": "10001",
            },
        ]
    )

    with pytest.raises(NavigationResponseError) as exc_info:
        create_provider(client).get_route(
            NavigationProviderQuery(
                origin="上海虹桥站",
                destination="人民广场",
                departure_time="now",
            )
        )

    assert "INVALID_USER_KEY" in str(exc_info.value)
    assert "test-secret-key" not in str(exc_info.value)


def test_amap_navigation_provider_transport_error_propagates_without_retry():
    client = FakeHttpClient(exc=NavigationTransportError("timeout"))

    with pytest.raises(NavigationTransportError):
        create_provider(client).get_route(
            NavigationProviderQuery(
                origin="上海虹桥站",
                destination="人民广场",
                departure_time="now",
            )
        )

    assert len(client.calls) == 1
