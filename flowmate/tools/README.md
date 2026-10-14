# FlowMate Tools

FlowMate tools implement the shared `BaseTool` contract. Installed capability is
kept separate from Planner and runtime authorization.

Implemented tools:

- `weather_tool`
- `navigation_tool`
- `calendar_tool`
- `notification_tool`
- `smart_home_tool`
- `vehicle_tool`

`weather_tool` keeps the same `BaseTool` contract for both offline and real
weather use. Default runtime and tests use `MockWeatherProvider`; developers can
explicitly inject `OpenMeteoWeatherProvider` for real read-only Open-Meteo
geocoding plus forecast calls. Planner capability is unchanged: the Planner still
selects `weather_tool`, not provider-specific tools.

`navigation_tool` keeps the same route-information contract for offline and real
navigation use. Default runtime and tests use `MockNavigationProvider`;
developers can explicitly inject `AmapNavigationProvider` for real read-only
Amap geocoding plus driving route queries. It returns route information only and
does not control, move, start, lock, unlock, or otherwise operate vehicles.

`notification_tool` keeps the same immediate text-notification contract for
offline and real delivery. Default runtime and tests use
`MockNotificationProvider`; developers can explicitly inject
`FeishuWebhookNotificationProvider` for real Feishu custom bot text delivery.
Notification is MEDIUM risk and must pass backend human confirmation before any
real provider send attempt.

`smart_home_tool` is Planner-authorized for explicit immediate mock control.
Execution still requires deterministic action-aware risk assessment and human
confirmation. It is not authorized for dynamic execution.

`vehicle_tool` provides deterministic mock status, lock, unlock, and climate
commands. It controls no real vehicle and provides no movement, remote-driving,
summon, or autonomous-driving capability. It is Planner-authorized for explicit
immediate actions, with deterministic LOW/MEDIUM/HIGH action risk and HITL for
side effects. It is not authorized for dynamic execution.
