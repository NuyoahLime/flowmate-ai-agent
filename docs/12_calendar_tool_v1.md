# CalendarTool V1

## 1. Goal

Add a read-only mock `calendar_tool` that can query deterministic calendar
events by date or by a date plus time window.

## 2. Read-only Scope

Allowed:

- query events on a date
- query events in a time window
- return meeting title, time, and location

Not allowed:

- create events
- update events
- delete events
- accept or reject meeting invitations
- cancel meetings
- call Google Calendar, Outlook, CalDAV, Apple Calendar, or any real calendar API

## 3. Input Schema

`CalendarToolInput`:

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `date` | `str` | yes | none |
| `start_time` | `str | None` | no | `None` |
| `end_time` | `str | None` | no | `None` |

Extra fields are forbidden.

## 4. Event Schema

`CalendarEvent`:

| Field | Type |
| --- | --- |
| `id` | `str` |
| `title` | `str` |
| `start_time` | `str` |
| `end_time` | `str` |
| `location` | `str | None` |
| `description` | `str | None` |

## 5. Result Schema

`CalendarToolResult`:

| Field | Type |
| --- | --- |
| `date` | `str` |
| `events` | `list[CalendarEvent]` |
| `event_count` | `int` |

`event_count` must equal `len(events)`.

## 6. Mock Data

For `date="tomorrow"`:

| ID | Title | Time | Location |
| --- | --- | --- | --- |
| `event-001` | `Product Weekly Meeting` | `08:30-09:30` | `company` |
| `event-002` | `Project Review` | `14:00-15:00` | `company` |

The mock data is deterministic. The same input returns the same output.

## 7. Time Window Semantics

An event is included when:

```text
event.start_time >= start_time
AND
event.start_time < end_time
```

If `start_time` is omitted, there is no lower bound. If `end_time` is omitted,
there is no upper bound.

## 8. Registry Integration

`create_default_registry()` now registers:

- `weather_tool`
- `navigation_tool`
- `calendar_tool`

No special dispatch was added to the registry.

## 9. Validation

`ToolArgumentValidator` supports `calendar_tool` through the existing generic
path:

```text
ToolRegistry.get(tool_name)
-> tool.input_schema.model_validate(arguments)
```

No `calendar_tool` special case was added.

## 10. Execution Example

Request:

```json
{
  "date": "tomorrow",
  "start_time": "06:00",
  "end_time": "12:00"
}
```

Result:

```json
{
  "date": "tomorrow",
  "event_count": 1,
  "events": [
    {
      "id": "event-001",
      "title": "Product Weekly Meeting",
      "start_time": "08:30",
      "end_time": "09:30",
      "location": "company",
      "description": null
    }
  ]
}
```

## 11. Current Authorization Boundary

`ToolRegistry` and Planner authorization are intentionally separate:

- `ToolRegistry` means the system has a Tool installed.
- `LLMPlanner.allowed_tools` means the Planner is authorized to plan with that Tool.

Stage 16 registers `calendar_tool`, but the default LLMPlanner whitelist still
contains only:

- `weather_tool`
- `navigation_tool`

Planner calendar authorization is left for a later stage.

## 12. Future Write Capability

Read-only calendar query is considered low risk.

Future write operations such as create, update, delete, accept, reject, or cancel
may require higher risk classification and human confirmation.
