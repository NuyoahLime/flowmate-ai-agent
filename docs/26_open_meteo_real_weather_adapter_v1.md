# Stage 22: Open-Meteo Real Weather Adapter V1

## 1. Goal

Stage 22 connects the existing `weather_tool` to a real read-only weather
provider while preserving the tool contract and keeping default tests offline.

## 2. Stage21 Baseline

Stage 21/21R completed the Google Calendar real read adapter and smoke
validation. Calendar writes remained at zero.

## 3. Why Weather Is Second Real Domain API

Weather is a read-only, low-risk capability and fits the existing mock-first tool
architecture without changing Agent Core.

## 4. Existing WeatherTool Contract Audit

Input schema:

```json
{"location": "string", "date": "string"}
```

Result schema:

```json
{
  "location": "string",
  "date": "string",
  "condition": "string",
  "temperature_c": "float",
  "rain_probability": "float 0..1"
}
```

The contract was preserved.

## 5. Provider Architecture

`WeatherTool` now delegates to a provider:

```text
WeatherTool
├─ MockWeatherProvider
└─ OpenMeteoWeatherProvider
   ├─ OpenMeteoLocationResolver
   └─ WeatherTemporalResolver
```

## 6. WeatherProvider Protocol

`WeatherProvider.get_weather(query: WeatherProviderQuery) -> WeatherToolResult`
is the only provider method.

## 7. Mock Provider Preservation

`WeatherTool()` defaults to `MockWeatherProvider` and returns the previous
deterministic result: rain, 18C, rain probability 0.8.

## 8. OpenMeteoWeatherProvider

The real provider performs city-level geocoding, resolves the requested date,
requests the minimal daily forecast variables, and maps the response into the
existing `WeatherToolResult`.

## 9. Location Resolution

`OpenMeteoLocationResolver` maps a location string to
`ResolvedWeatherLocation(query, name, latitude, longitude, timezone, country_code)`.

## 10. Geocoding Boundary

The resolver uses the first best match returned by Open-Meteo. Ambiguous-location
disambiguation is not implemented in V1. Empty results raise
`WeatherLocationNotFoundError`.

## 11. Temporal Resolution

`WeatherTemporalResolver` supports `today`, `tomorrow`, and ISO `YYYY-MM-DD`.
Tests use fixed timezone-aware clocks.

## 12. Timezone Strategy

Forecast requests use the resolved location timezone. Server local timezone is
not used for real weather date resolution.

## 13. Forecast Query Mapping

Requested daily variables are limited to:

- `weather_code`
- `temperature_2m_max`
- `precipitation_probability_max`

## 14. Weather Code Mapping

Open-Meteo weather codes are mapped deterministically to `clear`, `cloudy`,
`fog`, `rain`, `snow`, `thunderstorm`, or `unknown`.

## 15. Tool Result Mapping

Open-Meteo values are normalized to the existing `WeatherToolResult`. Raw API
responses are not exposed to Task, PlanStep, ToolCall, or Tool result schemas.

## 16. Network / Proxy Handling

The implementation uses standard environment proxy handling. No proxy URL is
hardcoded in source.

## 17. Timeout Strategy

Real requests use a finite timeout. Default is 10 seconds and can be overridden
with `OPEN_METEO_TIMEOUT_SECONDS`.

## 18. Error Taxonomy

Weather errors are separated into configuration, location-not-found, transport,
response, mapping, and forecast-range errors.

## 19. Privacy

The smoke script prints city-level requested/resolved location only. It does not
log precise private addresses or raw provider JSON.

## 20. Offline Tests

Unit tests use fake HTTP clients and fixed clocks. Pytest does not call
Open-Meteo.

## 21. Dynamic Compatibility

Dynamic execution accepts a real-shaped weather provider through the unchanged
`weather_tool` result schema.

## 22. Real Smoke

Run manually:

```powershell
python scripts\open_meteo_weather_smoke.py --location "Shanghai"
python scripts\open_meteo_weather_smoke.py --location "Shanghai" --date tomorrow
```

If the local network needs a proxy, configure standard proxy environment
variables in the shell before running.

## 23. Engineering Gate

Provider abstraction, mock provider, real provider, explicit timezone, fixed
clock tests, finite timeout, and offline pytest are required.

## 24. Real Integration Gate

At least one real geocoding call and one real forecast call must succeed through
`OpenMeteoWeatherProvider` and `WeatherTool`.

## 25. Current Limitations

V1 does not implement weather alerts, AQI, historical weather, address-level
geocoding, multi-provider fallback, retry, SLA semantics, or proactive weather
monitoring.

## 26. Stage23 Navigation Readiness

Calendar and Weather now both follow provider-based real read integration. This
supports a future Navigation adapter without Agent Core changes.

## 27. Conclusion

FlowMate now has a second real domain provider while preserving mock-first
testing and Planner boundaries.
