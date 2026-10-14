import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.integrations.navigation import (
    AmapLocationResolver,
    AmapNavigationProvider,
    NavigationConfigurationError,
    NavigationProviderError,
    UrllibNavigationHttpClient,
)
from flowmate.tools.navigation import NavigationTool, NavigationToolResult


class CountingNavigationHttpClient(UrllibNavigationHttpClient):
    def __init__(self) -> None:
        self.geocoding_call_count = 0
        self.poi_call_count = 0
        self.route_call_count = 0

    def get_json(self, url, *, params, timeout_seconds):
        if "/v3/geocode/geo" in url:
            self.geocoding_call_count += 1
        elif "/v5/place/text" in url:
            self.poi_call_count += 1
        elif "/v5/direction/driving" in url:
            self.route_call_count += 1
        return super().get_json(url, params=params, timeout_seconds=timeout_seconds)


class RecordingAmapLocationResolver(AmapLocationResolver):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.resolved_locations = []

    def resolve(self, location: str, *, region_hint=None):
        resolved = super().resolve(location, region_hint=region_hint)
        self.resolved_locations.append(resolved)
        return resolved


def env_status(name: str) -> str:
    return "configured" if os.getenv(name) else "missing"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real Amap navigation smoke.")
    parser.add_argument("--origin", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--departure-time", default="now")
    args = parser.parse_args()

    print(
        json.dumps(
            {
                "provider": "amap",
                "configuration": {
                    "AMAP_WEB_SERVICE_KEY": env_status("AMAP_WEB_SERVICE_KEY"),
                    "HTTP_PROXY": env_status("HTTP_PROXY"),
                    "HTTPS_PROXY": env_status("HTTPS_PROXY"),
                    "NO_PROXY": env_status("NO_PROXY"),
                },
                "origin": args.origin,
                "destination": args.destination,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    api_key = os.getenv("AMAP_WEB_SERVICE_KEY")
    if not api_key:
        print(
            json.dumps(
                {
                    "success": False,
                    "error_type": "NavigationConfigurationError",
                    "error": "AMAP_WEB_SERVICE_KEY is required.",
                    "real_amap_geocoding_call_count": 0,
                    "real_amap_route_call_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    http_client = CountingNavigationHttpClient()
    location_resolver = RecordingAmapLocationResolver(
        api_key=api_key,
        http_client=http_client,
    )

    try:
        provider = AmapNavigationProvider(
            api_key=api_key,
            http_client=http_client,
            location_resolver=location_resolver,
        )
        result = NavigationTool(provider=provider).run(
            {
                "origin": args.origin,
                "destination": args.destination,
                "departure_time": args.departure_time,
            }
        )
    except (NavigationConfigurationError, NavigationProviderError) as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                    "real_amap_geocoding_call_count": http_client.geocoding_call_count,
                    "real_amap_poi_call_count": http_client.poi_call_count,
                    "real_amap_route_call_count": http_client.route_call_count,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    origin = location_resolver.resolved_locations[0]
    destination = location_resolver.resolved_locations[1]
    print(
        json.dumps(
            {
                "success": True,
                "origin_resolved": True,
                "destination_resolved": True,
                "route_found": True,
                "origin_canonical": origin.canonical_name,
                "destination_canonical": destination.canonical_name,
                "origin_city": origin.city,
                "origin_adcode": origin.adcode,
                "destination_city": destination.city,
                "destination_adcode": destination.adcode,
                "location_context_valid": (
                    origin.region_name == destination.region_name
                ),
                "origin_coordinates_valid": isinstance(origin.longitude, float)
                and isinstance(origin.latitude, float),
                "destination_coordinates_valid": isinstance(destination.longitude, float)
                and isinstance(destination.latitude, float),
                "result_schema_valid": isinstance(result, NavigationToolResult),
                "result": result.model_dump(),
                "real_amap_geocoding_call_count": http_client.geocoding_call_count,
                "real_amap_poi_call_count": http_client.poi_call_count,
                "real_amap_route_call_count": http_client.route_call_count,
                "real_calendar_write_calls": 0,
                "real_notification_executions": 0,
                "real_smart_home_executions": 0,
                "real_vehicle_executions": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
