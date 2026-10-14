# Stage 26: Proactive Trigger V1

## 1. Goal

Stage 26 adds a deterministic proactive trigger core for calendar lead-time
departure preparation.

## 2. Stage25 Baseline

Task persistence, task history, and reload are already available.

## 3. Reactive vs Proactive

FlowMate can now create a task from a persisted future calendar trigger when
`tick(now=...)` is called.

## 4. Trigger Scope

V1 supports only `CALENDAR_EVENT_LEAD_TIME`.

## 5. Why Calendar Lead-time First

Morning departure planning is already grounded by calendar, weather, and
navigation capabilities.

## 6. Trigger Domain

`TriggerDefinition` stores event source identity, start time, location, summary,
lead time, status, and generated task id.

## 7. Trigger Lifecycle

`ACTIVE -> FIRED`, `ACTIVE -> EXPIRED`, or explicit `CANCELLED` in future.

## 8. Persistence

Triggers are stored in SQLite in the `triggers` table.

## 9. Registration

`CalendarTriggerRegistrationService` registers eligible timed events with a
location.

## 10. Due Evaluation

`trigger_at = event_start - lead_time_minutes`.

## 11. Expiration

If `now >= event_start`, an unfired trigger becomes `EXPIRED`.

## 12. Task Creation

`ProactiveTaskFactory` creates a normal planned Task with weather and navigation
steps grounded to the source event location.

## 13. Atomicity

Task save and trigger fired update happen in one SQLite transaction.

## 14. Duplicate Prevention

The same source event cannot create multiple ACTIVE/FIRED triggers, and a FIRED
trigger cannot create duplicate tasks on repeated ticks.

## 15. Restart Idempotency

After restart, the persisted FIRED trigger prevents duplicate task creation.

## 16. Dynamic Runtime Integration

The task factory reuses the existing observation-driven continuation planner for
weather and navigation step construction.

## 17. HITL Preservation

Triggers do not confirm or execute side effects.

## 18. Side-effect Containment

V1 creates tasks only. It does not execute notification, smart-home, or vehicle
tools.

## 19. Fixed Clock

Tests pass explicit timezone-aware `now` values.

## 20. Timezone

Absolute trigger times are stored as UTC ISO8601 strings.

## 21. Offline Tests

All tests use temporary SQLite files and no real providers.

## 22. Trigger Eval V1

`evals/proactive_trigger_eval_v1.json` covers due, not-due, expired, missing
location, all-day, duplicate, and restart cases.

## 23. Limitations

No background scheduler, recurrence, event cancellation reconciliation, or
multi-process locking is implemented.

## 24. Future Scheduler

Future stages can attach a worker to call `tick()` periodically.

## 25. Stage27 Frontend Readiness

Task and trigger history are now readable for a frontend demo.

## 26. Interview Takeaway

FlowMate can proactively create a grounded task without autonomously executing a
side effect.
