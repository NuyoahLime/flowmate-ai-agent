import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.integrations.weather import (
    OpenMeteoLocationResolver,
    OpenMeteoWeatherProvider,
    UrllibWeatherHttpClient,
    WeatherProviderError,
)
from flowmate.tools.weather import WeatherTool, WeatherToolResult


class CountingWeatherHttpClient(UrllibWeatherHttpClient):
    def __init__(self) -> None:
        self.geocoding_call_count = 0
        self.forecast_call_count = 0

    def get_json(self, url, *, params, timeout_seconds):
        if "geocoding-api.open-meteo.com" in url:
            self.geocoding_call_count += 1
        elif "api.open-meteo.com" in url:
            self.forecast_call_count += 1
        return super().get_json(url, params=params, timeout_seconds=timeout_seconds)


class RecordingLocationResolver(OpenMeteoLocationResolver):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.last_location = None

    def resolve(self, location: str):
        resolved = super().resolve(location)
        self.last_location = resolved
        return resolved


def env_status(name: str) -> str:
    return "configured" if os.getenv(name) else "missing"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real Open-Meteo weather smoke.")
    parser.add_argument("--location", required=True)
    parser.add_argument("--date", default="today")
    args = parser.parse_args()

    http_client = CountingWeatherHttpClient()
    location_resolver = RecordingLocationResolver(http_client=http_client)
    provider = OpenMeteoWeatherProvider(
        http_client=http_client,
        location_resolver=location_resolver,
    )
    tool = WeatherTool(provider=provider)

    print(
        json.dumps(
            {
                "provider": "open_meteo",
                "proxy": {
                    "HTTP_PROXY": env_status("HTTP_PROXY"),
                    "HTTPS_PROXY": env_status("HTTPS_PROXY"),
                    "NO_PROXY": env_status("NO_PROXY"),
                },
                "requested_location": args.location,
                "requested_date": args.date,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    try:
        result = tool.run({"location": args.location, "date": args.date})
    except WeatherProviderError as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                    "real_weather_geocoding_call_count": http_client.geocoding_call_count,
                    "real_weather_forecast_call_count": http_client.forecast_call_count,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    resolved = location_resolver.last_location
    schema_valid = isinstance(result, WeatherToolResult)
    print(
        json.dumps(
            {
                "success": True,
                "resolved_location": resolved.name if resolved is not None else None,
                "resolved_latitude_valid": (
                    isinstance(resolved.latitude, float) if resolved is not None else False
                ),
                "resolved_longitude_valid": (
                    isinstance(resolved.longitude, float) if resolved is not None else False
                ),
                "resolved_timezone": resolved.timezone if resolved is not None else None,
                "result_schema_valid": schema_valid,
                "result": result.model_dump(),
                "real_weather_geocoding_call_count": http_client.geocoding_call_count,
                "real_weather_forecast_call_count": http_client.forecast_call_count,
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
