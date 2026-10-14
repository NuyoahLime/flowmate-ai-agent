# Notification Real Eval Validation

## 1. Purpose
Stage 17.1R validates the Stage 17.1 notification Planner authorization against a real provider.

This is validation, not optimization.

## 2. Provider Environment
- `LLM_API_KEY`: configured
- `LLM_MODEL`: `deepseek-v4-flash`
- `LLM_BASE_URL`: `https://api.deepseek.com`

No API key was printed or written.

## 3. Offline Baseline
Latest pytest:
- 303 passed in 4.98s

Offline gates were already passing:
- Engineering
- RiskPolicy
- Human-in-the-loop enforcement

## 4. Notification Dataset Results
Dataset:
- `evals/planner_notification_v1.json`
- 16 cases

Result:
- `evals/results/llm_planner_notification_v1_stage17_1r.json`

Metrics:
- Scenario Accuracy: 1.000
- Supported Recall: 1.000
- Unsupported Recall: 1.000
- Tool Selection Accuracy: 1.000
- Parameter Accuracy: 1.000
- Parameter Completeness: 1.000
- Schema Valid Rate: 1.000
- Extra Tool Rate: 0.000

## 5. Category Metrics
- Immediate Notification Supported Recall: 1.000
- Scheduled Notification Unsupported Recall: 1.000
- Conditional Notification Unsupported Recall: 1.000
- Notification Minimality Accuracy: 1.000

## 6. Notification Safety Gate
Scheduled and conditional notification requests were rejected.

No scheduled or conditional case incorrectly planned `notification_tool`.

## 7. Notification Minimality
Notification over-selection cases:
- none

Non-notification tasks did not receive `notification_tool`.

## 8. Provider Retry Observations
Notification dataset:
- Retry Cases: 0
- Retry Recovery Rate: N/A
- Total Provider Attempts: 16
- Average Provider Attempts Per Case: 1.000

V2 regression:
- Retry Cases: 0
- Retry Recovery Rate: N/A
- Total Provider Attempts: 22
- Average Provider Attempts Per Case: 1.000

Total provider attempts:
- initial calls: 38
- retry calls: 0
- total attempts: 38

## 9. planner_eval_v2 Regression
Dataset:
- `evals/planner_eval_v2.json`
- 22 cases

Result:
- `evals/results/llm_planner_v2_after_notification_authorization_stage17_1r.json`

Metrics:
- Scenario Accuracy: 0.955
- Supported Recall: 0.909
- Unsupported Recall: 1.000
- Tool Selection Accuracy: 0.909
- Parameter Accuracy: 0.909
- Parameter Completeness: 1.000
- Schema Valid Rate: 0.955
- Extra Tool Rate: 0.000

## 10. Notification Misselection Audit
V2 notification misselection case IDs:
- none

No old weather/navigation/calendar task was polluted by `notification_tool`.

## 11. Failure Attribution
V2 had one semantic failure:
- `unsupported-calendar-002`
- expected: `calendar_tool`
- predicted: unsupported
- reason: provider judged month-range calendar read unsupported

This is not a notification over-selection regression and not a provider infrastructure failure.

Provider failures:
- none

## 12. Stage17.1 Final Acceptance
Engineering Gate:
- PASS

Notification Capability Gate:
- PASS

Safety Gate:
- PASS

Regression Gate:
- PASS for notification authorization impact

## 13. Remaining Risks
The real provider still has some semantic variability on non-notification calendar-read boundaries.

This should be tracked separately from notification authorization.

## 14. Stage17.2 Readiness
`READY_FOR_STAGE_17_2 = true`

Stage 17.2 may proceed, provided it keeps the same safety structure:
- RiskPolicy remains source of truth
- HITL remains required for side-effecting notification execution
- no real Push API unless explicitly authorized in a later stage
