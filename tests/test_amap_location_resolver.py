import pytest

from flowmate.integrations.navigation import (
    AmapLocationResolver,
    NavigationConfigurationError,
    NavigationLocationNotFoundError,
    NavigationResponseError,
    NavigationTransportError,
    ResolvedNavigationLocation,
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


def test_location_resolver_requires_api_key():
    with pytest.raises(NavigationConfigurationError):
        AmapLocationResolver(api_key="")


def test_location_resolver_maps_structured_address():
    client = FakeHttpClient(
        {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "count": "1",
            "geocodes": [
                {
                    "formatted_address": "上海市闵行区上海虹桥站",
                    "location": "121.327907,31.200316",
                    "adcode": "310112",
                    "city": "上海市",
                }
            ],
        }
    )
    resolver = AmapLocationResolver(
        api_key="test-secret-key",
        http_client=client,
        timeout_seconds=3,
    )

    result = resolver.resolve("上海虹桥站")

    assert result.query == "上海虹桥站"
    assert result.canonical_name == "上海市闵行区上海虹桥站"
    assert result.longitude == 121.327907
    assert result.latitude == 31.200316
    assert result.adcode == "310112"
    assert result.city == "上海市"
    assert result.source == "geocode"
    assert client.calls[0][1] == {
        "key": "test-secret-key",
        "address": "上海虹桥站",
    }
    assert client.calls[0][2] == 3


def test_location_resolver_maps_landmark_and_uses_first_match():
    resolver = AmapLocationResolver(
        api_key="test-secret-key",
        http_client=FakeHttpClient(
            {
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "count": "2",
                "geocodes": [
                    {
                        "formatted_address": "上海市黄浦区人民广场",
                        "location": "121.475190,31.228833",
                    },
                    {
                        "formatted_address": "其他人民广场",
                        "location": "120.000000,30.000000",
                    },
                ],
            }
        ),
    )

    result = resolver.resolve("人民广场")

    assert result.canonical_name == "上海市黄浦区人民广场"
    assert result.amap_location() == "121.47519,31.228833"


def test_location_resolver_uses_region_hint_for_poi_fallback():
    client = FakeHttpClient()
    client.responses = [
        {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "count": "1",
            "geocodes": [
                {
                    "formatted_address": "上海市闵行区上海虹桥站",
                    "location": "121.327907,31.200316",
                    "adcode": "310112",
                    "city": "上海市",
                }
            ],
        },
        {"status": "0", "info": "ENGINE_RESPONSE_DATA_ERROR", "infocode": "30001"},
        {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "pois": [
                {
                    "name": "上海人民广场",
                    "address": "黄浦区人民广场",
                    "location": "121.475213,31.228827",
                    "adcode": "310101",
                    "cityname": "上海市",
                    "citycode": "021",
                    "pname": "上海市",
                },
                {
                    "name": "北京人民广场",
                    "address": "东城区人民广场",
                    "location": "116.407526,39.904030",
                    "adcode": "110101",
                    "cityname": "北京市",
                    "citycode": "010",
                    "pname": "北京市",
                },
            ],
        },
    ]

    def get_json(url, *, params, timeout_seconds):
        client.calls.append((url, params, timeout_seconds))
        return client.responses.pop(0)

    client.get_json = get_json
    resolver = AmapLocationResolver(api_key="test-secret-key", http_client=client)
    origin = resolver.resolve("上海虹桥站")
    result = resolver.resolve("人民广场", region_hint=origin)

    assert result.source == "poi"
    assert result.city == "上海市"
    assert result.adcode == "310101"
    assert client.calls[2][1] == {
        "key": "test-secret-key",
        "keywords": "人民广场",
        "page_size": 1,
        "page_num": 1,
        "region": "上海市",
        "city_limit": "true",
    }


def test_location_resolver_regrounds_ambiguous_cross_region_geocode():
    client = FakeHttpClient()
    client.responses = [
        {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "count": "1",
            "geocodes": [
                {
                    "formatted_address": "四川省眉山市仁寿县人民广场",
                    "location": "104.133931,29.995638",
                    "adcode": "511421",
                    "city": "眉山市",
                    "province": "四川省",
                }
            ],
        },
        {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "pois": [
                {
                    "name": "上海人民广场",
                    "address": "黄浦区人民广场",
                    "location": "121.475213,31.228827",
                    "adcode": "310101",
                    "cityname": "上海市",
                    "citycode": "021",
                    "pname": "上海市",
                }
            ],
        },
    ]

    def get_json(url, *, params, timeout_seconds):
        client.calls.append((url, params, timeout_seconds))
        return client.responses.pop(0)

    client.get_json = get_json
    resolver = AmapLocationResolver(api_key="test-secret-key", http_client=client)
    origin = ResolvedNavigationLocation(
        query="上海虹桥站",
        canonical_name="上海虹桥站",
        longitude=121.327907,
        latitude=31.200316,
        city="上海市",
        province="上海市",
    )

    result = resolver.resolve("人民广场", region_hint=origin)

    assert result.source == "poi"
    assert result.city == "上海市"
    assert client.calls[1][1]["region"] == "上海市"
    assert client.calls[1][1]["city_limit"] == "true"


def test_location_resolver_empty_geocodes_raise_not_found():
    resolver = AmapLocationResolver(
        api_key="test-secret-key",
        http_client=FakeHttpClient(
            {"status": "1", "info": "OK", "infocode": "10000", "geocodes": []}
        ),
    )

    with pytest.raises(NavigationLocationNotFoundError):
        resolver.resolve("missing place")


def test_location_resolver_falls_back_to_poi_text_search_for_landmark():
    client = FakeHttpClient()
    client.responses = [
        {"status": "0", "info": "ENGINE_RESPONSE_DATA_ERROR", "infocode": "30001"},
        {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "pois": [
                {
                    "name": "上海虹桥站",
                    "address": "申贵路1500号",
                    "location": "121.327907,31.200316",
                    "adcode": "310112",
                    "cityname": "上海市",
                }
            ],
        },
    ]

    def get_json(url, *, params, timeout_seconds):
        client.calls.append((url, params, timeout_seconds))
        return client.responses.pop(0)

    client.get_json = get_json
    resolver = AmapLocationResolver(api_key="test-secret-key", http_client=client)

    result = resolver.resolve("上海虹桥站")

    assert result.canonical_name == "上海虹桥站 (申贵路1500号)"
    assert result.longitude == 121.327907
    assert result.latitude == 31.200316
    assert client.calls[1][1] == {
        "key": "test-secret-key",
        "keywords": "上海虹桥站",
        "page_size": 1,
        "page_num": 1,
    }


def test_location_resolver_current_location_is_not_guessed():
    resolver = AmapLocationResolver(
        api_key="test-secret-key",
        http_client=FakeHttpClient(),
    )

    with pytest.raises(NavigationLocationNotFoundError):
        resolver.resolve("当前位置")


def test_location_resolver_malformed_response_raises_response_error():
    resolver = AmapLocationResolver(
        api_key="test-secret-key",
        http_client=FakeHttpClient(
            {
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "geocodes": [{"formatted_address": "Broken"}],
            }
        ),
    )

    with pytest.raises(NavigationResponseError):
        resolver.resolve("broken")


def test_location_resolver_amap_business_error_does_not_leak_key():
    resolver = AmapLocationResolver(
        api_key="test-secret-key",
        http_client=FakeHttpClient(
            {
                "status": "0",
                "info": "INVALID_USER_KEY",
                "infocode": "10001",
            }
        ),
    )

    with pytest.raises(NavigationResponseError) as exc_info:
        resolver.resolve("上海虹桥站")

    assert "INVALID_USER_KEY" in str(exc_info.value)
    assert "test-secret-key" not in str(exc_info.value)


def test_location_resolver_explicit_cross_city_destination_is_not_overridden():
    client = FakeHttpClient(
        {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "count": "1",
            "geocodes": [
                {
                    "formatted_address": "北京市东城区天安门",
                    "location": "116.397463,39.909187",
                    "adcode": "110101",
                    "city": "北京市",
                }
            ],
        }
    )
    resolver = AmapLocationResolver(api_key="test-secret-key", http_client=client)
    origin = AmapLocationResolver(
        api_key="test-secret-key",
        http_client=FakeHttpClient(
            {
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "count": "1",
                "geocodes": [
                    {
                        "formatted_address": "上海市闵行区上海虹桥站",
                        "location": "121.327907,31.200316",
                        "adcode": "310112",
                        "city": "上海市",
                    }
                ],
            }
        ),
    ).resolve("上海虹桥站")

    result = resolver.resolve("北京天安门", region_hint=origin)

    assert result.city == "北京市"
    assert result.adcode == "110101"


def test_location_resolver_network_error_propagates_transport_error():
    resolver = AmapLocationResolver(
        api_key="test-secret-key",
        http_client=FakeHttpClient(exc=NavigationTransportError("timeout")),
    )

    with pytest.raises(NavigationTransportError):
        resolver.resolve("上海虹桥站")
