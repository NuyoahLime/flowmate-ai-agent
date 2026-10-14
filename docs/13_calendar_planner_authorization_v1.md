# Calendar Planner Authorization V1

## 1. Goal

Authorize the LLMPlanner to plan read-only calendar queries using the existing
mock `calendar_tool`.

## 2. Stage 16 Installed Capability

Stage 16 installed:

- `weather_tool`
- `navigation_tool`
- `calendar_tool`

`calendar_tool` is read-only, mock, deterministic, and already integrated with
ToolRegistry, ToolArgumentValidator, and ToolExecutor.

## 3. Planner Authorization Change

Default LLMPlanner authorized tools changed from:

```text
weather_tool
navigation_tool
```

to:

```text
weather_tool
navigation_tool
calendar_tool
```

The Tool Spec is still generated from ToolRegistry and each Tool input schema.
No second hand-written Calendar argument schema was added.

## 4. Calendar Read Boundary

Supported:

- query calendar events
- query schedules
- query meetings
- query events within a time window

Calendar read is low risk and should use `requires_confirmation=false`.

## 5. Calendar Write Boundary

Unsupported:

- create calendar events
- update calendar events
- delete calendar events
- accept invitations
- reject invitations
- cancel meetings
- reschedule meetings

Calendar topic related does not imply calendar write capability.

## 6. Dynamic Dependency Boundary

Unsupported in this version:

```text
calendar_tool
-> runtime observation
-> generate navigation_tool arguments from that observation
```

The planner must not guess meeting time or meeting location before the calendar
tool has actually executed.

## 7. Calendar Planner Dataset

`evals/planner_calendar_v1.json` contains 15 cases:

| Category | Cases |
| --- | ---: |
| `calendar_read_supported` | 7 |
| `calendar_write_unsupported` | 4 |
| `dynamic_dependency_unsupported` | 4 |

## 8. Metrics

The eval uses the existing PlannerEvaluator metrics:

- Scenario Accuracy
- Supported Recall
- Unsupported Recall
- Tool Selection Accuracy
- Parameter Accuracy
- Parameter Completeness
- Schema Valid Rate
- Extra Tool Rate
- Retry Cases
- Retry Recovery Rate
- Average Provider Attempts

## 9. Calendar Eval Results

Real provider result:

| Metric | Value |
| --- | ---: |
| Cases | 15 |
| Scenario Accuracy | 1.000 |
| Supported Recall | 1.000 |
| Unsupported Recall | 1.000 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 0.857 |
| Parameter Completeness | 0.905 |
| Unsupported Accuracy | 1.000 |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |
| Retry Cases | 2 |
| Retry Recovery Rate | 0.500 |
| Total Provider Attempts | 17 |
| Average Provider Attempts Per Case | 1.133 |

Category recalls:

| Category | Recall |
| --- | ---: |
| Calendar Read Supported Recall | 1.000 |
| Calendar Write Unsupported Recall | 1.000 |
| Dynamic Dependency Unsupported Recall | 1.000 |

## 10. Main Regression Results

Main Dataset after Calendar authorization:

| Metric | Value |
| --- | ---: |
| Cases | 22 |
| Scenario Accuracy | 0.955 |
| Supported Recall | 1.000 |
| Unsupported Recall | 0.917 |
| Tool Selection Accuracy | 1.000 |
| Parameter Accuracy | 0.980 |
| Parameter Completeness | 1.000 |
| Unsupported Accuracy | 0.917 |
| Schema Valid Rate | 1.000 |
| Extra Tool Rate | 0.000 |
| Retry Cases | 0 |
| Retry Recovery Rate | N/A |
| Total Provider Attempts | 22 |
| Average Provider Attempts Per Case | 1.000 |

No old weather/navigation supported case selected `calendar_tool`.

## 11. Failure Cases

Calendar Dataset:

- `calendar-read-002`: missing `start_time` and `end_time`; planned `calendar_tool`
  with `date=tomorrow`.
- `calendar-read-005`: used `start_time=09:00`, expected `06:00`.

Main Dataset:

- `commute-001`: weather location was `company`, expected `current_city`.
- `unsupported-calendar-002`: old Main Dataset expected unsupported for
  "查一下我下个月有哪些安排"; after Calendar read authorization, the model planned
  `calendar_tool`. This is a historical dataset expectation conflict rather
  than a weather/navigation over-selection failure.

## 12. Retry Observations

Calendar Eval retry cases:

- `calendar-read-005`: first attempt `provider_invalid_json`, second attempt
  provider succeeded but final result had a parameter value error.
- `calendar-dynamic-001`: first attempt `provider_empty_output`, second attempt
  succeeded.

Main Dataset had no retry cases.

## 13. Remaining Limitation

Planner calendar authorization works at the read/write boundary, but time-window
parameter extraction still needs improvement. Dynamic tool dependency remains
unsupported by design.

## 14. Conclusion

Stage 16.1 successfully authorizes read-only Calendar planning:

- `calendar_tool` appears in LLMPlanner Tool Spec.
- Calendar reads are supported.
- Calendar writes remain unsupported.
- Dynamic dependency tasks remain unsupported.
- No Tool execution occurred during real eval.

The stage is accepted for authorization and safety boundary. Parameter precision
for calendar time windows remains a follow-up issue.
