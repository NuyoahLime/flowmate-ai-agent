# Stage 23: Amap Real Navigation Adapter V1

## 1. Goal

Stage 23 connects the existing `navigation_tool` to Amap Web Service geocoding
and driving route planning while preserving the current tool schema.

## 2. Stage22 Baseline

Stage 22 completed Open-Meteo real weather integration with default mock
behavior preserved.

## 3. NavigationTool Contract Audit

Input schema:

```json
{
  "origin": "string",
  "destination": "string",
  "departure_time": "string"
}
```

Result schema:

```json
{
  "origin": "string",
  "destination": "string",
  "distance_km": "float >= 0",
  "duration_minutes": "int >= 0",
  "traffic": "string"
}
```

The contract was preserved.

## 4. Provider Architecture

```text
NavigationTool
├─ MockNavigationProvider
└─ AmapNavigationProvider
   ├─ AmapLocationResolver
   └─ Amap driving route query
```

Planner still emits only `navigation_tool`.

## 5. NavigationProvider Protocol

`NavigationProvider.get_route(query: NavigationProviderQuery) ->
NavigationToolResult` is the provider contract.

## 6. Mock Provider Preservation

`NavigationTool()` defaults to `MockNavigationProvider` and preserves the
previous deterministic result: 18.6 km, 42 minutes, heavy traffic.

## 7. Why Amap

Amap provides China-focused geocoding and driving route Web Service APIs that
fit the current public-landmark smoke scenarios.

## 8. Web Service Key Boundary

The real adapter requires `AMAP_WEB_SERVICE_KEY`. The key is read from the
environment or passed explicitly to the provider. It is not part of Planner or
Tool schemas.

## 9. Credential Security

The smoke script prints only configured/missing status. Provider errors do not
include full request URLs or API keys.

## 10. Location Resolution

`AmapLocationResolver` maps location strings to
`ResolvedNavigationLocation(query, canonical_name, longitude, latitude, adcode,
city)`.

## 11. Geocoding

V1 uses the first valid Amap geocode result. Empty geocodes raise
`NavigationLocationNotFoundError`.

## 12. Coordinate Semantics

Amap coordinates stay inside the Amap provider boundary and are represented as
explicit `longitude, latitude` fields. Route requests use `longitude,latitude`.

## 13. Driving Route Query

V1 uses `/v5/direction/driving` with minimal parameters: `key`, `origin`, and
`destination`.

## 14. Route Selection Strategy

If Amap returns multiple paths, V1 maps the first recommended path.

## 15. Distance / Duration Mapping

`distance` meters maps to `distance_km = round(meters / 1000, 1)`.
`duration` seconds maps to `duration_minutes = ceil(seconds / 60)`.

## 16. Route Information vs Vehicle Control

`navigation_tool` returns route information only. It does not move a vehicle,
start a car, send a route to a car, or perform any physical vehicle action.

## 17. HTTP Timeout

Requests use a finite timeout. Default is 10 seconds and can be overridden with
`AMAP_TIMEOUT_SECONDS`.

## 18. Proxy Handling

The adapter uses standard environment proxy handling. No personal proxy URL is
hardcoded.

## 19. Error Taxonomy

Navigation errors are split into configuration, location-not-found, transport,
response, mapping, and route-not-found errors.

## 20. Privacy

Smoke tests use public landmarks. The adapter should not log full private
addresses, raw route responses, full URLs, or API keys.

## 21. Offline Tests

Unit tests use fake HTTP clients and fixture JSON. Pytest performs zero real
Amap calls.

## 22. Dynamic Compatibility

Dynamic morning departure execution accepts real-shaped navigation provider
results without changing `DynamicTaskOrchestrator`.

## 23. Navigation Grounding Preservation

The existing invariant remains: dynamic navigation destination must come from
the selected calendar observation location.

## 24. Real Smoke

Run manually:

```powershell
python scripts\amap_navigation_smoke.py --origin "上海虹桥站" --destination "人民广场"
python scripts\amap_navigation_smoke.py --origin "上海站" --destination "上海虹桥站"
```

`AMAP_WEB_SERVICE_KEY` must be configured with an Amap Web Service key.

## 25. Engineering Gate

Provider abstraction, mock provider, Amap provider, Amap location resolver,
schema preservation, default mock behavior, offline tests, and unchanged Planner
boundaries are required.

## 26. Real Integration Gate

Real origin geocode, destination geocode, driving route query, and
`NavigationToolResult` schema validation must succeed.

## 27. Current Limitations

V1 does not implement walking, cycling, transit, truck routing, waypoints,
route alternatives, turn-by-turn guidance, GPS tracking, route monitoring,
vehicle control, or proactive rerouting.

## 28. Stage24 Readiness

After Calendar, Weather, and Navigation real read integrations, FlowMate can
consider a real notification boundary in a later stage without changing Agent
Core.

## 29. Conclusion

Navigation now follows the same provider-based integration pattern as Calendar
and Weather while preserving Planner and Tool contracts.
