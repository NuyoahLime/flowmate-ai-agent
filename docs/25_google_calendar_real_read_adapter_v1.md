# Google Calendar Real Read Adapter V1

## 1. Goal

Stage 21 introduces FlowMate's first real domain-service adapter while preserving
the existing CalendarTool input, result, Planner, risk, and dynamic contracts.
CalendarTool now delegates reads through an injected CalendarProvider.

## 2. Stage 20 Baseline

The baseline was `496 passed`. All six Tools and Planner capabilities were mock,
and `planner_eval_v3` was the current static capability baseline with all formal
metrics at 1.000.

## 3. Why Calendar Is First Real API

Calendar is read-only, already LOW risk, has stable structured events, and is the
runtime observation source for existing dynamic commute planning. It provides a
lower-risk productization boundary than real SmartHome or Vehicle control.

## 4. Provider Architecture

```text
                    +-- MockCalendarProvider
CalendarTool -------+
                    +-- GoogleCalendarProvider
                               |
                               +-- Google Calendar events.list
```

Planner and DynamicTaskOrchestrator continue to reference only `calendar_tool`.

## 5. CalendarProvider Protocol

`CalendarProvider.list_events(CalendarProviderQuery) -> list[CalendarEvent]`

The query preserves semantic `date`, optional `start_time`, and optional
`end_time`. Google SDK types and raw payloads do not enter domain schemas.

## 6. Mock Provider Preservation

`CalendarTool()` lazily constructs MockCalendarProvider. Existing `tomorrow`
events remain Product Weekly Meeting at 08:30 and Project Review at 14:00.
Existing start-inclusive/end-exclusive filtering remains in CalendarTool.

## 7. Google Provider

GoogleCalendarProvider receives an already constructed Calendar v3 service,
explicit timezone, calendar ID, and optional resolver. It performs read-only
events.list pagination and maps timed events into CalendarEvent.

## 8. OAuth Read-only Boundary

The only requested scope is:

`https://www.googleapis.com/auth/calendar.events.readonly`

No `calendar.events`, `calendar`, or other write scope exists. No create, update,
delete, reschedule, invitation response, or mutation API is implemented.

## 9. Credential Security

Configuration uses:

- `GOOGLE_CALENDAR_CLIENT_SECRET_FILE`
- `GOOGLE_CALENDAR_TOKEN_FILE`
- `GOOGLE_CALENDAR_TIMEZONE`
- `GOOGLE_CALENDAR_ID` (optional, defaults to primary)

`.secrets/`, root credentials/token files, and client-secret JSON patterns are
ignored. Logs and smoke output never print secret paths, token contents, client
secrets, refresh tokens, access tokens, or authorization headers.

## 10. Temporal Resolution

CalendarTemporalResolver converts current semantic dates into concrete aware
windows. It supports `today`, `tomorrow`, and `next month`, matching current
Planner Gold. Unsupported date semantics fail explicitly. A clock can be injected
for deterministic tests.

## 11. Timezone Strategy

Timezone is mandatory and sourced from `GOOGLE_CALENDAR_TIMEZONE`. ZoneInfo
conversion is explicit. Tests prove that system-local timezone is not used.

With fixed time 2026-08-09 in Asia/Shanghai:

- today: 2026-08-09 00:00 through 2026-08-10 00:00
- tomorrow: 2026-08-10 00:00 through 2026-08-11 00:00
- next month: 2026-09-01 00:00 through 2026-10-01 00:00

Canonical tomorrow windows remain morning 06:00-12:00, afternoon 12:00-18:00,
and evening 18:00-23:59.

## 12. Google Query Mapping

events.list receives `calendarId`, RFC3339 `timeMin`/`timeMax`,
`singleEvents=true`, `orderBy=startTime`, `showDeleted=false`, and the configured
`timeZone`. Calendar ID defaults to `primary`; custom IDs require explicit config.

## 13. Pagination

