# Stage 25: Persistence / Task History V1

## 1. Goal

Stage 25 adds durable task history for already-created execution state.

## 2. Stage24 Baseline

Stage24 notification delivery remains unchanged. Persistence does not depend on
real Feishu configuration.

## 3. Persistence vs Memory

This stage stores structured runtime state, not chat memory, RAG, or agent
memory.

## 4. Domain Boundary

Persistence stores the existing `Task`, `PlanStep`, `ToolCall`, and confirmation
state without changing domain schema.

## 5. Aggregate Design

`Task` is the aggregate root. Steps and tool calls are stored with the task.

## 6. Repository Architecture

`TaskRepository` provides save, load, and list-history access.

## 7. SQLite Decision

V1 uses SQLite via the Python standard library.

## 8. Database Schema

Tables:

- `tasks`
- `plan_steps`
- `tool_calls`

## 9. Domain Mapping

The persistence layer maps between SQLite rows and Pydantic domain models.

## 10. Serialization

JSON fields are stored as deterministic UTF-8 text. Pickle is not used.

## 11. Transaction Boundary

Saving a task aggregate is transactional.

## 12. Checkpoints

Persistence captures created, confirmed, executing, step updates, and final
task states.

## 13. Confirmation Persistence

`PENDING`, `CONFIRMED`, `REJECTED`, and `NOT_REQUIRED` survive reload.

## 14. Failed Task Persistence

Failed tasks keep their step and tool-call outcomes.

## 15. Restart Scenario

A reloaded task keeps the same status and confirmation state.

## 16. History Query

`list_history()` returns recent tasks with `limit`.

## 17. API

Read-only history endpoints:

- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`

## 18. Secret Boundary

Provider secrets are not persisted.

## 19. Offline Tests

Repository tests use temporary SQLite files only.

## 20. Limitations

No automatic resume, scheduler, queue, or background worker is implemented.

## 21. PostgreSQL Future Migration

SQLite is a V1 boundary; repository abstraction allows later PostgreSQL
replacement.

## 22. Stage26 Readiness

Persistence provides the base for later resume or UI history work.

## 23. Interview Takeaway

Stage25 proves the execution state can be persisted without mutating planner or
executor semantics.
