# Stage 28.3: Real Information Provider E2E Acceptance

## Scope

The accepted runtime is:

```text
Real LLMPlanner
+ Open-Meteo real weather
+ Amap real navigation
+ Mock calendar, notification, smart-home, and vehicle providers
```

Provider selection is explicit through `FLOWMATE_TOOL_MODE`:

- `mock` is the safe default.
- `real_information` enables only Open-Meteo and Amap.
- Provider availability is never inferred from credential presence.
- Real provider failures are not replaced with Mock success.

## Provider Contract Audit

`WeatherTool` keeps the existing input and result schemas:

```text
input:  location, date
result: location, date, condition, temperature_c, rain_probability
```

`NavigationTool` keeps the existing input and result schemas:

```text
input:  origin, destination, departure_time
result: origin, destination, distance_km, duration_minutes, traffic
```

The Planner emits `weather_tool` and `navigation_tool` in both modes. The
runtime registry selects the provider without exposing provider names to the
Planner or changing Tool arguments.

## Provider Matrix

| Capability | Tool | Mock Provider | Real Provider | Acceptance runtime | Real acceptance | Side-effect risk |
|---|---|---|---|---|---|---|
| Calendar | `calendar_tool` | Mock calendar | Google adapter available separately | Mock | Not called | Read-only |
| Weather | `weather_tool` | `MockWeatherProvider` | `OpenMeteoWeatherProvider` | Open-Meteo | PASS | Read-only |
| Navigation | `navigation_tool` | `MockNavigationProvider` | `AmapNavigationProvider` | Amap | PASS | Read-only |
| Notification | `notification_tool` | Mock notification | Feishu adapter available separately | Mock | Not called | External message |
| Smart Home | `smart_home_tool` | Mock-only | None | Mock | Not called | Physical control |
| Vehicle | `vehicle_tool` | Mock-only | None | Mock | HITL boundary verified | Physical control |

## Real Smoke Results

Open-Meteo used public location `Beijing`/`北京` and `tomorrow`:

- Geocoding request: 1
- Forecast request: 1
- Resolved timezone: `Asia/Shanghai`
- Result schema: valid
- Result fields: condition, temperature, and rain probability present

Amap used public POIs `上海虹桥站` and `人民广场`:

- Origin geocoding: successful
- Destination region grounding: successful
- Destination canonical city: Shanghai
- Driving route: successful
- Distance and duration: positive and schema-valid

The first real run exposed an invalid 1919.6 km route because the ambiguous
destination was geocoded to Sichuan. The adapter now re-grounds ambiguous
cross-region destinations with the origin region and rejects unresolved
cross-region results. Explicit cross-city destinations remain supported.

## Real Agent E2E

The real browser and API acceptance used an isolated SQLite database and public
inputs only.

1. `帮我看看明天北京的天气`
   - Real LLM selected only `weather_tool`.
   - Arguments preserved `北京` and `tomorrow`.
   - Open-Meteo returned a valid result.
   - Task completed and persisted.

2. `我明天上午9点从上海虹桥站出发去人民广场`
   - Real LLM selected only `navigation_tool`.
   - Arguments preserved both POIs and `tomorrow 09:00`.
   - Amap returned a grounded Shanghai route.
   - Task completed and persisted.

3. `解锁我的车`
   - Vehicle stayed Mock-only.
   - Risk stayed HIGH.
   - Task stayed `WAITING_CONFIRMATION / PENDING`.
   - ToolCall stayed PENDING with no result.
   - The confirmation button was not used.

4. `帮我写一封邮件给老板`
   - Returned Unsupported with HTTP 422.
   - No executable Task was created or persisted.

## Failure Boundary

Offline fault injection verifies that Provider exceptions produce:

```text
ToolCall FAILED
PlanStep FAILED
Task FAILED
error persisted and reloadable
provider call count = 1
```

There is no Tool Provider retry and no automatic Mock fallback. Existing bounded
LLM Provider retry remains a separate Planner concern.

## Frontend Acceptance

The Vue page displayed:

- Open-Meteo real active
- Amap real active
- Calendar, Notification, Smart Home, and Vehicle as Mock
- Task history matching API persistence
- Real weather and route results matching Task JSON
- Vehicle HITL without execution
- A readable Unsupported message

Desktop and mobile browser checks passed. The mobile layout was hardened so a
390 px viewport has no horizontal overflow.

## Verification

```text
python -m pytest
695 passed in 15.20s

frontend npm run build
PASS
```

No real calendar, notification, smart-home, or vehicle action occurred. No API
key or private location was printed or persisted.

## Conclusion

FlowMate Stage 28.3 Real Information Provider Acceptance Complete
