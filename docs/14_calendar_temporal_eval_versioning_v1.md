# Calendar Temporal Semantics & Eval Versioning V1

## Problem
Stage 16.1 proved `calendar_tool` can be used for read-only planning. Stage 16.2 focuses on a narrower issue: when the user specifies a time-of-day, the Planner must preserve that temporal intent in calendar arguments without changing calendar capability boundaries or Tool contracts.

## Stage16.1 Findings
- `calendar_tool` is read-only.
- Calendar read is authorized.
- Calendar write remains unsupported.
- Morning commute planning is not the same problem as calendar read planning.

## Calendar Temporal Convention
The project now uses one canonical mapping for calendar temporal expressions:
- whole day: `date=tomorrow`, omit `start_time` and `end_time`
- morning: `date=tomorrow`, `start_time=06:00`, `end_time=12:00`
- afternoon: `date=tomorrow`, `start_time=12:00`, `end_time=18:00`
- evening: `date=tomorrow`, `start_time=18:00`, `end_time=23:59`

This mapping is generated from a single source of truth in `flowmate/agent/temporal_conventions.py` and inserted into the Planner prompt.

## Temporal Constraint Preservation
To measure whether the Planner keeps explicit time-of-day constraints intact, the evaluator adds:
- `temporal_constraint_preserved`
- `temporal_constraint_preservation_rate`

The metric only applies when a supported calendar case explicitly expects both `start_time` and `end_time`.

## Temporal Eval Dataset
`evals/planner_calendar_temporal_v1.json` contains 12 cases:
- whole_day: 3
- morning: 3
- afternoon: 3
- evening: 3

All 12 cases are read-only calendar planning cases.

## Historical Gold Drift
`planner_eval_v1.json` remains the historical baseline.

`planner_eval_v2.json` is the capability-updated dataset:
- only `unsupported-calendar-002` changed
- it moved from unsupported to supported
- the new gold is `calendar_tool` with `date="next month"`

This change is capability-driven, not model-driven.

## Capability-driven Dataset Versioning
The versioning rule is:
- model weakness never changes gold labels
- capability expansion may change gold labels when the new capability is genuinely authorized

That is why `planner_eval_v1.json` is preserved, while `planner_eval_v2.json` records the read-only calendar capability surface after Stage 16.1.

## planner_eval_v1 vs v2
- v1: historical baseline for weather + navigation
- v2: capability baseline including read-only calendar read
- v1 is not modified
- v2 contains one relabeled case for calendar read

## Temporal Eval Results
`scripts/eval_llm_planner_with_retry.py evals/planner_calendar_temporal_v1.json evals/results/llm_planner_calendar_temporal_v1.json`

Metrics:
- Cases: 12
- Scenario Accuracy: 1.000
- Supported Recall: 1.000
- Unsupported Recall: N/A
- Tool Selection Accuracy: 1.000
- Parameter Accuracy: 1.000
- Parameter Completeness: 1.000
- Temporal Constraint Preservation Rate: 1.000
- Unsupported Accuracy: N/A
- Schema Valid Rate: 1.000
- Extra Tool Rate: 0.000
- Retry Cases: 0
- Retry Recovery Rate: N/A
- Total Provider Attempts: 12
- Average Provider Attempts Per Case: 1.000

Category breakdown:
- whole_day: N/A
- morning: 1.000
- afternoon: 1.000
- evening: 1.000

## V2 Results
`scripts/eval_llm_planner_with_retry.py evals/planner_eval_v2.json evals/results/llm_planner_v2.json`

Metrics:
- Cases: 22
- Scenario Accuracy: 0.955
- Supported Recall: 0.909
- Unsupported Recall: 1.000
- Tool Selection Accuracy: 0.909
- Parameter Accuracy: 0.909
- Parameter Completeness: 1.000
- Temporal Constraint Preservation Rate: N/A
- Unsupported Accuracy: 1.000
- Schema Valid Rate: 0.955
- Extra Tool Rate: 0.000
- Retry Cases: 0
- Retry Recovery Rate: N/A
- Total Provider Attempts: 22
- Average Provider Attempts Per Case: 1.000

## Failure Cases
Only one V2 case failed:
- `commute-006`
- category: `morning_commute`
- failure type: scenario_error
- the model rejected a supported morning commute request as unsupported

This failure is semantic over-conservatism, not a calendar temporal mapping error.

## Safety Boundaries
The stage did not change:
- CalendarTool schema
- ToolExecutor
- TaskExecutor
- any Tool runtime behavior
- any Planner capability outside calendar temporal semantics

No Tool was executed during this stage.

## Dynamic Dependency Limitation
The main remaining limitation is semantic, not temporal:
- some commute cases still depend on the model inferring that morning commute planning can be done without fully knowing the meeting time
- the current Planner was conservative on `commute-006`

That is a capability boundary, not a temporal-convention bug.

## Conclusion
Stage 16.2 establishes a stable calendar temporal convention, versioned evaluation datasets, and a cleaner metric for temporal preservation.

The important result is:
- temporal mapping is now canonical
- temporal preservation rate is 1.000 on the temporal dataset
- `planner_eval_v1` remains historical
- `planner_eval_v2` reflects capability-driven relabeling
- no Tool execution occurred
