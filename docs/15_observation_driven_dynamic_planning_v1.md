# Observation-driven Dynamic Planning V1

## 1. Problem
Static planning was enough for read-only flows, but it cannot complete a request like:

`帮我安排明早出门`

when the second half of the plan depends on a real calendar observation.

## 2. Why Static Planning Is Insufficient
Static planning must guess the full Task before any tool runs.
For morning departure planning, that is too weak:
- the first step should inspect the calendar
- the next step should depend on the selected calendar event
- navigation arguments should come from the observation, not from speculation

## 3. Dynamic Planning Scope
Stage 16.3 supports only one bounded scenario:
- Morning Departure Dynamic Planning

Allowed flow:
- Plan
- Execute Calendar
- Observe
- Re-plan

Not allowed:
- generic agent loops
- self-consistency
- multi-agent
- Retry as planning
- LangGraph
- ReAct

## 4. Architecture
The implementation uses a small orchestration layer:
- `DynamicTaskOrchestrator`
- `ObservationDrivenContinuationPlanner`
- `DynamicPlanningState`
- `ToolObservation`

Static planners remain unchanged.

## 5. Dynamic State Model
`DynamicPlanningState` contains:
- `user_input`
- `phase`
- `task`
- `observations`
- `iteration_count`
- `max_iterations`
- `selected_event`
- `failure_type`
- `error`

## 6. ToolObservation
`ToolObservation` is a structured record of runtime tool output:
- `tool_name`
- `step_id`
- `result`
- `error`

It is not a natural-language string.

## 7. Plan -> Execute -> Observe -> Re-plan
Stage 16.3 does this:
1. create an initial Task with only `calendar_tool`
2. execute the calendar step through `ToolExecutor`
3. collect a structured observation
4. select the earliest event by `start_time`
5. build continuation steps from the observation

## 8. Calendar Event Selection
If multiple events are returned, the earliest `start_time` wins.

This is deterministic Python logic, not model sampling.

## 9. Observation Grounding
Continuation planning must use the real observation.

For supported cases:
- `navigation.destination` must equal the selected calendar event location
- it cannot be guessed as `office` or `company` if the observation says otherwise

## 10. Failure Handling
Dynamic planning fails safely for:
- `no_calendar_event`
- `missing_event_location`
- `tool_execution_error`
- `continuation_planning_error`
- `max_iterations_exceeded`
- `unsupported_dynamic_goal`

## 11. Dynamic Eval
`evals/planner_dynamic_morning_v1.json` contains 10 cases:
- dynamic_navigation_supported: 4
- dynamic_weather_navigation_supported: 2
- no_event_failure: 2
- missing_location_failure: 2

## 12. Integration Test
The dynamic integration test confirms:
- CalendarTool mock executes
- observation is produced
- continuation planning uses the observed event location
- WeatherTool and NavigationTool are not executed inside eval

## 13. Provider Call Analysis
For this stage:
- initial planning calls: 0
- continuation planning calls: 0
- retry calls: 0
- total provider attempts: 0

The stage is intentionally deterministic.

## 14. Static Planner Regression
Static planner behavior remains unchanged.

No existing planner dataset, executor, or Tool schema was rewritten.

## 15. Retry vs Re-plan
Retry handles provider failure.
Re-plan handles new information from observation.

They are different mechanisms.

## 16. Current Limitations
- only one dynamic scenario is supported
- continuation logic is deterministic
- no generic branching engine exists
- no runtime clarification loop exists

## 17. Whether LangGraph Is Justified Yet
Not yet.

The current dynamic flow is bounded, single-branch, and linear enough to remain in explicit Python.

It would need:
- broader branching
- multiple observation types
- looping over several dependent steps
- mixed failure recovery

before a graph runtime becomes a defensible move.

## 18. Conclusion
Stage 16.3 adds the smallest useful observation-driven planning loop:
- calendar first
- observation second
- continuation third

It solves the morning departure dependency without turning the project into a generic agent framework.
