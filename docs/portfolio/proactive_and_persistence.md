# Proactive and Persistence

FlowMate uses persistence for auditability and trigger state, not memory.

## Task History

TaskRepository stores Task, PlanStep, ToolCall, confirmation state, result and error fields in SQLite. The frontend reads history through FastAPI only.

## Trigger Persistence

TriggerRepository stores proactive calendar trigger state so restart behavior can be evaluated. The trigger model supports ACTIVE, FIRED, CANCELLED and EXPIRED states.

## Explicit Tick

Stage 26 intentionally avoids a background scheduler. Trigger evaluation happens through an explicit API call:

```text
POST /api/v1/triggers/tick
```

This makes demo behavior deterministic and avoids hidden autonomous side effects.

## Duplicate Prevention

Trigger evaluation checks duplicate registration and duplicate fire behavior. Current Proactive Trigger Eval V1 records 12 cases with restart idempotency and side-effect containment at 1.000.