GoogleCalendarProvider follows every non-empty `nextPageToken` and passes it as
`pageToken` until no token remains. It does not silently stop after page one.

## 14. Recurring Events

`singleEvents=true` delegates recurring-instance expansion to Google. Recurring
instance responses map like other timed events; FlowMate does not implement RRULE.

## 15. Event Mapping

Google `id`, `summary`, `start.dateTime`, `end.dateTime`, `location`, and
`description` map to existing CalendarEvent fields. Times are converted into the
configured timezone and formatted as HH:MM. Missing summary becomes `(untitled)`.
Missing location and description remain None.

## 16. All-day Event V1 Boundary

All-day events expose dates without precise times, which the current
CalendarEvent contract cannot represent without fabrication. V1 skips them and
does not invent 00:00 or 23:59.

## 17. Error Taxonomy

- CalendarProviderError
- CalendarTemporalResolutionError
- GoogleCalendarAuthError
- GoogleCalendarConfigurationError
- GoogleCalendarTransportError
- GoogleCalendarResponseError
- GoogleCalendarMappingError

Provider exceptions flow through the existing generic ToolExecutor and produce a
FAILED ToolCall with a readable error. No Google-specific executor exists.

## 18. Privacy / Logging

The adapter emits no raw event logging. Errors contain type and operation context,
not full titles, locations, descriptions, OAuth JSON, or authorization data. The
smoke command hides custom calendar IDs and descriptions by default.

## 19. Unit Tests

Stage 21 adds 41 offline tests across provider abstraction, deterministic temporal
resolution, fake Google service responses, OAuth construction, pagination,
mapping, failure propagation, and Dynamic compatibility. All 537 project tests
pass without Google credentials or network access.

## 20. Dynamic Compatibility

A Google-shaped fake Provider injected through CalendarTool drives the unchanged
DynamicTaskOrchestrator. Calendar observation selects the event, and existing
navigation continuation uses its location. The orchestrator does not inspect the
Provider type.

## 21. Real Smoke

`python scripts/google_calendar_smoke.py` explicitly loads OAuth settings, permits
installed-app OAuth, builds a Google service, performs one CalendarTool read, and
prints a sanitized summary. `--show-events` explicitly reveals a limited title,
start time, and location list; description is never printed.

## 22. Engineering Gate

PASS:

- Provider abstraction complete
- Mock preserved and default
- Google read adapter complete
- timezone and relative-date resolver deterministic
- pagination and recurring instances supported
- read-only OAuth scope only
- fake-service and full regression tests pass
- Planner, RiskPolicy, execution core, Dynamic code, and V3 Gold unchanged

## 23. Real Integration Gate

`BLOCKED_BY_GOOGLE_OAUTH_SETUP`:

- GOOGLE_CALENDAR_CLIENT_SECRET_FILE: missing
- GOOGLE_CALENDAR_TOKEN_FILE: missing
- GOOGLE_CALENDAR_TIMEZONE: missing
- GOOGLE_CALENDAR_ID: defaults to primary

The smoke command exited before OAuth or API access. Real Calendar read calls are
zero and real Calendar write calls are zero.

## 24. Current Limitations

- local installed-app OAuth only, not production multi-user OAuth
- timed events only; all-day events skipped
- no Calendar API retry, webhook, polling, sync token, persistence, or writes
- current semantic dates only: today, tomorrow, next month
- CalendarTool description remains frozen to preserve Planner Prompt in Stage 21

## 25. Next Real API

Stage 22 Weather integration should begin only after Stage 21's real Calendar
smoke is completed, unless the project explicitly accepts carrying this OAuth
integration Gate as pending. Calendar write remains out of scope.

## 26. Conclusion

Stage 21 Engineering Gate passes and proves the Provider architecture, but the
stage is not fully complete without one explicit real Google Calendar read.
Current status is `ENGINEERING_PASS_REAL_SMOKE_PENDING`.
